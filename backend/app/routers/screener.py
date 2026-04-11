"""Screener-Only job creation and public test session endpoints.

Authenticated routes (require tenant JWT):
  POST /screener/jobs/extract-from-text  — AI extracts job details from pasted text
  POST /screener/jobs/extract-from-url   — fetch URL, AI extracts job details
  POST /screener/jobs                    — create a screener_only job

Public routes (no auth):
  GET  /screener/test/{application_id}/{token}          — get test session state
  POST /screener/test/{application_id}/{token}/answer   — submit an answer
  POST /screener/test/{application_id}/{token}/complete — complete the test
"""

import json
import logging
import random
import string
import uuid
from datetime import datetime, timezone
from html.parser import HTMLParser
from typing import Any

import httpx
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.application import Application
from app.models.job import Job
from app.models.tenant import Tenant
from app.models.test_session import TestSession
from app.routers.auth import get_current_tenant
from app.routers.jobs import _generate_job_ref
from app.schemas.job import JobResponse
from app.services.ai_provider import AIProvider
from app.services.audit_trail import AuditTrailService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/screener", tags=["screener"])

# Separate router for public action endpoints not under /screener prefix
actions_router = APIRouter(tags=["screener-actions"])


# ── HTML text extractor (no external deps) ────────────────────────────────────

class _TextExtractor(HTMLParser):
    _SKIP_TAGS = {"script", "style", "nav", "header", "footer", "noscript", "meta", "link"}

    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []
        self._depth = 0
        self._skip_depth: int | None = None

    def handle_starttag(self, tag: str, attrs: list) -> None:
        if tag in self._SKIP_TAGS:
            if self._skip_depth is None:
                self._skip_depth = self._depth
        self._depth += 1

    def handle_endtag(self, tag: str) -> None:
        self._depth -= 1
        if self._skip_depth is not None and self._depth <= self._skip_depth:
            self._skip_depth = None

    def handle_data(self, data: str) -> None:
        if self._skip_depth is None:
            text = data.strip()
            if text:
                self._parts.append(text)

    def get_text(self) -> str:
        return "\n".join(self._parts)


# ── AI extraction helper ──────────────────────────────────────────────────────

_EXTRACT_SYSTEM = (
    "You are an expert recruiter. Extract job details from this job description "
    "and return ONLY valid JSON with no markdown or explanation."
)

_EXTRACT_PROMPT_TEMPLATE = """Extract all details from this job description:

{text}

Return JSON exactly like this:
{{
  "title": "...",
  "job_type": "permanent|contract|casual",
  "location": "...",
  "work_type": "onsite|hybrid|remote",
  "salary_min": null,
  "salary_max": null,
  "experience_years": 3,
  "required_skills": ["skill1", "skill2"],
  "tech_stack": ["tech1", "tech2"],
  "description": "...",
  "evaluation_prompt": "Evaluate the candidate on their experience with...",
  "interview_questions_count": 5
}}"""


async def _extract_job_details(text: str, tenant: Tenant) -> dict[str, Any]:
    """Call AI provider to extract structured job details from free text."""
    ai = AIProvider(tenant)
    prompt = _EXTRACT_PROMPT_TEMPLATE.format(text=text[:8000])
    raw = await ai.complete(prompt=prompt, system=_EXTRACT_SYSTEM, max_tokens=2048)

    # Strip markdown code fences if present
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("```")[1]
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
        cleaned = cleaned.strip()

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        logger.error("screener extract: JSON parse failed: %s\nraw=%s", exc, raw[:500])
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI returned invalid JSON — please try again",
        ) from exc

    return data


# ── Request / response schemas ────────────────────────────────────────────────

class ExtractFromTextRequest(BaseModel):
    text: str


class ExtractFromUrlRequest(BaseModel):
    url: str


class ScreenerJobCreate(BaseModel):
    title: str
    job_type: str | None = None
    location: str | None = None
    work_type: str | None = None
    salary_min: float | None = None
    salary_max: float | None = None
    experience_years: int | None = None
    required_skills: list[str] = []
    tech_stack: list[str] = []
    description: str | None = None
    evaluation_prompt: str | None = None
    interview_questions_count: int = 5
    minimum_score: int = 6
    interview_type: str = "text"


class ScreenerJobResponse(BaseModel):
    job: JobResponse
    jobs_email: str
    application_instructions: str


class TestSessionState(BaseModel):
    session_id: str
    application_id: str
    status: str
    interview_type: str
    current_question_index: int
    total_questions: int
    current_question: str | None
    job_title: str | None
    firm_name: str | None
    completed: bool


class AnswerRequest(BaseModel):
    answer: str
    question_index: int


# ── Authenticated endpoints ───────────────────────────────────────────────────

@router.post("/jobs/extract-from-text")
async def extract_from_text(
    body: ExtractFromTextRequest,
    tenant: Tenant = Depends(get_current_tenant),
) -> dict[str, Any]:
    """Use AI to extract structured job details from pasted job description text."""
    if not body.text.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="text is required")
    return await _extract_job_details(body.text, tenant)


@router.post("/jobs/extract-from-url")
async def extract_from_url(
    body: ExtractFromUrlRequest,
    tenant: Tenant = Depends(get_current_tenant),
) -> dict[str, Any]:
    """Fetch a URL, extract visible text, then use AI to extract job details."""
    url = body.url.strip()
    if not url.startswith(("http://", "https://")):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid URL")

    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0 (compatible; AIWorkerz/1.0)"})
        resp.raise_for_status()
        html = resp.text
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"URL returned HTTP {exc.response.status_code}",
        ) from exc
    except Exception as exc:
        logger.error("screener extract_from_url: fetch failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not fetch URL",
        ) from exc

    parser = _TextExtractor()
    parser.feed(html)
    page_text = parser.get_text()

    if len(page_text.strip()) < 100:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Could not extract enough text from the URL",
        )

    return await _extract_job_details(page_text, tenant)


@router.post("/jobs", response_model=ScreenerJobResponse)
async def create_screener_job(
    body: ScreenerJobCreate,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
) -> ScreenerJobResponse:
    """Create a screener_only job and return application instructions."""
    job_ref = _generate_job_ref()

    job = Job(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        job_ref=job_ref,
        title=body.title,
        job_type=body.job_type,
        location=body.location,
        work_type=body.work_type,
        salary_min=body.salary_min,
        salary_max=body.salary_max,
        experience_years=body.experience_years,
        required_skills=body.required_skills or [],
        tech_stack=body.tech_stack or [],
        description=body.description,
        evaluation_prompt=body.evaluation_prompt,
        interview_questions_count=body.interview_questions_count,
        minimum_score=body.minimum_score,
        interview_type=body.interview_type,
        mode="screener_only",
        status="active",
        candidate_target=0,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    audit = AuditTrailService(db, tenant.id)
    await audit.emit(
        job_id=job.id,
        event_type="screener.job_created",
        event_category="resume_screener",
        severity="success",
        actor="system",
        summary=f"Screener Only job created: {job.title}",
    )

    jobs_email = tenant.jobs_email or tenant.email_inbox or "jobs@aiworkerz.com"
    instructions = (
        f"Email your resume to {jobs_email} with subject: {job_ref}"
    )

    return ScreenerJobResponse(
        job=JobResponse.model_validate(job),
        jobs_email=jobs_email,
        application_instructions=instructions,
    )


# ── Public test endpoints ─────────────────────────────────────────────────────

async def _get_test_session_or_404(
    application_id: uuid.UUID,
    token: str,
    db: AsyncSession,
) -> TestSession:
    result = await db.execute(
        select(TestSession).where(
            TestSession.application_id == application_id,
            TestSession.token == token,
        ).limit(1)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test session not found")

    now = datetime.now(timezone.utc)
    if session.token_expires_at.replace(tzinfo=timezone.utc) < now and not session.token_used:
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="Test session has expired")

    if session.status == "completed":
        return session  # allow re-view

    return session


@router.get("/test/{application_id}/{token}", response_model=TestSessionState)
async def get_test_session(
    application_id: uuid.UUID,
    token: str,
    db: AsyncSession = Depends(get_db),
) -> TestSessionState:
    """Public: return current test session state."""
    session = await _get_test_session_or_404(application_id, token, db)

    # Resolve job title and firm name
    job_result = await db.execute(select(Job).where(Job.id == session.job_id))
    job = job_result.scalar_one_or_none()
    tenant_result = await db.execute(
        select(Tenant).where(Tenant.id == session.tenant_id)
    )
    tenant = tenant_result.scalar_one_or_none()

    questions: list[str] = session.questions or []  # type: ignore[assignment]
    answers: list[Any] = session.answers or []       # type: ignore[assignment]
    answered_count = len(answers)
    total = len(questions)
    completed = session.status == "completed"
    current_q = questions[answered_count] if (not completed and answered_count < total) else None

    return TestSessionState(
        session_id=str(session.id),
        application_id=str(application_id),
        status=session.status,
        interview_type=session.interview_type,
        current_question_index=answered_count,
        total_questions=total,
        current_question=current_q,
        job_title=job.title if job else None,
        firm_name=tenant.name if tenant else None,
        completed=completed,
    )


@router.post("/test/{application_id}/{token}/answer")
async def submit_answer(
    application_id: uuid.UUID,
    token: str,
    body: AnswerRequest,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Public: store an answer and return the next question or completion signal."""
    session = await _get_test_session_or_404(application_id, token, db)

    if session.status == "completed":
        return {"completed": True, "message": "This test is already completed."}

    questions: list[str] = session.questions or []  # type: ignore[assignment]
    answers: list[Any] = list(session.answers or [])  # type: ignore[assignment]

    if body.question_index != len(answers):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Question index mismatch — answer already recorded or out of sequence",
        )

    answers.append({"question_index": body.question_index, "answer": body.answer})
    session.answers = answers

    # Mark started on first answer
    if not session.started_at:
        session.started_at = datetime.now(timezone.utc)

    db.add(session)
    await db.commit()

    next_index = len(answers)
    if next_index >= len(questions):
        return {"completed": False, "next_question": None, "next_index": next_index, "all_answered": True}

    return {
        "completed": False,
        "next_question": questions[next_index],
        "next_index": next_index,
        "all_answered": False,
    }


@router.post("/test/{application_id}/{token}/recording")
async def upload_recording(
    application_id: uuid.UUID,
    token: str,
    question_index: int,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Public: receive a recorded audio/video blob, transcribe via Whisper, store as answer.

    Multipart POST fields:
      - file: audio/video blob (webm/mp4/ogg/wav)
      - question_index: query param — which question this answers

    Flow:
      1. Upload blob to Supabase Storage (bucket: recordings)
      2. Transcribe with OpenAI Whisper
      3. Store recording URL in session.recording_urls
      4. Append transcript as answer (same shape as submit_answer)
      5. Return next_question or all_answered
    """
    import openai as _openai

    session = await _get_test_session_or_404(application_id, token, db)

    if session.status == "completed":
        return {"completed": True, "message": "This test is already completed."}

    questions: list[str] = session.questions or []  # type: ignore[assignment]
    answers: list[Any] = list(session.answers or [])  # type: ignore[assignment]
    recording_urls: list[Any] = list(session.recording_urls or [])  # type: ignore[assignment]
    transcripts: list[Any] = list(session.transcripts or [])  # type: ignore[assignment]

    if question_index != len(answers):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Question index mismatch — answer already recorded or out of sequence",
        )

    # Read file bytes
    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty file")

    content_type = file.content_type or "audio/webm"
    ext = "webm"
    if "mp4" in content_type:
        ext = "mp4"
    elif "ogg" in content_type:
        ext = "ogg"
    elif "wav" in content_type:
        ext = "wav"

    # 1. Upload to Supabase Storage
    storage_path = f"{application_id}/{question_index}.{ext}"
    storage_url = f"{settings.supabase_url}/storage/v1/object/recordings/{storage_path}"
    async with httpx.AsyncClient(timeout=30.0) as client:
        up_resp = await client.post(
            storage_url,
            content=file_bytes,
            headers={
                "Authorization": f"Bearer {settings.supabase_service_key}",
                "apikey": settings.supabase_service_key,
                "Content-Type": content_type,
            },
        )
    if up_resp.status_code not in (200, 201):
        logger.error("upload_recording: Supabase upload failed %s", up_resp.text[:200])
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Could not upload recording")

    public_url = f"{settings.supabase_url}/storage/v1/object/public/recordings/{storage_path}"

    # 2. Transcribe with OpenAI Whisper
    import io as _io
    transcript_text = ""
    if not settings.openai_api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Transcription not available — OpenAI API key not configured",
        )
    try:
        oai = _openai.OpenAI(api_key=settings.openai_api_key)
        audio_file = _io.BytesIO(file_bytes)
        audio_file.name = f"recording.{ext}"
        tr = oai.audio.transcriptions.create(model="whisper-1", file=audio_file)
        transcript_text = tr.text or ""
    except Exception as exc:
        logger.error("upload_recording: Whisper transcription failed: %s", exc)
        transcript_text = ""

    if not transcript_text.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Could not transcribe recording — please try again or use text input",
        )

    # 3 & 4. Store URL + transcript + answer
    recording_urls.append(public_url)
    transcripts.append({"question_index": question_index, "transcript": transcript_text})
    answers.append({"question_index": question_index, "answer": transcript_text})

    session.recording_urls = recording_urls
    session.transcripts = transcripts
    session.answers = answers

    if not session.started_at:
        session.started_at = datetime.now(timezone.utc)

    db.add(session)
    await db.commit()

    next_index = len(answers)
    if next_index >= len(questions):
        return {"completed": False, "next_question": None, "next_index": next_index, "all_answered": True, "transcript": transcript_text}

    return {
        "completed": False,
        "next_question": questions[next_index],
        "next_index": next_index,
        "all_answered": False,
        "transcript": transcript_text,
    }


@router.post("/test/{application_id}/{token}/complete")
async def complete_test(
    application_id: uuid.UUID,
    token: str,
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Public: mark test as completed and trigger scoring."""
    session = await _get_test_session_or_404(application_id, token, db)

    if session.status == "completed":
        return {"status": "already_completed", "message": "Your test has already been submitted."}

    now = datetime.now(timezone.utc)
    session.status = "completed"
    session.completed_at = now
    session.token_used = True

    # Update application
    app_result = await db.execute(
        select(Application).where(Application.id == application_id)
    )
    application = app_result.scalar_one_or_none()
    if application:
        application.test_completed_at = now
        application.test_status = "completed"

    db.add(session)
    await db.commit()

    # Trigger scoring task
    from app.tasks.screener_tasks import score_test
    score_test.delay(str(application_id), str(session.tenant_id))

    return {
        "status": "completed",
        "message": "Thank you! Your responses have been recorded and will be reviewed shortly.",
    }


# ── Public interview invitation endpoint ──────────────────────────────────────

from fastapi.responses import HTMLResponse, RedirectResponse


@actions_router.get(
    "/actions/invite/{application_id}/{token}",
    response_model=None,
    include_in_schema=True,
)
async def invite_interview_action(
    application_id: uuid.UUID,
    token: str,
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    """Public: hiring manager clicks to approve an interview invitation.

    Validates the token stored in application.interview_invite_token,
    marks the application as interview_invited, sends emails to candidate
    and hiring manager, and returns a confirmation page.
    """
    # Load application (no tenant auth — token is the auth mechanism)
    app_result = await db.execute(
        select(Application).where(Application.id == application_id)
    )
    application = app_result.scalar_one_or_none()
    if not application:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")

    # Validate token
    if not application.interview_invite_token or application.interview_invite_token != token:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid token")

    # Check expiry
    if application.interview_invite_expires_at:
        expires = application.interview_invite_expires_at
        if expires.tzinfo is None:
            from datetime import timezone as _tz
            expires = expires.replace(tzinfo=_tz.utc)
        if expires < datetime.now(timezone.utc):
            raise HTTPException(status_code=status.HTTP_410_GONE, detail="Invitation link has expired")

    # Idempotent: already invited
    if application.interview_invited:
        return RedirectResponse(url=f"{settings.frontend_url}/en/interview-invited?already=1", status_code=302)

    # Load job and tenant (no tenant filter — public endpoint)
    job_result = await db.execute(select(Job).where(Job.id == application.job_id))
    job = job_result.scalar_one_or_none()
    job_title = job.title if job else "the position"

    tenant_result = await db.execute(
        select(Tenant).where(Tenant.id == application.tenant_id)
    )
    tenant = tenant_result.scalar_one_or_none()

    # Mark as invited and invalidate token
    now = datetime.now(timezone.utc)
    application.interview_invited = True
    application.interview_invited_at = now
    application.status = "interview_invited"
    application.interview_invite_token = None  # invalidate
    await db.commit()

    hm_email = (job.hiring_manager_email if job else None) or (tenant.main_contact_email if tenant else None)

    # Send interview invitation email to candidate
    if tenant:
        candidate_html = (
            f"<div style='font-family:sans-serif;max-width:600px;margin:0 auto'>"
            f"<h2>Interview Invitation — {job_title}</h2>"
            f"<p>Dear {application.applicant_name},</p>"
            f"<p>Congratulations! We are delighted to invite you to interview for "
            f"<strong>{job_title}</strong> at {tenant.name}.</p>"
            f"<p>The hiring manager will be in touch with interview details shortly."
            f"{f' In the meantime, please contact {hm_email} with any questions.' if hm_email else ''}</p>"
            f"<p>We look forward to speaking with you.</p>"
            f"<p>Kind regards,<br>The Recruitment Team at {tenant.name}</p>"
            f"</div>"
        )
        from app.services.sendgrid_email import send_email
        await send_email(
            to=application.applicant_email,
            subject=f"Interview Invitation — {job_title} at {tenant.name}",
            html_body=candidate_html,
            tenant=tenant,
        )

        # Send confirmation to hiring manager
        if hm_email:
            hm_html = (
                f"<div style='font-family:sans-serif;max-width:600px;margin:0 auto'>"
                f"<h2>Interview invitation sent</h2>"
                f"<p>An interview invitation has been sent to "
                f"<strong>{application.applicant_name}</strong> ({application.applicant_email}) "
                f"for <strong>{job_title}</strong>.</p>"
                f"<p>Please contact them to arrange a suitable time.</p>"
                f"</div>"
            )
            await send_email(
                to=hm_email,
                subject=f"Interview invitation sent to {application.applicant_name}",
                html_body=hm_html,
                tenant=tenant,
            )

    # Audit (non-fatal)
    try:
        audit = AuditTrailService(db, application.tenant_id)
        await audit.emit(
            job_id=application.job_id,
            application_id=application.id,
            candidate_id=application.candidate_id,
            event_type="screener.interview_invited",
            event_category="resume_screener",
            severity="success",
            actor="hiring_manager",
            summary=f"Interview invitation sent to {application.applicant_name}",
            detail={"applicant_email": application.applicant_email},
        )
        await db.commit()
    except Exception as exc:
        logger.error("invite_interview_action: audit failed (non-fatal): %s", exc)

    candidate_name = application.applicant_name
    return RedirectResponse(
        url=f"{settings.frontend_url}/en/interview-invited?name={candidate_name}&role={job_title}",
        status_code=302,
    )


def _invite_confirmed_html(name: str, job_title: str) -> str:
    return f"""<!DOCTYPE html>
<html><head><title>Interview Invitation Sent</title></head>
<body style="font-family:sans-serif;max-width:480px;margin:60px auto;text-align:center;color:#1a1a2e">
<div style="background:#f0fdf4;border:1px solid #86efac;border-radius:12px;padding:40px">
<div style="font-size:48px;margin-bottom:16px">✓</div>
<h2 style="color:#16a34a;margin:0 0 12px">Interview Invitation Sent</h2>
<p style="color:#166534">{name} has been invited to interview for <strong>{job_title}</strong>.</p>
<p style="color:#166534;font-size:14px">They will receive an email with next steps shortly.</p>
</div>
</body></html>"""


def _invite_already_sent_html(name: str) -> str:
    return f"""<!DOCTYPE html>
<html><head><title>Already Sent</title></head>
<body style="font-family:sans-serif;max-width:480px;margin:60px auto;text-align:center;color:#1a1a2e">
<div style="background:#fefce8;border:1px solid #fde047;border-radius:12px;padding:40px">
<div style="font-size:48px;margin-bottom:16px">ℹ</div>
<h2 style="color:#ca8a04;margin:0 0 12px">Already Sent</h2>
<p style="color:#92400e">An interview invitation for {name} has already been sent.</p>
</div>
</body></html>"""
