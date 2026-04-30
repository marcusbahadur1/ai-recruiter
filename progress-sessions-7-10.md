# PROGRESS — Sessions 7–10 (Billing, RAG, Frontend, Kanban)

*Full index: see [PROGRESS.md](PROGRESS.md)*

---

### Session 10 — Dashboard Kanban Board + Static Mockup
- Created `mockup.html` in project root — self-contained static dashboard UI mockup (dark sidebar, stat cards, Kanban board, active jobs, activity feed) for design reference
- Added Kanban candidate pipeline board to dashboard (`/`) between stat cards and Active Jobs panel — five colour-coded columns: NEW (cyan), SCREENED (amber), INTERVIEWED (purple), OFFERED (green), HIRED (teal)
- Kanban initially built with dummy data, then replaced with live `candidatesApi.list()` calls
- `Candidate.status` enum values mapped to columns: discovered/profiled/scored → NEW, passed/emailed/applied → SCREENED, tested/interviewed → INTERVIEWED; OFFERED/HIRED intentionally empty (no matching status values in schema yet)
- Job filter dropdown re-fetches with `?job_id=` when changed; populates from `activeJobs` already loaded on the dashboard
- Column counts reflect real candidate counts; cards link to `/candidates/{id}`
- Avatar colour derived deterministically from candidate id; initials generated from real name
- `failed`/`rejected` candidates excluded from board entirely

### Session 9 — Widget Branding Config
- Widget colour/branding config section in Settings → Chat Widget: saves `widget_primary_color` and `widget_bot_name` per tenant
- `widget_primary_color` (String 20) and `widget_bot_name` (String 100) added to `tenants` model + `TenantUpdate` + `TenantResponse` schemas
- Alembic migration `0012` — `widget_primary_color`, `widget_bot_name` columns (applied)
- Settings page: loads saved widget config from tenant on mount; bot name text input; "Save Widget Settings" button (disabled on plans without widget access)
- Embed snippet updates live as colour/name changes; `botName` line included only when set
- `widget.js` reads `config.botName`, initialises header on load without API round-trip
- GDPR Delete button on `/candidates/{id}` confirmed fully implemented — no changes needed

### Session 8 — Frontend Pages + Bug Fixes
- Built `/billing` — plan card, credits bar, Stripe portal/subscribe CTA, plan comparison grid
- Built `/settings/knowledge-base` — stats, scrape history timeline, chunk preview, re-scrape (deduped), re-scrape all, drag-and-drop upload, URL scraper, plan guard
- Built `/settings/ai-recruiter` — plain-English system prompt editor, save + reset to default, "Custom prompt active" badge
- `recruiter_system_prompt` TEXT column added to `tenants` model + `TenantUpdate` + `TenantResponse` schemas
- `chat_sessions.py` uses tenant's custom prompt for job_collection phase when set; falls back to hardcoded default
- Alembic migration `0011` — `recruiter_system_prompt TEXT NULL` on tenants (applied)
- Removed duplicate "AI Recruiter Prompt" tab from `/settings` page (now lives only at sub-page)
- Added sidebar nav entries: Billing, Knowledge Base, AI Recruiter Prompt
- Added staging smoke test suite: 8 Playwright specs + `staging-smoke.yml` GitHub Actions workflow
- Bug fix: `rag_pipeline._store_chunk` — `async with db.begin()` created savepoint inside autobegun transaction; outer transaction never committed so all scraped chunks were silently discarded. Fixed with explicit `db.flush() + db.commit()`
- Bug fix: `rag_pipeline._crawl` — `crawl4ai` could hang indefinitely when Playwright can't launch a browser (WSL2); added `asyncio.wait_for(..., timeout=30.0)` so it falls back to httpx+BeautifulSoup after 30 s
- Bug fix: `rag.py` plan gate used wrong plan names (`small_firm`, `mid_firm`) — corrected to `agency_small`, `agency_medium`
- Bug fix: dashboard layout `<main>` had `overflow:hidden` — page content below viewport was inaccessible; changed to `overflowY:auto`

### Session 7 — Billing, RAG, Widget, Email Templates, Super Admin
- `webhooks.py` — Stripe (4 events: checkout, invoice paid/failed, subscription deleted) + email HMAC webhook
- `promo_codes.py` — full CRUD + public validate endpoint
- `rag.py` — scrape, upload (PDF/DOCX/TXT), delete; plan-gated (agency_small+)
- `widget.py` — public POST /widget/{slug}/chat, rate-limited, RAG-backed
- `super_admin.py` — tenant list/patch, impersonation (logged), platform keys, health, audit view
- `billing.py` — Stripe Customer Portal + plan management
- `rag_pipeline.py` service — crawl4ai→httpx fallback scraper, chunking (500 tokens), pgvector cosine query
- `crypto.py` — Fernet encryption for tenant API keys
- 12 Jinja2 email templates (all per spec)
- 43 new tests (242 total)
