# AI Chat — Talent Scout Test Plan
Version: 1.0 | Date: 2026-04-30
Target: Production — https://app.airecruiterz.com
Login: marcusbahadur1@gmail.com
Email delivery: All emails use marcus@aiworkerz.com as hiring manager. Outreach emails
  go to real candidates unless EMAIL_TEST_MODE is enabled in Super Admin → Platform Keys.

---

## Approach

Playwright drives a real Chromium browser against production. Conversation turns are sent
via the API (same approach as the existing job-via-chat.spec.ts) so they are fast and
reliable. Browser UI is used for session-specific tests (navigate-away, refresh, new job).

Every conversation is stored server-side in chat_sessions.messages. To review any
conversation after a test run:
  1. Log in at app.airecruiterz.com → AI Recruiter Chat → Chat History
  2. Or query Supabase: SELECT id, phase, messages FROM chat_sessions ORDER BY created_at DESC

---

## Pre-conditions

- [ ] EMAIL_TEST_MODE enabled in Super Admin → Platform Keys (redirects all outreach to
      marcus@aiworkerz.com). Enable before running T01-T03, T07-T10.
- [ ] marcusbahadur1@gmail.com account has credits_remaining ≥ 10 (trial/unlimited plan)
- [ ] Credentials set in e2e/.env.production: PROD_TEST_EMAIL, PROD_TEST_PASSWORD

---

## AI Recruiter Prompt Changes (deployed with this test suite)

The 16-step flow was replaced with a smarter prompt:

### Rule 1 — Paste Detection
If the recruiter's first message contains a job description (80+ words, duties, skills,
salary, etc.), extract ALL fields in ONE pass. Show the Job Summary block immediately.
Only ask follow-up questions for genuinely missing REQUIRED fields:
  title, location, work_type, required_skills, experience_years,
  hiring_manager_name, hiring_manager_email.

Result: paste flow = ~2 turns (send JD → see summary → confirm → payment → done).

### Rule 2 — Streamlined Manual Flow (5 steps, was 16)
Step 1: Greeting
Step 2: Role basics (title + variations + skills + experience — combined)
Step 3: Location & compensation (location + work_type + salary — combined)
Step 4: Hiring details (HM name/email + min score + candidate count — combined)
Step 5: Assessment (outreach tone + evaluation criteria + test questions + format)
→ Immediately show Job Summary block after step 5

Result: manual flow = ~6 turns (was ~18).

---

## Test Scenarios

| ID  | Name                     | Method    | Credits | Verifies |
|-----|--------------------------|-----------|---------|----------|
| T01 | Full JD paste            | API       | 1       | Paste detection, 2-turn flow, job created |
| T02 | Partial JD paste         | API       | 1       | AI asks only for missing required fields |
| T03 | Manual conversational    | API       | 1       | 5-step flow, natural language |
| T04 | Navigate away + return   | Browser   | 0       | Session persists across navigation |
| T05 | New job fresh session    | Browser   | 0       | + New Job starts clean, no old session |
| T06 | Page refresh             | Browser   | 0       | Messages restored after reload |
| T07 | Remote global job        | API       | 1       | work_type=remote_global extraction |
| T08 | Executive / non-tech     | API       | 1       | tech_stack sparse for non-technical role |
| T09 | Minimal info             | API       | 1       | AI asks questions, no silent failures |
| T10 | Conflicting info         | API       | 1       | AI asks clarifying questions |
| T12 | Post-creation chat       | API       | 0       | Recruitment phase — AI answers questions |

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
Expected: Job Summary shown within 2 turns. Job created with title containing "Java".

### T02 — Marketing Manager (missing HM details)
```
We're looking for a Marketing Manager to lead our demand generation and content team.

Location: London, UK — hybrid 2 days in office
Experience: 4+ years B2B SaaS marketing
Required skills: Content Strategy, HubSpot, Google Analytics, LinkedIn Ads, SEO
Salary: GBP £65,000 – £80,000 per year
Team of 4 reports to this role.
```
Expected: AI extracts all fields, shows summary with hiring manager as "Not specified",
then asks specifically for hiring manager name and email. Does NOT re-ask for salary or location.

### T03 — Data Scientist (manual/conversational)
Opening: "I need to find a data scientist, someone experienced with Python and ML"
Expected: AI guides through 5 combined steps. Conversation feels natural.
HM email used: marcus@aiworkerz.com

### T04 — Navigation test (uses T01 JD)
No full JD creation — just establishes a session, navigates away to /jobs, returns.

### T05 — New job test
Starts any in-progress session, clicks + New Job, verifies fresh state.

### T06 — Refresh test
Establishes a session mid-conversation, refreshes browser, verifies messages restored.

### T07 — Senior React Developer (remote global)
```
Senior React Developer — fully remote, anywhere in the world.

5+ years React experience. TypeScript, Next.js, Redux, REST APIs, GraphQL.
Salary: USD $100,000 – $130,000 per year.
Team of 6 frontend engineers.
Hiring manager: Marcus Bahadur (marcus@aiworkerz.com)
Min score: 6, target 20 candidates.
```
Expected: work_type=remote_global extracted. location_variations covers global cities.

### T08 — Chief Financial Officer (non-tech executive)
```
We're searching for a CFO to join our ASX-listed company in Sydney.

The CFO will be responsible for all financial operations, reporting, capital allocation,
and investor relations. Must have 10+ years of experience in a senior finance role,
ideally as VP Finance or CFO. Strong background in IFRS, ASX compliance, M&A transactions.
MBA or CPA preferred. Onsite in Sydney CBD 5 days.
Salary package: AUD $350,000 – $450,000 total compensation.
Reports directly to the CEO. Current finance team of 12.
Hiring manager: Marcus Bahadur, marcus@aiworkerz.com.
Minimum score: 8. Target 10 candidates.
```
Expected: tech_stack is empty or Not specified. Skills focus on finance, not engineering.

### T09 — Minimal info
Opening: "I need a developer"
Expected: AI asks targeted questions without assuming anything.
Should collect all required fields before showing the Job Summary.

### T10 — Conflicting info
```
Frontend Developer — must work onsite in both Melbourne AND Sydney (both offices required),
salary is either $80k or equity only depending on experience level, 2 years experience
but must lead a team of 15 senior engineers and architects.
Hiring manager: Marcus Bahadur, marcus@aiworkerz.com
```
Expected: AI identifies the contradictions (dual location, salary ambiguity,
experience/seniority conflict) and asks clarifying questions.

### T12 — Post-creation recruitment chat
Uses an existing job that is already in recruitment phase.
Ask: "How many candidates have been found so far?"
Expected: AI responds with helpful recruitment-phase answer (not job_collection phase restart).

---

## Verification Matrix

For each test that creates a job, verify:
  ✓ chat_sessions.phase = 'recruitment' at end of test
  ✓ Job appears in GET /api/v1/jobs with correct title
  ✓ credits_remaining decremented by 1
  ✓ chat_sessions.messages contains full conversation transcript

For browser UI tests (T04, T05, T06), verify via DOM selectors:
  ✓ .msg.bot elements show previous AI messages after navigation/refresh
  ✓ .chat-input-wrap input is enabled (not disabled/loading)
  ✓ New session has empty messages list after + New Job click

---

## Running the Tests

```bash
cd e2e

# All chat tests (creates up to 9 jobs, costs 9 credits)
npm run chat:all

# Only browser UI tests (no credits consumed)
npm run chat:browser

# Only API conversation tests (each costs 1 credit)
npm run chat:api

# Single test
npx playwright test --config=playwright.chat.config.ts tests/chat/t01-paste-full.spec.ts

# With visible browser (useful for debugging)
npm run chat:headed
```

---

## After Tests Run

1. Log in at app.airecruiterz.com/en/chat/history to see all test conversations
2. Each conversation is tagged by job title (from the mock JDs above)
3. Check the Evaluation Report on each created job to see Scout activity
4. If email test mode was on, check marcus@aiworkerz.com for any received emails

---

## Known Limitations

- Tests use the live Claude Sonnet API — AI responses are non-deterministic. A test may
  occasionally fail if the AI produces an unexpected response format. Re-run once before
  investigating.
- T09 (minimal info) may need many turns and is the slowest test (~5 min).
- Chat test timeouts are set to 10 min per test to accommodate AI response latency.
