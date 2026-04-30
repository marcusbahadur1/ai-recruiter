# PROGRESS — Sessions 11–13 (Bug Fixes + i18n + E2E Tests)

*Full index: see [PROGRESS.md](PROGRESS.md)*

---

### Session 13 — Playwright E2E Tests
- 5 Playwright E2E specs written covering all SPEC §18.3 scenarios:
  - `01-job-via-chat.spec.ts` — recruiter posts job via AI chat, verifies job created in DB
  - `02-competency-test.spec.ts` — candidate completes competency test, `test_status` updated
  - `03-invite-to-interview.spec.ts` — hiring manager clicks Invite to Interview, confirmation page shown
  - `04-super-admin-impersonation.spec.ts` — super admin impersonates tenant, scoped data access verified
  - `05-locale-switching.spec.ts` — switch locale to DE/ES/FR, translated UI renders

### Session 12 — i18n Wiring + Migration Fix + Full Test Suite Pass
- i18n: Added `billing` namespace (29 keys) and `settings.widget*` keys (15 keys) to DE/ES/FR message files
- i18n: Wired `billing/page.tsx`, `settings/page.tsx`, and `layout.tsx` (sidebar nav labels) to use translations via `useTranslations`
- Migration fix: `fd821988c15c` was broken on fresh installs — auto-generated against already-migrated DB; rewrote to correctly add `tenants.user_id` column and `chat_sessions.user_id` index
- Bug fix: `super_admin.py` `TenantAdminUpdate.plan` Literal had stale names (`free/casual/individual/small_firm/mid_firm`); updated to current names (`trial/trial_expired/recruiter/agency_small/agency_medium/enterprise`)
- Test suite: Fixed all failing tests — 294 total, 0 failing (was 242 total with 31 failing)
  - `conftest.py` + mock factories: stale `plan="individual"` → `"trial"`; added missing nullable fields; added `candidate_target`, `interview_type`, `mode` to `make_job`; added `interview_type` to `make_application`
  - `test_talent_scout_tasks.py`: replaced stale `chain` mock with `enrich_profile.delay` mock; added missing `existing_count` DB result; set `mock_settings.plan_limits`; fixed `complete_json` → `complete` for score tests; lengthened outreach body to pass 20-char validation
  - `test_super_admin.py`: fixed stale plan names in test payloads (`"small_firm"` → `"agency_small"`, `"casual"` → `"recruiter"`); fixed promo duplicate test to mock `db.commit` not `db.begin`
  - `test_rag.py`: `"small_firm"` → `"agency_small"`; `"individual"` → `"trial"` in plan guards
  - `test_auth.py`: changed mock to 500 error so it doesn't trigger the "already registered" re-registration path (makes a real HTTP call)
  - `test_chat_sessions.py`: added count mock for payment phase job-limit check; updated non-JSON fallback assertion; removed two `_maybe_summarise` tests (function no longer exists in production code)
  - `test_embeddings.py`: import changed to `generate_embedding_async` (sync version removed in earlier session)
  - `test_ai_provider.py`: rewrote to test current `_get_claude_service()`/`_get_openai_service()` API

### Session 11 — Bug Fixes
- Fix: `GET /candidates?limit=200` returned 422 — FastAPI rejected value exceeding `le=100` cap; raised to `le=500` (`backend/app/routers/candidates.py`)
- Fix: Removed "Add candidate" dashed buttons from all five Kanban pipeline columns on the dashboard (`frontend/app/[locale]/(dashboard)/page.tsx`)
