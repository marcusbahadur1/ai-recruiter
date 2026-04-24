"""Celery application — broker, result backend, task routing, and Beat schedule.

Beat schedule timezone is ``Australia/Brisbane`` (AEST, UTC+10, no DST) so
schedules expressed as clock times match the SPEC exactly.
"""

from celery import Celery
from celery.schedules import crontab

from app.config import settings

celery_app = Celery(
    "ai_recruiter",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=[
        "app.tasks.talent_scout_tasks",
        "app.tasks.screener_tasks",
        "app.tasks.scheduled_tasks",
        "app.tasks.marketing_tasks",
    ],
)

celery_app.conf.update(
    # ── Serialisation ─────────────────────────────────────────────────────────
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    # ── Timezone (SPEC §14.2 schedules are given in AEST) ─────────────────────
    timezone="Australia/Brisbane",
    enable_utc=True,
    # ── Reliability ───────────────────────────────────────────────────────────
    # Acknowledge only after the task function returns successfully.
    task_acks_late=True,
    # Re-queue if the worker process dies mid-task.
    task_reject_on_worker_lost=True,
    # One task at a time per worker process to avoid memory pressure.
    worker_prefetch_multiplier=1,
    # ── Memory management (Railway 512 MB limit) ──────────────────────────────
    # 2 concurrent processes — enough for parallelism without OOM.
    worker_concurrency=2,
    # Recycle each worker process after 50 tasks to reclaim leaked memory.
    worker_max_tasks_per_child=50,
    # ── Broker connection ─────────────────────────────────────────────────────
    broker_connection_retry_on_startup=True,
    # ── Beat schedule (SPEC §14.2) ────────────────────────────────────────────
    beat_schedule={
        # Resume Screener — poll all tenant mailboxes every 5 minutes
        "poll-mailboxes": {
            "task": "app.tasks.screener_tasks.poll_mailboxes",
            "schedule": crontab(minute="*/5"),
        },
        # Hiring manager digest — 08:00 AEST daily
        "send-daily-summaries": {
            "task": "app.tasks.scheduled_tasks.send_daily_summaries",
            "schedule": crontab(hour=8, minute=0),
        },
        # Remove expired interview-invitation tokens — midnight AEST
        "cleanup-expired-tokens": {
            "task": "app.tasks.scheduled_tasks.cleanup_expired_tokens",
            "schedule": crontab(hour=0, minute=0),
        },
        # Keep tenant plan state in sync with Stripe — every hour
        "sync-stripe-plans": {
            "task": "app.tasks.scheduled_tasks.sync_stripe_plans",
            "schedule": crontab(minute=0),
        },
        # Re-scrape tenant websites for RAG — weekly Sunday 02:00 AEST
        "rag-refresh": {
            "task": "app.tasks.scheduled_tasks.rag_refresh",
            "schedule": crontab(day_of_week=0, hour=2, minute=0),
        },
        # Expire trials and send expiry emails — 08:00 AEST (22:00 UTC prev day)
        "process-expired-trials": {
            "task": "app.tasks.scheduled_tasks.process_expired_trials",
            "schedule": crontab(hour=22, minute=0),
        },
        # ── AI Marketing Module (MARKETING.md §Phase 6, times in UTC) ────────────
        # Note: celery_app timezone is Australia/Brisbane (UTC+10); these crontab
        # values use UTC clock times so they fire at the UTC times shown.
        "marketing-generate-posts": {
            "task": "app.tasks.marketing_tasks.generate_and_schedule_posts",
            "schedule": crontab(hour=2, minute=0),
        },
        "marketing-publish-posts": {
            "task": "app.tasks.marketing_tasks.publish_scheduled_posts",
            "schedule": crontab(minute="*/15"),
        },
        "marketing-collect-stats": {
            "task": "app.tasks.marketing_tasks.collect_post_stats",
            "schedule": crontab(hour=8, minute=0),
        },
        "marketing-auto-engage": {
            "task": "app.tasks.marketing_tasks.auto_engage",
            "schedule": crontab(hour=10, minute=0),
        },
        "marketing-refresh-tokens": {
            "task": "app.tasks.marketing_tasks.refresh_linkedin_tokens",
            "schedule": crontab(hour=0, minute=0),
        },
        "marketing-group-posts": {
            "task": "app.tasks.marketing_tasks.post_to_linkedin_groups",
            "schedule": crontab(day_of_week=2, hour=9, minute=0),
        },
    },
    # ── Task routing ──────────────────────────────────────────────────────────
    task_routes={
        "app.tasks.marketing_tasks.auto_engage": {"queue": "marketing"},
        "app.tasks.marketing_tasks.post_to_linkedin_groups": {"queue": "marketing"},
    },
)
