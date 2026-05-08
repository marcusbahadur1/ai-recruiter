# Fragile Zones — F1–F6 (Tasks and Services)

see FRAGILE_ZONES_B.md for F7–F11 (Billing, Celery async, Marketing, Screener)

---

## F1 — `discover_candidates` Long Loop

**Location**: `backend/app/tasks/talent_scout_tasks.py`
**Risk**: Loops 10 pages × N queries × 10 results. Each candidate saved atomically inside the loop. Mid-loop crash leaves orphan candidates; partial discovery looks like full discovery from outside.
**Safe pattern**: Idempotency check `existing_count >= target` at start. Each save its own commit — don't batch. Don't increase page limit without considering task timeout.

---

## F2 — AI Provider Fallover on Transient Errors

**Location**: `backend/app/services/ai_provider.py`
**Risk**: Any exception — including a 1s network timeout — triggers silent fallover to secondary provider. Response quality/format may change mid-job.
**Safe pattern**: Don't add retry logic inside the facade; it interferes with Celery's outer retry (double wait).

---

## F3 — BrightData Returns `{}` for Private Profiles

**Location**: `services/brightdata.py`, `enrich_profile` task
**Risk**: Private LinkedIn profiles return `{}` not an error. Task treats it as success, status set to `profiled`. Candidate proceeds to scoring with no profile data — silently gets a low score.
**Safe pattern**: Log explicitly when `brightdata_profile == {}`. Do not raise (candidate can still score on SERP snippet).

---

## F4 — Chat Session Persistence After Streaming

**Location**: `backend/app/routers/chat_sessions.py`, `_stream_generator`
**Risk**: Fresh `AsyncSessionLocal()` write after streaming can fail. Tokens already delivered to client — session state lost, conversation reset on reload.
**Safe pattern**: Never use request-scoped `db` for writes after a `yield`. Always fresh session, explicit UPDATE.

---

## F5 — IMAP Polling with Blocking `imaplib`

**Location**: `backend/app/tasks/screener_tasks.py`, `poll_mailboxes`
**Risk**: `imaplib` is blocking, runs in `run_in_executor()`. If IMAP server hangs, thread pool slot held indefinitely. Decrypted IMAP passwords live in worker memory during the call.
**Safe pattern**: Wrap IMAP ops in `asyncio.wait_for()`. Don't persist decrypted credentials beyond immediate scope.

---

## F6 — RAG Retrieval Has No Similarity Threshold

**Location**: `backend/app/services/rag_pipeline.py`, `query()`
**Risk**: pgvector returns top-k regardless of semantic distance. Low-relevance chunks injected into screening or chat context could degrade response quality.
**Safe pattern**: Add cosine distance filter (`<= 0.4`) before returning chunks. Currently accepted as-is — see open questions.
