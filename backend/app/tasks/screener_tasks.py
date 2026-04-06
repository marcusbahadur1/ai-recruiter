"""Celery tasks for the AI Resume Screener pipeline.

Task flow per application (SPEC §8):
  poll_mailboxes  →  screen_resume  →  invite_to_test
                                      [candidate completes test]
                                    →  score_test  →  [HM notified]

All tasks:
- Are idempotent (check current status before acting).
- Have max_retries=3 with exponential backoff (30s, 60s, 120s).
- Emit audit events on success and failure.
- Filter every DB query by tenant_id (guidelines §2).
- Never call AI SDKs directly — always go through AIProvider facade.
"""

import asyncio
import email as email_lib
import imaplib
import io
import json
import logging
import re
import time
import uuid
from datetime import datetime, timezone
from email.header import decode_header
from typing import Any

import numpy as np
import pdfplumber
from docx import Document
from jose import jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import AsyncSessionLocal
from app.models.application import Application
from app.models.candidate import Candidate
from app.models.job import Job
from app.models.tenant import Tenant
from app.services.ai_provider import AIProvider
from app.services.audit_trail import AuditTrailService
from app.services.crypto import decrypt
from app.services.embeddings import generate_embedding
from app.services.sendgrid_email import send_email
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)

_JWT_ALGORITHM = "HS256"
_SCREENING_EVAL_PROMPT = (
    "Given this is a {job_type} role requiring {experience_years}+ years experience "
    "with skills in {required_skills}, evaluate the following resume. "
    "Score 1–10 for suitability. Return ONLY valid JSON:\n"
    '{{"score": N, "reasoning": "...", "strengths": [...], "gaps": [...], '
    '"recommended_action": "pass|fail"}}\n\nResume:\n{resume_text}'
)
_TEST_SCORING_PROMPT = (
    "You are a senior technical interviewer. Review this competency test transcript "
    "for a {job_type} role and score the candidate's performance 1–10. "
    "Return ONLY valid JSON:\n"
    '{{"score": N, "reasoning": "...", "per_question": [{{"question": "...", '
    '"assessment": "..."}}], "recommended_action": "pass|fail"}}\n\n'
    "Job Requirements: {job_spec}\n\nTest Transcript:\n{transcript}"
)
_QUESTION_GEN_PROMPT = (
    "Generate {count} competency interview questions for a {job_type} role "
    "requiring {years}+ years experience with skills in {skills}. "
    "Return ONLY a JSON array of question strings."
)


# ── Celery tasks ───────────────────────────────────────────────────────────────


@celery_app.task(bind=True, max_retries=3, name="app.tasks.screener_tasks.poll_mailboxes")
def poll_mailboxes(self) -> None:  # type: ignore[override]
    """Poll IMAP mailboxes for all active tenants.

    Scheduled every 5 minutes (SPEC §14.2).  For each active tenant,
    fetches UNSEEN emails, parses job_ref, extracts resume text and
    embedding, creates Application records, and triggers screen_resume.
    """
    try:
        asyncio.run(_poll_mailboxes_impl())
    except Exception as exc:
        if self.request.retries >= self.max_retries:
            logger.error("poll_mailboxes permanently failed: %s", exc)
            return
        raise self.retry(exc=exc, countdown=2 ** self.request.retries * 30)


@celery_app.task(
    bind=True, max_retries=3, name="app.tasks.screener_tasks.screen_resume"
)
def screen_resume(self, application_id: str, tenant_id: str) -> None:
    """Screen a resume: cosine similarity + AI evaluation (SPEC §8.2).

    Idempotent — only acts when screening_status == 'pending'.
    On pass: triggers invite_to_test.
    On fail: sends polite rejection email.
    """
    try:
        asyncio.run(
            _screen_resume_impl(uuid.UUID(application_id), uuid.UUID(tenant_id))
        )
    except Exception as exc:
        if self.request.retries >= self.max_retries:
            asyncio.run(
                _emit_app_permanent_failure(
                    uuid.UUID(application_id), uuid.UUID(tenant_id),
                    "screen_resume", str(exc),
                )
            )
            return
        raise self.retry(exc=exc, countdown=2 ** self.request.retries * 30)


@celery_app.task(
    bind=True, max_retries=3, name="app.tasks.screener_tasks.invite_to_test"
)
def invite_to_test(self, application_id: str, tenant_id: str) -> None:
    """Generate AI test questions and send test invitation email (SPEC §8.3).

    Idempotent — only acts when test_status == 'not_started'.
    """
    try:
        asyncio.run(
            _invite_to_test_impl(uuid.UUID(application_id), uuid.UUID(tenant_id))
        )
    except Exception as exc:
        if self.request.retries >= self.max_retries:
            asyncio.run(
                _emit_app_permanent_failure(
                    uuid.UUID(application_id), uuid.UUID(tenant_id),
                    "invite_to_test", str(exc),
                )
            )
            return
        raise self.retry(exc=exc, countdown=2 ** self.request.retries * 30)


@celery_app.task(
    bind=True, max_retries=3, name="app.tasks.screener_tasks.score_test"
)
def score_test(self, application_id: str, tenant_id: str) -> None:
    """Score a completed competency test transcript (SPEC §8.3).

    Idempotent — only acts when test_status == 'completed'.
    On pass: notifies hiring manager with invite-interview link.
    On fail: sends polite rejection to candidate.
    """
    try:
        asyncio.run(
            _score_test_impl(uuid.UUID(application_id), uuid.UUID(tenant_id))
        )
    except Exception as exc:
        if self.request.retries >= self.max_retries:
            asyncio.run(
                _emit_app_permanent_failure(
                    uuid.UUID(application_id), uuid.UUID(tenant_id),
                    "score_test", str(exc),
                )
            )
            return
        raise self.retry(exc=exc, countdown=2 ** self.request.retries * 30)


# ── Async implementations ──────────────────────────────────────────────────────


async def _poll_mailboxes_impl() -> None:
    """Fetch all active tenants and poll each mailbox in sequence."""
    async with AsyncSessionLocal() as db:
        tenants = await _get_active_tenants(db)

    for tenant in tenants:
        try:
            loop = asyncio.get_event_loop()
            raw_emails = await loop.run_in_executor(None, _fetch_imap_emails, tenant)
            if raw_emails:
                async with AsyncSessionLocal() as db:
                    for raw in raw_emails:
                        await _process_raw_email(db, tenant, raw)
        except Exception as exc:
            logger.error(
                "Failed to poll mailbox for tenant %s (%s): %s",
                tenant.id, tenant.email_inbox, exc,
            )


async def _process_raw_email(
    db: AsyncSession, tenant: Tenant, raw: dict[str, Any]
) -> None:
    """Process one parsed email: validate, deduplicate, create Application."""
    audit = AuditTrailService(db, tenant.id)
    subject: str = raw.get("subject", "")
    sender_email: str = raw.get("sender_email", "")
    sender_name: str = raw.get("sender_name", sender_email)
    message_id: str = raw.get("message_id", "")
    attachment_bytes: bytes | None = raw.get("attachment_bytes")
    attachment_ext: str = raw.get("attachment_ext", "")

    # Step 1: Parse job_ref from subject
    job_ref = _extract_job_ref(subject)
    if not job_ref:
        logger.info("poll_mailboxes: no job_ref in subject '%s' — discarding", subject)
        return

    # Step 2: Look up job by job_ref + tenant
    job = await _get_job_by_ref(db, job_ref, tenant.id)
    if not job:
        await audit.emit(
            job_id=uuid.uuid4(),  # unknown job — no real job_id to attach to
            event_type="screener.job_ref_not_found",
            event_category="resume_screener",
            severity="warning",
            actor="system",
            summary=f"Job ref '{job_ref}' not found — email from {sender_email} discarded",
            detail={"subject": subject, "sender": sender_email},
        )
        return

    await audit.emit(
        job_id=job.id,
        event_type="screener.email_received",
        event_category="resume_screener",
        severity="info",
        actor="system",
        summary=f"Email received from {sender_email}",
        detail={"subject": subject, "sender": sender_email, "message_id": message_id},
    )
    await audit.emit(
        job_id=job.id,
        event_type="screener.job_ref_matched",
        event_category="resume_screener",
        severity="success",
        actor="system",
        summary=f"Job ref '{job_ref}' matched to '{job.title}'",
    )

    # Step 3: Deduplicate via Message-ID
    if message_id:
        dup = await _find_duplicate(db, message_id, tenant.id)
        if dup:
            await audit.emit(
                job_id=job.id,
                event_type="screener.duplicate_application",
                event_category="resume_screener",
                severity="info",
                actor="system",
                summary=f"Duplicate Message-ID — skipping {sender_email}",
                detail={"message_id": message_id},
            )
            return

    # Step 4: Check for PDF/DOCX attachment
    if not attachment_bytes or attachment_ext not in ("pdf", "docx"):
        await _send_no_attachment_reply(tenant, sender_email, sender_name, job)
        await audit.emit(
            job_id=job.id,
            event_type="screener.no_attachment",
            event_category="resume_screener",
            severity="warning",
            actor="system",
            summary=f"No PDF/DOCX attachment from {sender_email} — auto-reply sent",
        )
        return

    # Step 5: Extract resume text
    resume_text = _extract_text(attachment_bytes, attachment_ext)
    if not resume_text:
        logger.warning("poll_mailboxes: could not extract text from %s attachment", attachment_ext)
        return

    word_count = len(resume_text.split())
    await audit.emit(
        job_id=job.id,
        event_type="screener.resume_extracted",
        event_category="resume_screener",
        severity="info",
        actor="system",
        summary=f"Resume extracted: {word_count} words",
        detail={"word_count": word_count, "format": attachment_ext},
    )

    # Step 6: Generate embedding
    t0 = time.time()
    try:
        embedding = await generate_embedding(resume_text, tenant)
    except Exception as exc:
        logger.error("poll_mailboxes: embedding generation failed: %s", exc)
        embedding = None

    emb_ms = int((time.time() - t0) * 1000)
    if embedding:
        await audit.emit(
            job_id=job.id,
            event_type="screener.embedding_generated",
            event_category="resume_screener",
            severity="info",
            actor="system",
            summary="Resume embedding stored (1536 dims)",
            duration_ms=emb_ms,
        )

    # Step 7: Check for matching candidate (from Talent Scout)
    candidate_id = await _find_candidate_by_email(db, sender_email, job.id, tenant.id)

    # Step 8: Build storage path
    storage_path = (
        f"{tenant.id}/{job.id}/{sender_email}/resume.{attachment_ext}"
    )

    # Step 9: Create Application record
    app = Application(
        tenant_id=tenant.id,
        job_id=job.id,
        candidate_id=candidate_id,
        applicant_name=sender_name,
        applicant_email=sender_email,
        resume_storage_path=storage_path,
        resume_text=resume_text,
        resume_embedding=embedding,
        screening_status="pending",
        test_status="not_started",
        email_message_id=message_id or None,
        gdpr_consent_given=True,
        received_at=datetime.now(timezone.utc),
    )
    async with db.begin():
        db.add(app)
        await db.flush()

    if candidate_id:
        await audit.emit(
            job_id=job.id,
            application_id=app.id,
            candidate_id=candidate_id,
            event_type="screener.candidate_linked",
            event_category="resume_screener",
            severity="info",
            actor="system",
            summary=f"Applicant matched to Scout candidate",
        )

    # Step 10: Trigger screening task
    screen_resume.delay(str(app.id), str(tenant.id))


async def _screen_resume_impl(
    application_id: uuid.UUID, tenant_id: uuid.UUID
) -> None:
    """Idempotent: skip if screening_status != 'pending'."""
    async with AsyncSessionLocal() as db:
        app = await _get_application(db, application_id, tenant_id)
        if not app:
            logger.warning("screen_resume: application %s not found", application_id)
            return
        if app.screening_status != "pending":
            logger.info(
                "screen_resume: application %s already at %r — skipping",
                application_id, app.screening_status,
            )
            return

        job = await _get_job(db, app.job_id, tenant_id)
        tenant = await _get_tenant(db, tenant_id)
        if not job or not tenant:
            return

        audit = AuditTrailService(db, tenant_id)
        await audit.emit(
            job_id=job.id,
            application_id=app.id,
            candidate_id=app.candidate_id,
            event_type="screener.screening_started",
            event_category="resume_screener",
            severity="info",
            actor="system",
            summary=f"Screening resume for {app.applicant_name}",
        )

        # Cosine similarity between resume and job spec
        similarity = await _compute_job_similarity(app, job, tenant)

        # AI evaluation
        t0 = time.time()
        try:
            result = await _run_ai_screening(app, job, tenant)
        except Exception as exc:
            duration_ms = int((time.time() - t0) * 1000)
            await audit.emit(
                job_id=job.id, application_id=app.id,
                event_type="screener.screening_failed",
                event_category="resume_screener", severity="error",
                actor="system",
                summary=f"AI screening error for {app.applicant_name}: {exc}",
                duration_ms=duration_ms,
            )
            raise

        duration_ms = int((time.time() - t0) * 1000)
        score = int(result.get("score", 0))
        reasoning = result.get("reasoning", "")
        recommended = result.get("recommended_action", "fail")
        passed = score >= job.minimum_score and recommended != "fail"

        async with db.begin():
            app.screening_score = score
            app.screening_reasoning = reasoning
            app.screening_status = "passed" if passed else "failed"
            await db.flush()

        event_type = "screener.screening_passed" if passed else "screener.screening_failed"
        await audit.emit(
            job_id=job.id, application_id=app.id,
            candidate_id=app.candidate_id,
            event_type=event_type,
            event_category="resume_screener",
            severity="success" if passed else "info",
            actor="system",
            summary=(
                f"Scored {score}/10 — {'passed' if passed else 'below threshold'} "
                f"(similarity: {similarity:.2f})"
            ),
            detail={
                "score": score, "similarity": similarity, "reasoning": reasoning,
                "strengths": result.get("strengths", []),
                "gaps": result.get("gaps", []),
            },
            duration_ms=duration_ms,
        )

        if passed:
            invite_to_test.delay(str(app.id), str(tenant_id))
        else:
            await _send_rejection_email(tenant, app, job, reason="screening")
            await audit.emit(
                job_id=job.id, application_id=app.id,
                event_type="screener.rejection_email_sent",
                event_category="resume_screener", severity="info",
                actor="system",
                summary=f"Rejection email sent to {app.applicant_email}",
            )


async def _invite_to_test_impl(
    application_id: uuid.UUID, tenant_id: uuid.UUID
) -> None:
    """Idempotent: skip if test_status != 'not_started'."""
    async with AsyncSessionLocal() as db:
        app = await _get_application(db, application_id, tenant_id)
        if not app:
            logger.warning("invite_to_test: application %s not found", application_id)
            return
        if app.test_status != "not_started":
            logger.info(
                "invite_to_test: application %s already at test_status %r — skipping",
                application_id, app.test_status,
            )
            return

        job = await _get_job(db, app.job_id, tenant_id)
        tenant = await _get_tenant(db, tenant_id)
        if not job or not tenant:
            return

        # Generate questions via AI
        questions = await _generate_test_questions(job, tenant)
        if job.custom_interview_questions:
            questions.extend(job.custom_interview_questions)

        test_token = _sign_test_token(application_id)
        test_url = f"{settings.frontend_url}/test/{application_id}/{test_token}"

        async with db.begin():
            app.test_status = "invited"
            app.test_answers = {
                "questions": questions,
                "current_question_idx": 0,
                "answers": [],
                "full_conversation": [],
            }
            await db.flush()

        await send_email(
            to=app.applicant_email,
            subject=f"Your assessment for {job.title} — {job.job_ref}",
            html_body=_test_invitation_html(app, job, questions, test_url),
            tenant=tenant,
        )

        audit = AuditTrailService(db, tenant_id)
        await audit.emit(
            job_id=job.id, application_id=app.id,
            candidate_id=app.candidate_id,
            event_type="screener.test_invited",
            event_category="resume_screener", severity="success",
            actor="system",
            summary=f"Test invitation sent to {app.applicant_name} ({len(questions)} questions)",
            detail={"applicant_email": app.applicant_email, "question_count": len(questions)},
        )


async def _score_test_impl(
    application_id: uuid.UUID, tenant_id: uuid.UUID
) -> None:
    """Idempotent: skip if test_status != 'completed'."""
    async with AsyncSessionLocal() as db:
        app = await _get_application(db, application_id, tenant_id)
        if not app:
            logger.warning("score_test: application %s not found", application_id)
            return
        if app.test_status != "completed":
            logger.info(
                "score_test: application %s at test_status %r — skipping",
                application_id, app.test_status,
            )
            return

        job = await _get_job(db, app.job_id, tenant_id)
        tenant = await _get_tenant(db, tenant_id)
        if not job or not tenant:
            return

        audit = AuditTrailService(db, tenant_id)
        transcript = _build_transcript(app.test_answers or {})
        job_spec = _build_job_spec_text(job)

        t0 = time.time()
        try:
            ai = AIProvider(tenant)
            prompt = _TEST_SCORING_PROMPT.format(
                job_type=job.job_type or job.title,
                job_spec=job_spec,
                transcript=transcript,
            )
            result = await ai.complete_json(prompt=prompt, max_tokens=1000)
        except Exception as exc:
            duration_ms = int((time.time() - t0) * 1000)
            await audit.emit(
                job_id=job.id, application_id=app.id,
                event_type="screener.test_scored",
                event_category="resume_screener", severity="error",
                actor="system",
                summary=f"Test scoring error for {app.applicant_name}: {exc}",
                duration_ms=duration_ms,
            )
            raise

        duration_ms = int((time.time() - t0) * 1000)
        score = int(result.get("score", 0))
        recommended = result.get("recommended_action", "fail")
        passed = score >= job.minimum_score and recommended != "fail"

        async with db.begin():
            app.test_score = score
            app.test_status = "passed" if passed else "failed"
            await db.flush()

        event_type = "screener.test_scored" if passed else "screener.test_score_failed"
        await audit.emit(
            job_id=job.id, application_id=app.id,
            candidate_id=app.candidate_id,
            event_type=event_type,
            event_category="resume_screener",
            severity="success" if passed else "info",
            actor="system",
            summary=f"Test scored {score}/10 — {'passed' if passed else 'failed'}",
            detail={"score": score, "reasoning": result.get("reasoning", ""),
                    "per_question": result.get("per_question", [])},
            duration_ms=duration_ms,
        )

        if passed:
            await _notify_hiring_manager(tenant, app, job, score, audit)
        else:
            await _send_rejection_email(tenant, app, job, reason="test")
            await audit.emit(
                job_id=job.id, application_id=app.id,
                event_type="screener.rejection_email_sent",
                event_category="resume_screener", severity="info",
                actor="system",
                summary=f"Rejection email sent to {app.applicant_email} after test failure",
            )


# ── IMAP helpers (synchronous — run in thread executor) ────────────────────────


def _fetch_imap_emails(tenant: Tenant) -> list[dict[str, Any]]:
    """Open IMAP connection for tenant, fetch UNSEEN emails, mark as seen.

    Returns a list of raw email dicts for async processing.
    """
    host, port, user, password = _get_imap_credentials(tenant)
    results: list[dict[str, Any]] = []
    try:
        with imaplib.IMAP4_SSL(host, port) as M:
            M.login(user, password)
            M.select("INBOX")
            _, nums = M.search(None, "UNSEEN")
            for num in nums[0].split():
                _, data = M.fetch(num, "(RFC822)")
                raw_bytes = data[0][1] if data and data[0] else None
                if not raw_bytes:
                    continue
                parsed = _parse_raw_email(raw_bytes)
                if parsed:
                    results.append(parsed)
                    # Mark as read so we don't process twice
                    M.store(num, "+FLAGS", "\\Seen")
    except Exception as exc:
        logger.error("IMAP error for tenant %s: %s", tenant.id, exc)
    return results


def _get_imap_credentials(tenant: Tenant) -> tuple[str, int, str, str]:
    """Return (host, port, user, password) for this tenant's mailbox."""
    if tenant.email_inbox_host and tenant.email_inbox_user:
        password = (
            decrypt(tenant.email_inbox_password)
            if tenant.email_inbox_password
            else ""
        )
        return (
            tenant.email_inbox_host,
            tenant.email_inbox_port or 993,
            tenant.email_inbox_user,
            password,
        )
    # Platform-managed mailbox
    return (
        settings.imap_host,
        settings.imap_port,
        tenant.email_inbox or "",
        settings.imap_master_password,
    )


def _parse_raw_email(raw_bytes: bytes) -> dict[str, Any] | None:
    """Parse raw RFC822 bytes into a structured dict."""
    msg = email_lib.message_from_bytes(raw_bytes)
    subject = _decode_header_value(msg.get("Subject", ""))
    message_id = msg.get("Message-ID", "").strip()
    from_header = _decode_header_value(msg.get("From", ""))
    sender_name, sender_email = email_lib.utils.parseaddr(from_header)

    attachment_bytes: bytes | None = None
    attachment_ext = ""

    for part in msg.walk():
        ct = part.get_content_type()
        disp = str(part.get("Content-Disposition", ""))
        if "attachment" not in disp and ct not in (
            "application/pdf",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ):
            continue
        filename = part.get_filename() or ""
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        if ext in ("pdf", "docx"):
            attachment_bytes = part.get_payload(decode=True)
            attachment_ext = ext
            break

    return {
        "subject": subject,
        "message_id": message_id,
        "sender_name": sender_name.strip() or sender_email,
        "sender_email": sender_email.lower().strip(),
        "attachment_bytes": attachment_bytes,
        "attachment_ext": attachment_ext,
    }


def _decode_header_value(raw: str) -> str:
    """Decode RFC2047-encoded header values to a plain string."""
    parts = decode_header(raw)
    decoded = []
    for part, charset in parts:
        if isinstance(part, bytes):
            decoded.append(part.decode(charset or "utf-8", errors="replace"))
        else:
            decoded.append(part)
    return " ".join(decoded)


def _extract_text(data: bytes, ext: str) -> str:
    """Extract plain text from PDF or DOCX bytes."""
    try:
        if ext == "pdf":
            with pdfplumber.open(io.BytesIO(data)) as pdf:
                return "\n".join(p.extract_text() or "" for p in pdf.pages).strip()
        if ext == "docx":
            doc = Document(io.BytesIO(data))
            return "\n".join(para.text for para in doc.paragraphs).strip()
    except Exception as exc:
        logger.error("Text extraction failed (%s): %s", ext, exc)
    return ""


def _extract_job_ref(subject: str) -> str | None:
    """Extract 8-char alphanumeric job_ref from email subject."""
    match = re.search(r"\b([A-Z0-9]{6,12})\b", subject.upper())
    return match.group(1) if match else None


# ── AI helpers ─────────────────────────────────────────────────────────────────


async def _compute_job_similarity(
    app: Application, job: Job, tenant: Tenant
) -> float:
    """Return cosine similarity between resume_embedding and job spec embedding."""
    if app.resume_embedding is None:
        return 0.0
    try:
        job_spec = _build_job_spec_text(job)
        job_embedding = await generate_embedding(job_spec, tenant)
        return _cosine_similarity(list(app.resume_embedding), job_embedding)
    except Exception as exc:
        logger.warning("similarity computation failed: %s", exc)
        return 0.0


async def _run_ai_screening(
    app: Application, job: Job, tenant: Tenant
) -> dict[str, Any]:
    """Call AI with evaluation_prompt and resume text; return parsed JSON result."""
    resume_text = (app.resume_text or "")[:4000]  # truncate for token budget
    skills = ", ".join(job.required_skills or []) or "general skills"
    system = job.evaluation_prompt or _SCREENING_EVAL_PROMPT.format(
        job_type=job.job_type or job.title,
        experience_years=job.experience_years or 0,
        required_skills=skills,
        resume_text="",  # injected in user prompt below
    )
    prompt = _SCREENING_EVAL_PROMPT.format(
        job_type=job.job_type or job.title,
        experience_years=job.experience_years or 0,
        required_skills=skills,
        resume_text=resume_text,
    )
    ai = AIProvider(tenant)
    return await ai.complete_json(prompt=prompt, max_tokens=600)


async def _generate_test_questions(job: Job, tenant: Tenant) -> list[str]:
    """Generate AI competency questions for the job; fall back to defaults."""
    count = job.interview_questions_count or 5
    skills = ", ".join(job.required_skills or []) or "general skills"
    prompt = _QUESTION_GEN_PROMPT.format(
        count=count,
        job_type=job.job_type or job.title,
        years=job.experience_years or 0,
        skills=skills,
    )
    try:
        ai = AIProvider(tenant)
        raw = await ai.complete(prompt=prompt, max_tokens=800)
        questions = json.loads(raw)
        if isinstance(questions, list):
            return [str(q) for q in questions]
    except Exception as exc:
        logger.warning("question generation failed: %s", exc)
    return [
        f"Question {i + 1}: Please describe your experience with {skills}."
        for i in range(count)
    ]


# ── Email helpers ──────────────────────────────────────────────────────────────


async def _send_no_attachment_reply(
    tenant: Tenant, to: str, name: str, job: Job
) -> None:
    """Send an auto-reply asking the applicant to resubmit with a resume."""
    html = (
        f"<p>Dear {name},</p>"
        f"<p>Thank you for your interest in the <strong>{job.title}</strong> position "
        f"(ref: {job.job_ref}).</p>"
        f"<p>We were unable to find a PDF or DOCX resume attached to your email. "
        f"Please reply with your resume attached as a PDF or Word document.</p>"
        f"<p>Kind regards,<br>The Recruitment Team</p>"
    )
    await send_email(
        to=to,
        subject=f"Action Required: Please attach your resume — {job.job_ref}",
        html_body=html,
        tenant=tenant,
    )


async def _send_rejection_email(
    tenant: Tenant, app: Application, job: Job, reason: str
) -> None:
    """Send a polite rejection email to the applicant."""
    stage = "application" if reason == "screening" else "assessment"
    html = (
        f"<p>Dear {app.applicant_name},</p>"
        f"<p>Thank you for your interest in the <strong>{job.title}</strong> role "
        f"and for taking the time to submit your {stage}.</p>"
        f"<p>After careful consideration, we regret to inform you that we will not "
        f"be progressing your application at this time. We appreciate your interest "
        f"and wish you every success in your job search.</p>"
        f"<p>Kind regards,<br>The Recruitment Team</p>"
    )
    await send_email(
        to=app.applicant_email,
        subject=f"Update on your application — {job.title} ({job.job_ref})",
        html_body=html,
        tenant=tenant,
    )


async def _notify_hiring_manager(
    tenant: Tenant,
    app: Application,
    job: Job,
    test_score: int,
    audit: AuditTrailService,
) -> None:
    """Email the hiring manager with candidate results and invite-interview link."""
    if not job.hiring_manager_email:
        return

    invite_token = _sign_interview_token(app.id)
    invite_url = (
        f"{settings.frontend_url}/actions/invite-interview/{app.id}/{invite_token}"
    )

    html = (
        f"<p>Dear {job.hiring_manager_name or 'Hiring Manager'},</p>"
        f"<p>A candidate has successfully completed the competency assessment for "
        f"<strong>{job.title}</strong> ({job.job_ref}).</p>"
        f"<table style='border-collapse:collapse;width:100%'>"
        f"<tr><td><strong>Candidate</strong></td><td>{app.applicant_name}</td></tr>"
        f"<tr><td><strong>Email</strong></td><td>{app.applicant_email}</td></tr>"
        f"<tr><td><strong>Screening Score</strong></td><td>{app.screening_score}/10</td></tr>"
        f"<tr><td><strong>Test Score</strong></td><td>{test_score}/10</td></tr>"
        f"</table>"
        f"<p style='margin-top:24px'>"
        f"<a href='{invite_url}' style='background:#16a34a;color:white;padding:12px 24px;"
        f"border-radius:6px;text-decoration:none;font-weight:bold'>"
        f"Invite to Interview</a></p>"
        f"<p style='font-size:12px;color:#666'>This link expires in 7 days.</p>"
    )
    await send_email(
        to=job.hiring_manager_email,
        subject=f"Candidate Ready for Interview — {app.applicant_name} | {job.job_ref}",
        html_body=html,
        tenant=tenant,
    )

    await audit.emit(
        job_id=job.id,
        application_id=app.id,
        candidate_id=app.candidate_id,
        event_type="screener.hm_notified",
        event_category="resume_screener",
        severity="success",
        actor="system",
        summary=f"Hiring manager notified: {app.applicant_name} passed test ({test_score}/10)",
        detail={"hm_email": job.hiring_manager_email},
    )


def _test_invitation_html(
    app: Application, job: Job, questions: list[str], test_url: str
) -> str:
    """Build HTML body for the test invitation email."""
    return (
        f"<p>Dear {app.applicant_name},</p>"
        f"<p>Thank you for applying for <strong>{job.title}</strong> ({job.job_ref}).</p>"
        f"<p>We are pleased to invite you to complete a short competency assessment. "
        f"The assessment consists of {len(questions)} questions and should take "
        f"approximately 15–20 minutes.</p>"
        f"<p><a href='{test_url}' style='background:#2563eb;color:white;padding:12px 24px;"
        f"border-radius:6px;text-decoration:none;font-weight:bold'>Begin Assessment</a></p>"
        f"<p style='font-size:12px;color:#666'>If the button does not work, "
        f"copy and paste this link: {test_url}</p>"
    )


# ── JWT helpers ────────────────────────────────────────────────────────────────


def _sign_test_token(application_id: uuid.UUID) -> str:
    """Sign a JWT for the public competency test link."""
    payload = {
        "sub": str(application_id),
        "purpose": "competency_test",
        "iat": int(time.time()),
    }
    return jwt.encode(payload, settings.encryption_key, algorithm=_JWT_ALGORITHM)


def _sign_interview_token(application_id: uuid.UUID) -> str:
    """Sign a one-time JWT for the hiring manager interview invitation link."""
    from datetime import timedelta
    payload = {
        "sub": str(application_id),
        "purpose": "interview_invite",
        "exp": datetime.now(timezone.utc) + timedelta(days=7),
        "iat": int(time.time()),
    }
    return jwt.encode(payload, settings.encryption_key, algorithm=_JWT_ALGORITHM)


# ── DB helpers ─────────────────────────────────────────────────────────────────


async def _get_active_tenants(db: AsyncSession) -> list[Tenant]:
    """Return all active tenants."""
    result = await db.execute(
        select(Tenant).where(Tenant.is_active.is_(True))
    )
    return list(result.scalars().all())


async def _get_application(
    db: AsyncSession, application_id: uuid.UUID, tenant_id: uuid.UUID
) -> Application | None:
    result = await db.execute(
        select(Application).where(
            Application.id == application_id,
            Application.tenant_id == tenant_id,
        )
    )
    return result.scalar_one_or_none()


async def _get_job(
    db: AsyncSession, job_id: uuid.UUID, tenant_id: uuid.UUID
) -> Job | None:
    result = await db.execute(
        select(Job).where(Job.id == job_id, Job.tenant_id == tenant_id)
    )
    return result.scalar_one_or_none()


async def _get_job_by_ref(
    db: AsyncSession, job_ref: str, tenant_id: uuid.UUID
) -> Job | None:
    result = await db.execute(
        select(Job).where(Job.job_ref == job_ref, Job.tenant_id == tenant_id)
    )
    return result.scalar_one_or_none()


async def _get_tenant(db: AsyncSession, tenant_id: uuid.UUID) -> Tenant | None:
    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    return result.scalar_one_or_none()


async def _find_duplicate(
    db: AsyncSession, message_id: str, tenant_id: uuid.UUID
) -> Application | None:
    """Return existing application with same Message-ID, or None."""
    result = await db.execute(
        select(Application).where(
            Application.email_message_id == message_id,
            Application.tenant_id == tenant_id,
        )
    )
    return result.scalar_one_or_none()


async def _find_candidate_by_email(
    db: AsyncSession, email: str, job_id: uuid.UUID, tenant_id: uuid.UUID
) -> uuid.UUID | None:
    """Return candidate_id if a Scout candidate with this email exists for this job."""
    result = await db.execute(
        select(Candidate.id).where(
            Candidate.email == email,
            Candidate.job_id == job_id,
            Candidate.tenant_id == tenant_id,
        )
    )
    row = result.scalar_one_or_none()
    return row if row else None


# ── Permanent failure helper ───────────────────────────────────────────────────


async def _emit_app_permanent_failure(
    application_id: uuid.UUID,
    tenant_id: uuid.UUID,
    task_name: str,
    error: str,
) -> None:
    try:
        async with AsyncSessionLocal() as db:
            app = await _get_application(db, application_id, tenant_id)
            if not app:
                return
            audit = AuditTrailService(db, tenant_id)
            await audit.emit(
                job_id=app.job_id,
                application_id=application_id,
                event_type="system.task_failed_permanent",
                event_category="system",
                severity="error",
                actor="system",
                summary=f"{task_name} permanently failed for application {application_id}",
                detail={"error": error, "task": task_name},
            )
    except Exception:
        logger.exception(
            "Failed to emit permanent failure event for application %s", application_id
        )


# ── Misc helpers ───────────────────────────────────────────────────────────────


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    va, vb = np.array(a, dtype=np.float32), np.array(b, dtype=np.float32)
    norm_a = float(np.linalg.norm(va))
    norm_b = float(np.linalg.norm(vb))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return float(np.dot(va, vb) / (norm_a * norm_b))


def _build_transcript(test_answers: dict[str, Any]) -> str:
    """Serialize full_conversation into a readable transcript string."""
    lines = []
    for turn in test_answers.get("full_conversation", []):
        role = turn.get("role", "").capitalize()
        content = turn.get("content", "")
        lines.append(f"{role}: {content}")
    if not lines:
        # Fall back to answers list
        for entry in test_answers.get("answers", []):
            lines.append(f"Examiner: {entry.get('question', '')}")
            lines.append(f"Candidate: {entry.get('answer', '')}")
    return "\n".join(lines)


def _build_job_spec_text(job: Job) -> str:
    """Compact job spec for AI prompts."""
    skills = ", ".join(job.required_skills or [])
    return (
        f"Title: {job.title}\n"
        f"Job Type: {job.job_type or ''}\n"
        f"Experience: {job.experience_years or 0}+ years\n"
        f"Required Skills: {skills}\n"
        f"Description: {(job.description or '')[:500]}\n"
    )
