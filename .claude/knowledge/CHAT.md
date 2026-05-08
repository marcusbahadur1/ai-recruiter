# CHAT Domain

16-step job creation flow, 4 phases, streaming SSE, payment phase shortcut.

---

## Session Phases

```
job_collection → payment → recruitment → post_recruitment
```

| Phase | What happens |
|-------|-------------|
| `job_collection` | AI extracts job details from JD paste or conversational input |
| `payment` | Display credit balance, handle promo code, confirm payment |
| `recruitment` | Job + Scout active; chat answers questions about pipeline status |
| `post_recruitment` | Job closed/paused; historical context only |

## Session Data Model

- `messages`: JSONB array `[{role, content, timestamp}, ...]` — entire conversation
- `phase`: current phase string
- `job_id`: set after job creation (NULL until payment confirmed)
- `user_id`: Supabase Auth UUID (not an FK — not enforced at DB level)
- `tenant_id`: FK — all queries scoped by this

## Payment Shortcut (Critical)

When `session.phase == "payment"` and user message contains "confirm":
- **AI is bypassed entirely**
- Job is created directly from accumulated `job_fields` in Python
- This prevents AI JSON formatting errors from breaking job creation

See DECISIONS.md D4.

## Streaming Pattern

- Endpoint returns `StreamingResponse` (SSE)
- Frontend receives tokens in real-time via `ReadableStream`
- After stream completes: save session using **fresh** `AsyncSessionLocal()` with explicit `UPDATE`
- Do NOT use request-scoped `db` for this write (see DECISIONS.md D3)

## Credit Deduction

- 1 credit deducted at job creation (payment confirmation)
- If `tenant.credits_remaining < 1`: phase transitions to payment, user prompted to upgrade or use promo code

## Promo Code Flow

1. User types "promo CODE123" in payment phase
2. Router parses promo code
3. `SELECT * FROM promo_codes WHERE code = 'CODE123' AND is_active = true`
4. `UPDATE tenant SET credits_remaining += discount_amount`
5. `UPDATE promo_codes SET uses_remaining -= 1`

## Chat Sessions vs User

- Sessions scoped to `tenant_id`, not `user_id`
- All users on a tenant share the same session list (`GET /chat-sessions` returns all)
- `GET /chat-sessions/current` returns the most recent job_collection session for the tenant

## System Prompts

Three different system prompts depending on phase:
- `job_collection_system_prompt`: Extracts job fields from JD; returns structured JSON with current_step, job_fields, ready_for_payment
- `payment_system_prompt`: Handles credit balance display, promo code validation dialogue
- `recruitment_system_prompt`: General Q&A about Scout and Screener pipeline status

## Key Files

- `backend/app/routers/chat_sessions.py` — main router with `_stream_generator`
- `backend/app/models/chat_session.py` — ChatSession model
- `frontend/app/[locale]/(dashboard)/jobs/new/` — chat UI page
