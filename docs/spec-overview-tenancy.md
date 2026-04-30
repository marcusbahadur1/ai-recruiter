# Spec §1–2: Application Overview + Multi-Tenancy

*Full spec index: see [spec.md](spec.md)*

---

## 1. Application Overview

AI Recruiter is a multi-tenant SaaS recruitment automation platform at **airecruiterz.com**. Two independently licensable modules:
- **AI Talent Scout** — proactively sources and contacts passive candidates via LinkedIn profile discovery, scoring, and hyper-personalised outreach.
- **AI Resume Screener** — processes inbound applications, screens resumes, administers AI-driven competency tests, and manages interview invitations.

Both modules share Supabase/PostgreSQL, a unified admin dashboard, Stripe billing, and a real-time evaluation report in the AI Recruiter chat interface. Must be **GDPR compliant**. UI supports **EN, DE, ES, FR** via Next.js i18n routing.

### 1.1 Product Goals
- Reduce time-to-shortlist by 80% versus manual recruitment
- Operate autonomously 24/7 with human recruiter reviewing the evaluation report
- Support multiple recruitment firms (tenants) from a single deployment
- Include comprehensive automated test coverage — no manual QA tester required

### 1.2 Hosting

| Layer | Service |
|---|---|
| Backend API | Fly.io — `airecruiterz-api` app, `syd` region (FastAPI, Docker) |
| Database | Supabase (PostgreSQL 17 + pgvector + RLS) |
| Frontend | Fly.io — `airecruiterz-app` app, `syd` region (Next.js 16, standalone Docker) |
| Workers | Fly.io — `airecruiterz-worker` app, same image as API with `WORKER_MODE=1` |
| Redis | Fly.io Upstash Redis — `airecruiterz-redis` (Celery broker + result backend) |

### 1.3 Technology Stack

| Field | Value |
|---|---|
| Language | Python 3.12+ |
| Framework | FastAPI (async) |
| Database | Supabase (PostgreSQL 17 + pgvector) |
| ORM | SQLAlchemy 2.x async (asyncpg driver) |
| Task Queue | Celery + Redis |
| Auth | Supabase Auth (JWT + RLS) |
| AI / LLM | Anthropic Claude Sonnet (primary) + OpenAI (optional, tenant-selectable) |
| Frontend | Next.js 16 TypeScript App Router — Fly.io (i18n via `proxy.ts`, not `middleware.ts`) |
| Testing | pytest + pytest-asyncio + httpx + Playwright |

---

## 2. Multi-Tenancy Architecture

Every database table includes `tenant_id` (UUID) FK to the `tenants` table. Supabase RLS policies enforce all queries are scoped to the authenticated tenant. A tenant = one recruitment firm.

### 2.1 Tenant Data Model (key fields)

| Field | Description |
|---|---|
| id | UUID PRIMARY KEY |
| name | Recruitment firm name |
| slug | URL-safe identifier (e.g. 'acme-recruit') |
| email_inbox | Platform email address (jobs-{slug}@airecruiterz.com) |
| plan | ENUM: trial \| trial_expired \| recruiter \| agency_small \| agency_medium \| enterprise |
| credits_remaining | Integer — job credits for Talent Scout searches |
| ai_provider | ENUM: anthropic \| openai |
| ai_api_key | NULLABLE encrypted — tenant's own AI API key |
| search_provider | ENUM: scrapingdog \| brightdata \| both |
| brightdata_api_key | Encrypted |
| email_discovery_provider | ENUM: apollo \| hunter \| snov \| domain_deduction |
| stripe_customer_id | Stripe customer identifier |
| stripe_subscription_id | Active subscription identifier |
| gdpr_dpa_signed_at | TIMESTAMPTZ |
| is_active | BOOLEAN |

Also: `phone`, `address`, `main_contact_name`, `main_contact_email`, `website_url`, `email_inbox_host/port/user/password` (custom IMAP), `scrapingdog_api_key`, `apollo_api_key`, `hunter_api_key`, `snov_api_key`, `sendgrid_api_key`, `recruiter_system_prompt`, `widget_primary_color`, `widget_bot_name`.

> Platform-level keys set by super_admin. Tenant keys override platform keys when provided.
