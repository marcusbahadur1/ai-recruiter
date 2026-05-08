# Decisions — DB, Async, and Task Patterns (D1–D7)

see DECISIONS_PRODUCT.md for frontend/product decisions (D8–D13)

---

## D1 — NullPool on Both Engines

**Location**: `database.py`
**Why**: Celery calls `asyncio.run()` per task — new event loop each time. Pooled connections bound to old loop → `RuntimeError`. API engine also NullPool to prevent `DuplicatePreparedStatementError` with pgbouncer TRANSACTION mode.
**Do not add** `pool_size`, `max_overflow`, or any pool param.

## D2 — Two Separate DB Engines (Port 6543 vs 5432)

**Location**: `database.py`, `_build_task_db_url()`
**Why**: pgbouncer TRANSACTION mode (6543) reassigns backend Postgres connections between transactions; Celery retries get stale prepared statement names → collision. Session pooler (5432) keeps same backend connection per session. `_build_task_db_url()` auto-switches `:6543` → `:5432`.

## D3 — Fresh `AsyncSessionLocal()` for Chat Persistence

**Location**: `routers/chat_sessions.py`, `_stream_generator`
**Why**: After 30+ seconds streaming, request-scoped `db` (NullPool) is closed. Use fresh session with explicit `UPDATE chat_sessions SET ... WHERE id=...` after stream.
**Do not**: revert to `session.messages = ...; await db.commit()` on request-scoped db.

## D4 — Payment Phase Shortcut

**Location**: `routers/chat_sessions.py`, `_stream_generator`
**Why**: When `phase == "payment"` and user types "confirm", AI is bypassed — job creation runs in Python. Claude's JSON is variable; deterministic Python guarantees success.
**Do not remove** this shortcut or make job creation depend on AI output.

## D5 — `proxy.ts` not `middleware.ts`

**Location**: `frontend/proxy.ts`
**Why**: Next.js 16 uses `proxy.ts` for i18n routing. `middleware.ts` alongside it breaks locale detection. Proxy also rewrites `/api/v1/*` → Fly.io, enabling relative URLs.
**Do not**: create `middleware.ts`, delete `proxy.ts`, hardcode API URLs.

## D6 — Audit Events in Separate Try/Except

**Location**: `tasks/talent_scout_tasks.py`, `screener_tasks.py`
**Why**: Audit failure must never roll back business write. Business commit first; audit in own try/except. If audit fails, only audit row rolls back.

## D8 — Platform Verified Sender for All Outbound Email

**Location**: `services/sendgrid_email.py`, `_resolve_from_address`
**Why**: Tenants must not need their own SendGrid account. All mail sends from `outreach@airecruiterz.com` (once verified with domain auth in SendGrid). Tenants set `outreach_from_name` (e.g. "Marcus Bahadur, Acme Corp") as the display name — this is the only per-tenant email customisation.
**Do not**: use `tenant.email_inbox` (IMAP receive-only) as a From address. Do not require per-tenant SendGrid keys for basic operation.

## D7 — Sync Embeddings in Celery

**Location**: `services/embeddings.py`
**Why**: Celery `asyncio.run()` tears down the loop after the task. Async embedding calls using `get_event_loop()` raise "Event loop is closed". Sync OpenAI client avoids this.
**Do not**: switch Celery calls to the async variant.
