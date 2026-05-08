# System Map — Backend

see SYSTEM_MAP_FRONTEND.md for frontend modules and unusual couplings

---

## Layer Overview

```
[Browser]   Next.js 16 App Router + next-intl
               ↓ relative /api/v1/* (proxy.ts rewrites)
[API]       FastAPI (uvicorn async) — airecruiterz-api, Fly.io syd
               ↓ SQLAlchemy NullPool, port 6543 (transaction pooler)
[DB]        Supabase PostgreSQL + pgvector (ap-southeast-2)
               ↑ Celery tasks, NullPool, port 5432 (session pooler)
[Worker]    Celery + Redis — airecruiterz-worker, Fly.io syd
               ↓ BrightData, ScrapingDog, Apollo, Hunter, Snov,
                 SendGrid, Stripe, LinkedIn, OpenAI, Anthropic
```

---

## Backend Modules (`backend/app/`)

| Module | Owns | Must never |
|--------|------|-----------|
| `main.py` | App factory, middleware, router mounting | Business logic |
| `config.py` | Settings singleton, PLAN_LIMITS, email test flag | DB access |
| `database.py` | Two engines + session factories, `_build_task_db_url()` | Add connection pooling |
| `models/` | SQLAlchemy ORM table definitions | Call services or emit events |
| `schemas/` | Pydantic v2 request/response models | DB access |
| `routers/` | HTTP handlers, auth injection | Call AI SDKs directly |
| `services/` | Business logic, external API wrappers | — |
| `tasks/` | Celery task wrappers | Nest asyncio.run() calls |
| `templates/` | Jinja2 email templates | Logic |

## Key Services

| Service | Responsibility |
|---------|---------------|
| `ai_provider.py` | Unified AI facade — primary + fallback routing |
| `claude_ai.py` / `openai_ai.py` | SDK wrappers (complete, stream, JSON) |
| `talent_scout.py` | SERP query builder, audit event helpers |
| `scrapingdog.py` / `brightdata.py` | LinkedIn SERP + profile enrichment |
| `apollo.py` / `hunter.py` / `snov.py` | Email discovery providers |
| `email_deduction.py` | Pattern-based email guess + SMTP verify |
| `sendgrid_email.py` | Outbound email (tenant-branded) |
| `rag_pipeline.py` | Scrape → chunk → embed → store → query |
| `embeddings.py` | OpenAI text-embedding-3-small (sync/async) |
| `crypto.py` | Fernet encrypt/decrypt for all secrets |
| `audit_trail.py` | Structured event emission to `job_audit_events` |
| `marketing_content.py` | AI post generation + Unsplash images |
| `linkedin_api.py` | LinkedIn post publish + token refresh |

## Key Task Files

| File | Tasks |
|------|-------|
| `talent_scout_tasks.py` | `discover_candidates`, `enrich_profile`, `score_candidate`, `discover_email`, `send_outreach` |
| `screener_tasks.py` | `poll_mailboxes`, `screen_resume`, `invite_to_test`, `score_test`, `notify_hiring_manager`, `send_rejection_email` |
| `scheduled_tasks.py` | `send_daily_summaries`, `cleanup_expired_tokens`, `sync_stripe_plans`, `rag_refresh`, `process_expired_trials` |
| `marketing_tasks.py` | `generate_and_schedule_posts`, `publish_scheduled_posts`, `collect_post_stats`, `auto_engage`, `refresh_linkedin_tokens` |
