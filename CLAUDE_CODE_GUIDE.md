# AI Recruiter — Step-by-Step Build Guide
## Using Claude Code CLI to generate the application from SPEC.md

---

## PART 1 — ONE-TIME SETUP (do this once)

---

### Step 1 — Install WSL2 on Windows

WSL2 gives you a real Linux terminal on Windows. Claude Code requires it.

Open **PowerShell as Administrator** and run:
```
wsl --install
```
When it finishes, restart your computer. After restart, a Ubuntu terminal window will open and ask you to create a Linux username and password. Set these — you'll need them.

To open WSL2 any time after that: press `Windows key`, type `Ubuntu`, open it.

---

### Step 2 — Install Node.js inside WSL2

In your Ubuntu terminal:
```bash
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt-get install -y nodejs
```

Verify it worked:
```bash
node --version
# Should print v20.x.x

npm --version
# Should print 10.x.x
```

---

### Step 3 — Install Python 3.12 inside WSL2

```bash
sudo apt update
sudo apt install -y python3.12 python3.12-venv python3-pip
```

Verify:
```bash
python3.12 --version
# Should print Python 3.12.x
```

---

### Step 4 — Install Claude Code CLI

```bash
npm install -g @anthropic-ai/claude-code
```

Verify:
```bash
claude --version
```

---

### Step 5 — Authenticate Claude Code with your Anthropic API key

You need an Anthropic API key. If you don't have one:
1. Go to https://console.anthropic.com
2. Sign up or log in
3. Go to API Keys → Create Key
4. Copy the key (starts with `sk-ant-`)
5. Add some credits ($20 USD is plenty to start)

Now authenticate Claude Code:
```bash
claude
```

It will open a browser window asking you to log in or paste your API key. Do that. Once done you're authenticated.

---

### Step 6 — Create the GitHub repository

1. Go to https://github.com and create a new **private** repository called `ai-recruiter`
2. Do NOT initialise it with a README (we'll do that ourselves)
3. Copy the repository URL (e.g. `https://github.com/yourusername/ai-recruiter.git`)

Install git in WSL2 if needed:
```bash
sudo apt install -y git
git config --global user.email "your@email.com"
git config --global user.name "Your Name"
```

---

### Step 7 — Create the project folder and add the spec files

In WSL2:
```bash
# Navigate to where you want the project (accessible from Windows too)
cd /mnt/c/Users/YourWindowsUsername/Documents

# Create project folder
mkdir ai-recruiter
cd ai-recruiter

# Initialise git
git init
git remote add origin https://github.com/yourusername/ai-recruiter.git
```

Now copy `SPEC.md` and `guidelines.md` into this folder. You downloaded them from this chat — they'll be in your Windows Downloads folder. In WSL2:
```bash
cp /mnt/c/Users/YourWindowsUsername/Downloads/SPEC.md .
cp /mnt/c/Users/YourWindowsUsername/Downloads/guidelines.md .
```

Create a basic `.env.example` file (Claude Code will use this as a template):
```bash
cat > .env.example << 'EOF'
# Platform-level (Railway managed)
ANTHROPIC_API_KEY=sk-ant-your-key-here
OPENAI_API_KEY=sk-your-key-here
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_KEY=your-service-key
SUPABASE_ANON_KEY=your-anon-key
REDIS_URL=redis://localhost:6379/0
STRIPE_SECRET_KEY=sk_test_your-key
STRIPE_WEBHOOK_SECRET=whsec_your-secret
SENDGRID_API_KEY=SG.your-key
IMAP_HOST=mail.yourdomain.com
IMAP_PORT=993
IMAP_MASTER_PASSWORD=your-password
SCRAPINGDOG_API_KEY=your-key
BRIGHTDATA_API_KEY=your-key
ENCRYPTION_KEY=your-fernet-key
FRONTEND_URL=http://localhost:3000
ENVIRONMENT=development
EOF
```

Create a `.gitignore`:
```bash
cat > .gitignore << 'EOF'
.env
__pycache__/
*.pyc
.pytest_cache/
.mypy_cache/
node_modules/
.next/
venv/
*.egg-info/
dist/
.DS_Store
EOF
```

First commit:
```bash
git add .
git commit -m "Initial: add SPEC.md, guidelines.md, .env.example"
git push -u origin main
```

---

### Step 8 — Open the project in PyCharm

1. Open PyCharm
2. File → Open → navigate to your project folder (e.g. `C:\Users\YourName\Documents\ai-recruiter`)
3. PyCharm will detect it as a Python project
4. Create a virtual environment: PyCharm will prompt you, or go to Settings → Python Interpreter → Add → Virtual Environment

**Leave PyCharm open.** As Claude Code generates files in WSL2, PyCharm will show them appearing in real time. You use PyCharm for reading, reviewing, and manually editing — Claude Code does the generating.

---

## PART 2 — GENERATING THE APPLICATION

The golden rule: **one module per session, commit after each one.**

Never ask Claude Code to "generate the whole application". Always do it in the order below — each step depends on the previous one being done correctly.

---

### How to start a Claude Code session

In your WSL2 terminal, navigate to the project folder:
```bash
cd /mnt/c/Users/YourName/Documents/ai-recruiter
claude
```

This starts the Claude Code interactive session. You'll see a `>` prompt. Now paste your task prompt.

At the end of each session, type `/exit` or press `Ctrl+C`.

---

### SESSION 1 — Backend project structure + database models

**Paste this prompt:**
```
Read SPEC.md and guidelines.md carefully.

Your task: Set up the Python backend project structure and generate all SQLAlchemy 2.x async database models.

1. Create the folder structure as defined in SPEC.md Section 19:
   backend/app/main.py, config.py, database.py
   backend/app/models/ (one file per model)
   backend/requirements.txt
   backend/Dockerfile

2. requirements.txt must include at minimum:
   fastapi, uvicorn[standard], sqlalchemy[asyncio], asyncpg, alembic,
   pydantic[email], pydantic-settings, celery[redis], redis, httpx,
   anthropic, openai, cryptography, stripe, sendgrid, pdfplumber,
   python-docx, crawl4ai, pgvector, python-jose[cryptography],
   passlib[bcrypt], python-multipart, jinja2, pytest, pytest-asyncio,
   httpx, respx, playwright

3. Generate all SQLAlchemy models exactly as defined in SPEC.md Section 5:
   - Tenant (with all fields from Section 2.1)
   - Job (Section 5.1)
   - Candidate (Section 5.2)
   - Application (Section 5.3)
   - PromoCode (Section 5.4)
   - ChatSession (Section 5.5)
   - RagDocument (Section 5.6)
   - JobAuditEvent (Section 5.7 — append-only, with pgvector column)

4. Generate database.py with async SQLAlchemy session factory using asyncpg

5. Generate config.py using pydantic-settings reading from .env

6. Create an Alembic migration for all models including:
   - pgvector extension enable
   - All tables
   - The Postgres trigger on job_audit_events that fires NOTIFY audit_{job_id} after INSERT
   - All indexes (created_at on job_audit_events, tenant_id on all tables)

Do NOT generate routes or services yet — models only.
After generating, show me the complete list of files created.
```

**After it finishes:**
- Review the generated models in PyCharm
- Check all fields match SPEC.md Section 5
- Run: `cd backend && pip install -r requirements.txt && alembic upgrade head`
- Fix any errors Claude Code didn't catch
- Commit: `git add . && git commit -m "Session 1: database models and migrations"`

---

### SESSION 2 — Pydantic schemas + FastAPI app factory + auth

```
Read SPEC.md and guidelines.md.

The database models are already generated in backend/app/models/.

Your task: Generate Pydantic v2 schemas and the FastAPI application foundation.

1. Generate backend/app/schemas/ — one schema file per model with:
   - Base, Create, Update, and Response schemas for each model
   - Use model_config = ConfigDict(from_attributes=True) on all response schemas
   - Include PaginatedResponse generic schema

2. Generate backend/app/main.py:
   - FastAPI app with /api/v1 prefix
   - CORS middleware (FRONTEND_URL from config)
   - Include all routers (stub them in for now — just register the router, empty implementation)

3. Generate backend/app/routers/auth.py:
   - POST /api/v1/auth/signup — create user in Supabase Auth + create Tenant record
   - POST /api/v1/auth/login — return Supabase JWT
   - get_current_tenant dependency that validates JWT and returns Tenant from DB

4. Generate backend/app/routers/tenants.py:
   - GET /api/v1/tenants/me
   - PATCH /api/v1/tenants/me

5. All routes must follow guidelines.md rules — tenant_id from JWT only, never from body.

After generating, run: uvicorn app.main:app --reload
It should start without errors (even with stub routes).
```

**After it finishes:**
- Test: `curl http://localhost:8000/docs` should show the Swagger UI
- Commit: `git commit -m "Session 2: schemas, app factory, auth"`

---

### SESSION 3 — AI provider facade + core services

```
Read SPEC.md and guidelines.md.

Your task: Generate the AI provider facade and core integration services.

1. backend/app/services/claude_ai.py
   - Async wrapper around Anthropic SDK
   - Methods: complete(prompt, system, max_tokens), complete_json(prompt, system) → parsed dict
   - Uses ANTHROPIC_API_KEY from config OR tenant.ai_api_key if provided

2. backend/app/services/openai_ai.py
   - Same interface as claude_ai.py but using OpenAI SDK

3. backend/app/services/ai_provider.py
   - Facade that reads tenant.ai_provider and routes to the correct implementation
   - CRITICAL: All other services must use this facade, never call SDKs directly

4. backend/app/services/embeddings.py
   - generate_embedding(text: str) -> list[float]
   - Uses OpenAI text-embedding-3-small (1536 dims)
   - Falls back to Anthropic embeddings if tenant.ai_provider = 'anthropic'

5. backend/app/services/scrapingdog.py
   - search_linkedin(query: str, start: int, api_key: str) -> list[dict]
   - Calls GET https://api.scrapingdog.com/google with correct params from SPEC.md Section 7.1.2
   - Returns normalised list of {title, snippet, link}

6. backend/app/services/brightdata.py
   - get_linkedin_profile(linkedin_url: str, api_key: str) -> dict
   - Uses BrightData LinkedIn People Profiles dataset

7. backend/app/services/apollo.py
   - find_email(name: str, company: str, api_key: str) -> Optional[str]

8. backend/app/services/hunter.py
   - find_email(first_name, last_name, domain, api_key) -> Optional[str]
   - Only return if confidence > 70%

9. backend/app/services/snov.py
   - find_email(first_name, last_name, domain, api_key) -> Optional[str]

10. backend/app/services/email_deduction.py
    - EmailDeductionService class
    - Implement full algorithm from SPEC.md Section 7.4.4
    - Rate limiter: max 5 SMTP checks per minute per domain
    - All SMTP operations must be async

11. backend/app/services/sendgrid_email.py
    - send_email(to, subject, html_body, tenant) -> bool
    - Uses tenant.sendgrid_api_key if set, platform SENDGRID_API_KEY otherwise

12. Write unit tests for all services in backend/tests/unit/
    - Mock all external HTTP calls using respx
    - Test happy path and error path for each service
```

**After it finishes:**
- Run: `pytest backend/tests/unit/ -v`
- Fix any failing tests
- Commit: `git commit -m "Session 3: AI facade and integration services"`

---

### SESSION 4 — Audit trail service + Jobs/Candidates/Applications routes

```
Read SPEC.md and guidelines.md.

Your task: Generate the audit trail service and the main CRUD routes.

1. backend/app/services/audit_trail.py
   - AuditTrailService class with emit() method
   - emit() inserts a row into job_audit_events
   - Use all event_type strings exactly as defined in SPEC.md Section 15.2, 15.3, 15.4
   - Postgres NOTIFY is handled by the DB trigger (already in migration) — do not call NOTIFY from Python

2. backend/app/routers/audit.py
   - GET /api/v1/jobs/{id}/audit-stream — SSE endpoint using asyncpg LISTEN
   - GET /api/v1/jobs/{id}/audit-events — paginated history with filtering by category/severity
   - GET /super-admin/audit — platform-wide system+payment events (super_admin only)
   - SSE must handle client disconnect and release the LISTEN connection cleanly

3. backend/app/routers/jobs.py — full implementation:
   - GET /api/v1/jobs
   - POST /api/v1/jobs
   - GET /api/v1/jobs/{id}
   - PATCH /api/v1/jobs/{id}
   - POST /api/v1/jobs/{id}/trigger-scout
   - GET /api/v1/jobs/{id}/evaluation-report (SSE — reuse audit stream, filter for candidate status events)

4. backend/app/routers/candidates.py — full implementation including:
   - DELETE /api/v1/candidates/{id} — must call gdpr.anonymise_candidate(), not raw delete

5. backend/app/services/gdpr.py
   - anonymise_candidate(db, tenant_id, candidate_id) function
   - Replaces all PII with '[REDACTED]', clears brightdata_profile, deletes resume_embedding
   - Redacts PII in job_audit_events.detail JSONB for this candidate
   - Deletes resume files from Supabase Storage
   - Does NOT delete the candidate row or audit event rows

6. backend/app/routers/applications.py — full implementation

Write integration tests for all new routes in backend/tests/integration/.
```

**After it finishes:**
- Run: `pytest backend/tests/ -v`
- Commit: `git commit -m "Session 4: audit trail, CRUD routes"`

---

### SESSION 5 — Talent Scout Celery pipeline

```
Read SPEC.md and guidelines.md.

Your task: Generate the complete Talent Scout background pipeline.

1. backend/app/tasks/celery_app.py
   - Celery app configured with Redis broker
   - Beat schedule for all scheduled tasks from SPEC.md Section 14.2

2. backend/app/services/talent_scout.py
   - build_search_queries(job) -> list[str]
     Generates all title × location combinations per SPEC.md Section 7.1.1
     Location rules differ by work_type (onsite/hybrid/remote/remote_global)
   - All methods emit the correct audit events per SPEC.md Section 15.2

3. backend/app/tasks/talent_scout_tasks.py
   - discover_candidates(job_id, tenant_id) — Celery task, calls SERP API for all query combinations, creates Candidate records, deduplicates, fans out chord to tasks 2–5
   - enrich_profile(candidate_id, tenant_id) — BrightData call
   - score_candidate(candidate_id, tenant_id) — AI scoring via ai_provider facade
   - discover_email(candidate_id, tenant_id) — tries Apollo/Hunter/Snov based on tenant.email_discovery_provider, then EmailDeductionService fallback
   - send_outreach(candidate_id, tenant_id) — generates personalised email via AI, sends via SendGrid, GDPR unsubscribe link included

   ALL tasks must:
   - Have max_retries=3 with exponential backoff
   - Be idempotent (check current status before acting)
   - Emit audit events on both success and failure
   - Follow guidelines.md Celery rules exactly

4. Write unit tests for talent_scout.py and integration tests for the task chain
   Mock all external APIs per SPEC.md Section 18.4
```

**After it finishes:**
- Run: `pytest backend/tests/ -v`
- Commit: `git commit -m "Session 5: Talent Scout Celery pipeline"`

---

### SESSION 6 — Resume Screener pipeline + IMAP + chat sessions

```
Read SPEC.md and guidelines.md.

Your task: Generate the Resume Screener pipeline, IMAP poller, and chat session management.

1. backend/app/tasks/screener_tasks.py
   - poll_mailboxes() — polls IMAP for all active tenants, implements full flow from SPEC.md Section 8.1
   - screen_resume(application_id, tenant_id) — embedding similarity + AI evaluation per Section 8.2
   - invite_to_test(application_id, tenant_id) — generates test questions, creates test_session, sends invitation email
   - score_test(application_id, tenant_id) — scores full transcript

2. backend/app/routers/applications.py — add test chat endpoints:
   - GET /test/{id}/{token} — public, serve test interface (returns JSON for frontend)
   - POST /test/{id}/message — public, one turn of the test conversation, uses AI
   - GET /actions/invite-interview/{id}/{token} — public, processes hiring manager click

3. backend/app/routers/chat_sessions.py — full implementation:
   - GET /api/v1/chat-sessions/current — returns or creates current session
   - POST /api/v1/chat-sessions/{id}/message — appends message to DB, calls AI, returns response
   - POST /api/v1/chat-sessions/new
   - The AI system prompt for job collection follows SPEC.md Section 6.3 (16 steps)
   - Phase detection (job_collection → payment → recruitment) handled in backend

4. Write integration tests for all screener tasks and chat session routes
   Mock IMAP with pre-loaded test emails
```

**After it finishes:**
- Run: `pytest backend/tests/ -v`
- Commit: `git commit -m "Session 6: Resume Screener, IMAP poller, chat sessions"`

---

### SESSION 7 — Stripe, promo codes, webhooks, RAG, email templates

```
Read SPEC.md and guidelines.md.

Your task: Generate Stripe integration, promo codes, webhooks, RAG pipeline, and email templates.

1. backend/app/routers/webhooks.py
   - POST /webhooks/stripe — handles all 4 events from SPEC.md Section 4.3
   - POST /webhooks/email-received — HMAC verified

2. backend/app/routers/promo_codes.py — full CRUD

3. backend/app/services/rag_pipeline.py
   - scrape_website(tenant_id, url) — crawl4ai scrape, chunk, embed, store in rag_documents
   - upload_document(tenant_id, file_content, filename) — extract, chunk, embed, store
   - query(tenant_id, question, top_k=5) -> list[str] — cosine search rag_documents

4. backend/app/routers/rag.py and backend/app/routers/widget.py — full implementation

5. backend/app/templates/ — Jinja2 HTML email templates for all 12 templates in SPEC.md Section 17
   Each template must have: subject, html_body, text_fallback
   Every outreach template MUST include unsubscribe link placeholder

6. backend/app/routers/super_admin.py — full implementation per SPEC.md Section 11
```

**After it finishes:**
- Run: `pytest backend/tests/ -v`
- Commit: `git commit -m "Session 7: Stripe, RAG, email templates, super admin"`

---

### SESSION 8 — Full test suite + CI

```
Read SPEC.md and guidelines.md.

Your task: Complete the full test suite and GitHub Actions CI pipeline.

1. Ensure test coverage is at least 85% across all backend modules
   Run: pytest --cov=app --cov-report=term-missing
   Generate tests for any uncovered code

2. Complete backend/tests/unit/ — all service unit tests per SPEC.md Section 18.1
3. Complete backend/tests/integration/ — all route integration tests per SPEC.md Section 18.2
4. backend/tests/conftest.py — shared fixtures including:
   - test_db: creates test schema, runs migrations, tears down after session
   - test_tenant: creates a test tenant with known credentials
   - test_job: creates a test job for the test tenant
   - All mock clients for external services

5. .github/workflows/ci.yml:
   - Trigger: push to main and pull_request
   - Jobs: lint (ruff + mypy), test (pytest with coverage), build-check (docker build)
   - Use GitHub Secrets for SUPABASE_TEST_URL, TEST_API_KEYS etc.

After generating, run the full suite and show me the coverage report.
```

**After it finishes:**
- Run: `pytest --cov=app --cov-report=term-missing`
- Fix any coverage gaps
- Commit: `git commit -m "Session 8: full test suite and CI pipeline"`

---

### SESSION 9 — Next.js frontend

```
Read SPEC.md and guidelines.md.

Your task: Generate the Next.js 14 App Router frontend.

1. Scaffold the frontend:
   npx create-next-app@latest frontend --typescript --app --tailwind --no-src-dir

2. Install dependencies:
   cd frontend && npm install next-intl @supabase/supabase-js react-hook-form zod
   npm install @tanstack/react-query axios

3. Set up i18n with next-intl for EN, DE, ES, FR
   frontend/app/[locale]/layout.tsx as the root layout

4. Generate all pages per SPEC.md Section 12 in this order:
   - frontend/app/[locale]/(auth)/login/page.tsx
   - frontend/app/[locale]/(auth)/signup/page.tsx
   - frontend/app/[locale]/(dashboard)/layout.tsx — sidebar + topbar matching the mockup
   - frontend/app/[locale]/(dashboard)/page.tsx — dashboard home with stats and pipeline
   - frontend/app/[locale]/(dashboard)/chat/page.tsx — AI Recruiter chat with split-pane layout
   - frontend/app/[locale]/(dashboard)/jobs/page.tsx — jobs list
   - frontend/app/[locale]/(dashboard)/jobs/[id]/page.tsx — tabbed job detail (Evaluation + Audit + Spec)
   - frontend/app/[locale]/(dashboard)/candidates/page.tsx
   - frontend/app/[locale]/(dashboard)/candidates/[id]/page.tsx
   - frontend/app/[locale]/(dashboard)/applications/[id]/page.tsx
   - frontend/app/[locale]/(dashboard)/settings/page.tsx — settings with left-nav sections
   - frontend/app/[locale]/(dashboard)/super-admin/page.tsx
   - frontend/public/test/page.tsx — public test interface (no auth)

5. frontend/lib/api/ — typed API client matching all backend routes
6. SSE hook: frontend/hooks/useAuditStream.ts — EventSource with reconnect + replay

Use the colour scheme and layout from the HTML mockup:
   --navy: #0D1B2A, --blue: #1B6CA8, --cyan: #00C2E0
   Dark theme throughout, DM Sans font
```

**After it finishes:**
- Run: `cd frontend && npm run build`
- Fix any TypeScript errors
- Commit: `git commit -m "Session 9: Next.js frontend"`

---

### SESSION 10 — Final integration check

```
Read SPEC.md and guidelines.md.

Your task: Final integration check and fixes.

1. Start the full stack locally:
   - Backend: uvicorn app.main:app --reload (in backend/)
   - Celery worker: celery -A app.tasks.celery_app worker --loglevel=info
   - Frontend: npm run dev (in frontend/)

2. Walk through the complete job posting flow end-to-end:
   - Sign up as a new tenant
   - Post a job via the AI Recruiter chat (mock the AI responses)
   - Verify job is created in DB
   - Trigger the Talent Scout with mock candidate data
   - Verify audit events appear in the audit stream
   - Simulate a resume arriving via email (mock IMAP)
   - Verify the Application is created and screening runs

3. Fix any integration issues found

4. Run the full test suite one final time:
   pytest --cov=app --cov-report=term-missing

5. If coverage is below 85%, generate the missing tests

6. Final commit: git tag v1.0.0
```

---

## PART 3 — DEPLOYING TO PRODUCTION

---

### Step A — Set up Supabase

1. Go to https://supabase.com → New Project
2. Choose EU region (Frankfurt) for GDPR compliance
3. Copy your Project URL and API keys into Railway env vars
4. In Supabase SQL editor, run: `CREATE EXTENSION IF NOT EXISTS vector;`
5. Run Alembic migrations: `alembic upgrade head`
6. Enable RLS on all tables (Alembic migration handles this, but verify in Supabase dashboard)

---

### Step B — Set up Railway

1. Go to https://railway.app → New Project → Deploy from GitHub repo
2. Add three services: `web` (FastAPI), `worker` (Celery), `redis` (Redis plugin)
3. For `web` service: start command = `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
4. For `worker` service: start command = `celery -A app.tasks.celery_app worker --loglevel=info`
5. Add all environment variables from SPEC.md Section 20 to Railway's Variables tab
6. Connect your GitHub repo → Railway will auto-deploy on every push to main

---

### Step C — Set up Vercel

1. Go to https://vercel.com → New Project → Import from GitHub (select ai-recruiter repo, frontend folder)
2. Add environment variables: `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_API_URL`
3. Deploy → Vercel gives you a URL (e.g. `ai-recruiter.vercel.app`)

---

### Step D — Set up Stripe

1. Go to https://dashboard.stripe.com → Products → Add product for each of the 6 plans
2. Copy price IDs into your Railway env vars
3. Webhooks → Add endpoint → paste your Railway API URL + `/api/v1/webhooks/stripe`
4. Select events: `checkout.session.completed`, `invoice.payment_succeeded`, `invoice.payment_failed`, `customer.subscription.deleted`

---

### Step E — Smoke test production

1. Sign up as a new tenant on your live URL
2. Post a test job via the AI Recruiter chat
3. Watch the audit trail to verify the pipeline runs
4. Submit a test resume email and verify the screener picks it up

---

## TIPS FOR USING CLAUDE CODE EFFECTIVELY

**DO:**
- Start each session with "Read SPEC.md and guidelines.md" — every single time
- Keep sessions focused on one module
- Run tests after each session before moving on
- Commit after each session so you can roll back if needed
- When Claude Code makes a mistake, say exactly what's wrong: "The scoring function in talent_scout.py doesn't emit an audit event on failure. Fix it per guidelines.md rule 6."

**DON'T:**
- Ask it to "generate everything" in one go
- Skip the test runs between sessions
- Ignore guidelines.md violations — they compound into bigger problems later
- Start a new session without committing the last one first

**When something goes wrong:**
- Paste the exact error message into Claude Code
- Say: "Fix this error. Do not change any other files."
- After fixing: re-run tests to make sure nothing else broke

**Checking progress:**
- `git log --oneline` — see all your sessions as commits
- `pytest --cov=app` — see test coverage at any time
- `git diff HEAD~1` — see exactly what the last session changed

---

*Good luck Marcus — you have a complete spec, clear guidelines, and the right tool. Follow the session order and commit after each one. The first session is always the most important — get the models right and everything else builds cleanly on top.*
