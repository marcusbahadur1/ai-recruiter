# Decisions — Frontend and Product Patterns (D8–D13)

see DECISIONS.md for DB, async, and task decisions (D1–D7)

---

## D8 — ChatSession Messages as JSONB Array

**Location**: `backend/app/models/chat_session.py`, column `messages`
**Why**: Sessions are always read/written as a unit — no need to query individual messages. JSONB avoids a Message table join on every chat turn and allows adding fields to messages without a migration.
**Implication**: Messages are never individually addressable; always load/save the full array.

---

## D9 — Dashboard at `/en` not `/en/dashboard`

**Location**: `frontend/app/[locale]/(dashboard)/page.tsx`
**Why**: UX decision from early design. `/en/dashboard` has a redirect to `/en` for backwards compatibility.

---

## D10 — Super Admin Detected via API Probe

**Location**: `frontend/app/[locale]/(dashboard)/layout.tsx`
**Why**: `layout.tsx` calls `superAdminApi.getStats()` — 200 = super admin, 403 = regular user. Hardcoding `NEXT_PUBLIC_SUPER_ADMIN_EMAIL` at build time requires a redeploy on every change. API probe is dynamic.

---

## D11 — All API Calls Use Relative URLs

**Location**: All `frontend/lib/api/` functions
**Why**: `proxy.ts` rewrites `/api/v1/*` to Fly.io. No env var needed at runtime, no CORS issues.

---

## D12 — Unlimited Retries for 429/529 Overload

**Location**: `backend/app/tasks/talent_scout_tasks.py`, `score_candidate`, `send_outreach`
**Why**: AI overload is temporary. Abandoning a candidate job permanently because Claude was briefly rate-limited is worse than waiting. 429/529 bypass `max_retries` and retry every 300s indefinitely.

---

## D13 — Job Reference (job_ref) for Email Routing

**Location**: `backend/app/models/job.py`, `backend/app/tasks/screener_tasks.py`
**Why**: One IMAP inbox per tenant — no per-job sub-addresses. Resume emails must include `[JOB-XXXXXXXX]` in the subject. The screener parses this to route the email to the correct job.
