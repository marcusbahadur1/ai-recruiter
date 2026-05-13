# TODO — AI Recruiter (airecruiterz.com) — Active Items
Last updated: 2026-05-13 (session 37)

*Full index: see [TODO.md](TODO.md)*

## 🔴 Now — Client Pipeline

- ✅ **Phase 1 complete** — 7 new DB tables (migration 0024), `marketing_settings` extended, 6-tab shell at `/en/marketing`, sidebar label updated to "Client pipeline". Run `alembic upgrade head` on production to apply.
- Phase 2 — Prospects tab: list view, add/edit form, ICP score badge, stage kanban or table
- Phase 3 — Signals tab: signal cards, urgency badge, action/dismiss flow
- Phase 4 — Sequences tab: sequence list, step builder UI
- Phase 5 — Content tab: content calendar, post composer
- Phase 6 — Settings tab: ICP config, outreach limits, channel config forms
- Phase 7 — Backend: FastAPI routers + Pydantic schemas for all 7 new tables
- Phase 8 — Celery tasks: signal scraping (BrightData), sequence execution, outreach scheduling

## 🔴 Previous Now

- ✅ Register LinkedIn OAuth app at developer.linkedin.com; secrets set on Fly.io (LINKEDIN_CLIENT_ID, LINKEDIN_CLIENT_SECRET, LINKEDIN_REDIRECT_URI, UNSPLASH_ACCESS_KEY)
- ✅ Run `alembic upgrade head` on production DB — migrations 0014–0020 applied (ran locally via session pooler; fixed stale `0012` row in alembic_version that caused overlaps error)
- ✅ Deploy to Fly.io (api + worker + app); tag `v1.2.0`

⚠️ Action required: Regenerate LinkedIn Client Secret — it was shared in chat. Go to developer.linkedin.com → your app → Auth → regenerate, then update Fly.io secret: `fly secrets set LINKEDIN_CLIENT_SECRET=<new> --app airecruiterz-api && fly secrets set LINKEDIN_CLIENT_SECRET=<new> --app airecruiterz-worker`

⏳ LinkedIn MDP (Marketing Developer Platform) approval pending — required for company page posting. Once approved, connect via Marketing → Connect Account in the app UI. Personal profile posting works now.

## 🟡 Next (queued and ready)

- Add Hunter.io free tier API key to tenant settings — `domain_deduction` alone finds ~0% real candidate emails; Hunter (25 free/mo) is the practical minimum for Scout email delivery to work in production
- ✅ Fix AI model defaults to cheapest tiers (Haiku 4.5 / gpt-4o-mini) — done session 36
- ✅ Fix outbound email sender (platform verified sender + per-tenant display name) — done session 36
- ✅ Full end-to-end live test: 26/26 PASS — done session 36

## 🔵 Local Testing (pre-deployment gate)
- ✅ Verify IMAP poller picks up a test email and creates an application record
- ✅ Run `npm run smoke` locally against running app (`e2e/`) — 47/47 passing

## ⚪ Deferred / Parked

- GDPR checklist: DPA prompt on first login, unsubscribe link in outreach emails, GDPR delete functional — deferred until EU market launch
- Post-recruitment interview scheduling via AI chat (§6.5) — requires calendar integration not yet specced
- EU data residency enforcement (separate Supabase region for EU tenants) — infrastructure decision needed
- Enterprise plan onboarding SLA + custom onboarding flow — waiting on enterprise customer
- Upgrade competency test examiner to OpenAI Assistants API — persistent thread per test session, better conversational memory, cleaner back-and-forth probing (`backend/app/routers/applications.py` + `backend/app/tasks/screener_tasks.py`)
