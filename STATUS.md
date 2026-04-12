# AI Recruiter — Project Status & Context
*Last updated: April 12, 2026*
*This file is the single source of truth for Claude CLI sessions*

---

## HOW TO USE THIS FILE

At the start of every Claude CLI session type:
  Read ~/ai-recruiter/STATUS.md for full project context, then tell me what the next priority task is.

After completing work type:
  Update ~/ai-recruiter/STATUS.md — mark completed items as done, add any new known issues.

---

## PROJECT OVERVIEW

AI Recruiter is a multi-tenant SaaS recruitment automation platform at airecruiterz.com.
Owner: Marcus Bahadur (AIWorkerz, Brisbane, Australia)
Company name in app: AIWorkerz

Technology Stack:
- Backend: FastAPI (Python 3.12, async) + SQLAlchemy 2.x + asyncpg
- Database: Supabase PostgreSQL 15 + pgvector (project: ydizybmxfesbfkqpvbzr, ap-southeast-1)
- Task Queue: Celery + Redis
- Frontend: Next.js 16.2.2 (TypeScript, App Router, Turbopack)
- Auth: Supabase Auth (JWT)
- AI: OpenAI GPT-4o (primary) + Anthropic Claude (fallback) — ALWAYS try OpenAI first
- Embeddings: OpenAI text-embedding-3-small (1536 dims) — always OpenAI regardless of AI provider setting
- Email: SendGrid (outbound) + IMAP polling (inbound)
- Payments: Stripe (subscriptions)
- Candidate Discovery: ScrapingDog (SERP) + BrightData (LinkedIn profiles)
- Audio Transcription: OpenAI Whisper API
- File Storage: Supabase Storage (buckets: recordings, resumes)

---

## LOCAL DEVELOPMENT

Starting everything:

Terminal 1 - Backend:
  cd ~/ai-recruiter/backend && source venv/bin/activate && uvicorn app.main:app --reload

Terminal 2 - Frontend:
  cd ~/ai-recruiter/frontend && npm run dev

Terminal 3 - Celery:
  cd ~/ai-recruiter/backend && source venv/bin/activate && celery -A app.tasks.celery_app worker --loglevel=info

Terminal 4 - Claude CLI:
  cd ~/ai-recruiter && claude --dangerously-skip-permissions

Redis check (run if Celery won't connect):
  sudo service redis-server start && redis-cli ping

Stripe webhook (only for payment testing):
  stripe listen --forward-to localhost:8000/api/v1/webhooks/stripe

URLs:
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- Dashboard: http://localhost:3000/en (NOT /en/dashboard)

---

## KEY CONFIGURATION

Supabase:
- Project: ydizybmxfesbfkqpvbzr (ap-southeast-1)
- DATABASE_URL: postgresql+asyncpg://postgres.ydizybmxfesbfkqpvbzr:Recruiter2026dev@aws-1-ap-southeast-1.pooler.supabase.com:5432/postgres

Email:
- SendGrid from: marcus.bahadur@aiworkerz.com
- EMAIL_TEST_MODE=true (all emails go to marcus.bahadur@aiworkerz.com)
- IMAP inbox: marcus.bahadur@aiworkerz.com / mail.privateemail.com:993
- Platform jobs email: jobs@aiworkerz.com

Stripe (Test Mode):
- Recruiter: price_1TKTz6A5SiOfWjX1qr86cpx6 ($499/mo)
- Agency Small: price_1TKTzlA5SiOfWjX1l9f6GkTE ($999/mo)
- Agency Medium: price_1TKU0PA5SiOfWjX18ycn5bTL ($2,999/mo)

Other:
- SUPER_ADMIN_EMAIL: marcus@aiworkerz.com
- PLATFORM_JOBS_EMAIL: jobs@aiworkerz.com
- FRONTEND_URL: http://localhost:3000
- BACKEND_URL: http://localhost:8000

---

## TEST DATA

Test Tenant:
- ID: 21db1a7b-7c6b-4e8b-a407-9ce3c5a07412
- Name: Marcus Recruitment
- Email: marcus@aiworkerz.com
- Plan: recruiter

Test Jobs:
1. Senior Java Developer (Mode 1 - Talent Scout)
   - ID: a1d00834-4725-4e4b-bb45-b7e2a235bebc
   - Ref: JIYVD3NU
   - Location: Sydney, hybrid
   - Minimum score: 4 (RESET TO 6 BEFORE PRODUCTION)
   - 20 candidates discovered and emailed

2. Senior React Developer (Mode 2 - Screener Only)
   - Ref: 9ZMJE18W
   - Interview type: audio
   - Minimum score: 1 (RESET TO 6 BEFORE PRODUCTION)

Test email addresses:
- marcus@aiworkerz.com — main test account, super admin login
- marcusbahadur@protonmail.com — sends test resumes to the inbox
- marcus.bahadur@aiworkerz.com — IMAP inbox, receives candidate emails

Supabase Storage buckets (must exist):
- recordings — audio/video interview recordings (MUST BE CREATED MANUALLY in Supabase dashboard)

---

## AI PROVIDER ARCHITECTURE

Priority order (ALWAYS):
1. OpenAI GPT-4o — tried first for ALL AI calls
2. Anthropic Claude — fallback if OpenAI fails
3. Both fail — Celery retries every 300s with max_retries=None (forever)

Key files:
- ~/ai-recruiter/backend/app/services/ai_provider.py — facade, tries OpenAI first
- ~/ai-recruiter/backend/app/services/openai_ai.py — OpenAI wrapper
- ~/ai-recruiter/backend/app/services/claude_ai.py — Anthropic wrapper
- ~/ai-recruiter/backend/app/services/embeddings.py — SYNCHRONOUS embeddings for Celery

CRITICAL: generate_embedding() in embeddings.py uses synchronous OpenAI client.
DO NOT change to async — it breaks Celery workers with "Event loop is closed" errors.

---

## PIPELINE ARCHITECTURE

Talent Scout Pipeline (Mode 1 jobs):
  discover_candidates (ScrapingDog)
    -> enrich_profile (BrightData)
    -> score_candidate (AI 1-10)
    -> discover_email (Apollo/Hunter/Snov/EmailDeduction)
    -> send_outreach (personalised email via SendGrid)

File: ~/ai-recruiter/backend/app/tasks/talent_scout_tasks.py

Resume Screener Pipeline (both modes):
  poll_mailboxes (every 5 min, IMAP4_SSL)
    -> screen_resume (AI scores resume 1-10)
    -> invite_to_test (generates questions, sends test link with interview type instructions)
    -> [candidate completes test at /test/{id}/{token}]
    -> score_test (AI scores answers, generates full evaluation report)
    -> notify_hiring_manager (email with all scores + Invite to Interview button)
       OR send_rejection_email (if score below minimum)
  -> [HM clicks Invite to Interview one-click link]
    -> interview_invited (candidate gets invite, HM gets confirmation)

File: ~/ai-recruiter/backend/app/tasks/screener_tasks.py

Celery Beat Scheduled Tasks:
- poll_mailboxes: every 5 minutes
- process_expired_trials: daily at 22:00 UTC (08:00 AEST)
- retry_pending_outreach: every 30 minutes safety net

File: ~/ai-recruiter/backend/app/tasks/scheduled_tasks.py

---

## DATABASE

Current migration: 0010

To apply migrations:
  cd ~/ai-recruiter/backend && source venv/bin/activate && alembic upgrade head

Migration history:
- 0001: initial schema
- 0002: candidate_target on jobs
- 0003: tenant jobs_email
- 0004: candidate strengths/gaps
- 0005: team_members table, data_retention
- 0006: trial plan enum, trial date columns on tenants
- 0007: subscription dates on tenants
- 0008: screener mode on jobs, application screening columns, test_sessions table
- 0009: application status and resume_filename
- 0010: interview_type on jobs and test_sessions, recording_urls, transcripts

Key column values:
- jobs.mode: talent_scout | screener_only
- jobs.interview_type: text | audio | video | audio_video
- candidates.status: discovered | profiled | passed | failed | emailed | scoring_failed
- applications.status: received | screened_passed | screened_failed | test_invited | test_passed | test_failed | hm_notified | interview_invited | rejected
- tenants.plan: trial | trial_expired | recruiter | agency_small | agency_medium | enterprise

---

## SUBSCRIPTION PLANS

Trial: Free 14 days, 3 jobs, 10 candidates/job, 50 resumes/job
Recruiter: $499/mo, 5 jobs, 20 candidates/job, 50 resumes/job
Agency Small: $999/mo, 20 jobs, 40 candidates/job, 75 resumes/job
Agency Medium: $2,999/mo, 75 jobs, 60 candidates/job, 100 resumes/job
Enterprise: Custom, unlimited

After trial expires: user redirected to /subscribe, cannot access any other pages.

---

## FRONTEND ROUTING

CRITICAL: Dashboard is at /en (root), NOT /en/dashboard.

Routes:
- /en -> Dashboard
- /en/jobs -> Jobs list
- /en/jobs/new -> Job mode selection
- /en/jobs/new/screener -> Screener Only job creation
- /en/candidates -> Candidates list
- /en/applications -> Applications list
- /en/chat -> AI Recruiter Chat
- /en/chat/history -> Chat history
- /en/settings -> Settings
- /en/super-admin -> Super Admin
- /en/subscribe -> Subscription page (public)
- /en/billing/success -> Post-payment success (public)
- /en/test/[id]/[token] -> Competency test (public, token-protected)
- /en/interview-invited -> Interview invitation success (public)

Middleware: Uses proxy.ts (NOT middleware.ts).
NEVER delete proxy.ts. NEVER create middleware.ts alongside it.

---

## SECURITY

- RLS enabled on all tenant tables in Supabase
- Backend uses service role key (bypasses RLS correctly)
- Super admin: only SUPER_ADMIN_EMAIL can access /super-admin
- API keys encrypted at rest using ~/ai-recruiter/backend/app/services/crypto.py

---

## KNOWN BUGS

Non-fatal (acceptable for now):
1. Celery shows "RuntimeError: Event loop is closed" warnings — non-fatal, just noisy
2. Question generation occasionally fails with JSON parse error — falls back to generic questions

Must fix before production:
3. Debug print statements in screener_tasks.py — remove all print(f"[poll_mailboxes]...") lines
4. Test minimum scores too low — reset JIYVD3NU and 9ZMJE18W to minimum_score=6
5. EMAIL_TEST_MODE=true — must set to false in production

Pending verification:
6. Hiring manager notification email — last test scored 1/10 so rejection fired. Need to test full pipeline with passing score to verify HM email arrives correctly.
7. Video interview type — built but not fully tested end to end

---

## COMPLETED FEATURES

Core:
- [x] Multi-tenant with Supabase RLS
- [x] Supabase Auth + Super admin
- [x] Trial system (14 days, expiry email, subscribe redirect)
- [x] Stripe billing (checkout, webhooks, subscription activation)
- [x] Plan limits enforcement
- [x] i18n routing (EN, DE, ES, FR)

Dashboard:
- [x] Real data (jobs, candidates, pipeline counts, recent activity)
- [x] Global header search
- [x] Trial countdown banner

Jobs:
- [x] Jobs list with mode badges (AI Scout / Screener Only)
- [x] Job detail tabs (conditional on mode)
- [x] Salary formatted correctly
- [x] Audit trail (50 events, live stream, filters)

Candidates:
- [x] List with search, status filter, score filter
- [x] Profile with scoring history, BrightData profile display, outreach email HTML

Applications:
- [x] List with scores and status
- [x] Detail with full scoring history and per-question evaluation

AI Talent Scout:
- [x] Discovery, enrichment, scoring, email discovery, outreach
- [x] Unlimited retries for API overload
- [x] Retry safety net every 30 min

AI Resume Screener:
- [x] IMAP polling (per-tenant)
- [x] PDF/DOCX/DOC text extraction
- [x] Chunked embeddings (long resume support)
- [x] AI screening with score + strengths + gaps
- [x] Rejection emails (AI-generated)
- [x] Test invitation with interview type preparation instructions
- [x] Competency test — text interface
- [x] Competency test — audio interface (Whisper transcription)
- [x] Competency test — video interface (built, needs test)
- [x] Test scoring with full per-question evaluation report
- [x] Hiring manager notification with all 3 scores
- [x] One-click interview invitation (token-protected)

Job Creation:
- [x] Mode 1: AI chat creates job
- [x] Mode 2: Paste JD or URL extraction
- [x] Interview type selection per job
- [x] Application instructions with copy button

Settings:
- [x] General, API Keys, AI Provider, Email & Mailbox (with password encryption)
- [x] Knowledge Base (upload + scrape)
- [x] Chat Widget (embeddable snippet)
- [x] AI Recruiter Prompt
- [x] Team Members (invite flow)
- [x] Billing (plan comparison, Manage Billing)
- [x] Privacy & Data (DPA acceptance, data retention, export/delete)

Chat:
- [x] AI Recruiter Chat (job creation flow)
- [x] Chat History (list, view, resume)

Super Admin:
- [x] Platform API keys management
- [x] Tenant list (partial mock data)

---

## TODO LIST

Phase 1 - Core Features:

8. BUILD PROFILE DATABASE
   Background Celery task pre-populating candidate profiles for common titles/locations.
   New table: profile_cache (title, location, linkedin_url, brightdata_profile, last_updated)
   Celery beat task runs nightly, discovers and enriches profiles for common titles.
   When Talent Scout runs, check profile_cache first before calling ScrapingDog.

9. SUPER ADMIN REAL DATA
   Wire up: total tenants, active subscriptions, MRR calculation, failed tasks count.
   All Tenants table: real data with plan, credits, status, created_at.

10. DAILY CANDIDATE SUMMARY EMAIL
    Spec §7.6: Celery beat daily at 22:00 UTC (08:00 AEST).
    For each active job with activity in last 24h: email hiring manager with activity summary.

11. UNSUBSCRIBE FLOW VERIFICATION
    Verify /unsubscribe/{candidate_id} page sets candidates.opted_out=True.
    Verify opted-out candidates are never emailed again.

12. CHAT WIDGET TEST
    Test embeddable JS snippet from Settings -> Chat Widget on a real HTML page.
    Verify RAG pipeline responds correctly.

13. EMAIL CONFIRMATION (PRODUCTION)
    Enable in Supabase Auth settings. Customize confirmation email template.

14. SENDGRID DOMAIN AUTHENTICATION
    Set up SPF/DKIM for aiworkerz.com in Namecheap DNS via SendGrid.
    This fixes emails going to spam.

Phase 2 - Website Content:

15. HOME PAGE (airecruiterz.com)
    Hero, problem/solution, how it works, pricing, use cases, testimonials, CTA.
    "Start your 14-day free trial"

16. SALES SHEET
    One-page PDF for outreach. Features, pricing, contact info. AIWorkerz branded.

17. APP MOCKUP/DEMO
    Animated GIF or video showing full pipeline for home page.

Phase 3 - Application Help:

18. HELP SYSTEM
    Per-page contextual help (? icon -> slide-out panel).
    Full help documentation page at /help.

19. SUPPORT BUTTON
    Floating button, AI-powered first response, escalate to support@aiworkerz.com.

Phase 4 - Deployment:

20. PWA
    manifest.json, service worker, install prompt for iOS/Android.

21. DEPLOY
    Backend + Celery: Railway.app
    Frontend: Vercel
    Redis: Railway addon
    Custom domain: app.airecruiterz.com

22. PRODUCTION CONFIGURATION
    EMAIL_TEST_MODE=false, reset minimum scores, live Stripe keys, live API keys.

23. STRIPE LIVE MODE
    Create products in Stripe live mode, update price IDs and keys.

24. SENDGRID DOMAIN AUTH (see item 14)

Phase 5 - Post Launch:

25. MARKETING MODULE
    Platform level (markets airecruiterz.com to new tenants):
    - Content engine, lead generation, SEO blog, trial nurture, analytics, referral program

    Tenant level (Agency Small/Medium/Enterprise — helps agencies get clients):
    - Agency content engine, employer lead gen, agency SEO page, client nurture, analytics, referral

---

## IMPORTANT ARCHITECTURAL DECISIONS

1. OpenAI always first — Never change this. The AIProvider facade handles it automatically.

2. Synchronous embeddings in Celery — generate_embedding() MUST use synchronous OpenAI client.
   Changing to async breaks Celery with "Event loop is closed" errors.

3. proxy.ts not middleware.ts — This Next.js version uses proxy.ts.
   Never delete proxy.ts. Never create middleware.ts alongside it.

4. Dashboard at /en not /en/dashboard — All "dashboard" links go to "/" not "/dashboard".
   There is a redirect at /en/dashboard -> /en for backwards compatibility.

5. IMAP per-tenant — No shared platform inbox. Each tenant uses their own IMAP.
   Poller only runs for tenants with all 4 IMAP fields set.

6. Supabase Storage buckets must be created manually in Supabase dashboard.
   Currently needed: "recordings" (private).

7. Job minimum_score — Set low for testing (4 and 1). Reset to 6 before production.

8. EMAIL_TEST_MODE=true — All emails go to EMAIL_TEST_RECIPIENT. Set false for production.
