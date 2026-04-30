# Spec §9–12: RAG Widget, Candidate UI, Super Admin, Dashboard

*Full spec index: see [spec.md](spec.md)*

---

## 9. Firm Chat Widget & RAG Pipeline

Available from Agency Small plan upward.

### 9.1 Website Scraping

On tenant creation (if `website_url` provided): Celery task crawls website (crawl4ai or httpx + BeautifulSoup), chunks text (max 500 tokens/chunk), generates embeddings, stores in `rag_documents` with `source_type = 'website_scrape'`. Firm can trigger re-scrape from Settings > Knowledge Base.

### 9.2 Document Upload

Firms upload PDF/DOCX/TXT from Settings > Knowledge Base. Text extracted, chunked, embedded → `rag_documents` with `source_type = 'manual_upload'`. Firm can delete anytime (GDPR right to erasure).

### 9.3 Chat Widget

Lightweight JS snippet for firm's website `<head>`. Backed by `POST /widget/{slug}/chat` (public, rate-limited). RAG: embed query → cosine search `rag_documents` → inject top-k chunks into Claude prompt. Branded with `widget_primary_color` and `widget_bot_name` (stored on tenants table, migration 0012). Settings page: "Save Widget Settings" button persists via PATCH /tenants/me.

---

## 10. Candidate Search & Management UI

### 10.1 Candidate Search

Full-text search: name, title, company, skills, location. Filters: job, status, score range, location, date. Paginated table with score badges and status pills.

### 10.2 Candidate Profile Page

Full BrightData profile display, score history across jobs, outreach email history, resume and application history, status update control, notes field (recruiter-only), **GDPR Delete button** — permanently anonymises all PII, embeddings, BrightData profile.

---

## 11. Super Admin Panel

Route: `/super-admin` — separate auth guard, `super_admin` role only.

> **Super admin detection**: Probe `GET /super-admin/stats` on layout mount — 200 = super admin, 403 = regular user. Do NOT use `NEXT_PUBLIC_SUPER_ADMIN_EMAIL` env var (requires redeploy on every change).

Features: view all tenants (name, plan, credits, status, last active), impersonate any tenant (logged), platform API key management (Anthropic, OpenAI, SendGrid, ScrapingDog, BrightData), billing management, platform-wide promo codes, system health (Celery queue depth, failed tasks), platform audit view.

**Email Test Mode toggle**: state stored in Redis (`platform:email_test_mode`, `platform:email_test_recipient`). Amber warning banner shown across entire super admin page when active. Env var `EMAIL_TEST_MODE` remains as cold-start fallback.

---

## 12. Admin Dashboard

Next.js 16 App Router at `app.airecruiterz.com`. Supabase Auth protected. i18n: EN, DE, ES, FR.

| Page | Description |
|---|---|
| / (Home) | Stats overview + Kanban pipeline board (5 columns: NEW/SCREENED/INTERVIEWED/OFFERED/HIRED) |
| /chat | AI Recruiter chat — server-loaded history |
| /jobs | Job list with status, counts, actions |
| /jobs/{id} | Tabbed: Evaluation Report (SSE) + Audit Trail (SSE) + Job Spec |
| /candidates | Cross-job search and filter |
| /candidates/{id} | Profile, score, emails, notes, GDPR delete |
| /applications/{id} | Resume, screening result, test transcript, interview status |
| /settings | API keys, email inbox, team, AI provider, widget config |
| /settings/knowledge-base | Upload docs, view scrapes, trigger re-scrape |
| /settings/ai-recruiter | Plain-English prompt editor |
| /billing | Stripe Customer Portal |
| /promo-codes | Generate and manage codes |
| /super-admin | Super admin panel |
