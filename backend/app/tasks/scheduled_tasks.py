"""Scheduled (Beat) tasks — periodic maintenance jobs.

These tasks are invoked by Celery Beat on the schedule defined in
app.tasks.celery_app.  Each is a stub that will be fully implemented
in a future session; they are registered now so the worker starts
without ImportError.
"""

import logging

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
