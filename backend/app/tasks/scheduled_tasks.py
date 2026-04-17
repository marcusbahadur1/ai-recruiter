"""Scheduled (Beat) tasks — periodic maintenance jobs.

These tasks are invoked by Celery Beat on the schedule defined in
app.tasks.celery_app.  Each is a stub that will be fully implemented
in a future session; they are registered now so the worker starts
without ImportError.
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from sqlalchemy import func, select

from app.config import settings
from app.database import AsyncTaskSessionLocal as AsyncSessionLocal
from app.models.application import Application
from app.models.candidate import Candidate
from app.models.job import Job
from app.models.job_audit_event import JobAuditEvent
from app.models.rag_document import RagDocument
from app.models.tenant import Tenant
from app.services.sendgrid_email import send_email
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)

_TEMPLATES_DIR = Path(__file__).parent.parent / "templates"
_jinja_env = Environment(loader=FileSystemLoader(str(_TEMPLATES_DIR)), autoescape=True)


@celery_app.task(name="app.tasks.scheduled_tasks.send_daily_summaries")
def send_daily_summaries() -> None:
    """Email hiring managers their daily candidate digest (SPEC §14.2)."""
    asyncio.run(_send_daily_summaries_async())


async def _send_daily_summaries_async() -> None:
    """For every active job with pipeline activity in the last 24h, email the hiring manager."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)

    async with AsyncSessionLocal() as db:
        # All active jobs that have a hiring manager email configured.
        jobs_result = await db.execute(
            select(Job).where(
                Job.status == "active",
                Job.hiring_manager_email.isnot(None),
                Job.hiring_manager_email != "",
            )
        )
        jobs = jobs_result.scalars().all()

        for job in jobs:
            try:
                await _send_summary_for_job(db, job, cutoff)
            except Exception as exc:
                logger.error("send_daily_summaries: failed for job=%s: %s", job.id, exc)


async def _send_summary_for_job(db, job: Job, cutoff: datetime) -> None:
    """Build and send the daily summary email for a single job."""
    # Only send if there was audit activity in the last 24h.
    activity_result = await db.execute(
        select(func.count())
        .select_from(JobAuditEvent)
        .where(JobAuditEvent.job_id == job.id, JobAuditEvent.created_at >= cutoff)
    )
    if (activity_result.scalar_one() or 0) == 0:
        return

    # Fetch tenant.
    tenant_result = await db.execute(select(Tenant).where(Tenant.id == job.tenant_id))
    tenant = tenant_result.scalar_one_or_none()
    if not tenant:
        return

    # New candidates discovered in last 24h.
    new_cands_result = await db.execute(
        select(Candidate)
        .where(
            Candidate.job_id == job.id,
            Candidate.created_at >= cutoff,
        )
        .order_by(Candidate.suitability_score.desc().nulls_last())
    )
    new_candidates = [
        {
            "name": c.name,
            "score": c.suitability_score if c.suitability_score is not None else "—",
            "status": c.status,
            "linkedin_url": c.linkedin_url or "",
        }
        for c in new_cands_result.scalars().all()
    ]

    # New applications received in last 24h.
    new_apps_result = await db.execute(
        select(Application)
        .where(
            Application.job_id == job.id,
            Application.created_at >= cutoff,
        )
        .order_by(Application.resume_score.desc().nulls_last())
    )
    new_applications = [
        {
            "name": a.applicant_name,
            "email": a.applicant_email,
            "screening_score": a.resume_score if a.resume_score is not None else "—",
            "status": a.status,
        }
        for a in new_apps_result.scalars().all()
    ]

    # Nothing new today — skip.
    if not new_candidates and not new_applications:
        return

    # Totals for the job (all time).
    total_candidates = (
        await db.scalar(
            select(func.count())
            .select_from(Candidate)
            .where(Candidate.job_id == job.id)
        )
        or 0
    )
    passed_count = (
        await db.scalar(
            select(func.count())
            .select_from(Candidate)
            .where(
                Candidate.job_id == job.id,
                Candidate.status.in_(["passed", "emailed"]),
            )
        )
        or 0
    )
    emailed_count = (
        await db.scalar(
            select(func.count())
            .select_from(Candidate)
            .where(Candidate.job_id == job.id, Candidate.status == "emailed")
        )
        or 0
    )
    total_applications = (
        await db.scalar(
            select(func.count())
            .select_from(Application)
            .where(Application.job_id == job.id)
        )
        or 0
    )

    summary_date = datetime.now(timezone.utc).strftime("%A %-d %B %Y")
    report_url = f"{settings.frontend_url}/en/jobs/{job.id}"

    template = _jinja_env.get_template("daily_summary.html")
    html_body = template.render(
        hiring_manager_name=job.hiring_manager_name or "Hiring Manager",
        firm_name=tenant.name,
        job_title=job.title,
        job_ref=job.job_ref,
        summary_date=summary_date,
        new_candidates=new_candidates,
        new_applications=new_applications,
        report_url=report_url,
        total_candidates=total_candidates,
        passed_count=passed_count,
        emailed_count=emailed_count,
        total_applications=total_applications,
    )

    subject = f"Daily recruitment update — {job.title} ({summary_date})"
    await send_email(
        to=job.hiring_manager_email,
        subject=subject,
        html_body=html_body,
        tenant=tenant,
    )
    logger.info(
        "send_daily_summaries: summary sent for job=%s to %s (%d candidates, %d applications)",
        job.id,
        job.hiring_manager_email,
        len(new_candidates),
        len(new_applications),
    )


@celery_app.task(name="app.tasks.scheduled_tasks.cleanup_expired_tokens")
def cleanup_expired_tokens() -> None:
    """Null-out expired interview-invitation tokens from the database (SPEC §14.2).

    Applications keep their interview_invited status; only the one-time link
    token is cleared so it can no longer be replayed after expiry.
    """
    asyncio.run(_cleanup_expired_tokens_async())


async def _cleanup_expired_tokens_async() -> None:
    from sqlalchemy import update

    now = datetime.now(timezone.utc)
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            update(Application)
            .where(
                Application.interview_invite_token.isnot(None),
                Application.interview_invite_expires_at < now,
            )
            .values(interview_invite_token=None)
            .returning(Application.id)
        )
        cleared = len(result.fetchall())
        await db.commit()

    logger.info("cleanup_expired_tokens: cleared %d expired token(s)", cleared)


@celery_app.task(name="app.tasks.scheduled_tasks.sync_stripe_plans")
def sync_stripe_plans() -> None:
    """Reconcile tenant plan/active status against Stripe subscription state (SPEC §14.2).

    Acts as a safety net for missed webhooks.  For each tenant with a Stripe
    subscription ID the task retrieves the subscription and:
      - ``active`` / ``trialing``  → ensure is_active=True; sync plan from price
        metadata when it has drifted.
      - ``canceled`` / ``unpaid``  → mark is_active=False (tenant can no longer
        log in or post jobs).
      - Other statuses (``past_due``, ``incomplete``, …) → log only; the payment-
        failed webhook handles the user-facing email.

    Credits are never reset here — that is owned by the invoice-paid webhook so
    we do not double-award credits on each nightly sync.
    """
    asyncio.run(_sync_stripe_plans_async())


async def _sync_stripe_plans_async() -> None:
    import stripe as _stripe

    if not settings.stripe_secret_key:
        logger.warning("sync_stripe_plans: STRIPE_SECRET_KEY not set — skipping")
        return

    _stripe.api_key = settings.stripe_secret_key

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Tenant).where(
                Tenant.stripe_subscription_id.isnot(None),
                Tenant.stripe_subscription_id != "",
            )
        )
        tenants = result.scalars().all()

    logger.info("sync_stripe_plans: checking %d tenant(s)", len(tenants))

    for tenant in tenants:
        try:
            await _sync_one_tenant(tenant)
        except Exception as exc:
            logger.error("sync_stripe_plans: error for tenant %s: %s", tenant.id, exc)


async def _sync_one_tenant(tenant: Tenant) -> None:
    import stripe as _stripe

    sub = _stripe.Subscription.retrieve(tenant.stripe_subscription_id)
    status: str = sub.get("status", "")

    if status in ("active", "trialing"):
        # Derive plan from the first price item's metadata or nickname.
        items = sub.get("items", {}).get("data", [])
        new_plan: str | None = None
        if items:
            price = items[0].get("price", {})
            new_plan = (price.get("metadata") or {}).get("plan") or price.get(
                "nickname"
            )

        async with AsyncSessionLocal() as db:
            result = await db.execute(select(Tenant).where(Tenant.id == tenant.id))
            t = result.scalar_one_or_none()
            if not t:
                return
            changed = False
            if not t.is_active:
                t.is_active = True
                changed = True
            if new_plan and new_plan != t.plan:
                logger.info(
                    "sync_stripe_plans: tenant %s plan drift %r → %r",
                    t.id,
                    t.plan,
                    new_plan,
                )
                t.plan = new_plan
                changed = True
            if changed:
                await db.commit()

    elif status in ("canceled", "unpaid"):
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(Tenant).where(Tenant.id == tenant.id))
            t = result.scalar_one_or_none()
            if t and t.is_active:
                t.is_active = False
                await db.commit()
                logger.warning(
                    "sync_stripe_plans: tenant %s deactivated (subscription %s)",
                    tenant.id,
                    status,
                )
    else:
        logger.debug(
            "sync_stripe_plans: tenant %s subscription status=%r — no action",
            tenant.id,
            status,
        )


@celery_app.task(name="app.tasks.scheduled_tasks.rag_refresh")
def rag_refresh() -> None:
    """Re-scrape all tenant website sources and refresh the RAG vector store (SPEC §14.2).

    For every unique (tenant_id, source_url) pair stored as a ``website_scrape``
    RAG document the task deletes the existing chunks and re-scrapes the URL so
    the knowledge base stays fresh.  Uploaded files (PDFs / DOCX) are skipped —
    they don't change and must be re-uploaded manually.

    Only tenants on plans with widget access are processed (agency_small+).
    """
    asyncio.run(_rag_refresh_async())


async def _rag_refresh_async() -> None:
    from sqlalchemy import delete

    from app.services import rag_pipeline

    _WIDGET_PLANS = {"agency_small", "agency_medium", "enterprise"}

    async with AsyncSessionLocal() as db:
        # Find all unique (tenant_id, source_url) pairs for website scrapes.
        rows_result = await db.execute(
            select(RagDocument.tenant_id, RagDocument.source_url)
            .where(
                RagDocument.source_type == "website_scrape",
                RagDocument.source_url.isnot(None),
            )
            .distinct()
        )
        pairs: list[tuple] = rows_result.fetchall()

    logger.info("rag_refresh: %d website source(s) to refresh", len(pairs))

    for tenant_id, source_url in pairs:
        try:
            async with AsyncSessionLocal() as db:
                # Load tenant and check plan.
                t_result = await db.execute(
                    select(Tenant).where(Tenant.id == tenant_id)
                )
                tenant = t_result.scalar_one_or_none()
                if not tenant or tenant.plan not in _WIDGET_PLANS:
                    continue

                # Delete existing chunks for this URL before re-scraping.
                await db.execute(
                    delete(RagDocument).where(
                        RagDocument.tenant_id == tenant_id,
                        RagDocument.source_url == source_url,
                        RagDocument.source_type == "website_scrape",
                    )
                )
                await db.commit()

            # Re-scrape outside the delete transaction so a crawl failure
            # does not leave the tenant without any chunks indefinitely —
            # on next beat cycle the URL won't appear (no rows) and will
            # be skipped.  A failed scrape is logged and retried next run.
            async with AsyncSessionLocal() as db:
                docs = await rag_pipeline.scrape_website(
                    db=db,
                    tenant_id=tenant_id,
                    url=source_url,
                    tenant=tenant,
                )
                logger.info(
                    "rag_refresh: tenant=%s url=%s → %d chunk(s) stored",
                    tenant_id,
                    source_url,
                    len(docs),
                )
        except Exception as exc:
            logger.error(
                "rag_refresh: failed for tenant=%s url=%s: %s",
                tenant_id,
                source_url,
                exc,
            )


@celery_app.task(name="app.tasks.scheduled_tasks.process_expired_trials")
def process_expired_trials() -> None:
    """Mark expired trial tenants as trial_expired and send expiry emails (SPEC §4)."""
    asyncio.run(_process_expired_trials_async())


async def _process_expired_trials_async() -> None:
    """Find tenants whose trial has ended, update their plan, and email them."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Tenant).where(
                Tenant.plan == "trial",
                Tenant.trial_ends_at < datetime.now(timezone.utc),
                Tenant.trial_expiry_email_sent_at.is_(None),
            )
        )
        tenants = result.scalars().all()

        for tenant in tenants:
            # Count trial activity
            jobs_count = await db.scalar(
                select(func.count(Job.id)).where(Job.tenant_id == tenant.id)
            )
            candidates_count = await db.scalar(
                select(func.count(Candidate.id)).where(Candidate.tenant_id == tenant.id)
            )

            # Update plan to expired and record email timestamp
            tenant.plan = "trial_expired"
            tenant.trial_expiry_email_sent_at = datetime.now(timezone.utc)
            await db.commit()

            # Send expiry email
            if tenant.main_contact_email:
                try:
                    await send_email(
                        to=tenant.main_contact_email,
                        subject="Your AI Recruiter trial has ended",
                        html_body=_build_trial_expiry_email(
                            tenant, jobs_count or 0, candidates_count or 0
                        ),
                        tenant=tenant,
                    )
                    logger.info(
                        "process_expired_trials: expiry email sent to tenant=%s",
                        tenant.id,
                    )
                except Exception as exc:
                    logger.error(
                        "process_expired_trials: failed to email tenant=%s: %s",
                        tenant.id,
                        exc,
                    )


def _build_trial_expiry_email(
    tenant: Tenant, jobs_count: int, candidates_count: int
) -> str:
    """Build the HTML body for the trial expiry email."""
    frontend_url = settings.frontend_url
    name = tenant.main_contact_name or tenant.name
    return f"""
    <div style="font-family:sans-serif;max-width:600px;margin:0 auto">
      <h2>Your AI Recruiter trial has ended</h2>
      <p>Hi {name},</p>
      <p>Your 14-day free trial of AI Recruiter has come to an end.
      Here's what you accomplished during your trial:</p>
      <ul>
        <li>Jobs posted: {jobs_count}</li>
        <li>Candidates discovered: {candidates_count}</li>
      </ul>
      <p>To continue using AI Recruiter, choose a subscription plan
      that suits your needs:</p>
      <table style="width:100%;border-collapse:collapse;margin:20px 0">
        <tr style="background:#0D1B2A;color:white">
          <th style="padding:12px">Plan</th>
          <th style="padding:12px">Price</th>
          <th style="padding:12px">Jobs/mo</th>
          <th style="padding:12px">Candidates/job</th>
        </tr>
        <tr>
          <td style="padding:12px;border:1px solid #ddd">Recruiter</td>
          <td style="padding:12px;border:1px solid #ddd">$499/mo</td>
          <td style="padding:12px;border:1px solid #ddd">5</td>
          <td style="padding:12px;border:1px solid #ddd">20</td>
        </tr>
        <tr style="background:#f9f9f9">
          <td style="padding:12px;border:1px solid #ddd">Agency (Small)</td>
          <td style="padding:12px;border:1px solid #ddd">$999/mo</td>
          <td style="padding:12px;border:1px solid #ddd">20</td>
          <td style="padding:12px;border:1px solid #ddd">40</td>
        </tr>
        <tr>
          <td style="padding:12px;border:1px solid #ddd">Agency (Medium)</td>
          <td style="padding:12px;border:1px solid #ddd">$2,999/mo</td>
          <td style="padding:12px;border:1px solid #ddd">75</td>
          <td style="padding:12px;border:1px solid #ddd">60</td>
        </tr>
      </table>
      <div style="text-align:center;margin:30px 0">
        <a href="{frontend_url}/subscribe"
           style="background:#00C2E0;color:white;padding:14px 28px;
           text-decoration:none;border-radius:6px;font-weight:bold;
           margin-right:12px">
          Subscribe Now
        </a>
        <a href="{frontend_url}/login"
           style="background:#1B6CA8;color:white;padding:14px 28px;
           text-decoration:none;border-radius:6px;font-weight:bold">
          Log In
        </a>
      </div>
      <p style="color:#666;font-size:12px">
        Questions? Contact us at support@airecruiterz.com
      </p>
    </div>
    """
