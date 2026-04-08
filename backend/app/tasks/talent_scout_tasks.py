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

Architecture notes:
- Every task calls asyncio.run() to get a fresh event loop — Celery workers
  are synchronous processes and cannot share an async loop across tasks.
- NullPool is used for task DB sessions (see database.py) so connections are
  never pooled across event-loop boundaries.
- Audit events are committed separately from the business write so that an
  audit failure never rolls back a candidate/application record.
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
from app.database import AsyncTaskSessionLocal as AsyncSessionLocal
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
    """Discover candidates via SERP API for all title × location combinations."""
    try:
        asyncio.run(_discover_candidates_async(job_id, tenant_id))
    except Exception as exc:
        logger.error("discover_candidates failed (attempt %d): %s", self.request.retries + 1, exc)
        raise self.retry(exc=exc, countdown=2 ** self.request.retries * 30)


# ── Task 2: Profile Enrichment ─────────────────────────────────────────────────


@celery_app.task(bind=True, max_retries=3, name="app.tasks.talent_scout_tasks.enrich_profile")
def enrich_profile(self, candidate_id: str, tenant_id: str) -> None:
    """Fetch the candidate's public LinkedIn profile via BrightData."""
    try:
        asyncio.run(_enrich_profile_async(candidate_id, tenant_id))
    except Exception as exc:
        logger.error("enrich_profile failed for %s (attempt %d): %s", candidate_id, self.request.retries + 1, exc)
        raise self.retry(exc=exc, countdown=2 ** self.request.retries * 30)


# ── Task 3: Candidate Scoring ──────────────────────────────────────────────────


@celery_app.task(bind=True, max_retries=3, name="app.tasks.talent_scout_tasks.score_candidate")
def score_candidate(self, candidate_id: str, tenant_id: str) -> None:
    """Score the candidate against the job spec via the AI provider facade."""
    try:
        asyncio.run(_score_candidate_async(candidate_id, tenant_id))
    except Exception as exc:
        logger.error("score_candidate failed for %s (attempt %d): %s", candidate_id, self.request.retries + 1, exc)
        raise self.retry(exc=exc, countdown=2 ** self.request.retries * 30)


# ── Task 4: Email Discovery ────────────────────────────────────────────────────


@celery_app.task(bind=True, max_retries=3, name="app.tasks.talent_scout_tasks.discover_email")
def discover_email(self, candidate_id: str, tenant_id: str) -> None:
    """Discover the candidate's email via Apollo/Hunter/Snov + EmailDeductionService."""
    try:
        asyncio.run(_discover_email_async(candidate_id, tenant_id))
    except Exception as exc:
        logger.error("discover_email failed for %s (attempt %d): %s", candidate_id, self.request.retries + 1, exc)
        raise self.retry(exc=exc, countdown=2 ** self.request.retries * 30)


# ── Task 5: Email Outreach ─────────────────────────────────────────────────────


@celery_app.task(bind=True, max_retries=3, name="app.tasks.talent_scout_tasks.send_outreach")
def send_outreach(self, candidate_id: str, tenant_id: str) -> None:
    """Generate a hyper-personalised email via AI and send via SendGrid."""
    try:
        asyncio.run(_send_outreach_async(candidate_id, tenant_id))
    except Exception as exc:
        logger.error("send_outreach failed for %s (attempt %d): %s", candidate_id, self.request.retries + 1, exc)
        raise self.retry(exc=exc, countdown=2 ** self.request.retries * 30)


# ── Async implementations ──────────────────────────────────────────────────────


async def _discover_candidates_async(job_id: str, tenant_id: str) -> None:
    """Discover and persist candidates for a job via ScrapingDog SERP search."""
    job_uuid = uuid.UUID(job_id)
    tenant_uuid = uuid.UUID(tenant_id)

    async with AsyncSessionLocal() as db:
        job = await _get_job(db, job_uuid, tenant_uuid)
        if not job:
            logger.warning("discover_candidates: job %s not found for tenant %s", job_id, tenant_id)
            return

        tenant = await _get_tenant(db, tenant_uuid)
        if not tenant:
            logger.warning("discover_candidates: tenant %s not found", tenant_id)
            return

        print(f"[discover_candidates] job={job.title!r} ({job_id}) tenant={tenant_id}")
        logger.info("discover_candidates: starting for job %s (%s)", job_id, job.title)

        api_key = _resolve_scrapingdog_key(tenant)
        if not api_key:
            logger.error("discover_candidates: no ScrapingDog API key for tenant %s", tenant_id)
            return

        queries = TalentScoutService(db, tenant_uuid).build_search_queries(job)
        print(f"[discover_candidates] {len(queries)} queries built")
        logger.info("discover_candidates: %d queries for job %s", len(queries), job_id)

        existing_urls = await _get_existing_linkedin_urls(db, job_uuid, tenant_uuid)
        new_candidate_ids: list[str] = []

        for query in queries:
            print(f"[discover_candidates] query: {query[:80]!r}")
            for page in range(10):  # up to 10 pages (100 results) per query
                start = page * 10
                t0 = time.time()
                results = await scrapingdog.search_linkedin(query, start, api_key)
                duration_ms = int((time.time() - t0) * 1000)

                print(f"[discover_candidates] page={page} → {len(results)} results ({duration_ms}ms)")
                logger.info(
                    "discover_candidates: query=%r page=%d → %d results",
                    query[:60], page, len(results),
                )

                if not results:
                    break  # ScrapingDog returned nothing — no more pages for this query

                for result in results:
                    linkedin_url = result.get("link", "")
                    if not _is_linkedin_profile_url(linkedin_url):
                        continue
                    if linkedin_url in existing_urls:
                        continue

                    name, title = _parse_linkedin_result(result.get("title", ""))
                    if not name:
                        continue

                    print(f"[discover_candidates] saving: {name} @ {linkedin_url}")

                    candidate = Candidate(
                        tenant_id=tenant_uuid,
                        job_id=job_uuid,
                        name=name,
                        title=title or None,
                        snippet=result.get("snippet") or None,
                        linkedin_url=linkedin_url,
                        status="discovered",
                    )
                    db.add(candidate)
                    await db.flush()   # assigns candidate.id without committing
                    await db.commit()  # persist the candidate row immediately

                    existing_urls.add(linkedin_url)
                    new_candidate_ids.append(str(candidate.id))
                    print(f"[discover_candidates] saved candidate {candidate.id} — {name}")
                    logger.info("discover_candidates: saved candidate %s (%s)", candidate.id, name)

                    # Audit event is committed in a separate transaction so a
                    # failure here never rolls back the candidate we just saved.
                    try:
                        scout = TalentScoutService(db, tenant_uuid)
                        await scout.emit_candidate_discovered(job_uuid, candidate.id, name)
                        await db.commit()
                    except Exception as audit_exc:
                        logger.error(
                            "discover_candidates: audit emit failed for %s: %s",
                            candidate.id, audit_exc,
                        )
                        try:
                            await db.rollback()
                        except Exception:
                            pass

        print(f"[discover_candidates] done — {len(new_candidate_ids)} new candidates")
        logger.info(
            "discover_candidates: complete — %d new candidates for job %s",
            len(new_candidate_ids), job_id,
        )

        # Fan out processing chain per candidate (tasks 2–5)
        for cid in new_candidate_ids:
            chain(
                enrich_profile.si(cid, tenant_id),
                score_candidate.si(cid, tenant_id),
                discover_email.si(cid, tenant_id),
                send_outreach.si(cid, tenant_id),
            ).delay()


async def _enrich_profile_async(candidate_id: str, tenant_id: str) -> None:
    """Fetch the candidate's LinkedIn profile via BrightData and persist it."""
    cand_uuid = uuid.UUID(candidate_id)
    tenant_uuid = uuid.UUID(tenant_id)

    async with AsyncSessionLocal() as db:
        candidate = await _get_candidate(db, cand_uuid, tenant_uuid)
        if not candidate:
            logger.warning("enrich_profile: candidate %s not found", candidate_id)
            return

        # Idempotency — skip if already enriched or further in the pipeline
        if candidate.status != "discovered":
            logger.info(
                "enrich_profile: candidate %s already at status %r — skipping",
                candidate_id, candidate.status,
            )
            return

        tenant = await _get_tenant(db, tenant_uuid)
        if not tenant:
            return

        scout = TalentScoutService(db, tenant_uuid)

        if not candidate.linkedin_url:
            logger.info("enrich_profile: candidate %s has no LinkedIn URL — advancing", candidate_id)
            candidate.status = "profiled"
            candidate.brightdata_profile = {}
            await db.commit()
            try:
                await scout.emit_profile_enrichment_failed(
                    candidate.job_id, cand_uuid, "No LinkedIn URL", 0
                )
                await db.commit()
            except Exception:
                await db.rollback()
            return

        api_key = _resolve_brightdata_key(tenant)
        if not api_key:
            raise RuntimeError(f"No BrightData API key for tenant {tenant_id}")

        try:
            await scout.emit_profile_enrichment_started(candidate.job_id, cand_uuid)
            await db.commit()
        except Exception:
            await db.rollback()

        t0 = time.time()
        profile = await brightdata.get_linkedin_profile(candidate.linkedin_url, api_key)
        duration_ms = int((time.time() - t0) * 1000)

        if not profile:
            candidate.status = "profiled"
            candidate.brightdata_profile = {}
            await db.commit()
            try:
                await scout.emit_profile_enrichment_failed(
                    candidate.job_id, cand_uuid, "Empty profile returned", duration_ms
                )
                await db.commit()
            except Exception:
                await db.rollback()
            return

        company = (
            profile.get("current_company")
            or profile.get("company")
            or (profile.get("positions") or [{}])[0].get("company_name")
            or candidate.company
        )
        location = profile.get("location") or candidate.location

        candidate.brightdata_profile = profile
        candidate.status = "profiled"
        if company:
            candidate.company = str(company)
        if location:
            candidate.location = str(location)
        await db.commit()

        try:
            await scout.emit_profile_enrichment_success(
                candidate.job_id, cand_uuid, profile, duration_ms
            )
            await db.commit()
        except Exception:
            await db.rollback()


async def _score_candidate_async(candidate_id: str, tenant_id: str) -> None:
    """Score the candidate against the job spec via the AI provider facade."""
    cand_uuid = uuid.UUID(candidate_id)
    tenant_uuid = uuid.UUID(tenant_id)

    async with AsyncSessionLocal() as db:
        candidate = await _get_candidate(db, cand_uuid, tenant_uuid)
        if not candidate:
            logger.warning("score_candidate: candidate %s not found", candidate_id)
            return

        if candidate.status != "profiled":
            logger.info(
                "score_candidate: candidate %s at status %r — skipping",
                candidate_id, candidate.status,
            )
            return

        if not candidate.brightdata_profile:
            logger.info("score_candidate: candidate %s has no profile — skipping", candidate_id)
            return

        job = await _get_job(db, candidate.job_id, tenant_uuid)
        if not job:
            logger.warning("score_candidate: job %s not found", candidate.job_id)
            return

        tenant = await _get_tenant(db, tenant_uuid)
        if not tenant:
            return

        scout = TalentScoutService(db, tenant_uuid)

        try:
            await scout.emit_scoring_started(job.id, cand_uuid)
            await db.commit()
        except Exception:
            await db.rollback()

        job_spec = _build_job_spec_text(job)
        profile_text = json.dumps(candidate.brightdata_profile)
        prompt = _SCORING_PROMPT_TEMPLATE.format(job_spec=job_spec, profile=profile_text)

        t0 = time.time()
        ai = AIProvider(tenant)
        result = await ai.complete_json(prompt=prompt, max_tokens=512)
        duration_ms = int((time.time() - t0) * 1000)

        score = int(result.get("score", 0))
        reasoning = result.get("reasoning", "")
        passed = score >= job.minimum_score

        candidate.suitability_score = score
        candidate.score_reasoning = reasoning
        candidate.status = "passed" if passed else "failed"
        await db.commit()

        try:
            await scout.emit_scoring_success(job.id, cand_uuid, score, passed, duration_ms)
            await db.commit()
        except Exception:
            await db.rollback()


async def _discover_email_async(candidate_id: str, tenant_id: str) -> None:
    """Discover the candidate's email address via configured provider + deduction fallback."""
    cand_uuid = uuid.UUID(candidate_id)
    tenant_uuid = uuid.UUID(tenant_id)

    async with AsyncSessionLocal() as db:
        candidate = await _get_candidate(db, cand_uuid, tenant_uuid)
        if not candidate:
            logger.warning("discover_email: candidate %s not found", candidate_id)
            return

        if candidate.email:
            logger.info("discover_email: candidate %s already has email — skipping", candidate_id)
            return

        tenant = await _get_tenant(db, tenant_uuid)
        if not tenant:
            return

        scout = TalentScoutService(db, tenant_uuid)
        provider = tenant.email_discovery_provider or "domain_deduction"

        try:
            await scout.emit_email_discovery_started(candidate.job_id, cand_uuid, provider)
            await db.commit()
        except Exception:
            await db.rollback()

        name_parts = (candidate.name or "").strip().split(" ", 1)
        first_name = name_parts[0] if name_parts else ""
        last_name = name_parts[1] if len(name_parts) > 1 else ""
        company = candidate.company or ""
        scrapingdog_key = _resolve_scrapingdog_key(tenant)
        email: str | None = None
        email_source: str = "unknown"

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

        if not email:
            deducer = EmailDeductionService(scrapingdog_key)
            email = await deducer.find_email(first_name, last_name, company)
            if email:
                email_source = "deduced"

        if email:
            candidate.email = email
            candidate.email_source = email_source
        else:
            candidate.email_source = "unknown"
        await db.commit()

        try:
            if email:
                await scout.emit_email_found(candidate.job_id, cand_uuid, email_source)
            else:
                await scout.emit_email_not_found(candidate.job_id, cand_uuid)
            await db.commit()
        except Exception:
            await db.rollback()


async def _send_outreach_async(candidate_id: str, tenant_id: str) -> None:
    """Generate a personalised outreach email via AI and send it via SendGrid."""
    cand_uuid = uuid.UUID(candidate_id)
    tenant_uuid = uuid.UUID(tenant_id)

    async with AsyncSessionLocal() as db:
        candidate = await _get_candidate(db, cand_uuid, tenant_uuid)
        if not candidate:
            logger.warning("send_outreach: candidate %s not found", candidate_id)
            return

        if candidate.status != "passed":
            logger.info(
                "send_outreach: candidate %s at status %r — skipping",
                candidate_id, candidate.status,
            )
            return

        if candidate.opted_out:
            logger.info("send_outreach: candidate %s opted out — skipping", candidate_id)
            return

        if candidate.outreach_email_sent_at is not None:
            logger.info("send_outreach: candidate %s already emailed — skipping", candidate_id)
            return

        if not candidate.email:
            logger.info("send_outreach: candidate %s has no email — skipping", candidate_id)
            return

        job = await _get_job(db, candidate.job_id, tenant_uuid)
        if not job:
            logger.warning("send_outreach: job %s not found", candidate.job_id)
            return

        tenant = await _get_tenant(db, tenant_uuid)
        if not tenant:
            return

        scout = TalentScoutService(db, tenant_uuid)
        system_prompt = job.outreach_email_prompt or _DEFAULT_OUTREACH_SYSTEM_PROMPT
        user_prompt = _build_outreach_user_prompt(candidate, job, tenant)

        t0 = time.time()
        ai = AIProvider(tenant)
        email_data = await ai.complete_json(
            prompt=user_prompt, system=system_prompt, max_tokens=600
        )
        ai_duration_ms = int((time.time() - t0) * 1000)

        subject = email_data.get("subject") or f"Exciting {job.title} opportunity"
        body_text = email_data.get("body") or ""

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

        t_send = time.time()
        success = await send_email(
            to=candidate.email,
            subject=subject,
            html_body=html_body,
            tenant=tenant,
        )
        send_duration_ms = int((time.time() - t_send) * 1000)

        if success:
            candidate.outreach_email_content = html_body
            candidate.outreach_email_sent_at = datetime.now(timezone.utc)
            candidate.status = "emailed"
            await db.commit()
            try:
                await scout.emit_outreach_sent(job.id, cand_uuid, send_duration_ms)
                await db.commit()
            except Exception:
                await db.rollback()
        else:
            try:
                await scout.emit_outreach_failed(
                    job.id, cand_uuid, "SendGrid rejected the message", send_duration_ms
                )
                await db.commit()
            except Exception:
                await db.rollback()


# ── DB helpers ─────────────────────────────────────────────────────────────────


async def _get_job(db: AsyncSession, job_id: uuid.UUID, tenant_id: uuid.UUID) -> Job | None:
    result = await db.execute(
        select(Job).where(Job.id == job_id, Job.tenant_id == tenant_id)
    )
    return result.scalar_one_or_none()


async def _get_candidate(
    db: AsyncSession, candidate_id: uuid.UUID, tenant_id: uuid.UUID
) -> Candidate | None:
    result = await db.execute(
        select(Candidate).where(
            Candidate.id == candidate_id, Candidate.tenant_id == tenant_id
        )
    )
    return result.scalar_one_or_none()


async def _get_tenant(db: AsyncSession, tenant_id: uuid.UUID) -> Tenant | None:
    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    return result.scalar_one_or_none()


async def _get_existing_linkedin_urls(
    db: AsyncSession, job_id: uuid.UUID, tenant_id: uuid.UUID
) -> set[str]:
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
    if tenant.scrapingdog_api_key:
        return decrypt(tenant.scrapingdog_api_key)
    return settings.scrapingdog_api_key or None


def _resolve_brightdata_key(tenant: Tenant) -> str | None:
    if tenant.brightdata_api_key:
        return decrypt(tenant.brightdata_api_key)
    return settings.brightdata_api_key or None


# ── Parsing helpers ────────────────────────────────────────────────────────────


def _is_linkedin_profile_url(url: str) -> bool:
    return bool(url and "linkedin.com/in/" in url.lower())


def _parse_linkedin_result(raw_title: str) -> tuple[str, str]:
    """Parse a LinkedIn SERP result title into (name, job_title).

    Handles formats such as:
    - ``"Divesh Premdeep - Java Developer | LinkedIn"``
    - ``"Jane Doe | Senior Engineer at Acme | LinkedIn"``
    - ``"John Smith | LinkedIn"``
    """
    text = raw_title.strip()
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
    if not company:
        return None
    deducer = EmailDeductionService(scrapingdog_key)
    return await deducer._lookup_domain(company)  # noqa: SLF001
