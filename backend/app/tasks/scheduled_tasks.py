"""Scheduled (Beat) tasks — periodic maintenance jobs.

These tasks are invoked by Celery Beat on the schedule defined in
app.tasks.celery_app.  Each is a stub that will be fully implemented
in a future session; they are registered now so the worker starts
without ImportError.
"""

import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy import func, select

from app.config import settings
from app.database import AsyncTaskSessionLocal as AsyncSessionLocal
from app.models.candidate import Candidate
from app.models.job import Job
from app.models.tenant import Tenant
from app.services.sendgrid_email import send_email
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="app.tasks.scheduled_tasks.send_daily_summaries")
def send_daily_summaries() -> None:
    """Email hiring managers their daily candidate digest (SPEC §14.2)."""
    logger.info("send_daily_summaries: not yet implemented")


@celery_app.task(name="app.tasks.scheduled_tasks.cleanup_expired_tokens")
def cleanup_expired_tokens() -> None:
    """Delete expired interview-invitation tokens from the database (SPEC §14.2)."""
    logger.info("cleanup_expired_tokens: not yet implemented")


@celery_app.task(name="app.tasks.scheduled_tasks.sync_stripe_plans")
def sync_stripe_plans() -> None:
    """Sync tenant plan/subscription state from Stripe (SPEC §14.2)."""
    logger.info("sync_stripe_plans: not yet implemented")


@celery_app.task(name="app.tasks.scheduled_tasks.rag_refresh")
def rag_refresh() -> None:
    """Re-scrape tenant websites and refresh the RAG vector store (SPEC §14.2)."""
    logger.info("rag_refresh: not yet implemented")


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
                        "process_expired_trials: expiry email sent to tenant=%s", tenant.id
                    )
                except Exception as exc:
                    logger.error(
                        "process_expired_trials: failed to email tenant=%s: %s", tenant.id, exc
                    )


def _build_trial_expiry_email(tenant: Tenant, jobs_count: int, candidates_count: int) -> str:
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
