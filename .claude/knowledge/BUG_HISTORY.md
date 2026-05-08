# Bug History — B1–B5

see BUG_HISTORY_B.md for B6–B9

---

## B1 — DuplicatePreparedStatementError in Celery

**Symptom**: Celery tasks failed with `DuplicatePreparedStatementError`; retries also failed.
**Root cause**: pgbouncer TRANSACTION mode (port 6543) reassigned backend Postgres connections between transactions. Stale named prepared statements collided on new connections.
**Fix**: Celery engine → session pooler (port 5432). NullPool on both engines.
**Must not revert**: `_build_task_db_url()` port switch, NullPool on both engines.

---

## B2 — Chat Session Messages Lost After Streaming

**Symptom**: Conversation history lost on page reload; streamed responses vanished.
**Root cause**: Request-scoped `db` (NullPool) closed after long streaming. Final `await db.commit()` silently failed.
**Fix**: Fresh `AsyncSessionLocal()` after streaming, explicit `UPDATE chat_sessions SET messages=...`.
**Must not revert**: Fresh session pattern in `_stream_generator`.

---

## B3 — BrightData Double-Encoded JSON

**Symptom**: `brightdata_profile` stored as a string `"{\"name\":...}"` not a dict.
**Root cause**: BrightData API occasionally returned JSON double-encoded (JSON string of JSON string).
**Fix**: Detection for string-type response body; parse as JSON a second time before storing.
**Must not revert**: Double-decode check in `brightdata.py`.

---

## B4 — Wrong SendGrid Sender Address

**Symptom**: Outbound Scout emails rejected — "sender not verified".
**Root cause**: Used platform default `SENDGRID_FROM_EMAIL` instead of the verified sender `marcus.bahadur@aiworkerz.com`.
**Fix**: Updated `sendgrid_email.py` to use the verified sender.
**Must not revert**: `from_email` must be the verified address.

---

## B5 — `discover_candidates` Not Queued After Job Creation

**Symptom**: Talent Scout pipeline never started after chat confirmation.
**Root cause**: Task queued with wrong name or missing from `-Q celery` queue.
**Fix**: Corrected task name and queue in the chat payment shortcut path.
**Must not revert**: `discover_candidates` must be queued in `celery` queue (not `marketing`).
