"""Celery tasks for the AI Talent Scout pipeline.

Task chain per candidate (SPEC §14.1):
  discover_candidates  →  enrich_profile  →  score_candidate
                                           →  discover_email
                                           →  send_outreach

All tasks:
- Are idempotent (check current status before acting).
- Have max_retries=3 with exponential backoff (30s, 60s, 120s).
- Emit audit events on both success and failure (SPEC §15.2).
- Filter every DB query by tenant_id (guidelines §2).
- Never call AI SDKs directly — always go through AIProvider facade (guidelines §5).
"""

import asyncio
import json
import logging
import re
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from celery import chain
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import AsyncSessionLocal
from app.models.candidate import Candidate
from app.models.job import Job
from app.models.tenant import Tenant
from app.services import apollo, brightdata, hunter, scrapingdog, snov
from app.services.ai_provider import AIProvider
from app.services.audit_trail import AuditTrailService
from app.services.crypto import decrypt
from app.services.email_deduction import EmailDeductionService
from app.services.sendgrid_email import send_email
from app.services.talent_scout import TalentScoutService, _build_location_list, _build_title_list
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)

_DEFAULT_OUTREACH_SYSTEM_PROMPT = (
    "You are a professional recruiter writing to a passive candidate. "
    "Write a concise, friendly, and genuinely personalised email (max 200 words) "
    "that references specific details from the candidate's current role and experience. "
    "Do not sound like a mass email. Highlight why this specific opportunity is relevant "
    "to their career. Include the job reference and application instructions. "
    "Sign off with the recruiter's name. "
    'Return ONLY valid JSON: {"subject": "...", "body": "..."}'
)

_SCORING_PROMPT_TEMPLATE = (
    "You are an expert recruiter. Given the following job specification and candidate "
    "LinkedIn profile, score the candidate's suitability from 1 to 10. "
    "Return ONLY valid JSON.\n"
    "Job Spec: {job_spec}\n"
    "Candidate Profile: {profile}\n"
    'Respond with: {{"score": N, "reasoning": "...", "strengths": [...], "gaps": [...]}}'
)


# ── Task 1: Candidate Discovery ────────────────────────────────────────────────


@celery_app.task(bind=True, max_retries=3, name="app.tasks.talent_scout_tasks.discover_candidates")
def discover_candidates(self, job_id: str, tenant_id: str) -> None:
    """Discover candidates via SERP API for all title × location combinations.

    Creates Candidate records, deduplicates by linkedin_url per job, then fans
    out a processing chain (tasks 2–5) per newly discovered candidate.
    """
    try:
        asyncio.run(_discover_candidates_impl(uuid.UUID(job_id), uuid.UUID(tenant_id)))
    except Exception as exc:
        if self.request.retries >= self.max_retries:
            asyncio.run(
                _emit_job_permanent_failure(
                    uuid.UUID(job_id), uuid.UUID(tenant_id), "discover_candidates", str(exc)
                )
            )
            return
        raise self.retry(exc=exc, countdown=2 ** self.request.retries * 30)


# ── Task 2: Profile Enrichment ─────────────────────────────────────────────────


@celery_app.task(bind=True, max_retries=3, name="app.tasks.talent_scout_tasks.enrich_profile")
def enrich_profile(self, candidate_id: str, tenant_id: str) -> None:
    """Fetch the candidate's public LinkedIn profile via BrightData."""
    try:
        asyncio.run(_enrich_profile_impl(uuid.UUID(candidate_id), uuid.UUID(tenant_id)))
    except Exception as exc:
        if self.request.retries >= self.max_retries:
            asyncio.run(
                _emit_candidate_permanent_failure(
                    uuid.UUID(candidate_id), uuid.UUID(tenant_id), "enrich_profile", str(exc)
                )
            )
            return
        raise self.retry(exc=exc, countdown=2 ** self.request.retries * 30)


# ── Task 3: Candidate Scoring ──────────────────────────────────────────────────


@celery_app.task(bind=True, max_retries=3, name="app.tasks.talent_scout_tasks.score_candidate")
def score_candidate(self, candidate_id: str, tenant_id: str) -> None:
    """Score the candidate against the job spec via the AI provider facade."""
    try:
        asyncio.run(_score_candidate_impl(uuid.UUID(candidate_id), uuid.UUID(tenant_id)))
    except Exception as exc:
        if self.request.retries >= self.max_retries:
            asyncio.run(
                _emit_candidate_permanent_failure(
                    uuid.UUID(candidate_id), uuid.UUID(tenant_id), "score_candidate", str(exc)
                )
            )
            return
        raise self.retry(exc=exc, countdown=2 ** self.request.retries * 30)


# ── Task 4: Email Discovery ────────────────────────────────────────────────────


@celery_app.task(bind=True, max_retries=3, name="app.tasks.talent_scout_tasks.discover_email")
def discover_email(self, candidate_id: str, tenant_id: str) -> None:
    """Discover the candidate's email via Apollo/Hunter/Snov + EmailDeductionService."""
    try:
        asyncio.run(_discover_email_impl(uuid.UUID(candidate_id), uuid.UUID(tenant_id)))
    except Exception as exc:
        if self.request.retries >= self.max_retries:
            asyncio.run(
                _emit_candidate_permanent_failure(
                    uuid.UUID(candidate_id), uuid.UUID(tenant_id), "discover_email", str(exc)
                )
            )
            return
        raise self.retry(exc=exc, countdown=2 ** self.request.retries * 30)


# ── Task 5: Email Outreach ─────────────────────────────────────────────────────


@celery_app.task(bind=True, max_retries=3, name="app.tasks.talent_scout_tasks.send_outreach")
def send_outreach(self, candidate_id: str, tenant_id: str) -> None:
    """Generate a hyper-personalised email via AI and send via SendGrid."""
    try:
        asyncio.run(_send_outreach_impl(uuid.UUID(candidate_id), uuid.UUID(tenant_id)))
    except Exception as exc:
        if self.request.retries >= self.max_retries:
            asyncio.run(
                _emit_candidate_permanent_failure(
                    uuid.UUID(candidate_id), uuid.UUID(tenant_id), "send_outreach", str(exc)
                )
            )
            return
        raise self.retry(exc=exc, countdown=2 ** self.request.retries * 30)


# ── Async implementations ──────────────────────────────────────────────────────


async def _discover_candidates_impl(job_id: uuid.UUID, tenant_id: uuid.UUID) -> None:
    """Async body of discover_candidates."""
    async with AsyncSessionLocal() as db:
        job = await _get_job(db, job_id, tenant_id)
        if not job:
            logger.warning("discover_candidates: job %s not found for tenant %s", job_id, tenant_id)
            return

        tenant = await _get_tenant(db, tenant_id)
        if not tenant:
            logger.warning("discover_candidates: tenant %s not found", tenant_id)
            return

        scout = TalentScoutService(db, tenant_id)
        await scout.emit_job_started(job.id, job.title)

        queries = scout.build_search_queries(job)
        titles = _build_title_list(job)
        locations = _build_location_list(job)
        await scout.emit_queries_built(
            job.id, len(queries), len(titles), len(locations) or 0
        )

        api_key = _resolve_scrapingdog_key(tenant)
        if not api_key:
            logger.error("discover_candidates: no ScrapingDog API key for tenant %s", tenant_id)
            await scout.emit_serp_failed(job.id, "No ScrapingDog API key configured", 0)
            return

        # Load existing linkedin_urls to deduplicate within this job
        existing_urls = await _get_existing_linkedin_urls(db, job_id, tenant_id)
        new_candidate_ids: list[str] = []

        for query in queries:
            for page in range(10):  # 10 pages × 10 results = up to 100 per query
                start = page * 10
                t0 = time.time()
                results = await scrapingdog.search_linkedin(query, start, api_key)
                duration_ms = int((time.time() - t0) * 1000)
                await scout.emit_serp_success(job.id, len(results), page, duration_ms)

                for result in results:
                    linkedin_url = result.get("link", "")
                    if not _is_linkedin_profile_url(linkedin_url):
                        continue

                    if linkedin_url in existing_urls:
                        await scout.emit_candidate_duplicate(job.id, linkedin_url)
                        continue

                    name, title = _parse_linkedin_result(result.get("title", ""))
                    if not name:
                        continue

                    candidate = Candidate(
                        tenant_id=tenant_id,
                        job_id=job_id,
                        name=name,
                        title=title or None,
                        snippet=result.get("snippet") or None,
                        linkedin_url=linkedin_url,
                        status="discovered",
                    )
                    async with db.begin():
                        db.add(candidate)
                        await db.flush()

                    existing_urls.add(linkedin_url)
                    new_candidate_ids.append(str(candidate.id))
                    await scout.emit_candidate_discovered(job.id, candidate.id, name)

        # Fan out processing chain per candidate (tasks 2–5)
        tid = str(tenant_id)
        for cid in new_candidate_ids:
            chain(
                enrich_profile.si(cid, tid),
                score_candidate.si(cid, tid),
                discover_email.si(cid, tid),
                send_outreach.si(cid, tid),
            ).delay()

        await scout.emit_job_completed(job.id, len(new_candidate_ids), 0, 0)


async def _enrich_profile_impl(candidate_id: uuid.UUID, tenant_id: uuid.UUID) -> None:
    """Async body of enrich_profile."""
    async with AsyncSessionLocal() as db:
        candidate = await _get_candidate(db, candidate_id, tenant_id)
        if not candidate:
            logger.warning("enrich_profile: candidate %s not found", candidate_id)
            return

        # Idempotency — skip if already enriched or further in the pipeline
        if candidate.status != "discovered":
            logger.info(
                "enrich_profile: candidate %s already at status %r — skipping",
                candidate_id,
                candidate.status,
            )
            return

        tenant = await _get_tenant(db, tenant_id)
        if not tenant:
            return

        scout = TalentScoutService(db, tenant_id)
        await scout.emit_profile_enrichment_started(candidate.job_id, candidate.id)

        if not candidate.linkedin_url:
            await scout.emit_profile_enrichment_failed(
                candidate.job_id, candidate.id, "No LinkedIn URL", 0
            )
            return

        api_key = _resolve_brightdata_key(tenant)
        if not api_key:
            raise RuntimeError(f"No BrightData API key for tenant {tenant_id}")

        t0 = time.time()
        profile = await brightdata.get_linkedin_profile(candidate.linkedin_url, api_key)
        duration_ms = int((time.time() - t0) * 1000)

        if not profile:
            async with db.begin():
                candidate.status = "profiled"  # advance so chain can check
                candidate.brightdata_profile = {}
                await db.flush()
            await scout.emit_profile_enrichment_failed(
                candidate.job_id, candidate.id, "Empty profile returned", duration_ms
            )
            return

        # Extract company + location from profile if available
        company = (
            profile.get("current_company")
            or profile.get("company")
            or (profile.get("positions") or [{}])[0].get("company_name")
            or candidate.company
        )
        location = profile.get("location") or candidate.location

        async with db.begin():
            candidate.brightdata_profile = profile
            candidate.status = "profiled"
            if company:
                candidate.company = str(company)
            if location:
                candidate.location = str(location)
            await db.flush()

        await scout.emit_profile_enrichment_success(
            candidate.job_id, candidate.id, profile, duration_ms
        )


async def _score_candidate_impl(candidate_id: uuid.UUID, tenant_id: uuid.UUID) -> None:
    """Async body of score_candidate."""
    async with AsyncSessionLocal() as db:
        candidate = await _get_candidate(db, candidate_id, tenant_id)
        if not candidate:
            logger.warning("score_candidate: candidate %s not found", candidate_id)
            return

        # Idempotency — only score candidates that have been profiled
        if candidate.status != "profiled":
            logger.info(
                "score_candidate: candidate %s at status %r — skipping",
                candidate_id,
                candidate.status,
            )
            return

        # Cannot score without a profile
        if not candidate.brightdata_profile:
            logger.info(
                "score_candidate: candidate %s has empty profile — skipping",
                candidate_id,
            )
            return

        job = await _get_job(db, candidate.job_id, tenant_id)
        if not job:
            logger.warning("score_candidate: job %s not found", candidate.job_id)
            return

        tenant = await _get_tenant(db, tenant_id)
        if not tenant:
            return

        scout = TalentScoutService(db, tenant_id)
        await scout.emit_scoring_started(job.id, candidate.id)

        job_spec = _build_job_spec_text(job)
        profile_text = json.dumps(candidate.brightdata_profile)
        prompt = _SCORING_PROMPT_TEMPLATE.format(
            job_spec=job_spec, profile=profile_text
        )

        t0 = time.time()
        try:
            ai = AIProvider(tenant)
            result = await ai.complete_json(prompt=prompt, max_tokens=512)
        except Exception as exc:
            duration_ms = int((time.time() - t0) * 1000)
            await scout.emit_scoring_error(job.id, candidate.id, str(exc), duration_ms)
            raise  # propagate to trigger task retry

        duration_ms = int((time.time() - t0) * 1000)

        score = int(result.get("score", 0))
        reasoning = result.get("reasoning", "")
        passed = score >= job.minimum_score

        async with db.begin():
            candidate.suitability_score = score
            candidate.score_reasoning = reasoning
            candidate.status = "passed" if passed else "failed"
            await db.flush()

        await scout.emit_scoring_success(job.id, candidate.id, score, passed, duration_ms)


async def _discover_email_impl(candidate_id: uuid.UUID, tenant_id: uuid.UUID) -> None:
    """Async body of discover_email."""
    async with AsyncSessionLocal() as db:
        candidate = await _get_candidate(db, candidate_id, tenant_id)
        if not candidate:
            logger.warning("discover_email: candidate %s not found", candidate_id)
            return

        # Idempotency — skip if email already found
        if candidate.email:
            logger.info(
                "discover_email: candidate %s already has email — skipping", candidate_id
            )
            return

        tenant = await _get_tenant(db, tenant_id)
        if not tenant:
            return

        scout = TalentScoutService(db, tenant_id)
        provider = tenant.email_discovery_provider or "domain_deduction"
        await scout.emit_email_discovery_started(candidate.job_id, candidate.id, provider)

        name_parts = (candidate.name or "").strip().split(" ", 1)
        first_name = name_parts[0] if name_parts else ""
        last_name = name_parts[1] if len(name_parts) > 1 else ""
        company = candidate.company or ""

        scrapingdog_key = _resolve_scrapingdog_key(tenant)
        email: str | None = None
        email_source: str = "unknown"

        # ── Try configured provider ───────────────────────────────────────────
        if provider == "apollo":
            apollo_key = decrypt(tenant.apollo_api_key) if tenant.apollo_api_key else None
            if apollo_key:
                email = await apollo.find_email(candidate.name or "", company, apollo_key)
                if email:
                    email_source = "apollo"

        elif provider == "hunter":
            hunter_key = decrypt(tenant.hunter_api_key) if tenant.hunter_api_key else None
            if hunter_key:
                domain = await _lookup_company_domain(company, scrapingdog_key)
                if domain:
                    email = await hunter.find_email(first_name, last_name, domain, hunter_key)
                    if email:
                        email_source = "hunter"

        elif provider == "snov":
            snov_key = decrypt(tenant.snov_api_key) if tenant.snov_api_key else None
            if snov_key:
                domain = await _lookup_company_domain(company, scrapingdog_key)
                if domain:
                    email = await snov.find_email(first_name, last_name, domain, snov_key)
                    if email:
                        email_source = "snov"

        # ── EmailDeductionService fallback (always available) ─────────────────
        if not email:
            deducer = EmailDeductionService(scrapingdog_key)
            email = await deducer.find_email(first_name, last_name, company)
            if email:
                email_source = "deduced"

        # ── Persist result ────────────────────────────────────────────────────
        if email:
            async with db.begin():
                candidate.email = email
                candidate.email_source = email_source
                await db.flush()
            await scout.emit_email_found(candidate.job_id, candidate.id, email_source)
        else:
            async with db.begin():
                candidate.email_source = "unknown"
                await db.flush()
            await scout.emit_email_not_found(candidate.job_id, candidate.id)


async def _send_outreach_impl(candidate_id: uuid.UUID, tenant_id: uuid.UUID) -> None:
    """Async body of send_outreach."""
    async with AsyncSessionLocal() as db:
        candidate = await _get_candidate(db, candidate_id, tenant_id)
        if not candidate:
            logger.warning("send_outreach: candidate %s not found", candidate_id)
            return

        # Idempotency — only email candidates who passed the score threshold
        if candidate.status != "passed":
            logger.info(
                "send_outreach: candidate %s at status %r — skipping",
                candidate_id,
                candidate.status,
            )
            return

        # GDPR — never email opted-out candidates (guidelines §7)
        if candidate.opted_out:
            logger.info("send_outreach: candidate %s has opted out — skipping", candidate_id)
            return

        # Idempotency — skip if already emailed
        if candidate.outreach_email_sent_at is not None:
            logger.info("send_outreach: candidate %s already emailed — skipping", candidate_id)
            return

        # Cannot send without an email address
        if not candidate.email:
            logger.info("send_outreach: candidate %s has no email — skipping", candidate_id)
            return

        job = await _get_job(db, candidate.job_id, tenant_id)
        if not job:
            logger.warning("send_outreach: job %s not found", candidate.job_id)
            return

        tenant = await _get_tenant(db, tenant_id)
        if not tenant:
            return

        scout = TalentScoutService(db, tenant_id)

        # ── Generate personalised email via AI ────────────────────────────────
        system_prompt = job.outreach_email_prompt or _DEFAULT_OUTREACH_SYSTEM_PROMPT
        user_prompt = _build_outreach_user_prompt(candidate, job, tenant)

        t0 = time.time()
        try:
            ai = AIProvider(tenant)
            email_data = await ai.complete_json(
                prompt=user_prompt, system=system_prompt, max_tokens=600
            )
        except Exception as exc:
            duration_ms = int((time.time() - t0) * 1000)
            await scout.emit_outreach_failed(job.id, candidate.id, str(exc), duration_ms)
            raise  # trigger retry

        subject = email_data.get("subject") or f"Exciting {job.title} opportunity"
        body_text = email_data.get("body") or ""

        word_count = len(body_text.split())
        await scout.emit_outreach_generated(job.id, candidate.id, word_count)

        # ── Add GDPR unsubscribe link (guidelines §7, SPEC §7.5) ──────────────
        unsubscribe_url = f"{settings.frontend_url}/unsubscribe/{candidate.id}"
        html_body = (
            f"<div style='font-family:sans-serif;line-height:1.6'>"
            f"{body_text.replace(chr(10), '<br>')}"
            f"</div>"
            f"<hr style='margin-top:32px'>"
            f"<p style='font-size:11px;color:#999'>"
            f"If you no longer wish to receive recruitment emails from us, "
            f"<a href='{unsubscribe_url}'>click here to unsubscribe</a>."
            f"</p>"
        )

        # ── Send via SendGrid ─────────────────────────────────────────────────
        t_send = time.time()
        success = await send_email(
            to=candidate.email,
            subject=subject,
            html_body=html_body,
            tenant=tenant,
        )
        send_duration_ms = int((time.time() - t_send) * 1000)

        if success:
            async with db.begin():
                candidate.outreach_email_content = html_body
                candidate.outreach_email_sent_at = datetime.now(timezone.utc)
                candidate.status = "emailed"
                await db.flush()
            await scout.emit_outreach_sent(job.id, candidate.id, send_duration_ms)
        else:
            await scout.emit_outreach_failed(
                job.id, candidate.id, "SendGrid rejected the message", send_duration_ms
            )


# ── Permanent-failure helpers ──────────────────────────────────────────────────


async def _emit_job_permanent_failure(
    job_id: uuid.UUID, tenant_id: uuid.UUID, task_name: str, error: str
) -> None:
    """Emit system.task_failed_permanent for a job-level task."""
    try:
        async with AsyncSessionLocal() as db:
            scout = TalentScoutService(db, tenant_id)
            await scout.emit_task_failed_permanent(job_id, None, task_name, error)
    except Exception:
        logger.exception(
            "Failed to emit permanent failure event for job %s task %s", job_id, task_name
        )


async def _emit_candidate_permanent_failure(
    candidate_id: uuid.UUID, tenant_id: uuid.UUID, task_name: str, error: str
) -> None:
    """Emit system.task_failed_permanent for a candidate-level task."""
    try:
        async with AsyncSessionLocal() as db:
            candidate = await _get_candidate(db, candidate_id, tenant_id)
            job_id = candidate.job_id if candidate else None
            if not job_id:
                logger.error(
                    "Cannot emit permanent failure: candidate %s not found", candidate_id
                )
                return
            scout = TalentScoutService(db, tenant_id)
            await scout.emit_task_failed_permanent(job_id, candidate_id, task_name, error)
    except Exception:
        logger.exception(
            "Failed to emit permanent failure event for candidate %s task %s",
            candidate_id,
            task_name,
        )


# ── DB helpers ─────────────────────────────────────────────────────────────────


async def _get_job(db: AsyncSession, job_id: uuid.UUID, tenant_id: uuid.UUID) -> Job | None:
    """Fetch a job scoped to the given tenant."""
    result = await db.execute(
        select(Job).where(Job.id == job_id, Job.tenant_id == tenant_id)
    )
    return result.scalar_one_or_none()


async def _get_candidate(
    db: AsyncSession, candidate_id: uuid.UUID, tenant_id: uuid.UUID
) -> Candidate | None:
    """Fetch a candidate scoped to the given tenant."""
    result = await db.execute(
        select(Candidate).where(
            Candidate.id == candidate_id, Candidate.tenant_id == tenant_id
        )
    )
    return result.scalar_one_or_none()


async def _get_tenant(db: AsyncSession, tenant_id: uuid.UUID) -> Tenant | None:
    """Fetch a tenant by id."""
    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    return result.scalar_one_or_none()


async def _get_existing_linkedin_urls(
    db: AsyncSession, job_id: uuid.UUID, tenant_id: uuid.UUID
) -> set[str]:
    """Return the set of LinkedIn URLs already stored for this job."""
    result = await db.execute(
        select(Candidate.linkedin_url).where(
            Candidate.tenant_id == tenant_id,
            Candidate.job_id == job_id,
            Candidate.linkedin_url.is_not(None),
        )
    )
    return {row[0] for row in result.all()}


# ── API key helpers ────────────────────────────────────────────────────────────


def _resolve_scrapingdog_key(tenant: Tenant) -> str | None:
    """Tenant key takes priority over platform key."""
    if tenant.scrapingdog_api_key:
        return decrypt(tenant.scrapingdog_api_key)
    return settings.scrapingdog_api_key or None


def _resolve_brightdata_key(tenant: Tenant) -> str | None:
    """Tenant key takes priority over platform key."""
    if tenant.brightdata_api_key:
        return decrypt(tenant.brightdata_api_key)
    return settings.brightdata_api_key or None


# ── Parsing helpers ────────────────────────────────────────────────────────────


def _is_linkedin_profile_url(url: str) -> bool:
    """Return True if *url* looks like a LinkedIn profile (not a company page)."""
    return bool(url and "linkedin.com/in/" in url.lower())


def _parse_linkedin_result(raw_title: str) -> tuple[str, str]:
    """Parse a LinkedIn SERP result title into (name, job_title).

    Handles formats such as:
    - ``"Divesh Premdeep - Java Developer | LinkedIn"``
    - ``"Jane Doe | Senior Engineer at Acme | LinkedIn"``
    - ``"John Smith | LinkedIn"``
    """
    text = raw_title.strip()

    # Strip trailing LinkedIn branding
    for suffix in (" | LinkedIn", "- LinkedIn", "| LinkedIn"):
        if suffix in text:
            text = text[: text.rindex(suffix)].strip()

    if " - " in text:
        parts = text.split(" - ", 1)
        return parts[0].strip(), parts[1].strip()

    if " | " in text:
        parts = text.split(" | ", 1)
        return parts[0].strip(), parts[1].strip()

    return text, ""


def _build_job_spec_text(job: Job) -> str:
    """Serialise key job fields into a compact text block for the AI scoring prompt."""
    skills = ", ".join(job.required_skills or [])
    tech = ", ".join(job.tech_stack or [])
    return (
        f"Title: {job.title}\n"
        f"Job Type: {job.job_type or ''}\n"
        f"Location: {job.location} ({job.work_type})\n"
        f"Experience Required: {job.experience_years or 0}+ years\n"
        f"Required Skills: {skills}\n"
        f"Tech Stack: {tech}\n"
        f"Description: {job.description or ''}\n"
    )


def _build_outreach_user_prompt(candidate: Candidate, job: Job, tenant: Tenant) -> str:
    """Build the user-turn prompt for the outreach email AI call."""
    profile_summary = json.dumps(candidate.brightdata_profile or {})
    application_instructions = (
        f"To apply, email your resume to {tenant.email_inbox} "
        f"with subject line: {job.job_ref} \u2013 {{your_name}}"
    )
    return (
        f"Candidate Name: {candidate.name}\n"
        f"Current Title: {candidate.title or 'Unknown'}\n"
        f"Current Company: {candidate.company or 'Unknown'}\n"
        f"Location: {candidate.location or 'Unknown'}\n"
        f"LinkedIn Profile Data: {profile_summary}\n\n"
        f"Job Title: {job.title}\n"
        f"Job Reference: {job.job_ref}\n"
        f"Location: {job.location} ({job.work_type})\n"
        f"Required Skills: {', '.join(job.required_skills or [])}\n"
        f"Job Description: {job.description or ''}\n\n"
        f"Application Instructions: {application_instructions}\n"
        f"Recruiter Name: {job.hiring_manager_name or 'The Recruitment Team'}\n"
    )


async def _lookup_company_domain(company: str, scrapingdog_key: str | None) -> str | None:
    """Use EmailDeductionService to look up the company website domain."""
    if not company:
        return None
    deducer = EmailDeductionService(scrapingdog_key)
    return await deducer._lookup_domain(company)  # noqa: SLF001 — internal helper
