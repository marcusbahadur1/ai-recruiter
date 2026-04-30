# Spec §14: Background Task Architecture (Celery)

*Full spec index: see [spec.md](spec.md)*

---

## 14. Background Task Architecture (Celery)

Redis broker + result backend. Fly.io hosts FastAPI app and Celery worker as separate services (`airecruiterz-api` and `airecruiterz-worker`).

### 14.1 Talent Scout Task Chain

```
Task 1: talent_scout.discover_candidates(job_id)
  → iterates all title × location combinations
  → ScrapingDog/BrightData SERP calls with pagination
  → creates candidate records
  → fans out to Tasks 2–5 per candidate (Celery chord)

Task 2: talent_scout.enrich_profile(candidate_id)
  → BrightData LinkedIn People Profiles

Task 3: talent_scout.score_candidate(candidate_id)
  → Claude/OpenAI scoring

Task 4: talent_scout.discover_email(candidate_id)
  → Apollo/Hunter/Snov + EmailDeductionService

Task 5: talent_scout.send_outreach(candidate_id)
  → Claude email generation + SendGrid
```

Parallel concurrency limit: 5 candidates at a time. Progress written to `job_audit_events` → triggers Postgres NOTIFY → SSE.

### 14.2 Scheduled Tasks (Celery Beat)

| Task | Schedule |
|---|---|
| poll_mailboxes | Every 5 minutes |
| send_daily_summaries | Daily 08:00 AEST |
| cleanup_expired_tokens | Daily 00:00 |
| sync_stripe_plans | Hourly |
| rag_refresh | Weekly per tenant (if auto_refresh enabled) |
| process_expired_trials | Daily |

### 14.3 Marketing Tasks (Celery Beat)

| Task | Schedule |
|---|---|
| generate_and_schedule_posts | Daily 02:00 UTC |
| publish_scheduled_posts | Every 15 minutes |
| collect_post_stats | Daily 08:00 UTC |
| auto_engage | Daily 10:00 UTC (marketing queue) |
| refresh_linkedin_tokens | Daily 00:00 UTC |
| post_to_linkedin_groups | Tuesday 09:00 UTC (marketing queue) |

> **Celery task rules**: every task must have `max_retries=3`, exponential backoff (`countdown=2 ** self.request.retries * 30`), idempotency check (verify status before acting), and audit events on both success and failure. Tasks must be idempotent.
>
> **Worker queues**: main worker processes `celery` + `marketing` queues. Marketing queue concurrency = 1 (auto_engage sleeps 2–5 min between actions by design; increasing concurrency causes LinkedIn rate limit violations).
>
> **Task DB engine**: Celery tasks use session pooler (port 5432) not transaction pooler (port 6543) — `_build_task_db_url()` in `database.py` auto-switches. Transaction pooler causes `DuplicatePreparedStatementError` on Celery retries.
