<!-- BEGIN:nextjs-agent-rules -->
# AI Recruiter — Frontend Agent Guide

## Next.js version warning

This is **Next.js 16** App Router. APIs, conventions, and file structure differ from training data. Read `node_modules/next/dist/docs/` before writing code. Heed deprecation notices.

- i18n routing uses **`proxy.ts`**, NOT `middleware.ts` — do not create or modify `middleware.ts`
- All routes live under `app/[locale]/(dashboard)/` (authenticated) or `app/[locale]/(auth)/` (public) or `app/[locale]/(public)/` (token-protected public pages)
- API calls use **relative URLs** (`/api/v1/...`) — the Vercel proxy rewrites these to Railway. Never hardcode the Railway URL in frontend code.

---

## Project context

**AI Recruiter** (airecruiterz.com) — multi-tenant SaaS recruitment automation.

- Backend: FastAPI on Fly.io (`airecruiterz-api`, region `syd`) — `/home/marcus/ai-recruiter/backend/`
- Worker: Celery on Fly.io (`airecruiterz-worker`, same Docker image, `WORKER_MODE=1`)
- Frontend: Next.js 16 on Fly.io (`airecruiterz-app`, region `syd`) — `/home/marcus/ai-recruiter/frontend/` ← you are here
- Redis: Fly.io Upstash (`airecruiterz-redis`)
- DB: Supabase PostgreSQL + pgvector, RLS enabled on all tables
- Queue: Celery + Redis on Railway
- Auth: Supabase Auth (JWT), tokens attached via Axios interceptor in `lib/api/client.ts`
- Full spec: `../SPEC.md` | Progress: `../PROGRESS.md` | Tasks: `../TODO.md`

---

## Deploy commands (Fly.io)

**Backend API** (from `backend/`):
```bash
fly deploy --config fly.toml --app airecruiterz-api
```

**Celery Worker** (from `backend/`):
```bash
fly deploy --config fly.worker.toml --app airecruiterz-worker
```

**Frontend** (from `frontend/`) — pass `NEXT_PUBLIC_*` vars if they've changed:
```bash
fly deploy --config fly.toml --app airecruiterz-app
# First time or if Supabase vars change:
fly deploy --config fly.toml --app airecruiterz-app \
  --build-arg NEXT_PUBLIC_SUPABASE_URL=https://vigtvsdwbkspkqohvjna.supabase.co \
  --build-arg NEXT_PUBLIC_SUPABASE_ANON_KEY=<anon-key>
```

**Check logs:**
```bash
fly logs --app airecruiterz-api
fly logs --app airecruiterz-worker
fly logs --app airecruiterz-app
```

**SSH into a machine:**
```bash
fly ssh console --app airecruiterz-api
```

---

## Critical architecture decisions (do not change without understanding)

### Chat streaming payment shortcuts
`_stream_generator` in `backend/app/routers/chat_sessions.py` has server-side shortcuts for `session.phase == "payment"`. When the user types "confirm", the AI is bypassed entirely — job creation must NOT depend on Claude's JSON formatting. This mirrors the non-streaming path. Do not remove these shortcuts.

### Session persistence uses a fresh AsyncSession
After streaming many tokens, the request-scoped `db` session is unreliable with NullPool + FastAPI dependency lifecycle. Session save uses an explicit `UPDATE` via a brand-new `AsyncSessionLocal()`. Do not switch back to ORM-level `session.messages = ...; await db.commit()`.

### NullPool on main SQLAlchemy engine
`backend/app/database.py` uses `poolclass=NullPool` on the main engine. This prevents `DuplicatePreparedStatementError` with pgbouncer transaction mode. Do not add connection pooling to the main engine.

### No `NEXT_PUBLIC_API_URL` in code
All API calls use relative `/api/v1` paths. Vercel rewrites them to Railway. Never use `process.env.NEXT_PUBLIC_API_URL` — it was removed intentionally.

### Super admin detection via API probe
`layout.tsx` detects super admin by calling `superAdminApi.getStats()` (200 = super admin, 403 = regular user). Do not use `NEXT_PUBLIC_SUPER_ADMIN_EMAIL` — it's baked in at build time and requires a redeploy on every change.

---

## API layer (`lib/api/`)

- `client.ts` — Axios instance + Supabase auth interceptor + 401 redirect
- `index.ts` — all API functions (`authApi`, `jobsApi`, `chatApi`, `candidatesApi`, `applicationsApi`, `settingsApi`, `superAdminApi`, etc.)
- `types.ts` — TypeScript interfaces matching backend Pydantic schemas

Chat streaming uses `fetch` + `ReadableStream` (not Axios) — `chatApi.sendMessageStream()` is an async generator.

---

## Common gotchas

- **QueryClient per page**: each page creates `new QueryClient()` at module level. Cross-page cache invalidation doesn't exist — React Query fetches fresh on every page mount (staleTime 0 by default for most queries).
- **`hydratedRef` in chat page**: prevents React Query re-fetch from overwriting `sessionId` mid-conversation. Do not remove it.
- **i18n**: message files in `messages/{en,de,es,fr}.json`. Use `useTranslations('namespace')` in client components. Namespaces: `common`, `chat`, `jobs`, `candidates`, `applications`, `settings`, `billing`, `superAdmin`.
- **Kanban board**: uses `candidatesApi.list({ limit: 200 })` — backend cap is 500, not 100.
- **Widget JS**: `public/widget/widget.js` is a plain JS file served at `/widget/widget.js`. Edit it directly, no bundler.

---

## Branch strategy

- `main` — production branch, auto-deploys backend to Railway
- `feature/marketing` — marketing website work (sessions 30–31), separate from core app

Always work on `main` for core app fixes unless explicitly told otherwise.
<!-- END:nextjs-agent-rules -->
