# Call Sequences — Auth, Chat, Scout, Screener

see CALL_SEQUENCES_SERVICES.md for AI Provider, Billing, RAG, Marketing, Celery retry pattern

---

## 1. Auth / Tenant Resolution

```
POST /api/v1/auth/login {email, password}
  → Supabase Auth signInWithPassword()
  → Query Tenant WHERE user_id = sub
  → Return {access_token, refresh_token, tenant_id, plan}

All requests: Authorization: Bearer {token}
  → get_current_tenant(): decode JWT → SELECT tenant WHERE user_id=sub
  → Trial expiry middleware: 402 if expired (except /billing, /webhooks)
```
Failure: 401 (bad creds), email unconfirmed, 402 (trial expired)

---

## 2. 16-Step Job Creation via Chat

```
GET /chat-sessions/current → create if none (phase=job_collection)

POST /chat-sessions/{id}/message {content}
  → Append user msg to session.messages
  → AIProvider.stream_complete(job_collection_prompt) → SSE tokens
  → Parse: {job_fields, ready_for_payment}
  → If ready_for_payment: phase=payment
  → FRESH AsyncSessionLocal() → UPDATE messages+phase → COMMIT

POST /chat-sessions/{id}/message {content:"confirm"} [payment phase]
  → SHORTCUT: AI bypassed (see DECISIONS D4)
  → CREATE Job from job_fields
  → tenant.credits_remaining -= 1
  → session.job_id = job.id, phase=recruitment
  → emit job.created audit event
  → queue discover_candidates(job_id, tenant_id)
```
Failure: 402 (no credits), AI parse error (re-prompt), DB write fail

---

## 3. Talent Scout Pipeline (summary)

```
discover_candidates → ScrapingDog SERP → CREATE Candidates (status=discovered)
  → queue enrich_profile per candidate

enrich_profile → BrightData API → status=profiled → queue score_candidate

score_candidate → AIProvider.complete_json() → score 1-10
  → status=passed|failed → if passed: queue discover_email

discover_email → Apollo→Hunter→Snov→EmailDeduction
  → if found: queue send_outreach; else status=failed

send_outreach → AIProvider.complete_json() → SendGrid
  → outreach_email_sent_at=now
```
See SCOUT.md for idempotency guards and retry details.

---

## 4. Resume Screener Pipeline (summary)

```
[Beat 5min] poll_mailboxes → IMAP UNSEEN → parse job_ref from subject
  → CREATE Application(screening_status=pending) → queue screen_resume

screen_resume → embed resume → RAG context → AIProvider score
  → passed: queue invite_to_test; failed: queue send_rejection_email

invite_to_test → AIProvider generate questions → CREATE TestSession
  → UPDATE Application(test_status=invited) → SendGrid test link

[Candidate] POST /screener/test/{token}/submit
  → UPDATE TestSession(answers) → queue score_test

score_test → AIProvider score → passed: notify_hiring_manager
  → failed: send_rejection_email

notify_hiring_manager → SendGrid to hiring_manager_email
  → interview_invited=true
```
See SCREENER.md for full task detail.
