# TODO — AI Recruiter — Completed Items (Recent)
Last updated: 2026-04-28 (session 33)

*Full index: see [TODO.md](TODO.md) | Older completed items: [todo-done-historical.md](todo-done-historical.md)*

## ✅ Done (Recent)

- ✅ Fly.io migration complete — all three apps deployed and healthy (`airecruiterz-api`, `airecruiterz-worker`, `airecruiterz-app` in `syd`); SSL cert issued for `app.airecruiterz.com`; Stripe webhook updated to Fly.io URL; `next.config.ts` TypeScript type fix applied and deployed

- Railway worker healthcheck fix — removed `healthcheckPath`/`healthcheckTimeout` from `backend/railway.toml`; set healthcheck directly on api service via Railway GraphQL API; worker now deploys `SUCCESS` on every GitHub push (was failing since April 22nd)

- Email Test Mode toggle in super admin UI — `platform_settings.py` service stores state in Redis (`platform:email_test_mode`, `platform:email_test_recipient`); `GET/POST /super-admin/email-test-mode` endpoints; toggle card + persistent amber warning banner in super admin page; Celery worker reads from Redis at task runtime so no restart needed; env var `EMAIL_TEST_MODE` retained as cold-start fallback

- RLS security fix — migration `0013` enables `ROW LEVEL SECURITY` + `FORCE ROW LEVEL SECURITY` on all 10 tables; resolves Supabase `rls_disabled_in_public` + `sensitive_columns_exposed` alerts; verified on staging and production
- Fixed `migrations/env.py` — was hardcoded to `DATABASE_URL`; now reads `SQLALCHEMY_DATABASE_URL` + `DB_PASSWORD` matching `database.py` pattern; `alembic upgrade head` now works locally
- Environment files — `backend/.env-staging` and `backend/.env-production` created with all keys sourced from Railway; gitignored (GitHub push protection blocks plaintext secrets); `.env.example` updated as full variable reference

- AI chat streaming — `POST /chat-sessions/{id}/message/stream` SSE endpoint; tokens stream from Claude in real time; message field extracted from JSON mid-stream; all messages go to AI
- AI chat welcome message renders instantly on page load (removed isLoading gate)
- Diagnosed Railway UptimeRobot downtime as deploy-triggered restart — not a persistent issue
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
