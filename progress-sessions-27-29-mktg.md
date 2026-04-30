# PROGRESS — Sessions 27–29 (Marketing Phases 7–9)

*Full index: see [PROGRESS.md](PROGRESS.md)*

---

### Session 29 — AI Marketing Module: Phase 9 (Frontend: Super Admin Marketing Dashboard)

**Phase 9 — Super Admin Marketing Dashboard**
- `frontend/lib/api/index.ts` — `marketingApi.getAccounts()` and `marketingApi.toggleActive()` updated to accept optional `tenantId` param (passed as `?tenant_id=` query param to backend)
- `frontend/app/[locale]/(dashboard)/super-admin/marketing/page.tsx` — dedicated super admin marketing page:
  - Summary stat cards: eligible tenants, Agency Small count, Agency Medium+ count
  - Plan filter tabs (All / agency_small / agency_medium / enterprise)
  - Tenants table with expandable rows: click row loads `GET /marketing/accounts?tenant_id=...` and shows connected LinkedIn accounts inline
  - Per-tenant Enable / Pause toggle buttons calling `POST /marketing/toggle?tenant_id=...` with optimistic state
  - Back link to `/super-admin`
- `frontend/app/[locale]/(dashboard)/super-admin/page.tsx` — added "Marketing →" link button in section tabs to navigate to `/super-admin/marketing`
- `frontend/app/[locale]/(dashboard)/layout.tsx` — added page title for `/super-admin/marketing`

### Session 28 — AI Marketing Module: Phase 8 (Frontend: Tenant Marketing Dashboard)

**Phase 8 — Tenant Marketing Dashboard**
- `frontend/lib/api/types.ts` — added 6 marketing types: `MarketingAccount`, `MarketingSettings`, `MarketingPost`, `MarketingEngagement`, `MarketingAnalyticsSummary`, `DailyAnalytics`
- `frontend/lib/api/index.ts` — added `marketingApi` with 14 methods covering all 19 marketing API routes: OAuth connect/select-page/disconnect, settings CRUD + toggle, posts CRUD + approve/reject/delete/generate, analytics summary/daily, engagement list
- `frontend/app/[locale]/(dashboard)/layout.tsx` — added `MarketingIcon`, "AI Marketing" nav item in new "Marketing" section, page titles for `/marketing` and `/marketing/linkedin/select-page`
- `frontend/app/[locale]/(dashboard)/marketing/page.tsx` — full tenant marketing dashboard:
  - Analytics summary stat cards (total posts, impressions, avg engagement, top post) shown only when data exists
  - LinkedIn accounts panel: lists connected accounts with token expiry warning; "Connect Personal" / "Connect Company Page" buttons that initiate OAuth redirect; disconnect button per account
  - Automation settings panel: read view with all fields; edit form (frequency, post_time_utc, tone, target_audience, topics, requires_approval, include_images); enable/pause toggle (requires account connected)
  - Post queue: tab bar for draft/scheduled/posted/failed; per-post approve/reject/delete actions; AI Generate Post button; pagination; plan-gate 403 screen for non-eligible plans
  - OAuth callback handling: reads `?connected=true` / `?error=...` query params, shows success/error banner, clears params from URL
- `frontend/app/[locale]/(dashboard)/marketing/linkedin/select-page/page.tsx` — company page picker: reads `?token=`, fetches page list from API, radio-select UI, submits selection and redirects to `/marketing?connected=true`

### Session 27 — AI Marketing Module: Phase 7 (FastAPI Routers)

**Phase 7 — FastAPI Routers**
- `backend/app/routers/marketing_posts.py` — 7 routes under `/api/v1/marketing/posts`:
  `GET /posts` (paginated, filters: status/platform/date_from/date_to/page/page_size),
  `POST /posts` (create; auto-sets draft vs scheduled from `requires_approval`),
  `PATCH /posts/{id}` (edit draft/scheduled only),
  `POST /posts/{id}/approve` (draft → scheduled),
  `POST /posts/{id}/reject` (revert to draft),
  `DELETE /posts/{id}` (non-posted only),
  `POST /posts/generate` (AI-generate immediately via `MarketingContentGenerator`, always returns draft)
- `backend/app/routers/marketing_settings.py` — 3 routes:
  `GET /settings` (auto-creates from platform defaults if absent, `is_active=False`),
  `PATCH /settings` (plan-gates `auto_engage` to Agency Medium+),
  `POST /toggle` (flip `is_active`; super admin can pass `?tenant_id=` to toggle any tenant or platform row)
- `backend/app/routers/marketing_analytics.py` — 3 routes:
  `GET /analytics` (daily series grouped by posted_at date, clips to plan retention window),
  `GET /analytics/summary` (`MarketingAnalyticsSummary`: totals + avg engagement rate + top post),
  `GET /engagement` (paginated engagement log joined through `marketing_accounts.tenant_id`)
- `backend/app/routers/marketing_oauth.py` — enhanced `GET /accounts` with super admin `?tenant_id=` support
- `backend/app/main.py` — all 3 new routers registered; 19 marketing routes total
