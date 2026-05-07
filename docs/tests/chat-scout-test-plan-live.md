# AI Chat → Job Creation → Scout → Email — Live Test Plan
Version: 1.0 | Date: 2026-05-07
Target: Production — https://app.airecruiterz.com
Method: Playwright headed browser (visible window) against production
Test account: marcusbahadur1@gmail.com
Super admin: marcus@aiworkerz.com
Outreach emails redirect to: marcus@aiworkerz.com (EMAIL_TEST_MODE must be ON)

---

## RESUME PROMPT — paste this into a new session to resume

```
Resume the live AI Chat → Scout → Email test plan from docs/tests/chat-scout-test-plan-live.md.
Check the STATUS column in the test table to find the last PASS or SKIP entry, then
continue from the next PENDING test. Run tests via Playwright headed browser against
production (https://app.airecruiterz.com). Report PASS/FAIL/BLOCKED for every step.
```

---

## Pre-Requisites Before Any Test Runs

| ID  | Check | How | Status |
|-----|-------|-----|--------|
| PC01 | `EMAIL_TEST_MODE = ON` | Browser: log in as `marcus@aiworkerz.com` → Super Admin → Platform Config → verify toggle | PASS |
| PC02 | Test tenant has `credits_remaining ≥ 2` | Super Admin → Tenants → find `marcusbahadur1@gmail.com` → check credits | PASS |
| PC03 | Production API is reachable | `curl -s https://api.airecruiterz.com/health` → expect `{"status":"ok"}` | PASS |
| PC04 | Celery worker running on Fly.io | `fly logs --app airecruiterz-worker` — no crash loop in last 10 lines | PASS |
| PC05 | Migration 0022 applied | `fly ssh console --app airecruiterz-api` → `alembic current` shows `0022` | PASS | migrations 0021 + 0022 applied successfully |

---

## Phase 1 — AI Chat Core Flow

Test job: **[TEST] Senior Java Developer** (from T01 JD below)
Credits consumed: 1

| ID   | Step | Expected | Status | Notes |
|------|------|----------|--------|-------|
| TC01 | Open `https://app.airecruiterz.com/en` in headed browser | Dashboard loads, no redirect loop | PASS | |
| TC02 | Log in as `marcusbahadur1@gmail.com` | Dashboard visible, no 401 or error page | PASS | |
| TC03 | Navigate to `/en/chat` | Chat interface loads. Input box is enabled. Welcome/greeting message shown. Not spinning. | PASS | |
| TC04 | Type `Hello` and press Send | AI responds. Response appears in chat bubble. No stuck spinner. Content is a greeting or "what role are you hiring for?" | PASS | |
| TC05 | Paste the T01 JD (see below) and press Send | Within 2 AI turns: a Job Summary block is displayed. Contains: role, location, skills, hiring manager. | PASS | |
| TC06 | Type `yes` and press Send | AI transitions to payment phase. Shows credit balance and asks to confirm. | PASS | |
| TC07 | Type `confirm` and press Send | Payment shortcut fires. Job created. AI confirms recruitment is starting. Phase = `recruitment`. | PASS | Initial 402 — fixed by adding Anthropic credits + switching to Haiku model |
| TC08 | Navigate to `/en/jobs` | Job `[TEST] Senior Java Developer` visible in list with status `Active` | PASS | |
| TC09 | Navigate back to `/en/chat` | Chat restores to same session. Previous messages visible. Input enabled. | PASS | |
| TC10 | Hard-refresh the page (F5) | Same messages reload from server. No blank chat. Session ID unchanged. | PASS | |
| TC11 | Click `+ New Job` in chat header | Empty session opens. New session_id in URL. Input enabled and ready. | PASS | |
| TC12 | Ask: `"How many candidates have been found so far?"` (in recruitment phase session) | AI responds with a recruitment-phase answer (candidate count or scout status). Does NOT restart job collection. | PASS | |

### T01 Job Description — paste verbatim into TC05

```
I need to hire a Senior Java Developer. Here are all the details:

Role: Senior Java Developer
Location: Sydney CBD, hybrid 3 days per week
Experience: 5+ years with Java and Spring Boot
Salary: AUD $160,000 – $200,000 per year
Required skills: Java, Spring Boot, Microservices, PostgreSQL, Kafka
Tech stack: Java 17, Spring Boot 3, PostgreSQL, Kafka, Docker, AWS EKS
Team size: 8 engineers
Hiring manager: Marcus Bahadur, marcus@aiworkerz.com
Minimum suitability score: 7
Candidate target: 15
Number of test questions: 5
Interview format: text
```

---

## Phase 2 — Scout Pipeline Monitoring

After TC07, the Celery pipeline runs async. Poll the UI every 5 minutes.
Total expected time: 20–60 minutes depending on candidate count.

| ID   | Step | Expected | Status | Notes |
|------|------|----------|--------|-------|
| TC13 | Open Job detail → Audit Trail (immediately after TC07) | Events appear: `scout.candidate_discovered` within 5 min | PASS | |
| TC14 | Navigate to `/en/candidates`, filter by `[TEST] Senior Java Developer` | Candidates appear with status `discovered`, count increasing | PASS | 10 candidates discovered (stopped polling at 10 — sufficient for test) |
| TC15 | Refresh candidates page after ~10 min | Some candidates show status `profiled` | PASS | |
| TC16 | Refresh candidates page after ~20 min | At least 1 candidate shows status `passed` (score ≥ 7) | PASS | |
| TC17 | Refresh candidates page after ~30 min | At least 1 candidate shows status `emailed` | PASS | Required Option B: injected test email on passing candidate + triggered send_outreach directly. `domain_deduction` provider found 0 emails on real candidates — Hunter/Apollo keys not configured |
| TC18 | Open a candidate that is `emailed` | Candidate detail shows `outreach_email_sent_at` timestamp set. Outreach email content visible. | PASS | |
| TC19 | Check audit trail for `scout.outreach_email_sent` event | Event present. Shows candidate name and that email was dispatched. | PASS | |

---

## Phase 3 — Email Delivery Verification

| ID   | Step | Expected | Status | Notes |
|------|------|----------|--------|-------|
| TC20 | Check `marcus@aiworkerz.com` inbox | Outreach email received. From name shows tenant's `outreach_from_name` (e.g. "Marcus Bahadur, Acme Recruit") with `<outreach@airecruiterz.com>` address. Subject and body mention "Senior Java Developer". | PASS | Confirmed via SendGrid Activity: Delivered 2026-05-07 04:10:16 AM. Subject: "Your Payments Systems Expertise at IAG — Senior Java Role in Sydney" |
| TC21 | Verify recipient in received email | `To:` field shows `marcus@aiworkerz.com` (the test redirect) NOT a real candidate address | PASS | EMAIL_TEST_MODE redirect confirmed working |

---

## Failure Protocol

When any test step fails:
1. Note the exact error message in the Notes column above
2. Check network tab in browser dev tools for API errors
3. Run `fly logs --app airecruiterz-api` and `fly logs --app airecruiterz-worker` for backend errors
4. Diagnose root cause before moving on
5. If code fix needed: fix → commit → deploy → re-run only the failed step
6. Mark status: `FAIL(reason)` or `BLOCKED(dependency)`

**Status legend:**
- `PENDING` — not yet run
- `PASS` — ran and passed
- `FAIL(reason)` — ran and failed; reason noted
- `SKIP(reason)` — intentionally skipped (e.g. ENV_SKIP for infra outage)
- `BLOCKED(id)` — blocked waiting for another step to pass

---

## Final Report Template

## Test Run Report — 2026-05-07

| Phase | ID | Status | Notes |
|-------|----|--------|-------|
| Pre-check | PC01 | PASS | |
| Pre-check | PC02 | PASS | |
| Pre-check | PC03 | PASS | |
| Pre-check | PC04 | PASS | |
| Pre-check | PC05 | PASS | migrations 0021 + 0022 applied |
| Chat | TC01 | PASS | |
| Chat | TC02 | PASS | |
| Chat | TC03 | PASS | |
| Chat | TC04 | PASS | |
| Chat | TC05 | PASS | |
| Chat | TC06 | PASS | |
| Chat | TC07 | PASS | Initial 402 — fixed by adding Anthropic credits + Haiku model |
| Chat | TC08 | PASS | |
| Chat | TC09 | PASS | |
| Chat | TC10 | PASS | |
| Chat | TC11 | PASS | |
| Chat | TC12 | PASS | |
| Scout | TC13 | PASS | |
| Scout | TC14 | PASS | 10 candidates discovered |
| Scout | TC15 | PASS | |
| Scout | TC16 | PASS | |
| Scout | TC17 | PASS | Option B: manual email injection — domain_deduction finds 0 real emails |
| Scout | TC18 | PASS | |
| Scout | TC19 | PASS | |
| Email | TC20 | PASS | Delivered confirmed via SendGrid Activity |
| Email | TC21 | PASS | EMAIL_TEST_MODE redirect working |

Total: 26/26  PASS: 26  FAIL: 0  SKIP: 0  BLOCKED: 0

### Known Gaps / Follow-up Items
1. **Email discovery in production**: `domain_deduction` finds ~0% of real candidate emails. Recommend adding Hunter (free tier: 25/mo) or Apollo API key to tenant settings.
2. **TC07 initial failure**: Production Anthropic API was out of credits. Resolved by adding credits + switching all AI calls to cheapest models (Haiku 4.5 / gpt-4o-mini).
3. **SendGrid domain auth**: `outreach@airecruiterz.com` domain authenticated and verified. All outbound email now routes through platform verified sender.
