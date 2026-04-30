# TODO — AI Recruiter — Deployment History
Last updated: 2026-04-28 (session 33)

*Full index: see [TODO.md](TODO.md)*

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

- ✅ Create production Supabase project (Sydney, ap-southeast-2) — 11 tables, migration v0012, pgvector enabled
- ✅ Enable RLS on all 10 tables — migration 0013 applied to staging + production; verified via pg_class query
- ⏸ Enable Supabase point-in-time recovery + daily backups — deferred until first paying customer (requires Pro plan)
- ✅ Create Railway production environment — promoted staging env to production; Supabase swapped to Sydney project; ENVIRONMENT=production; EMAIL_TEST_MODE removed; auto-deploys from `main`
- ✅ Create Vercel production environment — `app.airecruiterz.com` live with HTTPS; production Supabase env vars set; `FRONTEND_URL` updated on Railway
- ✅ Configure Stripe production webhook + 3 plan products/prices (Recruiter $499, Agency Small $999, Agency Medium $2,999 AUD/mo); live keys set on Railway + Vercel
- ✅ Configure shared IMAP mail server — `privateemail.com:993` carried over from staging, already set on Railway
- ✅ Set all production env vars — all variables confirmed present on Railway (api + worker)
- ✅ Verify DB connected — `/health` confirmed `"db":"ok"`
- ✅ Signup working end-to-end — 201 response through Vercel proxy confirmed
- ✅ Remove `pwd_hint` and `host` diagnostic fields from `/health` response
- ✅ Railway health check configured — pings `/health` every 30s, auto-restarts on failure (`backend/railway.toml`)
- ✅ Uptime alerting — set up UptimeRobot monitors for Railway API + app.airecruiterz.com (manual step, see instructions)
- ✅ Fix critical production 500 bug — `AsyncSessionLocal` missing import in `main.py`
- ✅ Chat send working on production with SSE streaming restored — single `▋` cursor while waiting
- ✅ Fix `DuplicatePreparedStatementError` — switched main SQLAlchemy engine to `NullPool` in `backend/app/database.py`; eliminates prepared statement conflicts in pgbouncer transaction mode
- ✅ Fix chat history loss between turns — streaming persist now uses explicit UPDATE via fresh `AsyncSessionLocal` (NullPool + FastAPI dependency lifecycle made ORM commit unreliable after async yields); frontend `hydratedRef` prevents React Query re-fetch from overwriting `sessionId` mid-conversation (`backend/app/routers/chat_sessions.py`, `frontend/app/[locale]/(dashboard)/chat/page.tsx`)
- ✅ Fix signup error message — human-readable message when email already exists instead of raw JSON (`backend/app/routers/auth.py`)
- ✅ Fix super admin nav not appearing — replaced `NEXT_PUBLIC_SUPER_ADMIN_EMAIL` env var check with backend API probe (`frontend/app/[locale]/(dashboard)/layout.tsx`); confirmed Email Test Mode toggle working in production
- ✅ Vercel deploy process confirmed — GitHub auto-deploy unreliable; use `~/.local/bin/vercel --prod --scope marcusbahadur1s-projects` from `frontend/` directory
- ✅ Fix streaming payment shortcut — job creation now bypasses AI for confirm/cancel, same as non-streaming path
- ✅ Production smoke test: automated Playwright suite — 14 tests, auto-creates/deletes test account, full chat→job flow verified; run with `npm run prod:all` from `e2e/`
