# TODO — AI Recruiter (airecruiterz.com) — Active Items
Last updated: 2026-05-13 (session 42)

*Full index: see [TODO.md](TODO.md)*

## 🔴 Now — Client Pipeline

- ✅ **Phase 1 complete** — 7 new DB tables (migration 0024), `marketing_settings` extended, 6-tab shell at `/en/marketing`, sidebar label updated to "Client pipeline". Run `alembic upgrade head` on production to apply.
- ✅ **Phase 2 complete** — Settings tab built: ICP targeting, Channels (LinkedIn/BrightData/Hunter/SMTP), Signal config, Outreach limits, Tenant mode. Backend schemas extended. GET/PATCH `/api/marketing/settings` updated to expose pipeline JSONB fields.
- ✅ **Phase 3 complete** — Prospects tab: search/filter/sort toolbar, paginated table, ICP score circle with breakdown tooltip, stage pills, contextual action buttons, slide-over detail panel, add-prospects modal (BrightData scrape), Hunter.io email enrichment, enroll in sequence. Migration 0025 applied (extra prospect columns). 6 API routes.
- ✅ **Phase 4 complete** — Pipeline tab: 5-metric bar (delta + pct labels), div-based conversion funnel (blue ramp), live signals with action/dismiss, recent prospect activity table, active sequences with reply rate. 3 new API routes. `MarketingSignal` + `MarketingSequence` models added.
- ✅ **Phase 5 complete** — Signals tab: config bar (scrape freq + last run), 4 type tiles, signal feed (urgency-sorted, per-type actions, dismiss), "Run now" with Celery task + polling. Migration 0026 applied. Run `alembic upgrade head` on production.
- ✅ **Phase 6 complete** — Sequences tab: left panel (list + channel pills + status dots), right panel (step editor with debounced auto-save, performance metrics, inline name edit, status dropdown), new-sequence wizard (2-step: basics → AI-generate → edit → save), enroll modal. Backend: 10 routes, `process_enrollments` Celery task (15-min beat), migration 0027 (`step_name` column).
- ✅ **Phase 7 complete** — Content tab: post queue (Draft/Scheduled/Posted/Failed sub-tabs), post cards with type chips + metrics + attribution, Generate modal with AI-backed ROI/Pain/Proof/Tip prompts, inline edit/regenerate/discard/schedule actions, right panel stats (performance + content mix bar + upcoming schedule). Migration 0028 (connections_attributed + demos_attributed). New router: marketing_content.py (5 routes). Run `alembic upgrade head` on production.
- ✅ **Phase 8 complete** — Tenant mode: plan gating in sidebar (hidden if disabled, locked+UPGRADE badge if plan_too_low), upgrade modal → /billing, onboarding banner (first visit), LinkedIn-not-connected amber warning, BrightData replaced with "Platform managed" note for tenants, usage meters (prospects/sequences vs limits), admin tenant-usage table in SettingsTab, 429/400 enforcement on scrape + sequence create, `GET /marketing/tenant-status` + `GET /marketing/admin/tenant-usage` routes, `TenantStatusResponse` + `AdminTenantUsageResponse` schemas.

## 🔴 Previous Now

- ✅ Register LinkedIn OAuth app at developer.linkedin.com; secrets set on Fly.io (LINKEDIN_CLIENT_ID, LINKEDIN_CLIENT_SECRET, LINKEDIN_REDIRECT_URI, UNSPLASH_ACCESS_KEY)
- ✅ Run `alembic upgrade head` on production DB — migrations 0014–0020 applied (ran locally via session pooler; fixed stale `0012` row in alembic_version that caused overlaps error)
- ✅ Deploy to Fly.io (api + worker + app); tag `v1.2.0`

⚠️ Action required: Regenerate LinkedIn Client Secret — it was shared in chat. Go to developer.linkedin.com → your app → Auth → regenerate, then update Fly.io secret: `fly secrets set LINKEDIN_CLIENT_SECRET=<new> --app airecruiterz-api && fly secrets set LINKEDIN_CLIENT_SECRET=<new> --app airecruiterz-worker`

✅ LinkedIn Showcase Page posting complete — uses native Posts API (no MDP approval needed). Manual step required: add `w_organization_social` scope in LinkedIn Developer Portal (self-service, no review). See `linkedin_client.py` comment block. Run `alembic upgrade head` on production to apply migration 0029.

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
