# PROGRESS — Sessions 22–24 (Production Fixes + Email Test Mode)

*Full index: see [PROGRESS.md](PROGRESS.md)*

---

### Session 24 — Production Critical Bug Fix (AsyncSessionLocal + Chat Send + NullPool)
- **Root cause**: `main.py` trial-expiry middleware used `AsyncSessionLocal` but only `AsyncTaskSessionLocal` was imported — every API call was crashing with `NameError` before reaching any route handler. The global exception handler converted this to a 500 response. This affected all endpoints silently.
- **Fix**: Added `AsyncSessionLocal` to the import in `backend/app/main.py` — one line change.
- **Chat send also fixed**: Switched frontend chat from SSE streaming (`sendMessageStream`) back to standard non-streaming endpoint (`sendMessage` / `POST /chat-sessions/{id}/message`). Streaming was broken through the Vercel → Railway proxy. Non-streaming works reliably.
- **Frontend error handling improved**: `handleSend` now shows error messages in the chat UI instead of silently catching failures. User message is displayed immediately before the API call, so there's always visible feedback.
- **Vercel proxy hardened**: `next.config.ts` rewrite now falls back to hardcoded Railway URL if `NEXT_PUBLIC_API_URL` is empty or malformed (`.trim() || fallback`).
- **Vercel CLI installed**: `~/.local/bin/vercel` — used to deploy directly when GitHub → Vercel auto-deploy doesn't trigger.
- Chat send confirmed working on production `app.airecruiterz.com`.
- Restored SSE streaming in chat (`sendMessageStream`) — streaming was never broken, it was the `AsyncSessionLocal` 500 that killed every request. Tokens now stream in real time.
- Removed duplicate waiting indicator — typing dots and blinking `▋` cursor were both showing; dots removed, cursor retained.
- **NullPool fix for `DuplicatePreparedStatementError`**: asyncpg + pgbouncer transaction mode: connection pool (`pool_size=3`) was reusing asyncpg connections; named prepared statements from a previous request leaked on the pgbouncer server connection and caused `DuplicatePreparedStatementError` on reuse. Fixed by switching main engine to `poolclass=NullPool` — each request gets a fresh connection, matching the task engine which already used NullPool. (`backend/app/database.py`)

### Session 23 — Railway Worker Healthcheck Fix
- **Root cause diagnosed**: `backend/railway.toml` declared `healthcheckPath = "/health"` and `healthcheckTimeout = 30`. Because both `api` and `worker` services share the same `rootDirectory = "backend"` and neither had `railwayConfigFile` configured, Railway applied the healthcheck from `railway.toml` to both services. Celery has no HTTP server so the worker failed the healthcheck on every deployment — all deploys since April 22nd were failing.
- **Fix**: Removed `healthcheckPath` and `healthcheckTimeout` from `backend/railway.toml` entirely. Set healthcheck (`/health`, 30s) directly on the `api` service instance via Railway GraphQL API so the API continues to be health-checked. Worker service has no healthcheck at all.
- Committed and pushed to GitHub (`eb3cd9c`) — both `api` and `worker` deployed `SUCCESS` from the same push.
- Note: `worker.railway.toml` (with `startCommand = "sh worker.sh"`) exists but is not yet wired as the worker's config file — Railway uses the start command set directly in the dashboard (`celery -A app.tasks.celery_app:celery_app worker --beat --loglevel=info`). The TOML file is retained for reference.

### Session 22 — Email Test Mode Super Admin Toggle
- Added `backend/app/services/platform_settings.py` — Redis-backed runtime platform settings helpers: `get_email_test_mode()` reads `platform:email_test_mode` + `platform:email_test_recipient` keys from Redis, falls back to env vars if Redis unavailable or keys never set; `set_email_test_mode(enabled, recipient)` writes to Redis
- Updated `backend/app/tasks/talent_scout_tasks.py` — replaced `settings.email_test_mode` / `settings.email_test_recipient` with `get_email_test_mode()` so the Celery worker picks up runtime changes without restart
- Updated `backend/app/routers/super_admin.py` — added `EmailTestModeStatus` + `EmailTestModeUpdate` schemas; `GET /super-admin/email-test-mode` returns current state; `POST /super-admin/email-test-mode` persists toggle to Redis; both require super_admin auth
- Updated `frontend/lib/api/index.ts` — added `getEmailTestMode()` and `setEmailTestMode()` to `superAdminApi`
- Updated `frontend/app/[locale]/(dashboard)/super-admin/page.tsx`:
  - Persistent amber warning banner shown across entire page when test mode is active, with "Disable Now" quick-action button
  - Email Test Mode card in Platform Keys section: enable/disable toggle button (turns red when disabling), test recipient email input, current state display, polls state every 30 s
  - Env var `EMAIL_TEST_MODE` retained as cold-start fallback (staging `.env` files still work)
