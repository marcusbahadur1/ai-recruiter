# Celery Domain

Task structure, retry/backoff, idempotency, Beat schedule, queue config.

---

## App Config

- Broker + backend: Redis (`REDIS_URL`) — Fly.io Upstash
- Queues: `celery` (scout + screener), `marketing`
- Timezone: `Australia/Brisbane`
- Worker: `celery -A app.tasks.celery_app worker -Q celery,marketing --loglevel=info`

## Task Wrapper Pattern

All tasks are sync wrappers calling `asyncio.run()` — see DECISIONS D7.

```python
@celery_app.task(bind=True, max_retries=20)
def task_name(self, entity_id, tenant_id):
    try:
        asyncio.run(_async_impl(entity_id, tenant_id))
    except Exception as exc:
        if _is_overload_error(exc):   # 429/529/"rate_limit"
            raise self.retry(exc=exc, countdown=300)  # indefinite
        raise self.retry(exc=exc, countdown=min(2**self.request.retries*30, 3600))
```

Idempotency guard in every `_async_impl`:
```python
if entity.status != "expected_status":
    return  # already processed — safe to retry
```

## Retry Backoff

Attempts: 30s → 60s → 120s → … → 3600s cap. 429/529: 300s every time, unlimited.

## DB Access in Tasks

Use `AsyncTaskSessionLocal()` (port 5432 session pooler), never `AsyncSessionLocal` (port 6543).

## Beat Schedule

| Task | Schedule |
|------|----------|
| `poll_mailboxes` | Every 5 min |
| `publish_scheduled_posts` | Every 15 min |
| `sync_stripe_plans` | Every hour |
| `send_daily_summaries` | 08:00 AEST |
| `collect_post_stats` | 08:00 UTC |
| `auto_engage` | 10:00 UTC |
| `generate_and_schedule_posts` | 02:00 UTC |
| `refresh_linkedin_tokens` | 00:00 UTC |
| `cleanup_expired_tokens` | 00:00 AEST |
| `process_expired_trials` | 22:00 UTC |
| `rag_refresh` | Sunday 02:00 AEST |
| `post_to_linkedin_groups` | Tuesday 09:00 UTC |

## Permanent Failure

After `max_retries` exhausted: emit `system.task_failed_permanent` audit event. Manual intervention required.
