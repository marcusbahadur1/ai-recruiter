"""Applications router — screening, competency test, interview invitation.

Routes:
  GET  /applications?job_id={id}           — list applications
  GET  /applications/{id}                  — get application
  POST /applications/{id}/trigger-test     — send test invitation
  GET  /test/{id}/{token}                  — public: get test session state
  POST /test/{id}/message                  — public: one turn of AI examiner chat
  GET  /actions/invite-interview/{id}/{token}  — public: HM approves interview
"""

import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import HTMLResponse
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.application import Application
from app.models.job import Job
from app.models.tenant import Tenant
from app.routers.auth import get_current_tenant
from app.schemas.application import ApplicationResponse
from app.schemas.common import PaginatedResponse
from app.services.ai_provider import AIProvider
from app.services.audit_trail import AuditTrailService
from app.services.sendgrid_email import send_email

_AI_EXAMINER_SYSTEM = (
    "You are a friendly, professional AI competency examiner conducting a structured "
    "interview. Your role:\n"
    "- Present each question clearly and professionally.\n"
    "- If the candidate's answer is vague, too brief, or unclear, ask ONE targeted "
    "follow-up probe (e.g. 'Can you give a specific example?' or 'Could you elaborate?').\n"
    "- Once satisfied, move to the next question.\n"
    "- Do NOT reveal whether answers are correct or incorrect.\n"
    "- Maintain a warm but focused tone throughout.\n"
    "Return ONLY valid JSON: "
    '{"reply": "your message to the candidate", '
    '"answer_accepted": true|false, '
    '"test_complete": false}'
)

router = APIRouter(tags=["applications"])

# Token algorithm for interview invitation JWTs
_JWT_ALGORITHM = "HS256"
_INTERVIEW_TOKEN_EXPIRY_DAYS = 7


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _get_application_or_404(
    application_id: uuid.UUID,
    tenant_id: uuid.UUID,
    db: AsyncSession,
) -> Application:
    result = await db.execute(
        select(Application).where(
            Application.id == application_id,
            Application.tenant_id == tenant_id,
        )
    )
    app = result.scalar_one_or_none()
    if not app:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")
    return app


async def _get_job_or_404(
    job_id: uuid.UUID,
    tenant_id: uuid.UUID,
    db: AsyncSession,
) -> Job:
    result = await db.execute(
        select(Job).where(Job.id == job_id, Job.tenant_id == tenant_id)
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return job


def _sign_interview_token(application_id: uuid.UUID) -> str:
    """Sign a one-time JWT for the hiring manager interview invitation link."""
    payload = {
        "sub": str(application_id),
        "purpose": "interview_invite",
        "exp": datetime.now(timezone.utc) + timedelta(days=_INTERVIEW_TOKEN_EXPIRY_DAYS),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.encryption_key, algorithm=_JWT_ALGORITHM)


def _verify_interview_token(token: str) -> uuid.UUID:
    """Verify interview token and return the application_id.

    Raises HTTPException on invalid/expired token.
    """
    try:
        payload = jwt.decode(token, settings.encryption_key, algorithms=[_JWT_ALGORITHM])
        if payload.get("purpose") != "interview_invite":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid token purpose",
            )
        return uuid.UUID(payload["sub"])
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired interview invitation token",
        )


def _sign_test_token(application_id: uuid.UUID) -> str:
    """Sign a JWT for the public test link (no expiry — valid until test completed)."""
    import time
    payload = {
        "sub": str(application_id),
        "purpose": "competency_test",
        "iat": int(time.time()),
    }
    return jwt.encode(payload, settings.encryption_key, algorithm=_JWT_ALGORITHM)


def _verify_test_token(application_id: uuid.UUID, token: str) -> None:
    """Verify the test token belongs to this application.

    Raises HTTPException on mismatch.
    """
    try:
        payload = jwt.decode(
            token, settings.encryption_key, algorithms=[_JWT_ALGORITHM],
            options={"verify_exp": False},
        )
        if payload.get("purpose") != "competency_test":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid token")
        token_app_id = uuid.UUID(payload["sub"])
        if token_app_id != application_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Token mismatch")
    except JWTError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid test token")


# ── Protected routes ──────────────────────────────────────────────────────────

@router.get("/applications", response_model=PaginatedResponse[ApplicationResponse])
async def list_applications(
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
    job_id: uuid.UUID | None = Query(None),
    screening_status: str | None = Query(None),
    limit: int = Query(50, le=100),
    offset: int = Query(0, ge=0),
) -> PaginatedResponse[ApplicationResponse]:
    """List applications for this tenant, optionally filtered by job."""
    conditions = [Application.tenant_id == tenant.id]
    if job_id:
        conditions.append(Application.job_id == job_id)
    if screening_status:
        conditions.append(Application.screening_status == screening_status)

    result = await db.execute(
        select(Application).where(*conditions).order_by(Application.created_at.desc())
    )
    all_apps = result.scalars().all()
    total = len(all_apps)
    page = all_apps[offset: offset + limit]
    return PaginatedResponse(
        items=[ApplicationResponse.model_validate(a) for a in page],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/applications/{application_id}", response_model=ApplicationResponse)
async def get_application(
    application_id: uuid.UUID,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
) -> ApplicationResponse:
    """Retrieve a single application by ID."""
    app = await _get_application_or_404(application_id, tenant.id, db)
    return ApplicationResponse.model_validate(app)


@router.post(
    "/applications/{application_id}/trigger-test",
    status_code=status.HTTP_202_ACCEPTED,
)
async def trigger_test(
    application_id: uuid.UUID,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Generate AI test questions and send the test invitation email.

    Requires application.screening_status == 'passed'.  Generates
    job.interview_questions_count questions via the AI provider, stores them
    in application.test_answers, and sends the test link via SendGrid.
    """
    app = await _get_application_or_404(application_id, tenant.id, db)
    job = await _get_job_or_404(app.job_id, tenant.id, db)
    audit = AuditTrailService(db, tenant.id)

    if app.screening_status != "passed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Application must have passed screening before a test can be triggered",
        )
    if app.test_status not in ("not_started",):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Test already in status '{app.test_status}'",
        )

    # Generate questions via AI
    ai = AIProvider(tenant)
    q_count = job.interview_questions_count or 5
    skills = ", ".join(job.required_skills or []) or "general skills"
    prompt = (
        f"Generate {q_count} competency interview questions for a {job.job_type} role "
        f"requiring {job.experience_years or '?'}+ years experience with skills in {skills}. "
        f"Return ONLY a JSON array of question strings."
    )
    try:
        raw = await ai.complete(prompt=prompt, max_tokens=800)
        questions: list[Any] = json.loads(raw)
        if not isinstance(questions, list):
            questions = [raw]
    except Exception:
        questions = [f"Question {i + 1}: Please describe your experience with {skills}." for i in range(q_count)]

    # Append any custom questions
    if job.custom_interview_questions:
        questions.extend(job.custom_interview_questions)

    test_token = _sign_test_token(application_id)
    test_url = f"https://app.airecruiterz.com/test/{application_id}/{test_token}"

    # Persist questions and update test status
    app.test_status = "invited"
    app.test_answers = {"questions": questions, "answers": [], "conversation": []}
    await db.commit()

    # Send test invitation email
    html_body = (
        f"<p>Dear {app.applicant_name},</p>"
        f"<p>Thank you for applying for <strong>{job.title}</strong>.</p>"
        f"<p>Please complete your competency assessment by clicking the link below:</p>"
        f"<p><a href='{test_url}'>Begin Your Assessment</a></p>"
        f"<p>This assessment consists of {len(questions)} questions.</p>"
    )
    await send_email(
        to=app.applicant_email,
        subject=f"Your assessment for {job.title} — {job.job_ref}",
        html_body=html_body,
        tenant=tenant,
    )

    await audit.emit(
        job_id=job.id,
        application_id=application_id,
        candidate_id=app.candidate_id,
        event_type="screener.test_invited",
        event_category="resume_screener",
        severity="success",
        actor="system",
        summary=f"Test invitation sent to {app.applicant_name} ({len(questions)} questions)",
        detail={"applicant_email": app.applicant_email, "question_count": len(questions)},
    )
    return {"status": "accepted", "application_id": str(application_id), "test_url": test_url}


# ── Public routes ─────────────────────────────────────────────────────────────

@router.get("/test/{application_id}/{token}")
async def get_test(
    application_id: uuid.UUID,
    token: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Public — return current test state for a candidate.

    The response includes questions answered so far and the next question.
    Token is a signed JWT generated when the test was triggered.
    """
    _verify_test_token(application_id, token)

    # Fetch application without tenant scope — token is the auth mechanism
    result = await db.execute(
        select(Application).where(Application.id == application_id)
    )
    app = result.scalar_one_or_none()
    if not app:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test not found")
    if app.test_status not in ("invited", "in_progress", "completed", "passed", "failed"):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Test not available")

    test_data: dict = app.test_answers or {}
    questions: list = test_data.get("questions", [])
    answers: list = test_data.get("answers", [])
    answered_count = len(answers)
    total_count = len(questions)
    next_question = questions[answered_count] if answered_count < total_count else None

    # Mark as in_progress on first access
    if app.test_status == "invited":
        app.test_status = "in_progress"
        await db.commit()

    return {
        "application_id": str(application_id),
        "applicant_name": app.applicant_name,
        "test_status": app.test_status,
        "questions_total": total_count,
        "questions_answered": answered_count,
        "next_question": next_question,
        "completed": answered_count >= total_count,
    }


@router.post("/test/{application_id}/message")
async def post_test_message(
    application_id: uuid.UUID,
    body: dict,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Public — one turn of the AI examiner conversation.

    Body: ``{"token": "<jwt>", "answer": "<candidate answer text>"}``.

    The AI examiner evaluates each answer, optionally probing for more detail,
    then advances to the next question when satisfied.  When all questions are
    answered the test is marked 'completed' and the score_test Celery task is
    queued.
    """
    token: str = body.get("token", "")
    answer_text: str = body.get("answer", "").strip()

    _verify_test_token(application_id, token)

    if not answer_text:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Answer required"
        )

    result = await db.execute(
        select(Application).where(Application.id == application_id)
    )
    app = result.scalar_one_or_none()
    if not app or app.test_status not in ("invited", "in_progress"):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Test not active")

    # Load tenant for AI provider
    tenant_result = await db.execute(
        select(Tenant).where(Tenant.id == app.tenant_id)
    )
    tenant = tenant_result.scalar_one_or_none()

    job_result = await db.execute(
        select(Job).where(Job.id == app.job_id)
    )
    job = job_result.scalar_one_or_none()

    test_data: dict = app.test_answers or {
        "questions": [], "current_question_idx": 0,
        "answers": [], "full_conversation": [],
    }
    questions: list = test_data.get("questions", [])
    answers: list = test_data.get("answers", [])
    conversation: list = test_data.get("full_conversation", [])
    q_idx: int = test_data.get("current_question_idx", len(answers))

    if q_idx >= len(questions):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="All questions answered")

    current_question = questions[q_idx]
    conversation.append({"role": "candidate", "content": answer_text})

    # Build AI examiner prompt
    ai_reply, answer_accepted = await _run_examiner_turn(
        tenant=tenant,
        job=job,
        current_question=current_question,
        conversation=conversation,
        q_idx=q_idx,
        total=len(questions),
    )

    conversation.append({"role": "examiner", "content": ai_reply})

    if answer_accepted:
        answers.append({"question": current_question, "answer": answer_text})
        q_idx += 1

    is_complete = q_idx >= len(questions)
    new_status = "completed" if is_complete else "in_progress"

    app.test_answers = {
        "questions": questions,
        "current_question_idx": q_idx,
        "answers": answers,
        "full_conversation": conversation,
    }
    app.test_status = new_status
    await db.commit()

    # Emit audit event
    audit = AuditTrailService(db, app.tenant_id)
    if is_complete:
        if job:
            await audit.emit(
                job_id=job.id, application_id=app.id,
                candidate_id=app.candidate_id,
                event_type="screener.test_completed",
                event_category="resume_screener", severity="success",
                actor="candidate",
                summary=f"All {len(questions)} questions answered by {app.applicant_name}",
            )
        # Queue scoring task
        from app.tasks.screener_tasks import score_test
        score_test.delay(str(app.id), str(app.tenant_id))
    elif job:
        await audit.emit(
            job_id=job.id, application_id=app.id,
            candidate_id=app.candidate_id,
            event_type="screener.test_question_answered",
            event_category="resume_screener", severity="info",
            actor="candidate",
            summary=f"Q{q_idx} answered",
        )

    return {
        "answered": len(answers),
        "total": len(questions),
        "completed": is_complete,
        "message": ai_reply,
        "next_question": questions[q_idx] if not is_complete else None,
    }


async def _run_examiner_turn(
    tenant: Any,
    job: Any,
    current_question: str,
    conversation: list[dict[str, str]],
    q_idx: int,
    total: int,
) -> tuple[str, bool]:
    """Call the AI examiner and return (reply, answer_accepted).

    Falls back to accepting the answer directly if AI is unavailable.
    """
    if not tenant:
        return f"Thank you. Moving to the next question.", True

    next_q_hint = ""
    if q_idx + 1 < total:
        next_q_hint = f"\nIf you accept the answer, end with: 'Next question: ...'"

    history = "\n".join(
        f"{'Candidate' if t['role'] == 'candidate' else 'Examiner'}: {t['content']}"
        for t in conversation[-6:]  # last 3 exchanges
    )
    prompt = (
        f"Current question ({q_idx + 1}/{total}): {current_question}\n\n"
        f"Conversation so far:\n{history}\n\n"
        f"Decide: is the latest candidate answer sufficient? "
        f"Return JSON with 'reply', 'answer_accepted' (bool), 'test_complete' (bool)."
        f"{next_q_hint}"
    )

    try:
        ai = AIProvider(tenant)
        raw = await ai.complete_json(
            prompt=prompt, system=_AI_EXAMINER_SYSTEM, max_tokens=400
        )
        reply = str(raw.get("reply", "Thank you for your answer."))
        accepted = bool(raw.get("answer_accepted", True))
        return reply, accepted
    except Exception:
        # Fallback: accept the answer and echo it back
        return "Thank you for your answer.", True


@router.get("/actions/invite-interview/{application_id}/{token}", response_class=HTMLResponse)
async def invite_interview(
    application_id: uuid.UUID,
    token: str,
    db: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    """Public — hiring manager clicks this link to approve an interview invitation.

    Verifies the signed JWT, marks the application as interview_invited, sends
    the interview invitation email to the candidate, and returns an HTML
    confirmation page.
    """
    # Verify token and extract application_id
    token_app_id = _verify_interview_token(token)
    if token_app_id != application_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Token mismatch")

    result = await db.execute(
        select(Application).where(Application.id == application_id)
    )
    app = result.scalar_one_or_none()
    if not app:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")

    # Idempotent: already invited
    if app.interview_invited:
        return HTMLResponse(_interview_already_sent_html(app.applicant_name))

    # Load job for context (no tenant filter — HM has no JWT)
    job_result = await db.execute(select(Job).where(Job.id == app.job_id))
    job = job_result.scalar_one_or_none()
    job_title = job.title if job else "the position"

    # Load tenant for email
    tenant_result = await db.execute(
        select(Tenant).where(Tenant.id == app.tenant_id)
    )
    tenant = tenant_result.scalar_one_or_none()

    app.interview_invited = True
    app.interview_invited_at = datetime.now(timezone.utc)
    await db.commit()

    # Send interview invitation email to candidate
    if tenant:
        html_body = (
            f"<p>Dear {app.applicant_name},</p>"
            f"<p>Congratulations! You have been selected for an interview for "
            f"<strong>{job_title}</strong>.</p>"
            f"<p>You will receive further details about the interview schedule shortly.</p>"
        )
        await send_email(
            to=app.applicant_email,
            subject=f"Interview Invitation — {job_title}",
            html_body=html_body,
            tenant=tenant,
        )

    # Emit audit event
    if job and tenant:
        audit = AuditTrailService(db, app.tenant_id)
        await audit.emit(
            job_id=app.job_id,
            application_id=application_id,
            candidate_id=app.candidate_id,
            event_type="screener.interview_invited",
            event_category="resume_screener",
            severity="success",
            actor="hiring_manager",
            summary=f"Interview invitation sent to {app.applicant_name}",
            detail={"applicant_email": app.applicant_email},
        )

    return HTMLResponse(_interview_confirmed_html(app.applicant_name, job_title))


# ── HTML response helpers ──────────────────────────────────────────────────────

def _interview_confirmed_html(name: str, job_title: str) -> str:
    return f"""<!DOCTYPE html>
<html><head><title>Interview Invitation Sent</title></head>
<body style="font-family:sans-serif;max-width:480px;margin:60px auto;text-align:center">
<h2 style="color:#16a34a">Interview Invitation Sent</h2>
<p>{name} has been invited to interview for <strong>{job_title}</strong>.</p>
<p>They will receive an email with interview details shortly.</p>
</body></html>"""


def _interview_already_sent_html(name: str) -> str:
    return f"""<!DOCTYPE html>
<html><head><title>Already Sent</title></head>
<body style="font-family:sans-serif;max-width:480px;margin:60px auto;text-align:center">
<h2 style="color:#ca8a04">Already Sent</h2>
<p>An interview invitation for {name} has already been sent.</p>
</body></html>"""
