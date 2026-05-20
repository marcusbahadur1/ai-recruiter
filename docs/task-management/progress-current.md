# PROGRESS — AI Recruiter (airecruiterz.com) — Current State
Last updated: 2026-05-20 (session 43)

*Full session history: see [PROGRESS.md](PROGRESS.md)*

## Summary

Infrastructure fully migrated from Railway + Vercel to Fly.io. All compute on Fly.io (`syd`). Tagged `v1.2.0` (marketing module live). Client Pipeline all 8 phases complete. LinkedIn Showcase Page posting feature complete (session 43).

**Session 43 (2026-05-20) — LinkedIn Showcase Page Posting:**
Extended Content tab to support posting to LinkedIn Showcase Pages using LinkedIn's native Posts API. No third-party vendor — uses `LinkedIn-Version: 202502` REST API directly.

Backend:
- Migration `0029`: new `linkedin_pages` table (stores personal/company/showcase pages per tenant); `needs_reconnect` column on `marketing_accounts`; `target_pages` + `publish_results` JSONB columns on `marketing_posts`.
- `LinkedInPage` SQLAlchemy model in `marketing.py`. `MarketingAccount.needs_reconnect` + `MarketingPost.target_pages/publish_results` added.
- `linkedin_client.py`: manual setup comment block (LinkedIn Developer Portal steps); `get_admin_pages()` (new REST API organizationAcls); `get_organization()` (org detail); `create_post_v2()` + `_upload_image_v2()` (new Posts API `/rest/posts`); updated scopes now include `w_organization_social`.
- New service `publish_service.py`: `sync_linkedin_pages()` (discovers personal + all admin pages after OAuth); `publish_single_page()` (posts to one URN, updates `publish_results`); `publish_post_to_all_pages()` (iterates target_pages, sets post.status to posted/partial/failed).
- New router `marketing_linkedin_pages.py`: `GET /marketing/linkedin/pages`, `POST /marketing/linkedin/pages/sync`, `PATCH /marketing/linkedin/pages/:id`.
- `marketing_oauth.py`: calls `sync_linkedin_pages` after successful OAuth connect (personal, company, and page-select flows).
- `marketing_content.py`: `ContentPostRead` extended with `target_pages` + `publish_results`; `GenerateContentRequest` extended with `target_page_urns`; new routes `PATCH /:id/target-pages` + `POST /:id/retry-failed`.
- `marketing_tasks.py`: `_publish_scheduled_posts_async` updated to call `publish_post_to_all_pages` (multi-page publish) instead of single-account LinkedIn post.
- `config.py`: `linkedin_api_version` setting (default `"202502"`).
- `.env.example`: `LINKEDIN_API_VERSION=202502` documented.

Frontend:
- `types.ts`: `LinkedInPage`, `SyncPagesResponse`, `PagePublishResult` interfaces; `ContentPost` extended with `target_pages`/`publish_results`; `ContentPostStatus` extended with `"partial"`.
- `index.ts`: `listLinkedInPages()`, `syncLinkedInPages()`, `updateLinkedInPage()`, `updateTargetPages()`, `retryFailedPages()` added to `marketingApi`; `generateContent()` extended with `target_page_urns`.
- `SettingsTab.tsx`: LinkedIn channel row shows "N pages connected"; "Manage pages →" button opens slide-over panel with all discovered pages (logo, page name, type badge, follower count, is_active toggle, external link). "Refresh pages" button calls `syncLinkedInPages`. Note about showcase pages appearing automatically.
- `ContentTab.tsx`: loads LinkedIn pages alongside posts; `PostCard` shows "Publishing to:" page avatar row on draft/scheduled cards; shows per-page publish status (green ✓ / red ✕ / grey ◷) on posted/partial cards; "Retry failed pages" button on failed/partial posts; `partial` status handled (shows in Failed sub-tab). `GenerateModal` shows "Post to" checkbox list of active pages (personal pre-checked, others opt-in).

⚠️ Manual step required: developer must add `w_organization_social` scope in LinkedIn Developer Portal before showcase page posting works. See `linkedin_client.py` comment block for full instructions.
Run `alembic upgrade head` on production to apply migration 0029.

**Session 42 (2026-05-13) — Client Pipeline Phase 8 — Tenant Mode:**
Built full tenant isolation for the Client Pipeline module. Backend: `GET /marketing/tenant-status` returns access gating + usage stats + LinkedIn/Hunter state for any caller (super admin or tenant); `GET /marketing/admin/tenant-usage` returns per-tenant usage table (super admin only). Both routes in `marketing_settings.py`. Plan-ordering helper (`_plan_gte`, `_is_super_admin_tenant`) shared internally. Usage enforcement: `marketing_prospects.py` — before BrightData scrape, counts tenant's this-month prospects vs `tenant_mode_config.max_prospects_per_month`, returns 429 if over limit; `marketing_sequences.py` — before create, counts sequences vs `max_sequences`, returns 400 if over limit. `_get_or_create_settings` now sets `tenant_mode_enabled=false` for tenant rows + inherits signal/outreach defaults from platform. Schemas: `TenantStatusResponse`, `TenantUsageRow`, `AdminTenantUsageResponse` added to `schemas/marketing.py`. Frontend: `TenantStatus`, `TenantUsageRow`, `AdminTenantUsage` types in `types.ts`; `getTenantStatus()` + `getAdminTenantUsage()` added to `marketingApi`. `layout.tsx` fetches `getTenantStatus` alongside dashboard stats; Marketing section hidden entirely if tenant_mode_disabled, shown with UPGRADE badge + modal if plan_too_low. Upgrade modal links to `/billing`. `page.tsx` fetches tenant status on mount; passes to SettingsTab + ProspectsTab; shows onboarding banner (first-visit, no data, not super admin); shows LinkedIn-not-connected amber warning bar. `SettingsTab.tsx` accepts `tenantStatus` prop — hides Tenant mode section for tenants, replaces BrightData edit with "Platform managed" note for tenants, shows usage progress bars (prospects/sequences vs limits) for tenants subject to limits, shows per-tenant usage table for super admin (tenant name / plan / prospects this month / sequences / LinkedIn / last active). `ProspectsTab.tsx` accepts `tenantStatus` — `SlideOver` receives `hasHunter` prop; "Find email" button replaced with "Hunter.io not configured" note if key absent.

**Session 41 (2026-05-13) — Client Pipeline Phase 7 — Content Tab:**
Built the Content tab for `/en/marketing`. Backend: migration 0028 (adds `connections_attributed` + `demos_attributed` int columns to `marketing_posts`); new router `marketing_content.py` (5 routes: GET `/marketing/content`, POST `/marketing/content/generate`, GET `/marketing/content/stats`, PATCH `/marketing/content/:id`, DELETE `/marketing/content/:id`). Content posts use `post_type` values `roi_post`/`pain_post`/`proof_post`/`tip_post` stored in existing `marketing_posts` table. AI generation uses 4 dedicated system prompts (ROI/Pain/Proof/Tip) via `AIProvider.complete`. `/stats` route computes avg views, avg connections, post→demo rate, best post type, content mix %, and upcoming schedule. Soft-delete sets `status=discarded` (excluded from all list queries). LinkedIn posting handled by existing `publish_scheduled_posts` Celery task (runs every 15 min). Frontend: `ContentPost`, `ContentPostType`, `ContentPostStatus`, `ContentStatsResponse` types in `types.ts`; 5 API functions added to `marketingApi`; `ContentTab.tsx` built — two-column layout (65% left / 35% right). Left: sub-tabs (Draft/Scheduled/Posted/Failed) with counts, post cards with type chip (colour-coded by type), status badge, body preview with show-more toggle, metrics row (views/likes/comments/connections), attribution tinted box, context-sensitive action buttons (Approve+schedule popover, Edit inline textarea, Regenerate, Discard/Unschedule/Post now/Retry/View on LinkedIn). Right panel: Performance card (avg views, connections, demo rate, best type), Content mix segmented bar with legend + target note, Upcoming schedule list. Generate modal: post-type chip selector pre-filled with underrepresented type, optional topic hint. `page.tsx` wired with `ContentTab` dynamic import.

**Session 40 (2026-05-13) — Client Pipeline Phase 6 — Sequences Tab:**
Built the full Sequences tab for `/en/marketing`. Two-column layout (260px fixed left panel + fluid right). Left panel: sequence list with status dot (live/paused/draft), enrolled count, channel tag pills (LI/Email/Wait), "New sequence" dashed row. Right panel: inline-editable name, status dropdown chip, enrolled/persona/angle chips, 4-metric performance grid (sent, accept/open rate, reply rate, demos booked), step editor cards with debounced auto-save (1s), step-type badge, day offset, char counter for LI steps, condition field, step-level stats row, connector lines between steps, up/down reorder buttons, add-step link, trash on hover. New Sequence wizard: 2-step modal — step 1 collects name/persona/angle; step 2 shows AI-generated step templates (editable before saving). Enroll modal: multi-select from identified/connected prospects, bulk enroll. Backend: migration 0027 (`step_name` column on `marketing_sequence_steps`); `MarketingSequenceStep` + `MarketingEnrollment` SQLAlchemy models added to `marketing.py`; `SequenceStepRead/Create/Update`, `SequenceRead/Create/Update`, `SequenceStats`, `GenerateSequenceRequest/Response`, `EnrollProspectsRequest/Response` schemas; new router `marketing_sequences.py` (10 routes: list, create, update, delete, generate, list-steps, add-step, update-step, delete-step, enroll, stats); `process_enrollments` Celery task (15-min beat) in `marketing_tasks.py` — processes active enrollments: day_offset check, condition check, outreach window check, LinkedIn steps logged (MDP pending), email steps sent via SendGrid, outreach_log written, enrollment advanced. Frontend: `Sequence`, `SequenceStep`, `SequenceStats`, `GeneratedStep`, `EnrollProspectsResponse` types added; 10 API functions in `marketingApi`; `SequencesTab.tsx` built; `page.tsx` wired. API routes: GET/POST/PATCH/DELETE `/api/marketing/sequences`, POST `.../generate`, GET/POST/PATCH/DELETE `.../steps`, POST `.../enroll`, GET `.../stats`.

**Session 39 (2026-05-13) — Client Pipeline Phase 5 — Signals Tab:**
Built the Signals tab for `/en/marketing`. Backend: migration 0026 (adds `location`, `company_type`, `job_count` to `marketing_signals`; creates new `marketing_signal_runs` table with RLS); `MarketingSignalRun` model added to `marketing.py`; `MarketingSignalRun` + updated `MarketingSignal` registered in `models/__init__.py`; `SignalRunRead`, `SignalListResponse` schemas added + `SignalRead` extended; new router `marketing_signals.py` with 5 routes; `scrape_signals_for_tenant` Celery task added to `marketing_tasks.py` (BrightData hiring spikes + pain posts + growth signals + deduplication + demo signals fallback). Celery task registered on `marketing` queue. Frontend: `SignalRun`, `SignalListResponse` types added to `types.ts`; `Signal` extended with `location`/`company_type`/`job_count`; 4 new API functions (`listSignals`, `runSignalScrape`, `getSignalRun`, `actionSignalDirect`, `dismissSignalDirect`) added to `marketingApi`; `SignalsTab.tsx` built (config bar with scrape frequency + last run timestamp + "Run now" button with polling; 4 type tiles with active state; signal feed sorted by urgency then recency; per-type action buttons; actioned/dismissed states with 1.8s fade-out); `page.tsx` updated to load `SignalsTab` dynamically. API routes: GET `/api/marketing/signals`, POST `/api/marketing/signals/run`, GET `/api/marketing/signals/runs/:id`, PATCH `/api/marketing/signals/:id/action`, PATCH `/api/marketing/signals/:id/dismiss`.

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

---

## Client Pipeline Module — Complete Summary (All 8 Phases, Session 42)

### Tabs and what each does

| Tab | What it does |
|-----|-------------|
| **Pipeline** | 5-metric bar (prospects/connected/replied/demos/trials with 7-day delta), conversion funnel, live signals with action/dismiss, recent prospect activity table, active sequences with reply rate |
| **Prospects** | Search/filter/sort paginated table; ICP score circle with breakdown tooltip; stage pills; contextual action buttons; slide-over detail panel with stage selector, notes, timeline, enrich-email, enroll; add-prospects modal (BrightData scrape); Hunter.io email enrichment |
| **Signals** | Config bar (scrape frequency, last run timestamp, "Run now"); 4 signal type tiles (hiring spike / pain post / growth / demo); signal feed sorted by urgency; per-type action buttons; actioned/dismissed states with fade-out |
| **Sequences** | Two-column layout: left panel (sequence list with status dot, enrolled count, channel pills); right panel (step editor with debounced auto-save, performance metrics, inline name edit, status dropdown, up/down reorder, connector lines); new-sequence wizard (basics → AI-generate → edit → save); enroll modal (multi-select from identified/connected prospects) |
| **Content** | Post queue sub-tabs (Draft/Scheduled/Posted/Failed); post cards with type chip (ROI/Pain/Proof/Tip), status badge, body preview, metrics, attribution; inline edit/regenerate/approve+schedule/discard/post-now actions; Generate modal with AI; right panel: performance stats, content mix bar, upcoming schedule |
| **Settings** | ICP targeting (tag inputs: titles/company types/locations; size range; min score); Channels (LinkedIn OAuth, BrightData/Hunter keys, SMTP); Signal config; Outreach limits; Tenant mode (super admin only — enable toggle + limits); Tenant usage table (super admin); Usage meters (tenants) |

### API routes created (Client Pipeline phases 1–8)

| Method | Route | Purpose |
|--------|-------|---------|
| GET/PATCH | `/api/marketing/settings` | Get/update pipeline settings |
| GET | `/api/marketing/tenant-status` | Access gating + usage stats for current user |
| GET | `/api/marketing/admin/tenant-usage` | Super admin: per-tenant pipeline usage |
| GET/POST | `/api/marketing/prospects` | List / add prospects |
| POST | `/api/marketing/prospects/scrape` | BrightData scrape + ICP score |
| GET/PATCH | `/api/marketing/prospects/:id` | Get / update prospect |
| POST | `/api/marketing/prospects/:id/enrich-email` | Hunter.io email lookup |
| POST | `/api/marketing/prospects/:id/enroll` | Enroll in sequence |
| GET/POST | `/api/marketing/signals` | List / run signal scrape |
| POST | `/api/marketing/signals/run` | Trigger Celery signal scrape |
| GET | `/api/marketing/signals/runs/:id` | Poll scrape run status |
| PATCH | `/api/marketing/signals/:id/action` | Action a signal |
| PATCH | `/api/marketing/signals/:id/dismiss` | Dismiss a signal |
| GET/POST/PATCH/DELETE | `/api/marketing/sequences` | CRUD sequences |
| POST | `/api/marketing/sequences/generate` | AI-generate step templates |
| GET/POST/PATCH/DELETE | `/api/marketing/sequences/:id/steps` | CRUD steps |
| POST | `/api/marketing/sequences/:id/enroll` | Bulk enroll prospects |
| GET | `/api/marketing/sequences/:id/stats` | Sequence performance stats |
| GET | `/api/marketing/pipeline/summary` | Pipeline tab metrics |
| PATCH | `/api/marketing/pipeline/signals/:id/action` | Action signal (pipeline view) |
| PATCH | `/api/marketing/pipeline/signals/:id/dismiss` | Dismiss signal (pipeline view) |
| GET | `/api/marketing/content` | List content posts |
| POST | `/api/marketing/content/generate` | AI-generate content post |
| GET | `/api/marketing/content/stats` | Content performance stats |
| PATCH | `/api/marketing/content/:id` | Update content post (edit/schedule/approve) |
| DELETE | `/api/marketing/content/:id` | Soft-delete content post |

### Background jobs (Celery) and schedules

| Task | Schedule | Purpose |
|------|----------|---------|
| `scrape_signals_for_tenant` | On-demand (POST /signals/run) | BrightData hiring spike + pain posts + growth signals |
| `process_enrollments` | Every 15 min | Execute sequence steps for active enrollments |
| `publish_scheduled_posts` | Every 15 min | Publish scheduled content posts to LinkedIn |
| `generate_and_schedule_posts` | 02:00 UTC daily | AI-generate marketing content posts |
| `collect_post_stats` | 08:00 UTC daily | Pull LinkedIn post analytics |
| `auto_engage` | 10:00 UTC daily | Like + comment on LinkedIn posts |

### Third-party integrations

| Integration | Purpose |
|-------------|---------|
| **BrightData** | LinkedIn People Search (prospect scraping) + hiring signals; platform quota; tenants use platform key |
| **Hunter.io** | Email enrichment for prospects; tenants provide own key |
| **LinkedIn OAuth** | Personal profile posting + outreach; each tenant connects their own account |
| **Claude API** | 4 content post types (ROI/Pain/Proof/Tip prompts), sequence step generation |
| **SendGrid** | Outreach emails from sequences + outreach_from_email |
| **Unsplash** | Optional images for content posts (baked into post generation) |

### Tenant mode

| Setting | Value |
|---------|-------|
| Enabled by | Super admin toggle in Settings → Tenant mode |
| Min plan | Configurable — default `agency_small` ($999/mo) |
| Max prospects/month | Configurable — default 500 per tenant |
| Max sequences | Configurable — default 3 per tenant |
| Data isolation | Complete — every table filtered by `tenant_id` |
| LinkedIn | Each tenant connects their own account |
| Hunter.io | Each tenant provides their own API key |
| BrightData | Platform quota shared; per-tenant count enforced |
| Outreach | Enforced: 429 on prospect scrape if at limit, 400 on sequence create if at limit |
| UI differences | Tenant: no Tenant mode section, no BrightData key edit, usage meters shown |
| Admin visibility | Super admin Settings tab: usage table (tenant/plan/prospects/sequences/LinkedIn/last active) |
