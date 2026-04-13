# PROGRESS — AI Recruiter (airecruiterz.com)
Last updated: 2026-04-13

## Summary

The backend is feature-complete. The frontend is ~85% complete — all core pages exist, with a small set of missing pages (billing dashboard, promo codes, settings sub-pages, embeddable widget). E2E tests have not been started.

---

## Session History

### Session 1 — Foundation
- Database models: tenant, job, candidate, application, chat_session, rag_document, job_audit_event, promo_code
- Pydantic v2 schemas for all models
- FastAPI app factory, config, database session, asyncpg driver
- Supabase JWT middleware + auth dependency
- Alembic migrations scaffolded

### Session 2 — AI Facade + Integration Services
- `ai_provider.py` facade routing to Claude or OpenAI based on tenant config
- `claude_ai.py`, `openai_ai.py` — full implementations
- `scrapingdog.py`, `brightdata.py` — SERP + LinkedIn profile enrichment
- `apollo.py`, `hunter.io`, `snov.py` — email discovery services
- `email_deduction.py` — SMTP-verified domain deduction fallback
- `embeddings.py` — pgvector embedding generation
- 63 unit tests

### Session 3 — Core Routers
- `auth.py` — signup, login
- `tenants.py` — GET/PATCH /tenants/me
- `jobs.py` — full CRUD + trigger-scout + SSE evaluation report
- `candidates.py` — search/filter, profile, GDPR delete, send-outreach
- `applications.py` — list, detail, trigger-test, public test endpoints, invite-interview action

### Session 4 — Audit Trail + GDPR + Remaining Routers
- `audit.py` — SSE audit stream (asyncpg LISTEN/NOTIFY), paginated history, super admin view
- `audit_trail.py` service — append-only events, GDPR PII redaction in-place
- `gdpr.py` service — erasure, data export, retention flagging
- `gdpr_settings.py`, `team.py`, `search.py`, `dashboard.py`, `screener.py` routers
- 55 new tests (118 total)

### Session 5 — Celery + Talent Scout Pipeline
- `celery_app.py` — Redis broker, beat scheduler
- `talent_scout.py` service — full 5-step pipeline logic
- `talent_scout_tasks.py` — Celery chord: discover → enrich → score → email (parallel, 5 concurrency limit)
- `scheduled_tasks.py` — beat tasks: `poll_mailboxes`, `send_daily_summaries`, `cleanup_expired_tokens`, `sync_stripe_plans`, `rag_refresh`
- 51 new tests (169 total)

### Session 6 — Resume Screener + Chat Sessions
- `screener_tasks.py` — 4 Celery tasks: `poll_mailboxes` (IMAP, runs in thread executor), `screen_resume`, `invite_to_test`, `score_test`
- `applications.py` updated — AI examiner (Claude) for competency test chat, probing follow-ups, triggers `score_test.delay()` on completion
- `chat_sessions.py` — full implementation: GET /current, POST /new, POST /{id}/message
  - Phase-aware prompts: job_collection (16-step JSON) → payment → recruitment (plain text)
  - Phase transitions driven by JSON responses from AI, not prompt instructions
- 36 new tests (205 total)

### Session 7 — Billing, RAG, Widget, Email Templates, Super Admin
- `webhooks.py` — Stripe (4 events: checkout, invoice paid/failed, subscription deleted) + email HMAC webhook
- `promo_codes.py` — full CRUD + public validate endpoint
- `rag.py` — scrape, upload (PDF/DOCX/TXT), delete; plan-gated (small_firm+)
- `widget.py` — public POST /widget/{slug}/chat, rate-limited, RAG-backed
- `super_admin.py` — tenant list/patch, impersonation (logged), platform keys, health, audit view
- `billing.py` — Stripe Customer Portal + plan management
- `rag_pipeline.py` service — crawl4ai→httpx fallback scraper, chunking (500 tokens), pgvector cosine query
- `crypto.py` — Fernet encryption for tenant API keys
- 12 Jinja2 email templates (all per spec)
- 43 new tests (242 total)

---

## Current State by Layer

### Backend (`backend/`)

| Area | Status | Notes |
|---|---|---|
| Models | Complete | 8 models, all with tenant_id |
| Schemas | Complete | Pydantic v2 throughout |
| Routers | Complete | 19 routers registered in main.py |
| Services | Complete | 16 services |
| Celery tasks | Complete | talent_scout_tasks, screener_tasks, scheduled_tasks |
| Email templates | Complete | 12 Jinja2 HTML templates |
| Migrations | Complete | 11 Alembic versions (0001–0010 + user_id patch) |
| Unit tests | Complete | 17 test files, ~120 tests |
| Integration tests | Complete | 15 test files, ~122 tests |
| E2E tests | **Not started** | Playwright, 5 scenarios in SPEC §18.3 |

### Frontend (`frontend/`)

| Page | Route | Status |
|---|---|---|
| Login | `/login` | Done |
| Sign Up | `/signup` | Done |
| Home / Stats | `/` | Done (222 lines) |
| AI Recruiter Chat | `/chat` | Done (216 lines) |
| Chat History | `/chat/history` | Done |
| Jobs List | `/jobs` | Done |
| New Job (Scout) | `/jobs/new` | Done |
| New Job (Screener) | `/jobs/new/screener` | Done |
| Job Detail | `/jobs/{id}` | Done (380 lines) |
| Candidates List | `/candidates` | Done |
| Candidate Profile | `/candidates/{id}` | Done (306 lines) |
| Applications List | `/applications` | Done |
| Application Detail | `/applications/{id}` | Done (382 lines) |
| Settings | `/settings` | Done (1035 lines) |
| Settings: Knowledge Base | `/settings/knowledge-base` | **Missing** |
| Settings: AI Recruiter | `/settings/ai-recruiter` | **Missing** |
| Billing | `/billing` | **Missing** |
| Promo Codes | `/promo-codes` | **Missing** |
| Super Admin | `/super-admin` | Done (353 lines) |
| Help | `/help` | Done (321 lines) |
| Quick Start | `/quickstart` | Done (210 lines) |
| Competency Test | `/test/{id}/{token}` | Done (483 lines) |
| Interview Invited | `/interview-invited` | Done |
| Subscribe | `/subscribe` | Done (294 lines) |
| Billing Success | `/billing/success` | Done |
| Unsubscribe | `/unsubscribe/{candidateId}` | Done |
| Embeddable Widget JS | `public/widget/widget.js` | **Missing** |

### i18n
- Message files: EN, DE, ES, FR — exist in `frontend/messages/`
- Completeness of DE/ES/FR for sessions 6–7 UI strings: unverified

---

## Test Count History

| Session | New Tests | Total |
|---|---|---|
| 1–2 | 63 | 63 |
| 3 | ~55 | ~118 |
| 4 | 55 | ~118 |
| 5 | 51 | 169 |
| 6 | 36 | 205 |
| 7 | 43 | 242 |

**Current total: 242 tests** (unit + integration). E2E: 0.

---

## Known Issues

- `test_super_admin_audit_requires_super_admin_role` in `tests/integration/test_audit.py` makes a real Supabase HTTP call and fails in CI without live DB — pre-existing, not introduced in session 7.
- `resume_screener.py` is not a standalone service file (screener logic lives in `screener_tasks.py` directly) — diverges slightly from SPEC §19 file list but is functionally equivalent.
