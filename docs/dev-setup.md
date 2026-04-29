# AI Recruiter — Local Dev Setup

## Starting Everything

```bash
# Terminal 1 — Backend
cd ~/ai-recruiter/backend && source venv/bin/activate
uvicorn app.main:app --reload

# Terminal 2 — Frontend
cd ~/ai-recruiter/frontend && npm run dev

# Terminal 3 — Celery worker
cd ~/ai-recruiter/backend && source venv/bin/activate
celery -A app.tasks.celery_app worker -Q celery,marketing --loglevel=info

# Terminal 4 — Claude CLI
cd ~/ai-recruiter && claude --dangerously-skip-permissions
```

```bash
# Redis (if Celery won't connect)
sudo service redis-server start && redis-cli ping

# Stripe webhook (payment testing only)
stripe listen --forward-to localhost:8000/api/v1/webhooks/stripe
```

## Local URLs

- Frontend: http://localhost:3000/en (dashboard is at `/en`, NOT `/en/dashboard`)
- Backend API: http://localhost:8000
- Swagger UI: http://localhost:8000/docs

## Key Configuration

**Supabase (production):**
- Project: `vigtvsdwbkspkqohvjna` (ap-southeast-2, Sydney)
- Session pooler (port 5432) — used by Celery tasks
- Transaction pooler (port 6543) — used by API engine

**Email:**
- SendGrid from: `marcus.bahadur@aiworkerz.com`
- IMAP inbox: `marcus.bahadur@aiworkerz.com` / `mail.privateemail.com:993`
- Platform jobs email: `jobs@aiworkerz.com`
- `EMAIL_TEST_MODE=true` in dev — all emails go to `EMAIL_TEST_RECIPIENT`

**Stripe (test mode price IDs):**
- Recruiter: `price_1TKTz6A5SiOfWjX1qr86cpx6` ($499/mo)
- Agency Small: `price_1TKTzlA5SiOfWjX1l9f6GkTE` ($999/mo)
- Agency Medium: `price_1TKU0PA5SiOfWjX18ycn5bTL` ($2,999/mo)

**Other:**
- `SUPER_ADMIN_EMAIL`: `marcus@aiworkerz.com`
- `FRONTEND_URL`: `http://localhost:3000`

## Test Data

**Test Tenant:**
- Email: `marcus@aiworkerz.com`
- Plan: `recruiter`

**Test Jobs:**
1. Senior Java Developer (Talent Scout) — Ref: `JIYVD3NU`, Sydney hybrid
2. Senior React Developer (Screener Only) — Ref: `9ZMJE18W`, audio interview

**Test email addresses:**
- `marcus@aiworkerz.com` — main test account, super admin login
- `marcusbahadur@protonmail.com` — sends test resumes to inbox
- `marcus.bahadur@aiworkerz.com` — IMAP inbox

**Supabase Storage buckets (must be created manually in Supabase dashboard):**
- `recordings` — private bucket for audio/video interview recordings

## Architectural Decisions (do not change without understanding)

1. **Celery task DB uses session pooler (port 5432)** — `_build_task_db_url()` in `database.py` auto-switches. Transaction pooler (port 6543) causes `DuplicatePreparedStatementError` on Celery retries.

2. **Main SQLAlchemy engine uses `NullPool`** — prevents prepared statement conflicts with pgbouncer. Do not add connection pooling.

3. **Session persistence uses a fresh `AsyncSessionLocal()` with explicit `UPDATE`** — after streaming, the request-scoped `db` is unreliable with NullPool + FastAPI lifecycle.

4. **Synchronous embeddings in Celery** — `generate_embedding()` in `embeddings.py` uses the synchronous OpenAI client. Changing to async breaks Celery with "Event loop is closed" errors.

5. **`proxy.ts` not `middleware.ts`** — Next.js 16 uses `proxy.ts` for i18n routing. Never delete it, never create `middleware.ts` alongside it.

6. **Dashboard at `/en` not `/en/dashboard`** — there is a redirect at `/en/dashboard` → `/en` for backwards compatibility.

7. **IMAP per-tenant** — no shared platform inbox. Poller only runs for tenants with all 4 IMAP fields set.

8. **Super admin detected via API probe** — `layout.tsx` calls `superAdminApi.getStats()` (200 = super admin, 403 = regular user). No env var needed.

9. **AI provider order** — `ai_provider.py` tries the tenant's configured provider first, falls back to the other. Never call SDKs directly.
