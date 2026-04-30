# PROGRESS — Sessions 25–27 (Main Branch: Bug Fixes + Infra)

*Full index: see [PROGRESS.md](PROGRESS.md)*

---

### Session 27 (main) — Streaming Payment Shortcut Fix

- **Root cause**: `_stream_generator` sent payment confirmations to Claude and depended on Claude's JSON formatting. The non-streaming path had a `_detect_payment_intent` shortcut that streaming lacked.
- **Fix**: Added same shortcuts at the top of `_stream_generator` — bypasses AI entirely for confirm/cancel in payment phase.
- **Also fixed**: Jobs list page now shows an error message when `GET /jobs` fails.

### Session 26 (main) — Production Bug Fixes (Signup Error + Super Admin Detection)

- **Signup error message** — human-readable message when metadata tagging fails.
- **Super admin detection** — replaced `NEXT_PUBLIC_SUPER_ADMIN_EMAIL` env var check with backend API probe (`superAdminApi.getStats()` 200 = super admin, 403 = not).
- All fixes cherry-picked to `feature/marketing` branch.

### Session 25 — Chat History Loss Fix (Streaming Persist + Frontend Hydration Guard)

**Bug 1 — Backend: session messages never saved after streaming**
- **Root cause**: `_stream_generator` called `await db.commit()` to save `session.messages` after many async `yield` points (one per streamed token). With NullPool + FastAPI's dependency lifecycle, the request-scoped `db` session's connection is in an inconsistent state by the time the generator reaches the commit — the ORM-level flush silently skips the UPDATE. On the next turn the session loads from DB with empty `messages`, the AI sees no history, and responds with a fresh greeting.
- **Fix**: Replace ORM-level `session.messages = ...; await db.commit()` with an explicit `UPDATE chat_sessions SET messages=..., phase=..., job_id=..., updated_at=...` executed through a brand-new `AsyncSessionLocal()`. Payment-related changes (job creation, credit deduction, audit events — flushed via `_create_job_on_payment`) are still committed via the request-scoped `db` before the session UPDATE. (`backend/app/routers/chat_sessions.py`)

**Bug 2 — Frontend: session ID overwritten by React Query re-fetch**
- **Root cause**: If the user sent the first message before `getCurrentSession()` resolved, `handleSend` created a new session (A) and began streaming to it. When the query resolved, the `useEffect` watching `session` would overwrite `sessionId` with the query's session (B). All subsequent messages then went to session B which had no history.
- **Fix**: `hydratedRef` ensures `sessionId` + `messages` are populated from the server exactly once per component mount. Subsequent React Query re-fetches (network reconnect, stale revalidation) do not overwrite local state. (`frontend/app/[locale]/(dashboard)/chat/page.tsx`)
