# Fragile Zones — F7–F11 (Billing, Celery, Marketing, Screener)

see FRAGILE_ZONES.md for F1–F6 (tasks and services)

---

## F7 — Stripe Webhook Not Idempotent by Event ID

**Location**: `backend/app/routers/webhooks.py`
**Risk**: Stripe retries webhooks on delivery failure. `checkout.session.completed` firing twice could double-credit a tenant. No deduplication by `event.id` currently implemented.
**Safe pattern**: Store processed event IDs in a `stripe_events` table, check before processing. Not implemented yet — see open questions.

---

## F8 — PromoCode Has No Expiry Date Field

**Location**: `backend/app/models/` (PromoCode)
**Risk**: Only `is_active` boolean to disable codes — no `expires_at`. Codes must be manually deactivated; no time-based expiry.
**Safe pattern**: Add `expires_at` column in a migration before using codes in any marketing campaign.

---

## F9 — Celery Tasks Use `asyncio.run()` Per Task

**Location**: All task wrappers in `backend/app/tasks/`
**Risk**: Each task creates and destroys an event loop. Consequences:
- No shared async state between tasks
- Nested `asyncio.run()` inside a task raises "Cannot run loop while another is running"
- Long async calls can't be cleanly interrupted
**Safe pattern**: Keep all async code inside `_async_impl()`. Never call `asyncio.run()` from inside an already-running event loop.

---

## F10 — Marketing Token Refresh Race Condition

**Location**: `backend/app/tasks/marketing_tasks.py`, `publish_scheduled_posts`
**Risk**: Token refresh is checked per-post. Two posts for the same account publishing simultaneously may both attempt refresh — one refresh invalidates the other's token.
**Safe pattern**: Use a Redis lock at the account level before refreshing. Not implemented yet.

---

## F11 — Test Token Expiry Check on Submit (Unconfirmed)

**Location**: `backend/app/routers/screener.py`
**Risk**: Unclear whether `interview_invite_expires_at` is validated when a candidate submits at `POST /screener/test/{token}/submit`. If not, expired tokens can still be used.
**Status**: Low-confidence — verify in `screener.py` before working in this area. Listed in low-confidence areas memory.
