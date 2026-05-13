# PROGRESS — AI Recruiter (airecruiterz.com) — Current State
Last updated: 2026-05-13 (session 38)

*Full session history: see [PROGRESS.md](PROGRESS.md)*

## Summary

Infrastructure fully migrated from Railway + Vercel to Fly.io. All compute on Fly.io (`syd`). Tagged `v1.2.0` (marketing module live). AI Chat test suite complete — 12 Playwright tests (T01–T10, T12, browser T04–T06) all passing against production. `_JOB_COLLECTION_SYSTEM` prompt rewritten with explicit RULE A/B/C/D structure to enforce Job Summary output on JD paste. Test tenant upgraded to `agency_medium` plan.

**Session 38 (2026-05-13) — Client Pipeline Phase 4 — Pipeline Tab:**
Built the Pipeline tab for `/en/marketing`. Backend: `MarketingSignal` + `MarketingSequence` SQLAlchemy models added to `marketing.py`; `SignalRead`, `SignalActionRequest`, `SequenceSummary`, `FunnelRow`, `MetricCard`, `PipelineSummaryResponse` schemas added; new router `marketing_pipeline.py` with 3 routes registered in `main.py`. Frontend: `Signal`, `SequenceSummary`, `FunnelRow`, `MetricCard`, `PipelineSummary` types added to `types.ts`; `getPipelineSummary`, `actionSignal`, `dismissSignal` added to `marketingApi`; `PipelineTab.tsx` built (5-metric bar with 7-day delta + pct label, div-based conversion funnel with blue ramp, live signals panel with action/dismiss flow, recent prospect activity table, active sequences with reply rate); `page.tsx` updated with `onNavigate` prop for cross-tab navigation. API routes: GET `/api/marketing/pipeline/summary`, PATCH `/api/marketing/pipeline/signals/:id/action`, PATCH `/api/marketing/pipeline/signals/:id/dismiss`.

**Session 38 (2026-05-13) — Client Pipeline Phase 3 — Prospects Tab:**
Built the full Prospects tab for `/en/marketing`. Backend: migration 0025 (adds `location`, `company_size`, `company_type`, `last_linkedin_post_at`, `score_breakdown`, `notes` to `marketing_prospects`); `MarketingProspect` + `MarketingOutreachLog` SQLAlchemy models added to `marketing.py`; Pydantic schemas (`ProspectRead`, `ProspectCreate`, `ProspectUpdate`, `ScrapeRequest`, `ScrapeResponse`, `ProspectListResponse`, `OutreachLogRead`) added to `marketing.py` schemas; new router `marketing_prospects.py` with 6 routes registered in `main.py`. ICP scoring function (`compute_icp_score`) implemented server-side. BrightData search uses `gd_lxe7084k6l8iobbif` LinkedIn People Search dataset. Frontend: `ProspectListResponse`, `Prospect`, `OutreachLog`, `ScrapeRequest/Response` types added to `types.ts`; 7 API functions added to `marketingApi`; `ProspectsTab.tsx` built (search/filter chips/more filters/sort toolbar, 25-per-page table with avatar + ICP circle + source badge + stage pill + contextual action buttons, slide-over panel with stage selector/notes/timeline/enrich-email/enroll, add-prospects modal with tag inputs and progress indicator); `page.tsx` updated to load `ProspectsTab` dynamically. API routes: GET/POST `/api/marketing/prospects`, GET/PATCH `/api/marketing/prospects/:id`, POST `/api/marketing/prospects/:id/enrich-email`, POST `/api/marketing/prospects/:id/enroll`.

**Session 38 (2026-05-13) — Client Pipeline Phase 2 — Settings Tab:**
Built the Settings tab for `/en/marketing`. Five sections: ICP targeting (tag inputs for job titles, company types, locations; size range; min score), Channels (LinkedIn OAuth reconnect, BrightData/Hunter.io masked API keys with inline edit, SMTP mailbox config), Signal configuration (hiring spike threshold, scrape frequency, 4 toggles), Outreach limits (daily caps, time window, skip-weekends toggle), Tenant mode (info banner, enable toggle, per-tenant limits). Save PATCH to `/api/marketing/settings`. Extended `MarketingSettings` SQLAlchemy model with 6 new pipeline JSONB columns (already in DB from migration 0024). Extended Pydantic `MarketingSettingsRead`/`MarketingSettingsUpdate` schemas. Extended frontend `MarketingSettings` type with typed interfaces (`IcpConfig`, `ChannelConfig`, `SignalConfig`, `OutreachLimits`, `TenantModeConfig`). Added 2 new API routes: GET/PATCH `/api/marketing/settings` already existed — schemas updated to expose pipeline fields.

**Session 37 (2026-05-13) — Client Pipeline Phase 1:** Replaced `/en/marketing` (old LinkedIn post automation UI) with new "Client pipeline" tabbed shell (6 tabs: Pipeline, Prospects, Signals, Sequences, Content, Settings — all empty placeholders). Updated sidebar label from "AI Marketing" → "Client pipeline". Added migration 0024: 7 new pipeline tables (`marketing_prospects`, `marketing_signals`, `marketing_sequences`, `marketing_sequence_steps`, `marketing_enrollments`, `marketing_outreach_log`, `marketing_content`) + extended existing `marketing_settings` with ICP/outreach JSONB config columns + seeded platform-level defaults + RLS on all new tables.

**Session 36 (2026-05-07):** End-to-end live test run against production — 26/26 PASS. Fixed outbound email sender (platform verified sender `outreach@airecruiterz.com` + per-tenant display name). Added `outreach_from_name` column (migration 0022). Fixed AI provider defaults to cheapest models (Haiku 4.5 / gpt-4o-mini). Added `anthropic_model` + `openai_model` columns (migration 0021). Fixed OpenAI model dropdown in Settings UI. Confirmed full Scout pipeline: discover → enrich → score → email → SendGrid delivery. Known gap: `domain_deduction` email provider finds ~0 real candidate emails; Hunter/Apollo keys needed.

---

## Current State by Layer

### Backend (`backend/`)

| Area | Status | Notes |
|---|---|---|
| Models | Complete | 12 models (8 core + 4 marketing), all with tenant_id |
| Schemas | Complete | Pydantic v2 throughout |
| Routers | Complete (core) | 19 core + 4 marketing routers = 23 total in main.py |
| Services | Complete (core) | 16 core services + 4 marketing services |
| Celery tasks | Complete (core) | talent_scout_tasks, screener_tasks, scheduled_tasks, marketing_tasks |
| Email templates | Complete | 12 Jinja2 HTML templates |
| Migrations | Complete | 22 Alembic versions (0001–0022, incl. marketing tables + RLS + ai_model + outreach_from_name) |
| Unit tests | Complete | 17 test files, ~120 tests |
| Integration tests | Complete | 15 test files, ~122 tests; + marketing tests (81 new) = 375 total |
| E2E tests | Complete | 5 Playwright specs in `e2e/tests/` + production smoke suite in `e2e/tests/production/` |
| Infra config | Complete | `fly.toml` (API) + `fly.worker.toml` (Celery) — Fly.io `syd` region |
| Marketing API | Complete (`feature/marketing`) | 19 routes: posts, settings, analytics, OAuth/accounts |

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
| Marketing Dashboard | `/marketing` | Done |
| LinkedIn Page Selector | `/marketing/linkedin/select-page` | Done |
| Super Admin: Marketing | `/super-admin/marketing` | Done |

### i18n
- Message files: EN, DE, ES, FR — exist in `frontend/messages/`
- All billing and widget config UI strings wired in all four locales
- Sidebar nav labels translated in `layout.tsx`

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
| 12 | +52 (test fixes, new total) | 294 |
| 15 | 0 backend (smoke test fixes only) | 294 + 47 Playwright smoke |
| 27 | 0 (bug fix only — no new tests) | 294 + 47 Playwright smoke |

**Current total: 294 tests** (unit + integration). E2E: 5 scenario specs + 47 smoke tests (all passing).

---

## Known Issues

- `test_super_admin_audit_requires_super_admin_role` in `tests/integration/test_audit.py` makes a real Supabase HTTP call and fails in CI without live DB — pre-existing, not introduced in session 7.
- `resume_screener.py` is not a standalone service file (screener logic lives in `screener_tasks.py` directly) — diverges slightly from SPEC §19 file list but is functionally equivalent.
