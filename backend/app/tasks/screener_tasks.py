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
import secrets
import time
import uuid
from datetime import datetime, timedelta, timezone
from email.header import decode_header
from typing import Any

import numpy as np
import pdfplumber
from docx import Document
from jose import jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import AsyncTaskSessionLocal as AsyncSessionLocal
from app.models.application import Application
from app.models.candidate import Candidate
from app.models.job import Job
from app.models.tenant import Tenant
from app.models.test_session import TestSession
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
_QUESTION_GEN_SYSTEM = (
    "You are a technical interviewer. Return only a valid JSON array of interview questions."
)
_QUESTION_GEN_PROMPT = """\
You are an expert technical interviewer.
Generate exactly {count} different competency interview questions for this role:

Role: {job_type}
Required Skills: {skills}
Experience Required: {years}+ years

Requirements:
- Each question must be completely different
- Questions should test practical knowledge and experience
- Mix of technical and situational questions
- No yes/no questions

Return ONLY a valid JSON array with exactly {count} strings:
["Question 1?", "Question 2?", "Question 3?", "Question 4?", "Question 5?"]

Do not include any other text, just the JSON array.
"""


# ── Celery tasks ───────────────────────────────────────────────────────────────


@celery_app.task(bind=True, max_retries=3, name="app.tasks.screener_tasks.poll_mailboxes")
def poll_mailboxes(self) -> None:  # type: ignore[override]
    """Poll IMAP mailboxes for all active tenants.

    Scheduled every 5 minutes (SPEC §14.2).  For each active tenant,
    fetches UNSEEN emails, parses job_ref, extracts resume text and
    embedding, creates Application records, and triggers screen_resume.
    """
    try:
        asyncio.run(_poll_mailboxes_async())
    except Exception as exc:
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
        asyncio.run(_screen_resume_async(application_id, tenant_id))
    except Exception as exc:
        raise self.retry(exc=exc, countdown=2 ** self.request.retries * 30)


@celery_app.task(
    bind=True, max_retries=3, name="app.tasks.screener_tasks.invite_to_test"
)
def invite_to_test(self, application_id: str, tenant_id: str) -> None:
    """Generate AI test questions and send test invitation email (SPEC §8.3).

    Idempotent — only acts when test_status == 'not_started'.
    """
    try:
        asyncio.run(_invite_to_test_async(application_id, tenant_id))
    except Exception as exc:
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
        asyncio.run(_score_test_async(application_id, tenant_id))
    except Exception as exc:
        raise self.retry(exc=exc, countdown=2 ** self.request.retries * 30)


@celery_app.task(
    bind=True, max_retries=3, name="app.tasks.screener_tasks.notify_hiring_manager"
)
def notify_hiring_manager(self, application_id: str, tenant_id: str) -> None:
    """Email the hiring manager with candidate assessment results (SPEC §8.4).

    Includes resume score, test score, and a one-click interview invite link.
    """
    try:
        asyncio.run(_notify_hiring_manager_async(application_id, tenant_id))
    except Exception as exc:
        raise self.retry(exc=exc, countdown=2 ** self.request.retries * 30)


@celery_app.task(
    bind=True, max_retries=3, name="app.tasks.screener_tasks.send_rejection_email"
)
def send_rejection_email(self, application_id: str, tenant_id: str) -> None:
    """Send an AI-generated polite rejection email to the applicant (SPEC §8.5)."""
    try:
        asyncio.run(_send_rejection_email_async(application_id, tenant_id))
    except Exception as exc:
        raise self.retry(exc=exc, countdown=2 ** self.request.retries * 30)


# ── Async implementations ──────────────────────────────────────────────────────


async def _poll_mailboxes_async() -> None:
    """Poll each tenant's own IMAP inbox for new resume emails."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Tenant).where(
                Tenant.email_inbox_host.is_not(None),
                Tenant.email_inbox_user.is_not(None),
                Tenant.email_inbox_password.is_not(None),
                Tenant.email_inbox_port.is_not(None),
            )
        )
        tenants = result.scalars().all()

    logger.warning("poll_mailboxes: found %d tenants with IMAP configured", len(tenants))

    for tenant in tenants:
        logger.warning(
            "poll_mailboxes: polling %s for tenant %s",
            tenant.email_inbox_user, tenant.name,
        )
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
                tenant.id, tenant.email_inbox_user, exc,
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
        logger.warning(
            "screener: job ref '%s' not found — email from %s discarded",
            job_ref,
            sender_email,
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
    if not attachment_bytes or attachment_ext not in ("pdf", "docx", "doc"):
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
    resume_text = resume_text.replace("\x00", "").strip()
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
        embedding = generate_embedding(resume_text, tenant)
    except Exception as exc:
        logger.error("poll_mailboxes: embedding generation failed: %s", exc)
        embedding = None

    print(f"[poll_mailboxes] embedding generated: {embedding is not None}")
    print(f"[poll_mailboxes] about to create application for {sender_email}")
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
    resume_filename = raw.get("attachment_filename") or f"resume.{attachment_ext}"
    app = Application(
        tenant_id=tenant.id,
        job_id=job.id,
        candidate_id=candidate_id,
        applicant_name=sender_name,
        applicant_email=sender_email,
        resume_storage_path=storage_path,
        resume_filename=resume_filename,
        resume_text=resume_text,
        resume_embedding=embedding,
        status="received",
        screening_status="pending",
        test_status="not_started",
        email_message_id=message_id or None,
        gdpr_consent_given=True,
        received_at=datetime.now(timezone.utc),
    )
    db.add(app)
    await db.flush()  # assigns app.id
    print(f"[poll_mailboxes] application created with id: {app.id}")

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

    await db.commit()
    print(f"[poll_mailboxes] application committed successfully")
    # Step 10: Trigger screening task
    print(f"[poll_mailboxes] triggering screen_resume for {app.id}")
    screen_resume.delay(str(app.id), str(tenant.id))


async def _screen_resume_async(application_id: str, tenant_id: str) -> None:
    """Idempotent: skip if screening_status != 'pending'."""
    app_id = uuid.UUID(str(application_id))
    t_id = uuid.UUID(str(tenant_id))
    print(f"screen_resume: starting for application {application_id}")

    async with AsyncSessionLocal() as db:
        app = await _get_application(db, app_id, t_id)
        if not app:
            logger.warning("screen_resume: application %s not found", application_id)
            return
        if app.screening_status != "pending":
            logger.info(
                "screen_resume: application %s already at %r — skipping",
                application_id, app.screening_status,
            )
            return

        job = await _get_job(db, app.job_id, t_id)
        tenant = await _get_tenant(db, t_id)
        if not job or not tenant:
            return

        # Cosine similarity between resume and job spec
        similarity = await _compute_job_similarity(app, job, tenant)

        # AI evaluation
        print(f"screen_resume: running AI screening for application {application_id}")
        t0 = time.time()
        result = await _run_ai_screening(app, job, tenant)
        duration_ms = int((time.time() - t0) * 1000)

        score = int(result.get("score", 0))
        reasoning = result.get("reasoning", "")
        recommended = result.get("recommended_action", "fail")
        passed = score >= job.minimum_score

        # Primary fields (spec §8.2)
        app.resume_score = score
        app.resume_reasoning = reasoning
        app.resume_strengths = result.get("strengths", [])
        app.resume_gaps = result.get("gaps", [])
        app.status = "screened_passed" if passed else "screened_failed"
        # Legacy fields — kept for backward compat with existing queries
        app.screening_score = score
        app.screening_reasoning = reasoning
        app.screening_status = "passed" if passed else "failed"
        await db.commit()
        print(f"screen_resume: application {application_id} scored {score}/10 — {'passed' if passed else 'failed'}")

        # Audit in separate transaction (non-fatal)
        event_type = "screener.screening_passed" if passed else "screener.screening_failed"
        try:
            audit = AuditTrailService(db, t_id)
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
            await db.commit()
        except Exception as exc:
            logger.warning("screen_resume: audit emit failed (non-fatal): %s", exc)
            await db.rollback()

        if passed:
            invite_to_test.delay(str(app.id), str(t_id))
        else:
            send_rejection_email.delay(str(app.id), str(t_id))


async def _invite_to_test_async(application_id: str, tenant_id: str) -> None:
    """Idempotent: skip if test_status != 'not_started'."""
    app_id = uuid.UUID(str(application_id))
    t_id = uuid.UUID(str(tenant_id))
    print(f"invite_to_test: starting for application {application_id}")

    async with AsyncSessionLocal() as db:
        app = await _get_application(db, app_id, t_id)
        if not app:
            logger.warning("invite_to_test: application %s not found", application_id)
            return
        if app.test_status != "not_started":
            logger.info(
                "invite_to_test: application %s already at test_status %r — skipping",
                application_id, app.test_status,
            )
            return

        job = await _get_job(db, app.job_id, t_id)
        tenant = await _get_tenant(db, t_id)
        if not job or not tenant:
            return

        # Generate questions via AI
        questions = await _generate_test_questions(job, tenant)
        if job.custom_interview_questions:
            questions.extend(job.custom_interview_questions)

        # Generate secure token for the test session
        token = secrets.token_urlsafe(32)
        expires_at = datetime.now(timezone.utc) + timedelta(days=7)
        test_url = f"{settings.frontend_url}/test/{application_id}/{token}"

        # Create TestSession record
        test_session = TestSession(
            tenant_id=app.tenant_id,
            application_id=app.id,
            job_id=app.job_id,
            token=token,
            token_expires_at=expires_at,
            questions=questions,
            interview_type=job.interview_type,
            status="pending",
        )
        db.add(test_session)

        # Update application
        app.status = "test_invited"
        app.test_status = "invited"
        app.interview_invite_token = token
        app.interview_invite_expires_at = expires_at
        app.test_answers = {
            "questions": questions,
            "current_question_idx": 0,
            "answers": [],
            "full_conversation": [],
        }

        interview_type = job.interview_type or "text"

        prep_map = {
            "text": "This is a written assessment. You will answer questions by typing your responses.",
            "audio": "This is an audio assessment. <strong>You will need a microphone.</strong> Please ensure you are in a quiet environment before starting.",
            "video": "This is a video assessment. <strong>You will need a webcam and microphone.</strong> Please ensure you have good lighting and a quiet environment.",
            "audio_video": "This is a video interview. <strong>You will need a webcam and microphone.</strong> Please ensure you have good lighting, a quiet environment, and a professional background.",
        }
        prep_instructions = prep_map.get(interview_type, prep_map["text"])

        subject_map = {
            "text": f"Assessment Invitation — {job.title}",
            "audio": f"Audio Assessment Invitation — {job.title}",
            "video": f"Video Assessment Invitation — {job.title}",
            "audio_video": f"Video Interview Invitation — {job.title}",
        }
        subject = subject_map.get(interview_type, subject_map["text"])

        await send_email(
            to=app.applicant_email,
            subject=subject,
            html_body=_test_invitation_html(app, job, questions, test_url, prep_instructions),
            tenant=tenant,
        )

        await db.commit()
        print(f"invite_to_test: invitation sent to {app.applicant_email} ({len(questions)} questions)")

        # Audit in separate transaction (non-fatal)
        try:
            audit = AuditTrailService(db, t_id)
            await audit.emit(
                job_id=job.id, application_id=app.id,
                candidate_id=app.candidate_id,
                event_type="screener.test_invited",
                event_category="resume_screener", severity="success",
                actor="system",
                summary=f"Test invitation sent to {app.applicant_name} ({len(questions)} questions)",
                detail={"applicant_email": app.applicant_email, "question_count": len(questions)},
            )
            await db.commit()
        except Exception as exc:
            logger.warning("invite_to_test: audit emit failed (non-fatal): %s", exc)
            await db.rollback()


async def _score_test_async(application_id: str, tenant_id: str) -> None:
    """Idempotent: skip if test already scored (test_score is set)."""
    app_id = uuid.UUID(str(application_id))
    t_id = uuid.UUID(str(tenant_id))
    print(f"score_test: starting for application {application_id}")

    async with AsyncSessionLocal() as db:
        app = await _get_application(db, app_id, t_id)
        if not app:
            logger.warning("score_test: application %s not found", application_id)
            return
        # Already scored — idempotent
        if app.test_score is not None:
            logger.info("score_test: application %s already scored — skipping", application_id)
            return
        # Not yet complete — too early to score
        if app.test_status not in ("completed",):
            logger.info(
                "score_test: application %s at test_status %r — not yet complete, skipping",
                application_id, app.test_status,
            )
            return

        job = await _get_job(db, app.job_id, t_id)
        tenant = await _get_tenant(db, t_id)
        if not job or not tenant:
            return

        # Load test session (prefer TestSession record over test_answers dict)
        ts_result = await db.execute(
            select(TestSession).where(
                TestSession.application_id == app.id,
                TestSession.tenant_id == t_id,
            ).limit(1)
        )
        test_session = ts_result.scalar_one_or_none()

        # Build Q&A text for scoring
        if test_session:
            questions: list[str] = test_session.questions or []
            raw_answers: list[Any] = test_session.answers or []
        else:
            # Fall back to test_answers dict (legacy flow)
            questions = (app.test_answers or {}).get("questions", [])
            raw_answers = (app.test_answers or {}).get("answers", [])

        qa_text = ""
        for i, q in enumerate(questions):
            if i < len(raw_answers):
                entry = raw_answers[i]
                answer = entry.get("answer", "No answer provided") if isinstance(entry, dict) else str(entry)
            else:
                answer = "No answer provided"
            qa_text += f"\nQ{i + 1}: {q}\nA{i + 1}: {answer}\n"

        scoring_prompt = (
            f"You are an expert interviewer. Evaluate this candidate's responses "
            f"for the role of {job.title}.\n\n"
            f"Required Skills: {', '.join(job.required_skills or [])}\n"
            f"Experience Required: {job.experience_years or 0}+ years\n\n"
            f"Interview Q&A:\n{qa_text}\n\n"
            "Return ONLY valid JSON:\n"
            '{"overall_score": N, "overall_summary": "2-3 sentence overall assessment", '
            '"recommended_action": "pass" or "fail", '
            '"strengths": ["strength 1", "strength 2"], '
            '"gaps": ["gap 1", "gap 2"], '
            '"questions": [{"question": "...", "candidate_answer": "...", '
            '"assessment": "Brief assessment", "rating": "strong|adequate|weak", "score": N}]}'
        )

        print(f"score_test: running AI scoring for application {application_id}")
        t0 = time.time()
        ai = AIProvider(tenant)
        evaluation = await ai.complete_json(
            prompt=scoring_prompt,
            system="You are an expert technical interviewer providing detailed candidate evaluation.",
            max_tokens=2000,
        )
        duration_ms = int((time.time() - t0) * 1000)

        overall_score = int(evaluation.get("overall_score", 0))
        recommended = evaluation.get("recommended_action", "fail")
        passed = overall_score >= job.minimum_score and recommended != "fail"

        app.test_score = overall_score
        app.test_evaluation = evaluation
        app.test_completed_at = app.test_completed_at or datetime.now(timezone.utc)
        app.test_status = "passed" if passed else "failed"
        app.status = "test_passed" if passed else "test_failed"

        if test_session:
            test_session.status = "completed"
            test_session.completed_at = datetime.now(timezone.utc)

        await db.commit()
        print(f"score_test: application {application_id} scored {overall_score}/10 — {'passed' if passed else 'failed'}")

        # Audit in separate transaction (non-fatal)
        event_type = "screener.test_scored" if passed else "screener.test_score_failed"
        try:
            audit = AuditTrailService(db, t_id)
            await audit.emit(
                job_id=job.id, application_id=app.id,
                candidate_id=app.candidate_id,
                event_type=event_type,
                event_category="resume_screener",
                severity="success" if passed else "info",
                actor="system",
                summary=f"Test scored {overall_score}/10 — {'passed' if passed else 'failed'}",
                detail={
                    "overall_score": overall_score,
                    "overall_summary": evaluation.get("overall_summary", ""),
                    "strengths": evaluation.get("strengths", []),
                    "gaps": evaluation.get("gaps", []),
                },
                duration_ms=duration_ms,
            )
            await db.commit()
        except Exception as exc:
            logger.warning("score_test: audit emit failed (non-fatal): %s", exc)
            await db.rollback()

        if passed:
            notify_hiring_manager.delay(str(app.id), str(t_id))
        else:
            send_rejection_email.delay(str(app.id), str(t_id))


async def _notify_hiring_manager_async(application_id: str, tenant_id: str) -> None:
    """Email the hiring manager with full candidate assessment results."""
    app_id = uuid.UUID(str(application_id))
    t_id = uuid.UUID(str(tenant_id))

    async with AsyncSessionLocal() as db:
        app = await _get_application(db, app_id, t_id)
        if not app:
            logger.warning("notify_hiring_manager: application %s not found", application_id)
            return

        job = await _get_job(db, app.job_id, t_id)
        tenant = await _get_tenant(db, t_id)
        if not job or not tenant:
            return

        hm_email = job.hiring_manager_email or tenant.main_contact_email
        if not hm_email:
            logger.warning("notify_hiring_manager: no HM email for job %s", job.id)
            return

        # Generate interview invite token (simple secure token stored in DB)
        hm_token = secrets.token_urlsafe(32)
        hm_token_expires = datetime.now(timezone.utc) + timedelta(days=7)
        app.interview_invite_token = hm_token
        app.interview_invite_expires_at = hm_token_expires
        app.status = "hm_notified"
        await db.commit()

        invite_url = (
            f"{settings.backend_url}/api/v1/actions/invite/{application_id}/{hm_token}"
        )
        dashboard_url = (
            f"{settings.frontend_url}/applications/{application_id}"
        )

        # Build scores section
        scores_html = ""

        # Talent Scout score (Mode 1 only — when application came via Scout)
        if app.candidate_id:
            cand_result = await db.execute(
                select(Candidate).where(
                    Candidate.id == app.candidate_id,
                    Candidate.tenant_id == t_id,
                ).limit(1)
            )
            candidate = cand_result.scalar_one_or_none()
            if candidate and candidate.suitability_score:
                scores_html += (
                    f"<div style='background:#f8f9fa;padding:16px;border-radius:8px;margin:12px 0'>"
                    f"<h4 style='margin:0 0 8px'>🤖 AI Scout Score: {candidate.suitability_score}/10</h4>"
                    f"<p style='margin:0;color:#666'>{candidate.score_reasoning or ''}</p>"
                    f"</div>"
                )

        # Resume score
        if app.resume_score is not None:
            strengths_str = ", ".join(app.resume_strengths or [])
            gaps_str = ", ".join(app.resume_gaps or [])
            scores_html += (
                f"<div style='background:#f8f9fa;padding:16px;border-radius:8px;margin:12px 0'>"
                f"<h4 style='margin:0 0 8px'>📄 Resume Score: {app.resume_score}/10</h4>"
                f"<p style='margin:0;color:#666'>{app.resume_reasoning or ''}</p>"
                f"<p style='margin:8px 0 0'><strong>Strengths:</strong> {strengths_str}</p>"
                f"<p style='margin:4px 0 0'><strong>Gaps:</strong> {gaps_str}</p>"
                f"</div>"
            )

        # Test score
        evaluation: dict[str, Any] = app.test_evaluation or {}
        if app.test_score is not None:
            test_strengths = ", ".join(evaluation.get("strengths", []))
            test_gaps = ", ".join(evaluation.get("gaps", []))
            scores_html += (
                f"<div style='background:#f8f9fa;padding:16px;border-radius:8px;margin:12px 0'>"
                f"<h4 style='margin:0 0 8px'>🎤 Interview Score: {app.test_score}/10</h4>"
                f"<p style='margin:0;color:#666'>{evaluation.get('overall_summary', '')}</p>"
                f"<p style='margin:8px 0 0'><strong>Strengths:</strong> {test_strengths}</p>"
                f"<p style='margin:4px 0 0'><strong>Gaps:</strong> {test_gaps}</p>"
                f"</div>"
            )

        html_body = (
            f"<div style='font-family:sans-serif;max-width:600px;margin:0 auto'>"
            f"<h2>New Shortlisted Candidate: {app.applicant_name}</h2>"
            f"<p>A candidate has completed all screening stages for "
            f"<strong>{job.title}</strong> and is recommended for interview.</p>"
            f"<h3>Candidate Details</h3>"
            f"<p><strong>Name:</strong> {app.applicant_name}</p>"
            f"<p><strong>Email:</strong> {app.applicant_email}</p>"
            f"<h3>Assessment Results</h3>"
            f"{scores_html}"
            f"<div style='text-align:center;margin:32px 0'>"
            f"<a href='{invite_url}'"
            f"   style='background:#22c55e;color:white;padding:14px 28px;"
            f"text-decoration:none;border-radius:6px;font-weight:bold;margin-right:12px'>"
            f"✓ Invite to Interview</a>"
            f"<a href='{dashboard_url}'"
            f"   style='background:#1B6CA8;color:white;padding:14px 28px;"
            f"text-decoration:none;border-radius:6px;font-weight:bold'>"
            f"View Full Report</a>"
            f"</div>"
            f"<p style='color:#666;font-size:12px'>"
            f"The invite link expires on {hm_token_expires.strftime('%d %B %Y')}.</p>"
            f"</div>"
        )

        await send_email(
            to=hm_email,
            subject=f"Shortlisted: {app.applicant_name} for {job.title}",
            html_body=html_body,
            tenant=tenant,
        )

        # Audit (non-fatal)
        try:
            audit = AuditTrailService(db, t_id)
            await audit.emit(
                job_id=job.id, application_id=app.id,
                candidate_id=app.candidate_id,
                event_type="screener.hm_notified",
                event_category="resume_screener",
                severity="success",
                actor="system",
                summary=f"Hiring manager notified: {app.applicant_name} recommended for interview",
                detail={"hm_email": hm_email},
            )
            await db.commit()
        except Exception as exc:
            logger.warning("notify_hiring_manager: audit failed (non-fatal): %s", exc)
            await db.rollback()

        print(f"notify_hiring_manager: notified {hm_email} for application {application_id}")


async def _send_rejection_email_async(application_id: str, tenant_id: str) -> None:
    """Generate and send an AI-personalised rejection email."""
    app_id = uuid.UUID(str(application_id))
    t_id = uuid.UUID(str(tenant_id))

    async with AsyncSessionLocal() as db:
        app = await _get_application(db, app_id, t_id)
        if not app:
            logger.warning("send_rejection_email: application %s not found", application_id)
            return
        if app.status == "rejected":
            logger.info("send_rejection_email: already rejected — skipping %s", application_id)
            return

        job = await _get_job(db, app.job_id, t_id)
        tenant = await _get_tenant(db, t_id)
        if not job or not tenant:
            return

        # Generate personalised rejection via AI
        try:
            ai = AIProvider(tenant)
            rejection_text = await ai.complete(
                prompt=(
                    f"Write a polite, professional rejection email for:\n"
                    f"Candidate: {app.applicant_name}\n"
                    f"Role: {job.title}\n"
                    f"Company: {tenant.name}\n\n"
                    "The email should:\n"
                    "- Thank them for their application\n"
                    "- Politely decline\n"
                    "- Encourage future applications\n"
                    "- Be warm and professional\n"
                    "- Maximum 150 words\n"
                    "- Do not mention specific scores or reasons\n"
                    "- Do not use placeholder text like [Your Name] or [Your Position]\n"
                    f"- Sign off with: {tenant.main_contact_name or 'The Recruitment Team'}, {tenant.name}"
                ),
                system="You are a professional HR manager writing rejection emails.",
                max_tokens=300,
            )
        except Exception as exc:
            logger.warning("send_rejection_email: AI generation failed, using template: %s", exc)
            rejection_text = (
                f"Dear {app.applicant_name},\n\n"
                f"Thank you for your interest in the {job.title} role at {tenant.name} "
                "and for taking the time to submit your application.\n\n"
                "After careful consideration, we regret to inform you that we will not "
                "be progressing your application at this time. We appreciate your interest "
                "and wish you every success in your job search.\n\n"
                "Kind regards,\nThe Recruitment Team"
            )

        html_body = (
            f"<div style='font-family:sans-serif;max-width:600px;margin:0 auto'>"
            f"{rejection_text.replace(chr(10), '<br>')}"
            f"<br><br>"
            f"<p style='color:#666;font-size:12px'>"
            f"{tenant.name} | {tenant.main_contact_email or ''}</p>"
            f"</div>"
        )

        await send_email(
            to=app.applicant_email,
            subject=f"Your application for {job.title} at {tenant.name}",
            html_body=html_body,
            tenant=tenant,
        )

        app.status = "rejected"
        await db.commit()

        # Audit (non-fatal)
        try:
            audit = AuditTrailService(db, t_id)
            await audit.emit(
                job_id=job.id, application_id=app.id,
                event_type="screener.rejection_email_sent",
                event_category="resume_screener", severity="info",
                actor="system",
                summary=f"Rejection email sent to {app.applicant_email}",
            )
            await db.commit()
        except Exception as exc:
            logger.warning("send_rejection_email: audit failed (non-fatal): %s", exc)
            await db.rollback()

        print(f"send_rejection_email: sent to {app.applicant_email} for application {application_id}")


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
            logger.warning(f"IMAP: logged in successfully to {host}")
            M.select("INBOX")
            _, nums = M.search(None, "UNSEEN")
            email_ids = nums[0].split()
            logger.warning(f"IMAP: search returned {len(email_ids)} unseen emails")
            for i, num in enumerate(email_ids):
                logger.warning(f"IMAP: processing email {i+1} of {len(email_ids)}")
                _, data = M.fetch(num, "(RFC822)")
                raw_bytes = data[0][1] if data and data[0] else None
                if not raw_bytes:
                    continue
                parsed = _parse_raw_email(raw_bytes)
                if parsed:
                    subject = parsed.get("subject", "")
                    job_ref = _extract_job_ref(subject)
                    logger.warning(f"IMAP: subject='{subject}', job_ref='{job_ref}'")
                    attachment = parsed.get("attachment_bytes")
                    filename = f"{parsed.get('attachment_ext', '')}" if attachment else ""
                    logger.warning(f"IMAP: attachment found={bool(attachment)}, filename={filename}")
                    results.append(parsed)
                    # Mark as read so we don't process twice
                    M.store(num, "+FLAGS", "\\Seen")
    except Exception as exc:
        logger.error("IMAP error for tenant %s: %s", tenant.id, exc)
    return results




def _get_imap_credentials(tenant: Tenant) -> tuple[str, int, str, str]:
    """Return (host, port, user, password) for a tenant's custom mailbox."""
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


def _parse_raw_email(raw_bytes: bytes) -> dict[str, Any] | None:
    """Parse raw RFC822 bytes into a structured dict."""
    msg = email_lib.message_from_bytes(raw_bytes)
    subject = _decode_header_value(msg.get("Subject", ""))
    message_id = msg.get("Message-ID", "").strip()
    from_header = _decode_header_value(msg.get("From", ""))
    sender_name, sender_email = email_lib.utils.parseaddr(from_header)

    attachment_bytes: bytes | None = None
    attachment_ext = ""
    attachment_filename = ""

    for part in msg.walk():
        ct = part.get_content_type()
        filename = part.get_filename() or ""
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

        # Accept PDF, DOCX, or DOC regardless of Content-Disposition
        if ext in ("pdf", "docx", "doc") and filename:
            payload = part.get_payload(decode=True)
            if payload:
                attachment_bytes = payload
                attachment_ext = ext
                attachment_filename = filename
                break

        # Also check content-type directly
        if ct in (
            "application/pdf",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/msword",
            "application/vnd.ms-word",
        ):
            payload = part.get_payload(decode=True)
            if payload:
                attachment_bytes = payload
                if ct == "application/pdf":
                    attachment_ext = "pdf"
                elif ct in ("application/msword", "application/vnd.ms-word"):
                    attachment_ext = "doc"
                else:
                    attachment_ext = "docx"
                attachment_filename = filename or f"resume.{attachment_ext}"
                break

    return {
        "subject": subject,
        "message_id": message_id,
        "sender_name": sender_name.strip() or sender_email,
        "sender_email": sender_email.lower().strip(),
        "attachment_bytes": attachment_bytes,
        "attachment_ext": attachment_ext,
        "attachment_filename": attachment_filename,
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
    """Extract plain text from PDF, DOCX, or DOC bytes."""
    try:
        if ext == "pdf":
            with pdfplumber.open(io.BytesIO(data)) as pdf:
                return "\n".join(p.extract_text() or "" for p in pdf.pages).strip()
        if ext == "docx":
            doc = Document(io.BytesIO(data))
            return "\n".join(para.text for para in doc.paragraphs).strip()
        if ext == "doc":
            import docx2txt
            import os
            import tempfile
            with tempfile.NamedTemporaryFile(suffix=".doc", delete=False) as f:
                f.write(data)
                tmp_path = f.name
            try:
                text = docx2txt.process(tmp_path)
                return (text or "").strip()
            except Exception:
                # Last resort: decode stripping null bytes
                return data.decode("utf-8", errors="ignore").replace("\x00", "")
            finally:
                os.unlink(tmp_path)
    except Exception as exc:
        logger.error("Text extraction failed (%s): %s", ext, exc)
    return ""


def _extract_job_ref(subject: str) -> str | None:
    """Extract 8-char alphanumeric job_ref from email subject."""
    match = re.search(r"\b([A-Z0-9]{8})\b", subject.upper())
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
        job_embedding = generate_embedding(job_spec, tenant)
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
    job_type = job.job_type or job.title
    years = job.experience_years or 0
    prompt = _QUESTION_GEN_PROMPT.format(
        count=count,
        job_type=job_type,
        years=years,
        skills=skills,
    )
    try:
        ai = AIProvider(tenant)
        raw = await ai.complete(prompt=prompt, system=_QUESTION_GEN_SYSTEM, max_tokens=800)
        text = raw.strip()
        if "```" in text:
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        text = text.strip()
        questions = json.loads(text)
        if isinstance(questions, list) and len(questions) > 0:
            return [str(q) for q in questions[:count]]
    except Exception as exc:
        logger.warning("question generation failed: %s, raw: %.200s", exc, locals().get("raw", ""))
    first_skill = skills.split(",")[0].strip() if skills else "this technology"
    return [
        f"Describe your experience with {first_skill}.",
        f"Tell me about a challenging project you worked on as a {job_type}.",
        "How do you approach debugging complex issues in your work?",
        "Describe a situation where you had to learn a new technology quickly.",
        "How do you ensure code quality in your projects?",
    ][:count]


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
    db: AsyncSession,
    tenant_id: uuid.UUID,
) -> None:
    """Email the hiring manager with candidate results and invite-interview link."""
    if not job.hiring_manager_email:
        return

    invite_token = _sign_interview_token(app.id)
    invite_url = (
        f"{settings.backend_url}/api/v1/actions/invite/{app.id}/{invite_token}"
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
    print(f"score_test: hiring manager notified for application {app.id}")

    # Audit in separate transaction (non-fatal)
    try:
        audit = AuditTrailService(db, tenant_id)
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
        await db.commit()
    except Exception as exc:
        logger.warning("score_test: hm_notified audit failed (non-fatal): %s", exc)
        await db.rollback()


def _test_invitation_html(
    app: Application, job: Job, questions: list[str], test_url: str,
    prep_instructions: str = "This is a written assessment. You will answer questions by typing your responses.",
) -> str:
    """Build HTML body for the test invitation email."""
    return (
        f"<p>Dear {app.applicant_name},</p>"
        f"<p>Thank you for applying for <strong>{job.title}</strong> ({job.job_ref}).</p>"
        f"<p>We are pleased to invite you to complete a short competency assessment. "
        f"The assessment consists of {len(questions)} questions and should take "
        f"approximately 15–20 minutes.</p>"
        f"<div style='background:#f0f9ff;border:1px solid #00C2E0;"
        f"border-radius:8px;padding:16px;margin:16px 0'>"
        f"<strong>📋 Assessment Format:</strong><br>"
        f"{prep_instructions}"
        f"</div>"
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




async def _get_application(
    db: AsyncSession, application_id: uuid.UUID, tenant_id: uuid.UUID
) -> Application | None:
    result = await db.execute(
        select(Application).where(
            Application.id == application_id,
            Application.tenant_id == tenant_id,
        ).limit(1)
    )
    return result.scalar_one_or_none()


async def _get_job(
    db: AsyncSession, job_id: uuid.UUID, tenant_id: uuid.UUID
) -> Job | None:
    result = await db.execute(
        select(Job).where(Job.id == job_id, Job.tenant_id == tenant_id).limit(1)
    )
    return result.scalar_one_or_none()


async def _get_job_by_ref(
    db: AsyncSession, job_ref: str, tenant_id: uuid.UUID
) -> Job | None:
    result = await db.execute(
        select(Job).where(Job.job_ref == job_ref, Job.tenant_id == tenant_id).limit(1)
    )
    return result.scalar_one_or_none()


async def _get_tenant(db: AsyncSession, tenant_id: uuid.UUID) -> Tenant | None:
    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id).limit(1))
    return result.scalar_one_or_none()


async def _find_duplicate(
    db: AsyncSession, message_id: str, tenant_id: uuid.UUID
) -> Application | None:
    """Return existing application with same Message-ID, or None."""
    result = await db.execute(
        select(Application).where(
            Application.email_message_id == message_id,
            Application.tenant_id == tenant_id,
        ).limit(1)
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
        ).limit(1)
    )
    row = result.scalar_one_or_none()
    return row if row else None


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

# ── Public aliases for testing ─────────────────────────────────────────────────
# Tests import these names; they map to the async implementations above.
_screen_resume_impl = _screen_resume_async
_invite_to_test_impl = _invite_to_test_async
_score_test_impl = _score_test_async
_poll_mailboxes_impl = _poll_mailboxes_async
