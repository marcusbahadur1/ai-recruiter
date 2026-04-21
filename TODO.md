# TODO — AI Recruiter (airecruiterz.com)
Last updated: 2026-04-21 (session 19)

## 🔴 Now (current sprint / active work)

All Now items complete — see ✅ Done below.

## 🟡 Next (queued and ready)

All Now items complete — see ✅ Done below.

## 🔵 Local Testing (pre-deployment gate)
- ✅ Verify IMAP poller picks up a test email and creates an application record
- ✅ Run `npm run smoke` locally against running app (`e2e/`) — 47/47 passing

## 🟣 Staging Deployment

- ✅ Create staging Supabase project — apply schema via Alembic migrations, enable pgvector + RLS
- ✅ Seed staging DB with anonymised copy of production data (`pg_dump --data-only` with PII scrubbed)
- ✅ Create Railway staging environment — deploy FastAPI + Celery worker + Redis from `main` branch
- ✅ Create Vercel staging environment — point at staging Railway API + staging Supabase
- ✅ Configure staging Stripe webhook endpoint → staging Railway URL
- ✅ Add GitHub secrets: `STAGING_URL`, `STAGING_API_URL`, `STAGING_TEST_EMAIL`, `STAGING_TEST_PASSWORD`
- ✅ Set remaining staging env vars — `SENDGRID_API_KEY`, `ANTHROPIC_API_KEY`, `SCRAPINGDOG_API_KEY`, `BRIGHTDATA_API_KEY`, `ENCRYPTION_KEY`, `OPENAI_API_KEY`, `STRIPE_SECRET_KEY`, `SUPER_ADMIN_EMAIL`, `FRONTEND_URL`, `ENVIRONMENT` all confirmed set on Railway (api + worker)
- ✅ Run `npm ci && npx playwright install` in `e2e/` to generate `package-lock.json` for CI cache — already committed in session 15
- ✅ Trigger `staging-smoke.yml` manually — 47/47 smoke tests passing against staging
- ✅ Manually sign off staging — all features confirmed working

## 🟠 Production Deployment

- ✅ Create production Supabase project (Sydney, ap-southeast-2) — 11 tables, migration v0012, pgvector + RLS enabled
- ⏸ Enable Supabase point-in-time recovery + daily backups — deferred until first paying customer (requires Pro plan)
- ✅ Create Railway production environment — promoted staging env to production; Supabase swapped to Sydney project; ENVIRONMENT=production; EMAIL_TEST_MODE removed; auto-deploys from `main`
- ✅ Create Vercel production environment — `app.airecruiterz.com` live with HTTPS; production Supabase env vars set; `FRONTEND_URL` updated on Railway
- ✅ Configure Stripe production webhook + 3 plan products/prices (Recruiter $499, Agency Small $999, Agency Medium $2,999 AUD/mo); live keys set on Railway + Vercel
- ✅ Configure shared IMAP mail server — `privateemail.com:993` carried over from staging, already set on Railway
- ✅ Set all production env vars — all variables confirmed present on Railway (api + worker)
- ✅ Verify DB connected — `/health` confirmed `"db":"ok"`
- ✅ Signup working end-to-end — 201 response through Vercel proxy confirmed
- Remove `pwd_hint` and `host` diagnostic fields from `/health` response (cleanup)
- Run final smoke test on production: sign up → post job → verify full pipeline
- GDPR checklist: DPA prompt on first login, unsubscribe link in outreach emails, GDPR delete functional
- Set up Railway health checks + uptime alerting

## ⚪ Deferred / Parked

- Post-recruitment interview scheduling via AI chat (§6.5) — requires calendar integration not yet specced
- EU data residency enforcement (separate Supabase region for EU tenants) — infrastructure decision needed
- Enterprise plan onboarding SLA + custom onboarding flow — waiting on enterprise customer
- Upgrade competency test examiner to OpenAI Assistants API — persistent thread per test session, better conversational memory, cleaner back-and-forth probing (`backend/app/routers/applications.py` + `backend/app/tasks/screener_tasks.py`)

## ✅ Done

- Frontend smoke test: full walkthrough complete — signup, email confirmation, post job via AI chat, jobs, candidates, applications, settings, billing all working correctly
- SSE streams verified: Evaluation Report + Audit Trail both show live activity on `/jobs/{id}`
- Supabase email confirmation enabled; custom SMTP via SendGrid configured (sender: marcus.bahadur@aiworkerz.com); confirmation email template updated to AIRecruiterz branding
- Backend smoke test: Swagger UI loads at `http://localhost:8000/docs`, all 19 routers registered
- Verified all `scheduled_tasks.py` beat tasks fully implemented: `send_daily_summaries`, `cleanup_expired_tokens`, `sync_stripe_plans`, `rag_refresh`, `process_expired_trials`

- Playwright E2E test: recruiter posts job via AI chat → verify job created in DB (`e2e/tests/01-job-via-chat.spec.ts`)
- Playwright E2E test: candidate completes competency test → `test_status` updated (`e2e/tests/02-competency-test.spec.ts`)
- Playwright E2E test: hiring manager clicks Invite to Interview → confirmation page shown (`e2e/tests/03-invite-to-interview.spec.ts`)
- Playwright E2E test: super admin impersonates tenant → scoped data access verified (`e2e/tests/04-super-admin-impersonation.spec.ts`)
- Playwright E2E test: switch locale to DE/ES/FR → translated UI renders (`e2e/tests/05-locale-switching.spec.ts`)

- i18n: `billing` namespace (29 keys) + `settings.widget*` (15 keys) added to DE/ES/FR; wired in `billing/page.tsx`, `settings/page.tsx`, `layout.tsx` sidebar nav
- Fixed all 52 failing tests — 294 unit + integration tests, 0 failures (`backend/tests/`)
- Fixed Alembic migration `fd821988c15c` — `tenants.user_id` was never added on fresh installs; rewrote migration properly
- Fixed `super_admin.py` `TenantAdminUpdate.plan` Literal — stale plan names updated to current schema

- Bug fix: `GET /candidates` limit cap raised from 100 → 500; Kanban board's `limit=200` request was returning 422 (`backend/app/routers/candidates.py`)
- Bug fix: Removed "Add candidate" buttons from all Kanban pipeline columns (`frontend/app/[locale]/(dashboard)/page.tsx`)

- Dashboard Kanban candidate pipeline board — live data from `candidatesApi.list()`, 5 stage columns, job filter, card links to candidate profile (`frontend/app/[locale]/(dashboard)/page.tsx`)
- Created `mockup.html` — static self-contained dashboard UI mockup for design reference (project root)
- Add widget colour/branding config section to `/settings` — `widget_primary_color`, `widget_bot_name` saved per tenant; migration 0012 applied (`frontend/app/[locale]/(dashboard)/settings/page.tsx`)
- Build embeddable chat widget JS snippet (`frontend/public/widget/widget.js`)
- Wire live SSE for Evaluation Report + Audit Trail on `/jobs/{id}` (`frontend/app/[locale]/(dashboard)/jobs/[id]/page.tsx`)
- Implement GDPR Delete button on `/candidates/{id}` — confirmed already implemented, no changes needed

- Database models: tenant, job, candidate, application, chat_session, rag_document, job_audit_event, promo_code (`backend/app/models/`)
- Pydantic v2 schemas for all models (`backend/app/schemas/`)
- FastAPI app factory, config, database session, Supabase JWT middleware (`backend/app/`)
- Auth router: signup, login (`backend/app/routers/auth.py`)
- Tenant + Job + Candidate + Application + Chat Sessions + Audit + RAG + Widget + Promo Codes + Super Admin + Webhooks routers (`backend/app/routers/`)
- AI provider facade: Claude Sonnet + OpenAI, tenant-switchable (`backend/app/services/ai_provider.py`)
- Services: ScrapingDog, BrightData, Apollo, Hunter, Snov, EmailDeductionService, embeddings, rag_pipeline, audit_trail, GDPR, SendGrid, crypto (`backend/app/services/`)
- Celery app + Talent Scout pipeline tasks (discover → enrich → score → email) (`backend/app/tasks/talent_scout_tasks.py`)
- Resume Screener Celery tasks: IMAP poller, screen_resume, invite_to_test, score_test (`backend/app/tasks/screener_tasks.py`)
- AI examiner chat for competency test (`backend/app/routers/applications.py`)
- 12 Jinja2 email templates (outreach, rejection, test invite/reject, HM invite, daily summary, welcome, payment failed, promo, GDPR) (`backend/app/templates/`)
- 242 unit + integration tests across all services and routes (`backend/tests/`)
- 12 Alembic migrations (`backend/migrations/versions/`)
- Frontend auth pages: login, signup (`frontend/app/[locale]/(auth)/`)
- Frontend dashboard home (`/`) — stats overview (`frontend/app/[locale]/(dashboard)/page.tsx`)
- Frontend chat page (`/chat`) — server-loaded history, 16-step job flow (`frontend/app/[locale]/(dashboard)/chat/page.tsx`)
- Frontend chat history page (`/chat/history`)
- Frontend jobs list (`/jobs`), job detail (`/jobs/{id}`), new job Scout (`/jobs/new`), new job Screener (`/jobs/new/screener`)
- Frontend candidates list (`/candidates`) and profile page (`/candidates/{id}`)
- Frontend applications list (`/applications`) and detail (`/applications/{id}`)
- Frontend billing dashboard (`/billing`) — plan card, credits bar, plan comparison, Stripe portal button (`frontend/app/[locale]/(dashboard)/billing/`)
- Settings: Knowledge Base sub-page (`/settings/knowledge-base`) — stats, per-source cards, scrape history timeline, chunk preview, re-scrape (deduped), re-scrape all, drag-and-drop upload, URL scraper (`frontend/app/[locale]/(dashboard)/settings/knowledge-base/`)
- Settings: AI Recruiter Prompt sub-page (`/settings/ai-recruiter`) — plain-English prompt editor, save + reset to default, custom prompt badge (`frontend/app/[locale]/(dashboard)/settings/ai-recruiter/`)
- Frontend settings page (`/settings`) — API keys, email, team, AI provider, widget config (`frontend/app/[locale]/(dashboard)/settings/`)
- Frontend super admin panel (`/super-admin`)
- Frontend help page (`/help`) and quick start page (`/quickstart`)
- Public pages: competency test (`/test/{id}/{token}`), interview-invited, subscribe, unsubscribe, billing success
- i18n message files: EN, DE, ES, FR (`frontend/messages/`)
- GitHub Actions CI workflow — lint + pytest + Docker build (`ci.yml`)
- Automated staging smoke test suite — 8 Playwright spec files + auth setup (`e2e/tests/smoke/`)
- GitHub Actions staging smoke workflow — auto-triggers after CI passes, waits for staging health, uploads failure artifacts (`staging-smoke.yml`)
- Bug fix: `rag_pipeline._store_chunk` — savepoint never committed outer transaction; fixed with explicit `flush() + commit()`
- Bug fix: `rag_pipeline._crawl` — crawl4ai could hang indefinitely on WSL2; added `asyncio.wait_for(..., timeout=30)`
- Bug fix: `rag.py` plan gate — wrong plan names (`small_firm/mid_firm`) corrected to `agency_small/agency_medium`
- Bug fix: dashboard layout `main` had `overflow:hidden` cutting off page content; changed to `overflowY:auto`
- `recruiter_system_prompt` TEXT column added to tenants model + migration 0011; `chat_sessions.py` uses it when set
