# Module 08 — Resume Screener & Applications Test Plan
Version: 1.0 | Date: 2026-05-01
Target: https://app.airecruiterz.com
Automation: Full (Playwright handles all UI + text-based tests; audio/video use fake media streams; IMAP bypassed via direct API ingest)

---

## Scope

Applications list (filter, table), Application detail (resume score, Trigger Test button),
Competency test — all formats (text, audio, video) from the candidate's browser perspective,
Interview invited page (candidate action), Unsubscribe page (candidate opts out),
Application status tracking across the full screening pipeline.

## Pre-conditions

- Screener job created in module 06 (JB14)
- `EMAIL_TEST_MODE=ON` (all screening/invite emails → marcus@aiworkerz.com)
- At least 1 application exists for the screener job — seeded via direct API call (see SC14)
- Test resume PDF: `e2e/fixtures/resume-test.pdf`
- Playwright launched with:
  `--use-fake-ui-for-media-stream --use-fake-device-for-media-stream`
  for audio/video recording tests

---

## Test Scenarios

| ID   | Name | Automated |
|------|------|-----------|
| SC01 | Applications list loads — table + columns | Yes |
| SC02 | Applications list — job filter dropdown | Yes |
| SC03 | Applications list — row click → application detail | Yes |
| SC04 | Application detail — resume score card (strengths/gaps) | Yes |
| SC05 | Application detail — Trigger Test button → email sent | Yes |
| SC06 | Application detail — status badge lifecycle display | Yes |
| SC07 | Competency test — text format: answer all questions, submit | Yes |
| SC08 | Competency test — audio format: record, stop, playback, submit | Yes (fake stream) |
| SC09 | Competency test — video format: record with video, submit | Yes (fake stream) |
| SC10 | Competency test — invalid/expired token → error state | Yes |
| SC11 | Competency test — landing page: job info + start button | Yes |
| SC12 | Interview invited page — renders for valid token | Yes |
| SC13 | Unsubscribe page — candidate opts out, flag set | Yes |
| SC14 | IMAP inbound flow — application seeded via API, full pipeline verified | Yes |

---

## Scenario Detail

### SC01 — Applications List Loads
1. Navigate to `/en/applications`
2. Verify: page title "Applications" + subtitle "X total applications"
3. Verify: table columns: Applicant | Email | Received | Resume Score | Test Score | Status
4. Verify: score pills are color-coded
5. Verify: status badges use correct values:
   received | screened_passed | screened_failed | test_invited | test_passed |
   test_failed | hm_notified | interview_invited | rejected
6. Verify: rows are clickable

### SC02 — Job Filter Dropdown
1. In applications list, locate the Job dropdown ("All Jobs")
2. Verify: dropdown lists all screener jobs for the tenant
3. Select the screener job created in module 06
4. Verify: table updates to show only applications for that job
5. Select "All Jobs" → full list returns

### SC03 — Row Click → Application Detail
1. Click any application row
2. Verify: navigates to `/en/applications/{id}`
3. Verify: applicant name in breadcrumb (Applications / [Name])

### SC04 — Application Detail: Resume Score Card
1. Navigate to `/en/applications/{id}` for a screened application
2. Verify: "Resume Score" card present with score pill (color-coded)
3. Verify: resume reasoning text is non-empty prose
4. Verify: Strengths section (green ✓ list) present
5. Verify: Gaps section (amber △ list) present

### SC05 — Trigger Test Button
Pre-condition: Application is in `screened_passed` status, test not yet sent.
1. On application detail, locate "Trigger Test" button
2. Click "Trigger Test"
3. Verify: button shows "Sending..." loading state
4. Wait for completion (up to 10s)
5. Verify: success state (button disappears or status changes)
6. Verify: `GET /api/v1/screener/applications/{id}` shows status = `test_invited`
7. Verify: EMAIL_TEST_MODE redirected test invitation to marcus@aiworkerz.com

### SC06 — Status Badge Lifecycle
1. Navigate to applications list
2. Verify at least one application shows each tracked status (or as many as exist):
   `received` → `screened_passed` → `test_invited` → `test_passed` → `interview_invited`
3. For each status, verify the badge text and color-coding match the status mapping

### SC07 — Competency Test: Text Format
Pre-condition: Obtain the test link from an application in `test_invited` status.
Extract `application_id` and `token` from the test invitation email or API.
1. Navigate to `/en/test/{application_id}/{token}`
2. Verify: landing page shows job info + "Start Test" button
3. Click "Start Test"
4. Verify: first question displays
5. For each question:
   a. Verify: textarea input visible
   b. Verify: character count display
   c. Type a test answer (≥ 50 chars)
   d. Submit or move to next question
6. After all questions: click "Submit Test"
7. Verify: completion message shown ("Thank you" or similar)
8. Verify: `GET /api/v1/screener/applications/{id}` shows status = `test_passed` or `test_failed`

### SC08 — Competency Test: Audio Format
Pre-condition: Screener job created with Assessment Format = "Audio recording".
Application in `test_invited` status. Playwright started with fake media flags.
1. Navigate to `/en/test/{application_id}/{token}`
2. Click "Start Test"
3. Verify: recording UI appears (no textarea — microphone controls only)
4. Click "Start recording" (green button)
5. Verify: timer starts counting up (MM:SS)
6. Wait 3 seconds (fake stream records silence)
7. Click "Stop" (red button)
8. Verify: playback control appears for the recorded answer
9. Click "Submit" for this answer
10. Repeat for remaining questions
11. Verify: completion state reached

### SC09 — Competency Test: Video Format
Same flow as SC08 but with video recording enabled.
1. Verify: video preview (fake webcam stream) renders during recording
2. Verify: both audio + video recorded together

### SC10 — Competency Test: Invalid Token
1. Navigate to `/en/test/00000000-0000-0000-0000-000000000000/invalid-token`
2. Verify: error state rendered (not a blank page or 404)
3. Verify: user-friendly error message (not a raw stack trace)

### SC11 — Competency Test Landing Page
1. Navigate to `/en/test/{valid_application_id}/{valid_token}`
2. Verify: job title displayed
3. Verify: "Start Test" button present and enabled
4. Verify: no recording or question UI yet (only landing)

### SC12 — Interview Invited Page
Pre-condition: Application in `interview_invited` status. Obtain `application_id` and `token`
from the interview invitation email (check marcus@aiworkerz.com with EMAIL_TEST_MODE=ON).
1. Navigate to `/en/interview-invited` with correct query params or path params
2. Verify: page renders without error
3. Verify: job title / company info visible
4. Verify: candidate action (accept/decline or acknowledgement) available

### SC13 — Unsubscribe Page
1. Navigate to `/en/unsubscribe/{candidateId}` using a real candidate ID from module 07
   (use the disposable test candidate, NOT an important candidate)
2. Verify: page renders — shows opt-out message and candidate name
3. Verify: opt-out confirmation button (or auto-opt-out on load)
4. Complete the opt-out action
5. Verify: success message shown
6. Verify: `GET /api/v1/candidates/{candidateId}` shows `opted_out = true`
7. Verify in module 07 (C14): candidate profile now shows the red "⊘ Opted Out" banner

### SC14 — IMAP Inbound Flow (API-seeded)
Mock approach: The IMAP poller is just a delivery mechanism — it receives an email and
calls the same internal ingest logic. We bypass the socket/polling layer entirely by
POSTing directly to the backend ingest endpoint with a multipart resume file.
This exercises 100% of the same code path (resume extraction, AI screening, scoring,
audit trail, status transitions) without waiting for a 5-minute IMAP cycle.

```js
// Test helper — seeds one application before this module runs
const form = new FormData()
form.append('job_id', screenerJobId)
form.append('applicant_email', 'testapplicant@example.com')
form.append('applicant_name', 'Test Applicant')
form.append('resume', fs.createReadStream('e2e/fixtures/resume-test.pdf'), 'resume.pdf')

await axios.post('/api/v1/screener/applications/ingest', form, {
  headers: { ...form.getHeaders(), Authorization: `Bearer ${tenantToken}` }
})
```

Steps:
1. Test setup calls the ingest helper above (runs once before SC01)
2. Navigate to `/en/applications`
3. Verify: the seeded application appears in the list (applicant name "Test Applicant")
4. Verify: `status = screened_passed` or `screened_failed` (AI has scored the resume)
5. Verify: Resume Score card in the application detail is populated
6. Verify: audit trail for the screener job shows ingest + screening events

**Note on IMAP socket testing:**
The IMAP socket connection itself (TCP handshake, IMAP IDLE, email parsing) is covered
by the backend unit tests in `backend/tests/test_imap_poller.py`. It does not need
to be re-tested at the E2E level on every run.

---

## Verification Matrix

| ID   | Key Assertion |
|------|---------------|
| SC01 | Table with correct columns, status badges present |
| SC02 | Job filter updates table |
| SC03 | Row click → /applications/{id} |
| SC04 | Resume score card with reasoning + strengths/gaps |
| SC05 | Trigger Test → status becomes `test_invited`, email sent |
| SC06 | Status badges match lifecycle stages |
| SC07 | Text test: all questions answered, completion shown, status updated |
| SC08 | Audio test: record/stop/submit cycle completes |
| SC09 | Video test: video preview + record/submit cycle completes |
| SC10 | Invalid token shows user-friendly error |
| SC11 | Landing page: job info + Start Test button visible |
| SC12 | Interview invited page renders correctly |
| SC13 | Unsubscribe sets opted_out flag, opted-out UI confirmed in module 07 |
| SC14 | API ingest → application created → resume scored → audit events present |
