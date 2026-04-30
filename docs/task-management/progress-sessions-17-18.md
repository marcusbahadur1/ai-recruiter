# PROGRESS — Sessions 17–18 (Production Deployment + CORS/DB Fixes)

*Full index: see [PROGRESS.md](PROGRESS.md)*

---

### Session 18 — Production CORS + DB Connectivity Fixes
- **CORS fix** — added `async rewrites()` to `frontend/next.config.ts` proxying `/api/v1/:path*` to Railway server-side; browser never contacts Railway directly so CORS is eliminated entirely
- Changed `frontend/lib/api/client.ts` `baseURL` from `${API_URL}/api/v1` to `/api/v1` (relative) to use the proxy
- Fixed `frontend/hooks/useAuditStream.ts` SSE URL to use relative `/api/v1/...` (removed `API_URL` constant)
- Fixed `frontend/app/[locale]/(public)/test/[id]/[token]/page.tsx` — changed `const API = process.env.NEXT_PUBLIC_API_URL` to `const API = ''` (relative)
- Fixed `frontend/app/[locale]/(auth)/signup/page.tsx` — better error display: extracts `response.data.detail` from Axios error before falling back to `e.message`
- **DB connection fix** — Railway's auto-injected `DATABASE_URL` used the wrong Supabase pooler host (`aws-0-ap-southeast-2`); asyncpg requires the transaction pooler (`aws-1-ap-southeast-2.pooler.supabase.com:6543`) — added `SQLALCHEMY_DATABASE_URL` env var explicitly on Railway
- Added `db_password: str | None` field to `backend/app/config.py` — allows storing the DB password as plain text to avoid URL-encoding issues with special characters
- Fixed `backend/app/database.py` `_build_db_url()` — previously called `str(parsed.set(password=...))` which triggered SQLAlchemy 2.x password redaction (`***`); now returns the `URL` object directly so asyncpg receives the real password
- Fixed `backend/app/database.py` `get_db()` — wrapped session `rollback()` and `close()` in nested try/except so cleanup errors don't leak as a second exception through Starlette's `ServerErrorMiddleware` (which would return plain-text "Internal Server Error" bypassing FastAPI's exception handler)
- Added global `unhandled_exception_handler` to `backend/app/main.py` — returns JSON 500 with real error detail instead of Starlette's plain-text fallback
- Added diagnostic `/health` endpoint enhancements (`pwd_hint`, `host`) — confirmed DB is reachable
- Created `backend/.railwayignore` — excludes `venv/`, `__pycache__/`, tests, etc. to prevent Railway upload timeouts
- Set `DB_PASSWORD=Recruiter2026prod` env var on Railway (confirmed working locally with asyncpg direct test)
- Renamed `SQLALCHEMY_DATABASE_URL` on Railway to avoid collision with Railway's auto-injected `DATABASE_URL`
- All fixes committed; final deploy in progress (URL-object fix is the last change, deployed via `railway up --service api --detach`)

### Session 17 — Production Deployment
- Production Supabase project created in Sydney (ap-southeast-2): `vigtvsdwbkspkqohvjna`
- pgvector enabled, all 11 tables created, Alembic migrations at v0012, RLS enabled on all tenant tables
- Supabase PITR/backups deferred — staying on free tier until first paying customer
- Railway environment promoted to production: Supabase swapped to Sydney (`vigtvsdwbkspkqohvjna`), `ENVIRONMENT=production`, staging-only `EMAIL_TEST_MODE`/`EMAIL_TEST_RECIPIENT` vars removed; API health check confirmed `{"status":"ok"}`
- Vercel production: `app.airecruiterz.com` live with HTTPS (A record `76.76.21.21` → Namecheap); production Supabase anon key + URL set; `FRONTEND_URL=https://app.airecruiterz.com` set on Railway
- Stripe production: 3 products + prices created (Recruiter `price_1TNh7s`, Agency Small `price_1TNh7t`, Agency Medium `price_1TNh7u`); webhook `we_1TNh85` → production Railway; live `sk_live_` + `pk_live_` set on Railway (api + worker) and Vercel
- IMAP + all production env vars confirmed set — `privateemail.com:993` carried over; all 20 vars present on Railway
