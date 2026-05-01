# Module 05 — AI Recruiter Chat & Job Creation Test Plan
Version: 2.0 | Date: 2026-05-01
Target: https://app.airecruiterz.com
Login: marcusbahadur1@gmail.com
Supersedes: ai-chat-talent-scout-test-plan.md (original v1.0)
Automation: API tests fully automated. Browser UI tests automated. AI responses non-deterministic (retry once on failure).

---

## Approach

Playwright drives a real Chromium browser. Conversation turns are sent via the streaming
API (same approach as existing job-via-chat.spec.ts) for speed and reliability. Browser UI
tests validate session persistence, navigation, and rendering. All jobs created are titled
with `[TEST]` prefix for easy identification and cleanup.

Every conversation is stored server-side in `chat_sessions.messages`. To review after a run:
  - Log in → AI Recruiter Chat → Chat History
  - Or: `SELECT id, phase, messages FROM chat_sessions ORDER BY created_at DESC`

---

## Pre-conditions

- [ ] `EMAIL_TEST_MODE=ON` (enable before running T01–T03, T07–T10)
- [ ] Test tenant has `credits_remaining ≥ 10`
- [ ] `PROD_TEST_EMAIL` and `PROD_TEST_PASSWORD` set in `e2e/.env.production`

---

## Prompt Changes (deployed with this suite)

**Rule 1 — Paste Detection:** 80+ word JD → extract ALL fields in one pass → show Job
Summary block → ask only for genuinely missing required fields
(title, location, work_type, required_skills, experience_years, hiring_manager_name,
hiring_manager_email). Result: ~2 turns.

**Rule 2 — Streamlined Manual Flow (5 steps):**
Step 1: Greeting | Step 2: Role basics | Step 3: Location & compensation
Step 4: Hiring details | Step 5: Assessment → Job Summary block
Result: ~6 turns (was ~18).

---

## Test Scenarios

| ID   | Name | Method | Credits | Automated |
|------|------|--------|---------|-----------|
| T01  | Full JD paste — 2-turn flow, job created | API | 1 | Yes |
| T02  | Partial JD paste — AI asks only for missing fields | API | 1 | Yes |
| T03  | Manual conversational — 5-step flow | API | 1 | Yes |
| T04  | Navigate away + return — session persists | Browser | 0 | Yes |
| T05  | New Job — fresh session, no old state | Browser | 0 | Yes |
| T06  | Page refresh — messages restored | Browser | 0 | Yes |
| T07  | Remote global job — work_type extraction | API | 1 | Yes |
| T08  | Executive / non-tech — sparse tech_stack | API | 1 | Yes |
| T09  | Minimal info — AI asks questions | API | 1 | Yes |
| T10  | Conflicting info — AI asks clarifiers | API | 1 | Yes |
| T12  | Post-creation recruitment chat | API | 0 | Yes |
| T13  | Chat History — session list, click to restore | Browser | 0 | Yes |

---

## Mock Job Descriptions

### T01 — Senior Java Developer (complete)
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
Expected: Job Summary within 2 turns. Job created with title containing "Java".

### T02 — Marketing Manager (missing HM details)
```
We're looking for a Marketing Manager to lead our demand generation team.
Location: London, UK — hybrid 2 days in office
Experience: 4+ years B2B SaaS marketing
Required skills: Content Strategy, HubSpot, Google Analytics, LinkedIn Ads, SEO
Salary: GBP £65,000 – £80,000 per year. Team of 4 reports to this role.
```
Expected: AI shows summary with HM "Not specified", then asks specifically for
HM name and email. Does NOT re-ask salary or location.

### T03 — Data Scientist (manual)
Opening: "I need to find a data scientist, someone experienced with Python and ML"
Expected: AI guides through 5 combined steps naturally. HM: marcus@aiworkerz.com

### T07 — Senior React Developer (remote global)
```
Senior React Developer — fully remote, anywhere in the world.
5+ years React experience. TypeScript, Next.js, Redux, REST APIs, GraphQL.
Salary: USD $100,000 – $130,000 per year. Team of 6.
Hiring manager: Marcus Bahadur (marcus@aiworkerz.com)
Min score: 6, target 20 candidates.
```
Expected: `work_type=remote_global`. Location variations covers global cities.

### T08 — CFO (non-tech executive)
```
We're searching for a CFO to join our ASX-listed company in Sydney.
10+ years senior finance role, ideally VP Finance or CFO.
Strong background in IFRS, ASX compliance, M&A transactions. MBA or CPA preferred.
Onsite Sydney CBD 5 days. Salary: AUD $350,000–$450,000.
Reports to CEO. Finance team of 12.
Hiring manager: Marcus Bahadur, marcus@aiworkerz.com.
Min score: 8. Target 10 candidates.
```
Expected: `tech_stack` empty or "Not specified". Skills focus on finance.

### T09 — Minimal Info
Opening: "I need a developer"
Expected: AI asks targeted questions without assuming anything.

### T10 — Conflicting Info
```
Frontend Developer — must work onsite in both Melbourne AND Sydney,
salary is either $80k or equity only depending on experience, 2 years experience
but must lead a team of 15 senior engineers.
Hiring manager: Marcus Bahadur, marcus@aiworkerz.com
```
Expected: AI identifies contradictions and asks clarifying questions.

### T12 — Post-creation Recruitment Chat
Uses an existing job already in `recruitment` phase.
Ask: "How many candidates have been found so far?"
Expected: AI gives a recruitment-phase answer (not a job_collection restart).

---

## Scenario Detail

### T04 — Navigate Away + Return
1. Open `/en/chat`, type any message to establish a session
2. Note the session ID from URL or state
3. Navigate to `/en/jobs`
4. Navigate back to `/en/chat`
5. Verify: `.msg.bot` elements show previous AI messages
6. Verify: input is enabled (not stuck loading)
7. Verify: session ID in URL matches original

### T05 — New Job Fresh Session
1. Open `/en/chat` with an active session
2. Click "+ New Job" in chat header
3. Verify: messages area clears (no old messages)
4. Verify: URL updates with new `session_id`
5. Verify: input is enabled and ready

### T06 — Page Refresh
1. Open `/en/chat`, send 2–3 messages
2. Hard-reload the page (Playwright `page.reload()`)
3. Verify: `.msg.bot` elements reload with prior messages
4. Verify: input re-enables after hydration
5. Verify: session_id in URL is the same as before reload

### T13 — Chat History Page
1. Navigate to `/en/chat/history`
2. Verify: list of past sessions renders (at least the sessions from T01–T03)
3. Verify: each row shows job title + date
4. Click on a session from T01
5. Verify: navigates to the chat with that session's messages restored
6. Verify: all T01 conversation messages are visible

---

## Verification Matrix — Job-Creating Tests

For each test that creates a job (T01–T03, T07–T10) verify:
- `chat_sessions.phase = 'recruitment'` at end
- Job appears in `GET /api/v1/jobs` with correct title
- `credits_remaining` decremented by 1
- `chat_sessions.messages` contains full conversation

For browser UI tests (T04–T06, T13) verify via DOM:
- `.msg.bot` elements restored after navigation/refresh
- Input enabled (not disabled/loading)
- Session state consistent

---

## Run Commands

```bash
cd e2e

# All chat tests
npm run chat:all

# API conversation tests only (credits consumed)
npm run chat:api

# Browser UI tests only (no credits)
npm run chat:browser

# Single test
npx playwright test --config=playwright.chat.config.ts tests/chat/t01-paste-full.spec.ts

# Headed (debug)
npm run chat:headed
```

---

## Known Limitations

- AI responses are non-deterministic. Retry once before treating as a failure.
- T09 (minimal info) may take many turns and is slowest (~5 min).
- Chat test timeouts: 10 min per test to accommodate AI latency.
- T12 requires a job already in `recruitment` phase — ensure module 05 created one.
