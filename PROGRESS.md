# PROGRESS — AI Recruiter (airecruiterz.com)
Last updated: 2026-04-13

## Summary

The backend is feature-complete. The frontend is complete for all core pages.
All "Now" sprint items are done. Dashboard has a live Kanban pipeline board. Remaining work is Playwright E2E tests, i18n verification, and deployment.

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
- `rag.py` — scrape, upload (PDF/DOCX/TXT), delete; plan-gated (agency_small+)
- `widget.py` — public POST /widget/{slug}/chat, rate-limited, RAG-backed
- `super_admin.py` — tenant list/patch, impersonation (logged), platform keys, health, audit view
- `billing.py` — Stripe Customer Portal + plan management
- `rag_pipeline.py` service — crawl4ai→httpx fallback scraper, chunking (500 tokens), pgvector cosine query
- `crypto.py` — Fernet encryption for tenant API keys
- 12 Jinja2 email templates (all per spec)
- 43 new tests (242 total)

### Session 10 — Dashboard Kanban Board + Static Mockup
- Created `mockup.html` in project root — self-contained static dashboard UI mockup (dark sidebar, stat cards, Kanban board, active jobs, activity feed) for design reference
- Added Kanban candidate pipeline board to dashboard (`/`) between stat cards and Active Jobs panel — five colour-coded columns: NEW (cyan), SCREENED (amber), INTERVIEWED (purple), OFFERED (green), HIRED (teal)
- Kanban initially built with dummy data, then replaced with live `candidatesApi.list()` calls
- `Candidate.status` enum values mapped to columns: discovered/profiled/scored → NEW, passed/emailed/applied → SCREENED, tested/interviewed → INTERVIEWED; OFFERED/HIRED intentionally empty (no matching status values in schema yet)
- Job filter dropdown re-fetches with `?job_id=` when changed; populates from `activeJobs` already loaded on the dashboard
- Column counts reflect real candidate counts; cards link to `/candidates/{id}`
- Avatar colour derived deterministically from candidate id; initials generated from real name
- `failed`/`rejected` candidates excluded from board entirely

### Session 9 — Widget Branding Config
- Widget colour/branding config section in Settings → Chat Widget: saves `widget_primary_color` and `widget_bot_name` per tenant
- `widget_primary_color` (String 20) and `widget_bot_name` (String 100) added to `tenants` model + `TenantUpdate` + `TenantResponse` schemas
- Alembic migration `0012` — `widget_primary_color`, `widget_bot_name` columns (applied)
- Settings page: loads saved widget config from tenant on mount; bot name text input; "Save Widget Settings" button (disabled on plans without widget access)
- Embed snippet updates live as colour/name changes; `botName` line included only when set
- `widget.js` reads `config.botName`, initialises header on load without API round-trip
- GDPR Delete button on `/candidates/{id}` confirmed fully implemented — no changes needed

### Session 8 — Frontend Pages + Bug Fixes
- Built `/billing` — plan card, credits bar, Stripe portal/subscribe CTA, plan comparison grid
- Built `/settings/knowledge-base` — stats, scrape history timeline, chunk preview, re-scrape (deduped), re-scrape all, drag-and-drop upload, URL scraper, plan guard
- Built `/settings/ai-recruiter` — plain-English system prompt editor, save + reset to default, "Custom prompt active" badge
- `recruiter_system_prompt` TEXT column added to `tenants` model + `TenantUpdate` + `TenantResponse` schemas
- `chat_sessions.py` uses tenant's custom prompt for job_collection phase when set; falls back to hardcoded default
- Alembic migration `0011` — `recruiter_system_prompt TEXT NULL` on tenants (applied)
- Removed duplicate "AI Recruiter Prompt" tab from `/settings` page (now lives only at sub-page)
- Added sidebar nav entries: Billing, Knowledge Base, AI Recruiter Prompt
- Added staging smoke test suite: 8 Playwright specs + `staging-smoke.yml` GitHub Actions workflow
- Bug fix: `rag_pipeline._store_chunk` — `async with db.begin()` created savepoint inside autobegun transaction; outer transaction never committed so all scraped chunks were silently discarded. Fixed with explicit `db.flush() + db.commit()`
- Bug fix: `rag_pipeline._crawl` — `crawl4ai` could hang indefinitely when Playwright can't launch a browser (WSL2); added `asyncio.wait_for(..., timeout=30.0)` so it falls back to httpx+BeautifulSoup after 30 s
- Bug fix: `rag.py` plan gate used wrong plan names (`small_firm`, `mid_firm`) — corrected to `agency_small`, `agency_medium`
- Bug fix: dashboard layout `<main>` had `overflow:hidden` — page content below viewport was inaccessible; changed to `overflowY:auto`

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
| Migrations | Complete | 13 Alembic versions (0001–0012 + user_id patch) |
| Unit tests | Complete | 17 test files, ~120 tests |
| Integration tests | Complete | 15 test files, ~122 tests |
| E2E tests | **Not started** | Playwright, 5 scenarios in SPEC §18.3 |

### Frontend (`frontend/`)

| Page | Route | Status |
|---|---|---|
| Login | `/login` | Done |
| Sign Up | `/signup` | Done |
| Home / Stats | `/` | Done |
| AI Recruiter Chat | `/chat` | Done |
| Chat History | `/chat/history` | Done |
| Jobs List | `/jobs` | Done |
| New Job (Scout) | `/jobs/new` | Done |
| New Job (Screener) | `/jobs/new/screener` | Done |
| Job Detail | `/jobs/{id}` | Done |
| Candidates List | `/candidates` | Done |
| Candidate Profile | `/candidates/{id}` | Done |
| Applications List | `/applications` | Done |
| Application Detail | `/applications/{id}` | Done |
| Settings | `/settings` | Done |
| Settings: Knowledge Base | `/settings/knowledge-base` | Done |
| Settings: AI Recruiter Prompt | `/settings/ai-recruiter` | Done |
| Billing | `/billing` | Done |
| Super Admin | `/super-admin` | Done |
| Help | `/help` | Done |
| Quick Start | `/quickstart` | Done |
| Competency Test | `/test/{id}/{token}` | Done |
| Interview Invited | `/interview-invited` | Done |
| Subscribe | `/subscribe` | Done |
| Billing Success | `/billing/success` | Done |
| Unsubscribe | `/unsubscribe/{candidateId}` | Done |
| Embeddable Widget JS | `public/widget/widget.js` | Done |
| Static Mockup | `mockup.html` (project root) | Done |

### i18n
- Message files: EN, DE, ES, FR — exist in `frontend/messages/`
- Completeness of DE/ES/FR for billing and widget config UI strings: unverified

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
| 8 | 0 (frontend + bug fixes only) | 242 |

**Current total: 242 tests** (unit + integration). E2E: 0.

---

## Known Issues

- `test_super_admin_audit_requires_super_admin_role` in `tests/integration/test_audit.py` makes a real Supabase HTTP call and fails in CI without live DB — pre-existing, not introduced in session 7.
- `resume_screener.py` is not a standalone service file (screener logic lives in `screener_tasks.py` directly) — diverges slightly from SPEC §19 file list but is functionally equivalent.
- DE/ES/FR translations for billing and widget config UI strings added in session 7–8 have not been verified for completeness.
