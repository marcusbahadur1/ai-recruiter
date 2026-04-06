# AI Recruiter — Application Specification v3.0
**airecruiterz.com — Python Rebuild**
*Version 3.0 | April 2026*

---

## Table of Contents

1. [Application Overview](#1-application-overview)
2. [Multi-Tenancy Architecture](#2-multi-tenancy-architecture)
3. [Authentication & User Roles](#3-authentication--user-roles)
4. [Stripe Billing & Plans](#4-stripe-billing--plans)
5. [Core Data Models](#5-core-data-models)
6. [AI Recruiter Chat Interface](#6-ai-recruiter-chat-interface)
7. [AI Talent Scout Module](#7-ai-talent-scout-module)
8. [AI Resume Screener Module](#8-ai-resume-screener-module)
9. [Firm Chat Widget & RAG Pipeline](#9-firm-chat-widget--rag-pipeline)
10. [Candidate Search & Management UI](#10-candidate-search--management-ui)
11. [Super Admin Panel](#11-super-admin-panel)
12. [Admin Dashboard](#12-admin-dashboard)
13. [Backend API Routes](#13-backend-api-routes-fastapi)
14. [Background Task Architecture](#14-background-task-architecture-celery)
15. [Job Audit Trail](#15-job-audit-trail)
16. [GDPR Compliance](#16-gdpr-compliance)
17. [Email Templates](#17-email-templates)
18. [Automated Testing Strategy](#18-automated-testing-strategy)
19. [Project Structure](#19-project-structure)
20. [Environment Variables](#20-environment-variables)
21. [Development Tooling](#21-development-tooling)
22. [Security Considerations](#22-security-considerations)
23. [Deployment Checklist](#23-deployment-checklist)
24. [Resolved Items](#24-resolved-items-from-v1--v2)

---

## 1. Application Overview

AI Recruiter is a multi-tenant SaaS recruitment automation platform hosted at **airecruiterz.com**. It replaces the existing Java application at aiworkerz.com with a Python-first stack, fully AI-generated using Claude Code CLI + PyCharm + Junie.

The platform has two independently licensable modules:
- **AI Talent Scout** — proactively sources and contacts passive candidates via LinkedIn profile discovery, scoring, and hyper-personalised outreach.
- **AI Resume Screener** — processes inbound applications, screens resumes, administers AI-driven competency tests, and manages the interview invitation workflow.

Both modules share Supabase/PostgreSQL, a unified admin dashboard, Stripe billing, and a real-time evaluation report in the AI Recruiter chat interface.

The application must be **GDPR compliant**. UI supports **English, German, Spanish, and French** at launch via Next.js i18n routing.

### 1.1 Product Goals
- Reduce time-to-shortlist by 80% versus manual recruitment
- Operate autonomously 24/7 with human recruiter reviewing the evaluation report
- Support multiple recruitment firms (tenants) from a single deployment
- Be entirely buildable by AI coding tools from this specification
- Include comprehensive automated test coverage — no manual QA tester required
- Full GDPR compliance throughout

### 1.2 Hosting Recommendation

| Layer | Service |
|---|---|
| Backend API | Railway.app (Python FastAPI, auto-deploy from GitHub) |
| Database | Supabase (PostgreSQL 15 + pgvector + RLS) |
| Frontend | Vercel (Next.js 14 App Router) |
| Workers | Railway worker dyno (Celery + Redis) |
| Email sending | SendGrid (transactional) |
| File storage | Supabase Storage |
| Resume embeddings | pgvector — generated at upload, used for AI comparison |

### 1.3 Technology Stack

| Field | Value |
|---|---|
| Language | Python 3.12+ |
| Framework | FastAPI (async) |
| Database | Supabase (PostgreSQL 15 + pgvector) |
| ORM | SQLAlchemy 2.x async (asyncpg driver) |
| Task Queue | Celery + Redis |
| Auth | Supabase Auth (JWT + RLS) |
| AI / LLM | Anthropic Claude Sonnet (primary) + OpenAI (optional, tenant-selectable) |
| Embeddings | OpenAI text-embedding-3-small or Anthropic embeddings — stored in pgvector |
| Email | SendGrid API + IMAP polling |
| Payments | Stripe (subscriptions + credits) |
| Candidate Search | ScrapingDog Google Search API AND/OR BrightData SERP API (tenant-selectable) |
| Profile Enrichment | BrightData LinkedIn People Profiles (collect by LinkedIn URL) |
| Email Discovery | Apollo.io (optional) + Hunter.io (optional) + Snov.io (optional) + custom EmailDeductionService (always available fallback) |
| i18n | Next.js built-in i18n routing (EN, DE, ES, FR) |
| Frontend | Next.js 14 TypeScript App Router — Vercel |
| CI/CD | GitHub Actions → Railway auto-deploy |
| Testing | pytest + pytest-asyncio + httpx + Playwright |

---

## 2. Multi-Tenancy Architecture

Every database table includes `tenant_id` (UUID) FK to the `tenants` table. Supabase RLS policies enforce all queries are scoped to the authenticated tenant. A tenant = one recruitment firm.

### 2.1 Tenant Data Model

| Field | Description |
|---|---|
| id | UUID PRIMARY KEY |
| name | Recruitment firm name |
| slug | URL-safe identifier (e.g. 'acme-recruit') |
| phone | Recruitment firm phone number |
| address | Full address (street, city, state, postcode, country) |
| main_contact_name | Primary contact person name |
| main_contact_email | Primary contact person email |
| email_inbox | Platform email address (jobs-{slug}@airecruiterz.com) |
| email_inbox_host | NULLABLE — custom IMAP host for firms using own mail server |
| email_inbox_port | NULLABLE — custom IMAP port |
| email_inbox_user | NULLABLE — custom IMAP username |
| email_inbox_password | NULLABLE — encrypted custom IMAP password |
| website_url | NULLABLE — scraped on creation for chat widget RAG |
| stripe_customer_id | Stripe customer identifier |
| stripe_subscription_id | Active subscription identifier |
| plan | ENUM: free \| casual \| individual \| small_firm \| mid_firm \| enterprise |
| credits_remaining | Integer — job credits for Talent Scout searches |
| ai_provider | ENUM: anthropic \| openai |
| ai_api_key | NULLABLE encrypted — tenant's own AI API key |
| search_provider | ENUM: scrapingdog \| brightdata \| both |
| scrapingdog_api_key | Encrypted (optional) |
| brightdata_api_key | Encrypted |
| email_discovery_provider | ENUM: apollo \| hunter \| snov \| domain_deduction |
| apollo_api_key | Encrypted (optional) |
| hunter_api_key | Encrypted (optional) |
| snov_api_key | Encrypted (optional) |
| sendgrid_api_key | Encrypted (optional) |
| gdpr_dpa_signed_at | TIMESTAMPTZ |
| created_at | TIMESTAMPTZ |
| is_active | BOOLEAN |

> Platform-level keys set by super_admin. Tenant keys override platform keys when provided.

---

## 3. Authentication & User Roles

Authentication via Supabase Auth. On sign-up, tenant record created and user assigned `admin` role. One person can hold multiple roles simultaneously (admin + recruiter + hiring_manager for small firms).

### 3.1 Roles

| Role | Description |
|---|---|
| super_admin | Platform owner — view all tenants, manage platform API keys, billing, impersonate. Separate /super-admin route. |
| admin | Firm owner — full access to their tenant |
| recruiter | Can manage jobs, view reports, trigger searches. May also hold hiring_manager role. |
| hiring_manager | Receives daily summaries, approves interview invitations via email link. No dashboard login required. |

### 3.2 Self-Serve Sign-Up Flow

1. User selects plan on airecruiterz.com pricing page
2. Stripe Checkout completes
3. Webhook fires to `/webhooks/stripe` — tenant created, plan activated
4. Welcome email with magic link to set password
5. Onboarding wizard: firm name, phone, address, contact details, email inbox prefix, website URL, API keys
6. Background task scrapes website for RAG if website_url provided
7. GDPR DPA prompt — must accept before candidate search features activate

---

## 4. Stripe Billing & Plans

### 4.1 Plan Structure

| Plan | Price AUD/mo | Jobs | Candidates/Job | Modules |
|---|---|---|---|---|
| Free | $0 | 1 | 10 | Screener only |
| Casual | $99 | 3 | 30 | Screener + Scout |
| Individual Recruiter | $499 | 10 | 100 | Screener + Scout |
| Small Firm | $999 | 30 | 300 | Screener + Scout + Chat Widget |
| Mid-Size Firm | $2,999 | 100 | 1,000 | All features + priority support |
| Enterprise | Custom | Unlimited | Unlimited | All + SLA + custom onboarding |

### 4.2 Promo Codes

Stored in `promo_codes` table. Can grant: fixed credits, percentage discount, or full plan access for N days. Validated at AI Recruiter chat payment step.

### 4.3 Stripe Webhooks

- `checkout.session.completed` → activate subscription, create tenant
- `invoice.payment_succeeded` → renew monthly credits
- `invoice.payment_failed` → flag tenant, send warning email
- `customer.subscription.deleted` → downgrade to free

---

## 5. Core Data Models

### 5.1 Jobs

| Field | Description |
|---|---|
| id | UUID PRIMARY KEY |
| tenant_id | UUID FK → tenants.id |
| job_ref | VARCHAR(20) — unique alphanumeric (e.g. MI0T4AM3), generated on creation |
| title | VARCHAR(200) — normalised 1–2 word title for internal search |
| title_variations | JSONB — array of similar titles to broaden search |
| job_type | VARCHAR(100) — e.g. Accountant, Java Developer |
| description | TEXT |
| required_skills | JSONB — array of skill strings |
| experience_years | INTEGER |
| salary_min | NUMERIC |
| salary_max | NUMERIC |
| location | VARCHAR(200) |
| location_variations | JSONB — nearby locations for broadened search |
| work_type | ENUM: onsite \| hybrid \| remote \| remote_global |
| tech_stack | JSONB — array |
| team_size | INTEGER NULLABLE |
| minimum_score | INTEGER DEFAULT 6 |
| hiring_manager_email | VARCHAR(255) |
| hiring_manager_name | VARCHAR(200) |
| evaluation_prompt | TEXT — auto-populated by AI if blank |
| outreach_email_prompt | TEXT |
| interview_questions_count | INTEGER DEFAULT 5 |
| custom_interview_questions | JSONB |
| ai_recruiter_config | JSONB — configurable chat instructions |
| status | ENUM: draft \| active \| paused \| closed |
| created_at | TIMESTAMPTZ |
| updated_at | TIMESTAMPTZ |

### 5.2 Candidates

| Field | Description |
|---|---|
| id | UUID PRIMARY KEY |
| tenant_id | UUID FK |
| job_id | UUID FK → jobs.id |
| name | VARCHAR(300) |
| title | VARCHAR(300) |
| snippet | TEXT — search result snippet |
| linkedin_url | VARCHAR(500) |
| email | VARCHAR(255) NULLABLE |
| email_source | ENUM: apollo \| hunter \| snov \| deduced \| manual \| unknown |
| company | VARCHAR(300) |
| location | VARCHAR(300) |
| brightdata_profile | JSONB — full public LinkedIn profile |
| resume_embedding | vector(1536) NULLABLE |
| suitability_score | INTEGER NULLABLE — 1–10 |
| score_reasoning | TEXT |
| status | ENUM: discovered \| profiled \| scored \| passed \| failed \| emailed \| applied \| tested \| interviewed \| rejected |
| outreach_email_sent_at | TIMESTAMPTZ NULLABLE |
| outreach_email_content | TEXT |
| gdpr_consent_given | BOOLEAN DEFAULT FALSE |
| gdpr_consent_at | TIMESTAMPTZ NULLABLE |
| created_at | TIMESTAMPTZ |

### 5.3 Applications

| Field | Description |
|---|---|
| id | UUID PRIMARY KEY |
| tenant_id | UUID FK |
| job_id | UUID FK |
| candidate_id | UUID FK NULLABLE |
| applicant_name | VARCHAR(300) |
| applicant_email | VARCHAR(255) |
| resume_storage_path | VARCHAR(500) — Supabase Storage path |
| resume_text | TEXT |
| resume_embedding | vector(1536) — pgvector |
| screening_score | INTEGER NULLABLE |
| screening_reasoning | TEXT |
| screening_status | ENUM: pending \| passed \| failed |
| test_status | ENUM: not_started \| invited \| in_progress \| completed \| passed \| failed |
| test_score | INTEGER NULLABLE |
| test_answers | JSONB |
| interview_invited | BOOLEAN DEFAULT FALSE |
| interview_invited_at | TIMESTAMPTZ NULLABLE |
| email_message_id | VARCHAR(500) — deduplication |
| gdpr_consent_given | BOOLEAN DEFAULT TRUE |
| received_at | TIMESTAMPTZ |
| created_at | TIMESTAMPTZ |

### 5.4 Promo Codes

| Field | Description |
|---|---|
| id | UUID PRIMARY KEY |
| tenant_id | UUID FK NULLABLE (NULL = platform-wide) |
| code | VARCHAR(50) UNIQUE |
| type | ENUM: credits \| discount_pct \| full_access |
| value | NUMERIC |
| expires_at | TIMESTAMPTZ NULLABLE |
| max_uses | INTEGER NULLABLE |
| uses_count | INTEGER DEFAULT 0 |
| is_active | BOOLEAN DEFAULT TRUE |

### 5.5 Chat Sessions

| Field | Description |
|---|---|
| id | UUID PRIMARY KEY |
| tenant_id | UUID FK |
| user_id | UUID FK — Supabase Auth user |
| job_id | UUID FK NULLABLE — linked once job created |
| messages | JSONB — [{role, content, timestamp}] |
| phase | ENUM: job_collection \| payment \| recruitment \| post_recruitment |
| created_at | TIMESTAMPTZ |
| updated_at | TIMESTAMPTZ |

> **IMPORTANT**: Chat history is stored server-side in chat_sessions, NOT in browser state. Frontend fetches latest session on page load via `GET /chat-sessions/current`.

### 5.6 RAG Documents

| Field | Description |
|---|---|
| id | UUID PRIMARY KEY |
| tenant_id | UUID FK |
| source_type | ENUM: website_scrape \| manual_upload |
| source_url | VARCHAR(500) NULLABLE |
| filename | VARCHAR(300) NULLABLE |
| content_text | TEXT |
| embedding | vector(1536) |
| created_at | TIMESTAMPTZ |

### 5.7 Job Audit Events

| Field | Description |
|---|---|
| id | UUID PRIMARY KEY |
| tenant_id | UUID FK (RLS enforced) |
| job_id | UUID FK → jobs.id |
| candidate_id | UUID FK NULLABLE |
| application_id | UUID FK NULLABLE |
| event_type | VARCHAR(80) — e.g. scout.outreach_email_sent |
| event_category | ENUM: talent_scout \| resume_screener \| payment \| system |
| severity | ENUM: info \| success \| warning \| error |
| actor | ENUM: system \| recruiter \| candidate \| hiring_manager |
| actor_user_id | UUID NULLABLE |
| summary | VARCHAR(500) — human-readable one-liner |
| detail | JSONB — full structured payload |
| duration_ms | INTEGER NULLABLE |
| created_at | TIMESTAMPTZ DEFAULT now() — IMMUTABLE, indexed |

> **IMPORTANT**: job_audit_events is **append-only**. No UPDATE or DELETE. GDPR erasure **redacts PII within detail JSONB in-place** (replace with '[REDACTED]') rather than deleting rows. A Postgres trigger fires `NOTIFY audit_{job_id}` after every INSERT, enabling real-time SSE delivery.

---

## 6. AI Recruiter Chat Interface

### 6.1 Server-Side Chat History

- History stored in `chat_sessions.messages` JSONB, never in browser
- Frontend loads via `GET /chat-sessions/current` on page load
- Each turn: frontend POSTs to `POST /chat-sessions/{id}/message`, backend appends to DB, calls AI, appends response, returns it
- If session grows long, backend summarises older messages and prepends summary
- 'New Job' button creates fresh chat_session record

### 6.2 Configurable AI Recruiter Instructions

- System prompt stored in `jobs.ai_recruiter_config` JSONB
- super_admin sets platform-wide default
- Tenant admin edits via Settings > AI Recruiter Prompt (plain-English editor with Reset to Default)
- JSON output requirements injected as a separate hidden system message — recruiter never sees raw JSON
- Phase transitions (job_collection → payment → recruitment → post_recruitment) managed by backend logic, not AI prompt

### 6.3 Chat Flow — Job Creation (16 Steps)

1. Greeting — AI invites recruiter to paste job description or describe role
2. Title extraction — normalised 1–2 word title + display title, confirm both
3. Title variations — 3–5 similar titles suggested (e.g. 'Accountant' → 'Finance Manager', 'Management Accountant', 'CPA'), recruiter edits
4. Required Skills — extracted from description, recruiter adds/removes
5. Experience — years confirmed
6. Salary Range — min/max (optional)
7. Location + Work Type — location confirmed, work_type asked (onsite/hybrid/remote/remote_global), location_variations auto-generated
8. Tech Stack — extracted + recruiter additions
9. Team Size — optional
10. Job Description — clean summary presented for confirmation
11. Hiring Manager — name and email (can be recruiter themselves)
12. Minimum Suitability Score — 1–10 scale explained, threshold set (default: 6)
13. Candidate Count — recruiter sets target, AI explains multi-variation strategy
14. Email Outreach Prompt — default shown, recruiter customises if desired
15. Resume Evaluation Prompt — AI generates default via Claude for this job_type, shown for customisation. Also: number of AI test questions (default 5) + manual questions
16. Confirmation & Payment — structured job summary card, confirm/edit, credit cost displayed, promo code or payment, job created, Scout triggered

### 6.4 Evaluation Report (Real-Time in Chat)

Updated via SSE stream (`GET /jobs/{id}/audit-stream`). Columns:

| Column | Description |
|---|---|
| Name | Candidate full name |
| Title | Current job title |
| Location | City/country |
| Email | Discovered email (masked if not found) |
| Status | discovered / profiled / scored / passed / failed / emailed |
| Evaluation Summary | Link → modal with score, reasoning, strengths, gaps |
| Resume | Link if received |
| LinkedIn | Direct profile link |
| Profile | Full BrightData profile modal |
| Score | N / 10 |
| Mailed | Yes/No |
| Invite Email | View exact email sent |
| Follow-up Email | Link when sent |

### 6.5 Post-Recruitment — Interview Scheduling

Recruiter asks AI to schedule interviews. AI collects: candidate name(s), datetime, meeting link, additional notes. Backend sends calendar invitations.

---

## 7. AI Talent Scout Module

Background Celery pipeline triggered after job confirmed and paid.

### 7.1 Step 1 — Candidate Discovery

**Search Strategy:**
- For each combination of `title_variation × location_variation`, call SERP API
- Each query: up to 100 results (10 per page × 10 pages via `start` param)
- Multiple variations = total pool far exceeds 100
- Query format: `"{title_variant} {location_variant} site:linkedin.com/in/"`
- Location matching rules by work_type:
  - `onsite` / `hybrid`: nearby cities within commuting distance
  - `remote`: major cities in same country
  - `remote_global`: no location filter

**ScrapingDog API:**
- `GET https://api.scrapingdog.com/google`
- Params: `api_key`, `query`, `advance_search=false`, `results=10`, `start=0..90`
- Response fields used: `organic_results[].title`, `organic_results[].snippet`, `organic_results[].link`
- Cost: 5 credits per request

**BrightData SERP (alternative):**
- Used when `tenant.search_provider = brightdata` or `both`
- Same query construction, response normalised to same internal structure

**Candidate Record Creation:**
- `name` — parsed from LinkedIn title (e.g. "Divesh Premdeep - Java Developer | LinkedIn" → "Divesh Premdeep")
- `title` — job title portion
- `snippet` — search result snippet
- `linkedin_url` — full URL
- `status = 'discovered'`
- Deduplication: skip if `linkedin_url` already exists for this job

**Audit event emitted:** `scout.candidate_discovered` (or `scout.candidate_duplicate_skipped`)

### 7.2 Step 2 — LinkedIn Profile Enrichment

- Call BrightData **LinkedIn People Profiles** dataset (collect by LinkedIn URL)
- Store full profile JSON in `candidates.brightdata_profile`
- Update status to `'profiled'`
- If error/empty: flag as `profile_unavailable`, skip scoring, retain in report
- **Audit events:** `scout.profile_enrichment_success` / `scout.profile_enrichment_failed`

### 7.3 Step 3 — Candidate Scoring

Call configured AI provider (Claude Sonnet default) with:
- Full job specification (title, skills, experience, location, description)
- Candidate's BrightData profile

AI returns JSON:
```json
{
  "score": 8,
  "reasoning": "2–3 sentence explanation",
  "strengths": ["point 1", "point 2", "point 3"],
  "gaps": ["gap 1", "gap 2"]
}
```

Scoring prompt template:
```
You are an expert recruiter. Given the following job specification and candidate LinkedIn profile,
score the candidate's suitability from 1 to 10. Return ONLY valid JSON.
Job Spec: {job_spec}
Candidate Profile: {profile}
Respond with: {"score": N, "reasoning": "...", "strengths": [...], "gaps": [...]}
```

- If `score >= job.minimum_score` → status = `'passed'`
- Else → status = `'failed'`
- **Audit events:** `scout.scoring_success` / `scout.scoring_failed_threshold` / `scout.scoring_error`

### 7.4 Step 4 — Email Discovery

Priority order based on `tenant.email_discovery_provider`:

**Apollo.io (optional, tenant-selectable):**
- `POST https://api.apollo.io/v1/people/match` with name + organization_name
- Bulk: `POST https://api.apollo.io/v1/people/bulk_match`
- `email_source = 'apollo'`

**Hunter.io (optional):**
- `POST https://api.hunter.io/v2/email-finder` with first_name, last_name, domain
- Store if confidence > 70%
- `email_source = 'hunter'`

**Snov.io (optional):**
- `POST https://api.snov.io/v1/get-emails-from-names`
- `email_source = 'snov'`

**EmailDeductionService (always available fallback):**
1. Look up company domain via Google search
2. Check formats: `firstname.lastname@domain`, `f.lastname@domain`, `firstname@domain`, `flastname@domain`
3. SMTP verify (connect, RCPT TO, check 250 response — do NOT send)
4. Rate limit: max 5 SMTP checks per minute per domain
5. Store with `email_source = 'deduced'` if verified
6. If nothing found: `email_source = 'unknown'`, flag for manual

**Audit events:** `scout.email_found_apollo` / `scout.email_found_hunter` / `scout.email_found_deduced` / `scout.email_not_found`

### 7.5 Step 5 — Hyper-Personalised Email Outreach

For each candidate with `status = 'passed'` and discovered email:

- AI generates email using `job.outreach_email_prompt` as system prompt
- Uses candidate's BrightData profile (current role, company, skills, summary)
- Includes job ref and application instructions:
  `"To apply, email your resume to {tenant.email_inbox} with subject line: {job_ref} – {your_name}"`

Default outreach prompt:
```
You are a professional recruiter writing to a passive candidate. Write a concise, friendly,
and genuinely personalised email (max 200 words) that references specific details from the
candidate's current role and experience. Do not sound like a mass email. Highlight why this
specific opportunity is relevant to their career. Include the job reference and application
instructions. Sign off with the recruiter's name.
```

- Store final email in `candidates.outreach_email_content`
- Status → `'emailed'`
- Send via SendGrid (tenant key if configured, platform key fallback)
- **GDPR**: include unsubscribe link in every outreach email
- **Audit event:** `scout.outreach_email_sent` / `scout.outreach_email_failed`

### 7.6 Step 6 — Daily Candidate Summary

Celery beat task, daily at 08:00 AEST. For each active job with activity in last 24h:
- Email to `job.hiring_manager_email`
- Contents: newly discovered/contacted candidates with scores, candidates who applied, link to evaluation report

---

## 8. AI Resume Screener Module

Sold independently. Candidates from Talent Scout and candidates from job boards both email to same tenant inbox.

### 8.1 Mailbox Polling

Celery periodic task every 5 minutes via IMAP4_SSL. Per email:

1. Parse subject for `job_ref` (e.g. "MI0T4AM3 – John Smith Application")
2. Look up job by `job_ref` + `tenant_id`. If not found: log and discard
3. Extract sender email and name from headers
4. Check for PDF/DOCX attachment. If none: auto-reply requesting resubmission
5. Store resume in Supabase Storage: `{tenant_id}/{job_id}/{applicant_email}/resume.{ext}`
6. Extract text: `pdfplumber` (PDF), `python-docx` (DOCX)
7. Generate embedding from resume text. Store in `resume_embedding` (pgvector)
8. Create Application record. If email matches existing Candidate → set `candidate_id`
9. Deduplicate via email Message-ID header
10. Trigger screening task

**Audit events:** `screener.email_received`, `screener.job_ref_matched`, `screener.resume_extracted`, `screener.no_attachment`, `screener.duplicate_application`

> IMAP config: platform-managed by default (`email_inbox_host/port/user/password` in tenant settings). Larger firms can override with their own mail server.

### 8.2 Resume Screening

- Compare resume vs job spec using **cosine similarity** between `resume_embedding` and job spec embedding (pgvector)
- Call AI with `job.evaluation_prompt` and extracted resume text for detailed scoring

Default evaluation prompt (generated by Claude at job creation):
```
Given this is a {job_type} role requiring {experience_years}+ years experience
with skills in {required_skills}, evaluate the following resume. Score 1–10 for suitability.
Return JSON: {"score": N, "reasoning": "...", "strengths": [...], "gaps": [...], "recommended_action": "pass|fail"}
```

- If `score >= job.minimum_score` → `screening_status = 'passed'`
- Else → `'failed'`, send AI-generated polite rejection email

**Audit events:** `screener.screening_passed` / `screener.screening_failed` / `screener.rejection_email_sent`

### 8.3 AI Competency Test

Test link: `/test/{application_id}/{token}` (public, token-protected)

**Test Generation:**
- `job.interview_questions_count` (default 5) AI-generated questions for this `job_type` + `required_skills`
- All `job.custom_interview_questions` appended
- Stored in `test_sessions` table

**Test Interface** — browser chat, AI examiner (Claude Sonnet):
- Asks one question at a time
- Probes with follow-ups if vague
- Friendly, professional tone
- Does not reveal correct/incorrect
- Ends gracefully after all questions

**Test Scoring:**
- Overall score out of 10
- Per-question assessment
- Recommended action: pass | fail
- If passed: `test_status = 'passed'`
- If failed: polite rejection email, `test_status = 'failed'`

**Audit events:** `screener.test_invited`, `screener.test_started`, `screener.test_question_answered`, `screener.test_completed`, `screener.test_scored`

### 8.4 Interview Invitation Workflow

For `test_status = 'passed'`, email hiring manager:
- Candidate name, screening score, test score, evaluation summary
- **'Invite to Interview' button** → `/actions/invite-interview/{application_id}/{token}`
- Token = signed JWT (7-day expiry, one-time-use) — no dashboard login required

When hiring manager clicks:
1. Token verified (valid, not used, not expired)
2. `interview_invited = TRUE`, `interview_invited_at` stamped
3. Interview invitation email sent to candidate
4. Confirmation sent to hiring manager

**Audit events:** `screener.hm_notified`, `screener.interview_invited`, `screener.interview_invite_expired`

---

## 9. Firm Chat Widget & RAG Pipeline

Available from Small Firm plan upward.

### 9.1 Website Scraping

On tenant creation (if `website_url` provided):
1. Celery task crawls website (crawl4ai or httpx + BeautifulSoup)
2. Each page: text chunked (max 500 tokens/chunk), embeddings generated
3. Stored in `rag_documents` with `source_type = 'website_scrape'`
4. Firm can trigger re-scrape from Settings > Knowledge Base

### 9.2 Document Upload

- Firms upload PDF/DOCX/TXT from Settings > Knowledge Base
- Stored in Supabase Storage
- Text extracted, chunked, embedded → `rag_documents` with `source_type = 'manual_upload'`
- Firm can delete anytime (GDPR right to erasure)

### 9.3 Chat Widget

- Lightweight JS snippet for firm's website `<head>`
- Backed by `GET /widget/{tenant_slug}/chat` (public, rate-limited)
- RAG: embed query → cosine search `rag_documents` → inject top-k chunks into Claude prompt
- Branded with firm name, colour-configurable from dashboard

---

## 10. Candidate Search & Management UI

### 10.1 Candidate Search

- Full-text search: name, title, company, skills, location
- Filters: job, status, score range, location, date
- Paginated table with score badges and status pills

### 10.2 Candidate Profile Page

- Full BrightData profile display
- Score history across multiple jobs
- Outreach email history with timestamps
- Resume and application history
- Status update control (manual change)
- Notes field (recruiter-only)
- **GDPR Delete button** — permanently anonymises all PII, embeddings, BrightData profile

---

## 11. Super Admin Panel

Route: `/super-admin` — separate auth guard, `super_admin` role only.

- View all tenants: name, plan, credits, status, last active
- Impersonate any tenant (logged audit event)
- **Platform API key management**: Anthropic, OpenAI, SendGrid, ScrapingDog, BrightData
- Default AI provider setting (Anthropic or OpenAI)
- Billing management: Stripe subscriptions, manual credit adjustments
- Platform-wide promo code creation
- System health: Celery queue depth, failed tasks, recent errors
- Platform audit view: system + payment events across all tenants (no candidate PII)

---

## 12. Admin Dashboard

Next.js 14 App Router at `app.airecruiterz.com`. Supabase Auth protected. i18n: EN, DE, ES, FR.

| Page | Description |
|---|---|
| / (Home) | Stats overview: active jobs, candidates today, applications, credits |
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
| /help | In-app user guide |
| /super-admin | Super admin panel |

---

## 13. Backend API Routes (FastAPI)

All routes prefixed `/api/v1`. Require JWT Bearer unless marked public.

### 13.1 Auth & Tenant
- `POST /auth/signup` (public)
- `POST /auth/login` (public)
- `GET /tenants/me`
- `PATCH /tenants/me`
- `GET /super-admin/tenants` (super_admin only)
- `POST /super-admin/impersonate/{tenant_id}` (super_admin only, logged)

### 13.2 Chat Sessions
- `GET /chat-sessions/current`
- `POST /chat-sessions/{id}/message`
- `POST /chat-sessions/new`

### 13.3 Jobs
- `GET /jobs`
- `POST /jobs`
- `GET /jobs/{id}`
- `PATCH /jobs/{id}`
- `POST /jobs/{id}/trigger-scout`
- `GET /jobs/{id}/evaluation-report` (SSE)

### 13.4 Candidates
- `GET /candidates` (search + filter)
- `GET /candidates/{id}`
- `PATCH /candidates/{id}`
- `DELETE /candidates/{id}` (GDPR erasure)
- `POST /candidates/{id}/send-outreach`

### 13.5 Applications
- `GET /applications?job_id={id}`
- `GET /applications/{id}`
- `POST /applications/{id}/trigger-test`
- `GET /test/{id}/{token}` (public)
- `POST /test/{id}/message` (public)
- `GET /actions/invite-interview/{id}/{token}` (public)

### 13.6 RAG & Widget
- `POST /rag/scrape`
- `POST /rag/documents`
- `DELETE /rag/documents/{id}`
- `GET /widget/{slug}/chat` (public, rate-limited)

### 13.7 Promo Codes & Webhooks
- `GET /promo-codes`
- `POST /promo-codes`
- `DELETE /promo-codes/{id}`
- `POST /promo-codes/validate` (public)
- `POST /webhooks/stripe` (public, signature verified)
- `POST /webhooks/email-received` (HMAC verified)

### 13.8 Audit Trail
- `GET /jobs/{id}/audit-stream` (SSE — real-time events)
- `GET /jobs/{id}/audit-events` (paginated history + export)
- `GET /super-admin/audit` (super_admin only)

---

## 14. Background Task Architecture (Celery)

Redis broker + result backend. Railway hosts FastAPI app and Celery worker as separate services.

### 14.1 Talent Scout Task Chain

```
Task 1: talent_scout.discover_candidates(job_id)
  → iterates all title × location combinations
  → ScrapingDog/BrightData SERP calls with pagination
  → creates candidate records
  → fans out to Tasks 2–5 per candidate (Celery chord)

Task 2: talent_scout.enrich_profile(candidate_id)
  → BrightData LinkedIn People Profiles

Task 3: talent_scout.score_candidate(candidate_id)
  → Claude/OpenAI scoring

Task 4: talent_scout.discover_email(candidate_id)
  → Apollo/Hunter/Snov + EmailDeductionService

Task 5: talent_scout.send_outreach(candidate_id)
  → Claude email generation + SendGrid
```

Parallel concurrency limit: 5 candidates at a time. Progress written to `job_audit_events` → triggers Postgres NOTIFY → SSE.

### 14.2 Scheduled Tasks (Celery Beat)

| Task | Schedule |
|---|---|
| poll_mailboxes | Every 5 minutes |
| send_daily_summaries | Daily 08:00 AEST |
| cleanup_expired_tokens | Daily 00:00 |
| sync_stripe_plans | Hourly |
| rag_refresh | Weekly per tenant (if auto_refresh enabled) |

---

## 15. Job Audit Trail

### 15.1 Data Model

See Section 5.7 for the `job_audit_events` table definition.

**Key rules:**
- Append-only — no UPDATE or DELETE ever
- GDPR erasure: redact PII in `detail` JSONB in-place, do not delete the row
- Postgres trigger fires `NOTIFY audit_{job_id}` JSON payload after every INSERT
- RLS: tenant can SELECT their own rows only

### 15.2 Talent Scout Event Types

| event_type | severity | Example summary |
|---|---|---|
| scout.job_started | info | Talent Scout started for job 'Java Developer' |
| scout.search_query_built | info | Built 6 queries (3 titles × 2 locations) |
| scout.serp_call_success | success | ScrapingDog returned 10 results (page 1) |
| scout.serp_call_failed | error | ScrapingDog API 429 — retrying in 30s |
| scout.candidate_discovered | info | Discovered: Divesh Premdeep |
| scout.candidate_duplicate_skipped | info | Skipped duplicate linkedin URL |
| scout.profile_enrichment_started | info | Requesting BrightData profile |
| scout.profile_enrichment_success | success | Profile received (16 yrs exp, 4 roles) |
| scout.profile_enrichment_failed | warning | Empty profile — skipping scoring |
| scout.scoring_started | info | Scoring candidate against job spec |
| scout.scoring_success | success | Scored 9/10 — passed threshold |
| scout.scoring_failed_threshold | info | Scored 4/10 — below threshold |
| scout.scoring_error | error | Claude API error — will retry |
| scout.email_discovery_started | info | Discovering email via Apollo |
| scout.email_found_apollo | success | Email found via Apollo (verified) |
| scout.email_found_hunter | success | Email found via Hunter.io (82%) |
| scout.email_found_snov | success | Email found via Snov.io |
| scout.email_found_deduced | success | Email deduced via SMTP verification |
| scout.email_not_found | warning | No email found — flagged for manual |
| scout.outreach_email_generated | info | Email generated (198 words) |
| scout.outreach_email_sent | success | Outreach email sent via SendGrid |
| scout.outreach_email_failed | error | SendGrid delivery failed |
| scout.job_completed | success | Scout complete: 47 discovered, 31 passed, 28 emailed |

### 15.3 Resume Screener Event Types

| event_type | severity | Example summary |
|---|---|---|
| screener.email_received | info | Email received from john.smith@gmail.com |
| screener.job_ref_matched | success | Job ref matched to 'Java Developer' |
| screener.job_ref_not_found | warning | Job ref not found — discarded |
| screener.resume_extracted | info | Resume extracted: 847 words, 2 pages |
| screener.no_attachment | warning | No attachment — auto-reply sent |
| screener.duplicate_application | info | Duplicate Message-ID — skipped |
| screener.candidate_linked | info | Applicant matched to Scout candidate |
| screener.embedding_generated | info | Resume embedding stored (1536 dims) |
| screener.screening_started | info | Screening resume against job spec |
| screener.screening_passed | success | Scored 8/10 — passed |
| screener.screening_failed | info | Scored 3/10 — below threshold |
| screener.rejection_email_sent | info | Rejection email sent |
| screener.test_invited | success | Test invitation sent |
| screener.test_started | info | Candidate opened test link |
| screener.test_question_answered | info | Q3 answered (45 seconds) |
| screener.test_completed | success | All 5 questions answered |
| screener.test_scored | success | Test scored 8/10 — passed |
| screener.test_score_failed | info | Test scored 4/10 — failed |
| screener.hm_notified | success | Hiring manager notified |
| screener.interview_invited | success | Interview invitation sent to candidate |
| screener.interview_invite_expired | warning | Token expired (7-day limit) |

### 15.4 Payment & System Events

| event_type | Description |
|---|---|
| payment.credit_charged | Credit deducted for job search |
| payment.promo_code_applied | Promo code applied at checkout |
| system.task_retry | Celery task retrying (attempt N/3) |
| system.task_failed_permanent | Task permanently failed after 3 attempts |
| system.gdpr_erasure | Candidate PII erased |
| system.data_export | Candidate data exported |

### 15.5 Real-Time Delivery

- FastAPI SSE endpoint: `GET /api/v1/jobs/{id}/audit-stream`
- asyncpg `add_listener()` subscribes to Postgres NOTIFY channel `audit_{job_id}`
- DB trigger fires NOTIFY with new event row as JSON after each INSERT
- Client reconnect: send `last_event_id` query param → server replays since that timestamp
- Single SSE stream drives both Evaluation Report table and Audit Trail feed

### 15.6 Audit Trail UI

Job detail page `/jobs/{id}` — tabbed interface:
- **Tab 1**: Evaluation Report (candidate table, SSE-driven)
- **Tab 2**: Audit Trail (chronological feed)

Feed columns per event:
- Colour-coded severity icon (info=blue, success=green, warning=amber, error=red)
- Category badge (Talent Scout / Resume Screener / Payment / System)
- Timestamp (relative, absolute on hover)
- Summary text
- Expand chevron → full detail JSONB as key-value list
- Candidate name → clickable link to candidate profile

Controls: filter by category, filter by severity, search by candidate/event type, Export CSV, live pulsing indicator.

---

## 16. GDPR Compliance

### 16.1 Lawful Basis

- **Talent Scout outreach**: legitimate interest. Every outreach email must include unsubscribe link. `opted_out = TRUE` → no further emails.
- **Resume processing**: consent (candidate submits voluntarily). `gdpr_consent_given = TRUE` on Application creation.
- **BrightData profiles**: publicly available data, legitimate interest. Only used for recruitment evaluation.

### 16.2 Data Subject Rights

- **Right to erasure**: `DELETE /candidates/{id}` and `DELETE /applications/{id}` anonymise all PII. Audit trail PII redacted in-place.
- **Right to access**: data export (JSON/CSV) available from admin dashboard.
- **Right to rectification**: recruiter can edit candidate data from profile page.

### 16.3 Data Retention

- Default: 12 months after last activity
- Tenant-configurable: 3–36 months
- Celery task flags records at retention limit, notifies tenant admin
- Resumes deleted in sync with Application record erasure

### 16.4 Data Processing Agreement

- Tenants must accept DPA during onboarding before candidate search activates
- `gdpr_dpa_signed_at` stamped on acceptance
- Tenant = data controller, airecruiterz.com = data processor

### 16.5 Technical Measures

- All data in transit: TLS 1.3
- All data at rest: AES-256 (Supabase)
- Tenant API keys: additionally Fernet-encrypted before DB storage
- Audit log for all data access, deletions, exports
- Data residency: EU Supabase region for EU tenants

---

## 17. Email Templates

All HTML, Jinja2 templates, SendGrid delivery. Support EN, DE, ES, FR.

| Template | Description |
|---|---|
| outreach_invite | Hyper-personalised candidate outreach (AI body + Jinja wrapper + unsubscribe link) |
| resume_rejection | Polite rejection after screening fails (AI-generated) |
| test_invitation | Invite to competency test with unique link |
| test_rejection | Polite rejection after test failure (AI-generated) |
| interview_invitation_hm | Hiring manager: candidate summary + Invite to Interview button |
| interview_invitation_candidate | Candidate: interview invitation |
| daily_summary | Hiring manager digest: new candidates + applications |
| welcome | Tenant sign-up welcome with onboarding link |
| payment_failed | Stripe payment failure alert |
| promo_code | Share promo code with prospect |
| data_retention_warning | Alert tenant that data approaching retention limit |
| gdpr_unsubscribe_confirm | Confirm candidate removed from outreach |

---

## 18. Automated Testing Strategy

No manual tester. All external APIs mocked. CI via GitHub Actions on every push to main.

### 18.1 Unit Tests (pytest)

- `EmailDeductionService` — all format variants, SMTP mock, rate limiter
- Scoring prompts — construction for various job types and providers
- Title variation generator — AI mock
- Location variation generator — per work_type logic
- Job creation — field extraction, job_ref uniqueness
- Promo code validation — expiry, usage limits
- Stripe webhook handler — each event type
- GDPR erasure — verify PII anonymisation
- Embedding generation — mock embedding API, verify vector stored
- Audit trail — event written after each pipeline step, GDPR redaction, SSE order

### 18.2 Integration Tests (pytest + httpx AsyncClient)

- Full auth flow: signup → login → JWT → protected route
- Job creation via chat session: POST message → mock AI → verify job created
- Talent Scout pipeline: mock ScrapingDog + BrightData + Claude + SendGrid → verify candidate records
- Multi-variation search: verify all title × location query combinations generated
- Resume Screener: mock IMAP + upload → verify Application + embedding created
- Test session: mock Claude → simulate answers → verify scoring
- Interview invitation: token generation, HM email, candidate email on click
- Stripe webhooks: plan changes, credit grants, downgrade
- GDPR delete: verify anonymisation
- RAG pipeline: mock scrape → verify rag_documents + embeddings
- Widget chat: mock RAG retrieval → verify response
- Audit trail: full Scout mock pipeline → verify all event_types in order

### 18.3 End-to-End Tests (Playwright)

- Recruiter posts job via AI chat → verify job in DB
- Evaluation report updates (mock SSE)
- Hiring manager clicks Invite to Interview → confirmation page
- Candidate completes test → test_status updated
- Super admin impersonates tenant → scoped access
- i18n: switch to DE/ES/FR → verify translated UI

### 18.4 Mock Strategy

| Service | Mock |
|---|---|
| ScrapingDog / BrightData SERP | Fixture JSON with sample organic_results |
| BrightData LinkedIn | Fixture JSON with sample profiles |
| Claude API / OpenAI | respx mock → deterministic JSON |
| SendGrid | Mock client capturing emails in-memory |
| Apollo / Hunter / Snov | Fixture JSON with sample enrichment |
| SMTP (deduction) | Mock socket returning 250 |
| IMAP | Mock mailbox with pre-loaded test emails |
| Stripe | stripe-mock or raw POST with test payloads |
| Embedding API | Mock returning deterministic 1536-dim zero vectors |

### 18.5 Test Configuration

- Separate Supabase project for testing (`TEST_DATABASE_URL`)
- Each run creates/destroys own tenant via fixtures
- `pytest-asyncio` for all async tests
- Coverage target: 85% minimum
- GitHub Actions: Python 3.12 on ubuntu-latest

---

## 19. Project Structure

```
ai-recruiter/
├── backend/
│   ├── app/
│   │   ├── main.py                       # FastAPI app factory
│   │   ├── config.py                     # Settings (pydantic-settings)
│   │   ├── database.py                   # Supabase/asyncpg session
│   │   ├── i18n/                         # Translation strings (en, de, es, fr)
│   │   ├── models/
│   │   │   ├── tenant.py
│   │   │   ├── job.py
│   │   │   ├── candidate.py
│   │   │   ├── application.py
│   │   │   ├── chat_session.py
│   │   │   ├── rag_document.py
│   │   │   ├── job_audit_event.py
│   │   │   └── promo_code.py
│   │   ├── schemas/                      # Pydantic v2 schemas
│   │   ├── routers/
│   │   │   ├── auth.py
│   │   │   ├── chat_sessions.py
│   │   │   ├── jobs.py
│   │   │   ├── candidates.py
│   │   │   ├── applications.py
│   │   │   ├── audit.py
│   │   │   ├── rag.py
│   │   │   ├── widget.py
│   │   │   ├── promo_codes.py
│   │   │   ├── super_admin.py
│   │   │   └── webhooks.py
│   │   ├── services/
│   │   │   ├── talent_scout.py
│   │   │   ├── resume_screener.py
│   │   │   ├── email_deduction.py
│   │   │   ├── apollo.py
│   │   │   ├── hunter.py
│   │   │   ├── snov.py
│   │   │   ├── brightdata.py
│   │   │   ├── scrapingdog.py
│   │   │   ├── claude_ai.py
│   │   │   ├── openai_ai.py
│   │   │   ├── ai_provider.py            # Facade — routes to claude or openai
│   │   │   ├── embeddings.py
│   │   │   ├── rag_pipeline.py
│   │   │   ├── audit_trail.py
│   │   │   ├── gdpr.py
│   │   │   └── sendgrid_email.py
│   │   ├── tasks/
│   │   │   ├── celery_app.py
│   │   │   ├── talent_scout_tasks.py
│   │   │   ├── screener_tasks.py
│   │   │   └── scheduled_tasks.py
│   │   └── templates/                    # Jinja2 email templates
│   ├── tests/
│   │   ├── conftest.py
│   │   ├── unit/
│   │   ├── integration/
│   │   └── e2e/
│   ├── migrations/                       # Alembic migrations
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/                             # Next.js 14 App Router
│   ├── app/
│   │   ├── [locale]/                     # i18n routing (en/de/es/fr)
│   │   ├── chat/
│   │   ├── jobs/
│   │   ├── candidates/
│   │   ├── settings/
│   │   └── super-admin/
│   ├── components/
│   ├── public/widget/                    # Embeddable widget JS
│   └── package.json
├── .github/workflows/ci.yml
├── railway.toml
├── SPEC.md                               ← THIS FILE
└── guidelines.md                         ← READ BEFORE EVERY TASK
```

---

## 20. Environment Variables

### 20.1 Platform-Level (Railway only — super_admin managed)

| Variable | Description |
|---|---|
| ANTHROPIC_API_KEY | Default Claude Sonnet API key |
| OPENAI_API_KEY | Default OpenAI API key |
| SUPABASE_URL | Supabase project URL |
| SUPABASE_SERVICE_KEY | Supabase service role key (server-side only) |
| SUPABASE_ANON_KEY | Supabase anon key (frontend) |
| REDIS_URL | Redis connection string |
| STRIPE_SECRET_KEY | Stripe secret key |
| STRIPE_WEBHOOK_SECRET | Stripe webhook signing secret |
| SENDGRID_API_KEY | Platform SendGrid key |
| IMAP_HOST | Shared mail server host |
| IMAP_PORT | 993 |
| IMAP_MASTER_PASSWORD | Master IMAP credential |
| SCRAPINGDOG_API_KEY | Platform ScrapingDog key |
| BRIGHTDATA_API_KEY | Platform BrightData key |
| ENCRYPTION_KEY | Fernet key for tenant API key encryption |
| FRONTEND_URL | https://app.airecruiterz.com |
| ENVIRONMENT | development \| staging \| production |

### 20.2 Tenant-Overridable (admin settings page)

Tenants can override: `ai_provider`, `ai_api_key`, `search_provider`, `scrapingdog_api_key`, `brightdata_api_key`, `email_discovery_provider`, `apollo_api_key`, `hunter_api_key`, `snov_api_key`, `sendgrid_api_key`, `email_inbox_host/port/user/password`.

---

## 21. Development Tooling

**Generation approach:** Claude Code CLI for initial scaffold → PyCharm + Junie for iteration.

**Generation order** (must follow dependency sequence):
1. Database models + Alembic migrations
2. Pydantic v2 schemas
3. FastAPI app factory + config + database session
4. Auth router + Supabase JWT middleware
5. Tenant + Job + Candidate + Application routers
6. AI provider facade (claude_ai.py + openai_ai.py + ai_provider.py)
7. Services: ScrapingDog, BrightData, email discovery, EmailDeductionService
8. Talent Scout service + Celery tasks
9. Resume Screener service + IMAP poller + Celery tasks
10. Audit trail service + Postgres trigger + SSE endpoint
11. RAG pipeline + widget endpoint
12. Stripe webhooks + promo codes
13. Email templates (Jinja2) + SendGrid service
14. Scheduled Celery beat tasks
15. Unit tests for all services
16. Integration tests for all routes
17. Next.js frontend (pages in order: auth → dashboard → chat → jobs → candidates → applications → settings → super-admin)
18. Playwright E2E tests

---

## 22. Security Considerations

- Tenant API keys encrypted with Fernet before Supabase storage
- Supabase RLS enforces row-level tenant isolation on every query
- Stripe webhook signatures verified with `stripe.Webhook.construct_event()`
- Test and interview tokens: signed JWTs, 7-day expiry, one-time-use flag
- IMAP credentials stored encrypted, connections use IMAP4_SSL
- EmailDeductionService rate-limited: 5 SMTP checks per minute per domain
- All inputs validated with Pydantic v2
- Public routes (`/test`, `/actions`, `/widget`) token-protected and rate-limited
- CORS: frontend domain only in production
- Audit log records all data access, deletions, exports, impersonations
- `/super-admin` routes require separate `super_admin` role guard

---

## 23. Deployment Checklist

1. Create Supabase project (EU region for GDPR). Run Alembic migrations. Enable RLS. Enable pgvector extension.
2. Create Railway project → FastAPI service + Celery worker + Redis. Set all platform env vars.
3. Create Vercel project → connect frontend repo → set `NEXT_PUBLIC_SUPABASE_URL` and `NEXT_PUBLIC_API_URL`.
4. Configure Stripe → 6 plan products/prices → webhook to `https://api.airecruiterz.com/api/v1/webhooks/stripe`.
5. Set up shared mail server → per-tenant mailbox provisioning.
6. Run GitHub Actions CI → all tests pass → deploy.
7. Smoke test: sign up → post test job → verify full pipeline.
8. GDPR check: DPA prompt on first login, unsubscribe in outreach emails, GDPR delete works.

---

## 24. Resolved Items from v1 & v2

| Item | Resolution |
|---|---|
| BrightData product | LinkedIn People Profiles — collect by LinkedIn URL |
| Email infrastructure | Platform-managed shared server by default. Larger firms can override with own IMAP. |
| Apollo.io | Optional, tenant-selectable. Hunter.io and Snov.io also integrated. Domain deduction always available. |
| Stripe pricing | Free / Casual $99 / Individual $499 / Small Firm $999 / Mid-Size $2,999 / Enterprise custom |
| Frontend framework | Next.js 14 App Router confirmed |
| Chat history | Server-side in chat_sessions table — not browser state |
| AI provider | Anthropic (default) + OpenAI (optional) — switchable at tenant level |
| SERP provider | ScrapingDog + BrightData SERP — both integrated, tenant-selectable |
| RAG / chat widget | Section 9. Website scraping + document upload + embeddable widget. Small Firm plan+. |
| GDPR | Full section (Section 16). Lawful basis, data rights, retention, DPA, technical measures. |
| Multi-language | EN, DE, ES, FR at launch via Next.js i18n routing |
| Candidate management UI | Section 10 — search, filter, profile, notes, GDPR delete |
| Domain | airecruiterz.com throughout |
| Embeddings | Resume + job spec embeddings in pgvector for similarity scoring |
| Audit trail | Section 15. 45 typed events, real-time SSE via Postgres LISTEN/NOTIFY, tabbed UI on job detail page |
