# Module 07 — Candidate Management Test Plan
Version: 1.0 | Date: 2026-05-01
Target: https://app.airecruiterz.com
Automation: Full (all tests automated unless marked [MANUAL])

---

## Scope

Candidates list (search, filters, table), candidate profile page (score reasoning,
LinkedIn profile card, outreach email card, actions sidebar), Send Outreach, Edit Notes,
GDPR Delete modal, opted-out candidate display.

## Pre-conditions

- Logged in as test tenant
- At least 2 candidates exist (created by Talent Scout in module 05)
- At least 1 candidate with a suitability score (profiled + scored)
- `EMAIL_TEST_MODE=ON` (Send Outreach test emails → marcus@aiworkerz.com)
- Use a disposable candidate for the GDPR delete test (C09) — not a real production candidate

---

## Test Scenarios

| ID   | Name | Automated |
|------|------|-----------|
| C01  | Candidates list loads — table with correct columns | Yes |
| C02  | Search — type name, results debounce and filter | Yes |
| C03  | Search — clear input, all candidates return | Yes |
| C04  | Status filter — each option filters table | Yes |
| C05  | Score filter — each option filters table | Yes |
| C06  | Candidate row click → profile page | Yes |
| C07  | Candidate profile — hero card (name, title, company, skills, score) | Yes |
| C08  | Candidate profile — AI Score Reasoning card (strengths + gaps) | Yes |
| C09  | Candidate profile — LinkedIn Profile card (headline, experience, education) | Yes |
| C10  | Candidate profile — Outreach Email card visible after outreach sent | Yes |
| C11  | Candidate profile — Send Outreach button → success state | Yes |
| C12  | Candidate profile — GDPR Delete modal: opens, cancel works | Yes |
| C13  | Candidate profile — GDPR Delete: confirm → anonymised, redirect to list | Yes |
| C14  | Opted-out candidate — red banner shown, Send Outreach disabled | Yes |
| C15  | Candidates list — empty state when no results match search | Yes |

---

## Scenario Detail

### C01 — Candidates List
1. Navigate to `/en/candidates`
2. Verify: page title "Candidates" visible
3. Verify: subtitle "X total across all jobs" (X ≥ 0)
4. Verify: table columns: Name | Current Title | Company | Location | Job | Score | Status | Email Source
5. Verify: at least 1 candidate row renders
6. Verify: score pills are color-coded (green ≥8, amber 6–7, red <6)
7. Verify: status badges use correct values (discovered / profiled / passed / failed / emailed / applied / tested / interviewed)

### C02 — Search (Debounced)
1. In candidates list, locate search input
2. Type the first name of a known candidate (from module 05 test jobs)
3. Wait 400ms (debounce period)
4. Verify: table updates to show only matching candidates
5. Verify: no full page reload (React Query re-fetch, table updates in place)

### C03 — Clear Search
1. After C02, clear the search input
2. Verify: full candidate list returns

### C04 — Status Filter
1. Open the Status dropdown ("All Statuses")
2. Select "Passed" → verify table shows only `passed` status candidates
3. Select "Emailed" → verify table updates
4. Select "Failed" → verify table updates (or shows empty state)
5. Select "All Statuses" → verify full list returns

### C05 — Score Filter
1. Open Score dropdown ("Any Score")
2. Select "8–10" → verify table shows only candidates with score ≥ 8
3. Select "6–7" → verify score range
4. Select "Below 6" → verify score range
5. Select "Any Score" → verify full list

### C06 — Row Click → Profile
1. Click any candidate row (not on a link within it)
2. Verify: browser navigates to `/en/candidates/{id}`
3. Verify: profile page loads with the candidate's name in the heading

### C07 — Hero Card
1. On candidate profile page:
2. Verify: avatar (initials in colored circle) visible
3. Verify: name (large heading) non-empty
4. Verify: title + company + location displayed
5. Verify: email shown (or "Not found")
6. Verify: top skills (up to 5 cyan tags) present
7. If score exists: verify score card on right with number "/10 Suitability" + status badge
8. If LinkedIn URL exists: verify "↗" link has `href` starting with `https://linkedin.com`

### C08 — AI Score Reasoning Card
1. On candidate profile page (candidate with a score):
2. Verify: "AI Score Reasoning" card present
3. Verify: reasoning text is non-empty prose
4. Verify: "Strengths" column (green) has ≥ 1 bullet with ✓ prefix
5. Verify: "Gaps" column (amber) has ≥ 0 bullets with △ prefix
6. Verify: 2-column grid layout renders correctly

### C09 — LinkedIn Profile Card
1. On candidate profile page:
2. Verify: "LinkedIn Profile" card present
3. Verify: headline (cyan text) non-empty
4. Verify: Current Position (title + company) displayed
5. Verify: About text (if available) displayed
6. Verify: Experience section shows ≥ 1 position (title + company + date range)
7. If education available: verify Education section present
8. Verify: Top Skills (from LinkedIn) shown as tags

### C10 — Outreach Email Card
Pre-condition: Use a candidate who has already received an outreach email.
1. On candidate profile page:
2. Verify: "Outreach Email Sent" card present
3. Verify: timestamp displayed
4. Verify: email content renders in white box (HTML safe-rendered, no raw tags visible)

### C11 — Send Outreach Button
Pre-condition: `EMAIL_TEST_MODE=ON`. Use a candidate who has NOT yet received outreach.
1. On candidate profile page, click "📧 Send Outreach"
2. Verify: button shows "Sending..."
3. Wait for completion (up to 10s)
4. Verify: success state (button text changes or success message)
5. Verify: "Outreach Email Sent" card appears on the page
6. Verify: EMAIL_TEST_MODE redirected email to marcus@aiworkerz.com (check via API or inbox)

### C12 — GDPR Delete Modal — Cancel
1. On candidate profile page, click "🗑 GDPR Delete" in the Actions sidebar
2. Verify: modal opens with title "GDPR Delete Candidate"
3. Verify: modal body contains the candidate's name
4. Verify: message says "This cannot be undone"
5. Verify: two buttons: "Cancel" + "Delete & Anonymise" (red)
6. Click "Cancel" → verify modal closes, candidate page still visible

### C13 — GDPR Delete: Confirm
Pre-condition: Use a disposable test candidate (not a real production candidate).
Create one via the test screener job in module 06 if needed.
1. On the disposable candidate's profile page
2. Click "🗑 GDPR Delete"
3. In modal, click "Delete & Anonymise"
4. Verify: modal closes
5. Verify: browser redirects to `/en/candidates`
6. Verify: the anonymised candidate no longer appears in the list (or name is redacted)
7. Verify: `GET /api/v1/candidates/{id}` returns 404 or anonymised data

### C14 — Opted-Out Candidate
Pre-condition: A candidate with `opted_out=true` (created via unsubscribe test in module 08).
1. Navigate to that candidate's profile page
2. Verify: red banner "⊘ Opted Out" visible at the top
3. Verify: "📧 Send Outreach" button is disabled (greyed out / `disabled` attribute)
4. Verify: rest of profile page renders normally

### C15 — Search Empty State
1. In candidates list, type a search string that matches no candidate (e.g., `xyznotaname`)
2. Wait for debounce
3. Verify: table shows "No candidates found." empty state (not an error)

---

## Verification Matrix

| ID  | Key Assertion |
|-----|---------------|
| C01 | Table with 8 columns, color-coded score pills |
| C02 | Search filters in place (debounced, no page reload) |
| C03 | Clear search restores full list |
| C04 | Status filter updates table for each value |
| C05 | Score filter updates table for each range |
| C06 | Row click → /candidates/{id} |
| C07 | Hero card: name, title, skills, score present |
| C08 | Score reasoning: strengths (✓) + gaps (△) |
| C09 | LinkedIn card: headline, experience, skills |
| C10 | Outreach email card renders HTML email content |
| C11 | Send Outreach succeeds, outreach card appears |
| C12 | GDPR modal opens, cancel closes it without action |
| C13 | Confirm delete → redirect → candidate anonymised |
| C14 | Opted-out banner + Send Outreach button disabled |
| C15 | Empty state rendered for no-match search |
