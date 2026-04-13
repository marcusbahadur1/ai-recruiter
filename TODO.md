# TODO — AI Recruiter (airecruiterz.com)
Last updated: 2026-04-13

## 🔴 Now (current sprint / active work)

All Now items complete — see ✅ Done below.

## 🟡 Next (queued and ready)

- Write Playwright E2E test: recruiter posts job via AI chat → verify job created in DB (`e2e/tests/`)
- Write Playwright E2E test: candidate completes competency test → `test_status` updated (`e2e/tests/`)
- Write Playwright E2E test: hiring manager clicks Invite to Interview → confirmation page shown (`e2e/tests/`)
- Write Playwright E2E test: super admin impersonates tenant → scoped data access verified (`e2e/tests/`)
- Write Playwright E2E test: switch locale to DE/ES/FR → translated UI renders (`e2e/tests/`)
- Verify all `scheduled_tasks.py` beat tasks are fully implemented: `send_daily_summaries`, `cleanup_expired_tokens`, `sync_stripe_plans`, `rag_refresh` (`backend/app/tasks/scheduled_tasks.py`)
- Add i18n translations for billing and widget config UI strings (`frontend/messages/de.json`, `es.json`, `fr.json`)
- Implement Alembic migration for any schema changes from sessions 5–7 not yet covered (`backend/migrations/versions/`)

## 🔵 Local Testing (pre-deployment gate)

- Run full pytest suite locally — all 242 tests must pass (`cd backend && pytest`)
- Start backend + Celery worker locally, smoke test all API routes via Swagger UI (`http://localhost:8000/docs`)
- Start frontend locally, manually walk through: signup → onboarding → post job → candidates → application → test → settings
- Verify SSE streams work locally: Evaluation Report + Audit Trail on `/jobs/{id}`
- Verify IMAP poller picks up a test email and creates an application record
- Run `npm run smoke` locally against running app (`e2e/`) → [depends on: Playwright E2E tests above]

## 🟣 Staging Deployment

- Create staging Supabase project — apply schema via Alembic migrations, enable pgvector + RLS
- Seed staging DB with anonymised copy of production data (`pg_dump --data-only` with PII scrubbed)
- Create Railway staging environment — deploy FastAPI + Celery worker + Redis from `main` branch
- Create Vercel staging environment — point at staging Railway API + staging Supabase
- Configure staging Stripe webhook endpoint → staging Railway URL
- Add GitHub secrets: `STAGING_URL`, `STAGING_API_URL`, `STAGING_TEST_EMAIL`, `STAGING_TEST_PASSWORD`
- Set all other staging env vars (separate keys from production: `STRIPE_SECRET_KEY`, `SENDGRID_API_KEY`, `ANTHROPIC_API_KEY`, etc.)
- Run `npm ci && npx playwright install` in `e2e/` to generate `package-lock.json` for CI cache
- Trigger `staging-smoke.yml` manually — verify all 8 smoke test specs pass against staging
- Manually sign off staging — confirm all features working before promoting to production

## 🟠 Production Deployment

- Create production Supabase project (EU region for GDPR) — run Alembic migrations, enable pgvector + RLS
- Enable Supabase point-in-time recovery + daily backups
- Create Railway production environment — configure auto-deploy from `main` on merge
- Create Vercel production environment — connect custom domain `app.airecruiterz.com`
- Configure Stripe production webhook endpoint → production Railway URL, create all 6 plan products/prices
- Configure shared IMAP mail server — provision per-tenant mailbox routing
- Set all production env vars (live Stripe keys, live SendGrid, live BrightData, etc.)
- Run final smoke test on production: sign up → post job → verify full pipeline
- GDPR checklist: DPA prompt on first login, unsubscribe link in outreach emails, GDPR delete functional
- Set up Railway health checks + uptime alerting

## ⚪ Deferred / Parked

- Post-recruitment interview scheduling via AI chat (§6.5) — requires calendar integration not yet specced
- EU data residency enforcement (separate Supabase region for EU tenants) — infrastructure decision needed
- Enterprise plan onboarding SLA + custom onboarding flow — waiting on enterprise customer
- Upgrade competency test examiner to OpenAI Assistants API — persistent thread per test session, better conversational memory, cleaner back-and-forth probing (`backend/app/routers/applications.py` + `backend/app/tasks/screener_tasks.py`)

## ✅ Done

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
