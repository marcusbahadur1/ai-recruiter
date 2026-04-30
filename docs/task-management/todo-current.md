# TODO — AI Recruiter (airecruiterz.com) — Active Items
Last updated: 2026-04-28 (session 33)

*Full index: see [TODO.md](TODO.md)*

## 🔴 Now

- ✅ Register LinkedIn OAuth app at developer.linkedin.com; secrets set on Fly.io (LINKEDIN_CLIENT_ID, LINKEDIN_CLIENT_SECRET, LINKEDIN_REDIRECT_URI, UNSPLASH_ACCESS_KEY)
- ✅ Run `alembic upgrade head` on production DB — migrations 0014–0020 applied (ran locally via session pooler; fixed stale `0012` row in alembic_version that caused overlaps error)
- ✅ Deploy to Fly.io (api + worker + app); tag `v1.2.0`

⚠️ Action required: Regenerate LinkedIn Client Secret — it was shared in chat. Go to developer.linkedin.com → your app → Auth → regenerate, then update Fly.io secret: `fly secrets set LINKEDIN_CLIENT_SECRET=<new> --app airecruiterz-api && fly secrets set LINKEDIN_CLIENT_SECRET=<new> --app airecruiterz-worker`

⏳ LinkedIn MDP (Marketing Developer Platform) approval pending — required for company page posting. Once approved, connect via Marketing → Connect Account in the app UI. Personal profile posting works now.

## 🟡 Next (queued and ready)

All other `main` items complete — see ✅ Done below.

## 🔵 Local Testing (pre-deployment gate)
- ✅ Verify IMAP poller picks up a test email and creates an application record
- ✅ Run `npm run smoke` locally against running app (`e2e/`) — 47/47 passing

## ⚪ Deferred / Parked

- GDPR checklist: DPA prompt on first login, unsubscribe link in outreach emails, GDPR delete functional — deferred until EU market launch
- Post-recruitment interview scheduling via AI chat (§6.5) — requires calendar integration not yet specced
- EU data residency enforcement (separate Supabase region for EU tenants) — infrastructure decision needed
- Enterprise plan onboarding SLA + custom onboarding flow — waiting on enterprise customer
- Upgrade competency test examiner to OpenAI Assistants API — persistent thread per test session, better conversational memory, cleaner back-and-forth probing (`backend/app/routers/applications.py` + `backend/app/tasks/screener_tasks.py`)
