# Module 06 — Job Management & Dashboard Test Plan
Version: 1.0 | Date: 2026-05-01
Target: https://app.airecruiterz.com
Automation: Full (all tests automated unless marked [MANUAL])

---

## Scope

Home dashboard (stat cards, Kanban, activity feed, pipeline funnel), Quick Start banner,
Jobs list (filters, table), New Job mode selection, Screener job 3-stage creation,
Job Detail (all tabs: Evaluation Report, Audit Trail, Job Spec, Applications,
Application Instructions), Pause/Re-run Scout, Export CSV, SSE live updates, Help page.

## Pre-conditions

- Logged in as test tenant
- At least 1 job in `recruitment` phase exists (created in module 05)
- At least 1 screener job exists (created in this module — JB10 creates it)
- At least 1 candidate exists in that job's pipeline

---

## Test Scenarios

| ID   | Name | Automated |
|------|------|-----------|
| JB01 | Home dashboard — stat cards load with non-negative values | Yes |
| JB02 | Home dashboard — Kanban board renders, "All Jobs" default selector | Yes |
| JB03 | Home dashboard — Kanban filter by specific job | Yes |
| JB04 | Home dashboard — Kanban candidate card → links to candidate profile | Yes |
| JB05 | Home dashboard — Activity feed loads, severity icons correct | Yes |
| JB06 | Home dashboard — Pipeline funnel renders all 8 stages | Yes |
| JB07 | Home dashboard — Quick Start banner links to /quickstart | Yes |
| JB08 | Home dashboard — Active Jobs table links to job detail | Yes |
| JB09 | Jobs list — All/Active/Paused/Closed filter buttons | Yes |
| JB10 | Jobs list — View button → job detail | Yes |
| JB11 | New Job page — mode selection cards visible and clickable | Yes |
| JB12 | Screener job — Stage 1 Paste tab: extract JD → Stage 2 preview | Yes |
| JB13 | Screener job — Stage 1 URL tab: extract from URL → Stage 2 preview | Yes |
| JB14 | Screener job — Stage 2 edit form: all fields editable, create job | Yes |
| JB15 | Screener job — Stage 3 success: copy instructions + copy post text | Yes |
| JB16 | Screener job — Stage 3: View Job button → job detail | Yes |
| JB17 | Job detail — Evaluation Report tab: stat cards, filters, candidate rows | Yes |
| JB18 | Job detail — Evaluation Report: Export CSV | Yes |
| JB19 | Job detail — Evaluation Report: SSE live stream badge | Yes |
| JB20 | Job detail — Audit Trail tab: filters, expand event, export CSV | Yes |
| JB21 | Job detail — Audit Trail: SSE live stream (events appear) | Yes |
| JB22 | Job detail — Job Spec tab: all fields displayed | Yes |
| JB23 | Job detail — Pause button: status changes to Paused | Yes |
| JB24 | Job detail — Re-run Scout: button triggers scout, audit event appears | Yes |
| JB25 | Job detail (screener) — Applications tab renders | Yes |
| JB26 | Job detail (screener) — Application Instructions tab: copy buttons | Yes |
| JB27 | Help page — all 8 sections load | Yes |
| JB28 | Help page — search returns relevant results | Yes |

---

## Scenario Detail

### JB01 — Stat Cards
1. Navigate to `/en`
2. Verify: 4 stat cards visible (Active Jobs, Candidates Today, Applications, Credits Remaining)
3. Verify: each card shows a non-negative integer
4. Verify: no spinner stuck (cards settle within 5s)

### JB02–JB04 — Kanban Board
1. Locate Kanban board on dashboard
2. Verify: column selector dropdown shows "All Jobs" by default
3. Verify: at least 5 columns visible: NEW | SCREENED | INTERVIEWED | OFFERED | HIRED
4. JB03: Open dropdown, select a specific job → verify cards update to show only that job's candidates
5. JB04: Click a candidate card → verify navigation to `/en/candidates/{id}`

### JB05 — Activity Feed
1. Locate Activity Feed section on dashboard
2. Verify: heading "Recent Activity" visible with live green dot
3. Verify: at least 1 event row renders
4. For each visible event: verify severity icon is one of ✓ / ✕ / ! / i
5. Verify: timestamps are present

### JB06 — Pipeline Funnel
1. Locate Pipeline Funnel section on dashboard
2. Verify: 8 stage labels visible:
   Discovered | Profiled | Scored | Passed | Emailed | Applied | Tested | Invited
3. Verify: each stage shows a numeric count (0 or above)

### JB07 — Quick Start Banner
1. If Quick Start is incomplete: verify banner "X/Y steps complete" + "Continue Setup →" button
2. Click "Continue Setup →"
3. Verify: navigates to `/en/quickstart`

### JB08 — Active Jobs Table
1. Locate Active Jobs table on dashboard
2. Verify: table has columns: Job | Candidates | Status
3. Verify: clicking a row navigates to `/en/jobs/{id}`
4. Verify: "View all" link navigates to `/en/jobs`

### JB09 — Jobs List Filters
1. Navigate to `/en/jobs`
2. Verify: 4 filter buttons: All | Active | Paused | Closed
3. Click "Active" — verify only Active-status rows shown (or empty state)
4. Click "Paused" — verify only Paused rows shown
5. Click "Closed" — verify only Closed rows shown
6. Click "All" — verify all rows return
7. Verify: active filter button has cyan background

### JB10 — Jobs List View Button
1. Navigate to `/en/jobs`
2. Click "View" button on any job row (stops row-click propagation)
3. Verify: navigates to `/en/jobs/{id}`

### JB11 — New Job Mode Selection
1. Navigate to `/en/jobs/new`
2. Verify: 2 cards visible:
   - "AI Talent Scout + Resume Screener" with "Start with AI Scout →" button
   - "Resume Screener Only" with "Screener Only →" button
3. Click "Start with AI Scout →" → verify navigates to `/en/chat`
4. Go back, click "Screener Only →" → verify navigates to `/en/jobs/new/screener`

### JB12 — Screener Job: Paste Extraction
1. Navigate to `/en/jobs/new/screener`
2. Verify: Stage 1, Paste tab active by default
3. Paste this JD:
   ```
   [TEST] Senior Python Developer — Sydney, hybrid 3 days.
   5+ years Python, FastAPI, PostgreSQL. Salary $150k–$180k AUD.
   Hiring manager: Marcus Bahadur, marcus@aiworkerz.com. Min score 7.
   ```
4. Click "Extract Job Details →"
5. Verify: button shows "Extracting job details..." during call
6. Verify: Stage 2 preview loads with extracted fields
7. Verify: title field contains "Python Developer" (non-empty)

### JB13 — Screener Job: URL Extraction
1. Navigate to `/en/jobs/new/screener`
2. Click "🔗 Job URL" tab
3. Enter a publicly accessible job URL (use a fixture URL from `e2e/fixtures/`)
4. Click "Extract from URL →"
5. Verify: Stage 2 preview loads with extracted fields
Note: If URL fetch fails in test environment, this is an ENV_SKIP.

### JB14 — Screener Job: Edit Form + Create
1. In Stage 2 (after JB12):
2. Verify all editable fields present: Job Title, Job Type (dropdown), Work Type (dropdown),
   Location, Salary Min/Max, Exp. Years, Required Skills (tag input), Tech Stack,
   Job Description, Min Score (slider), Interview Questions Count, Assessment Format (dropdown)
3. Edit Job Title → prepend "[TEST] " if not already present
4. Add skill tag: type "pytest", press Enter → tag appears
5. Remove a skill tag: click × → tag removed
6. Adjust Min Score slider to 6
7. Change Assessment Format to "Audio recording"
8. Click "Create Job →"
9. Verify: button shows "Creating Job..." during call
10. Verify: Stage 3 success screen loads

### JB15 — Screener Job: Copy Buttons
1. In Stage 3 success screen:
2. Verify: "📋 Copy Instructions" button present over instructions code block
3. Click it — verify text changes to "✓ Copied!" and clipboard contains instruction text
4. Verify: "📋 Copy Post Text" button present over post text block
5. Click it — verify "✓ Copied!" and clipboard contains post template

### JB16 — Screener Job: View Job Button
1. In Stage 3 success screen:
2. Click "View Job →"
3. Verify: navigates to `/en/jobs/{new_job_id}`
4. Verify: job detail page loads with correct title

### JB17 — Evaluation Report Tab
1. Navigate to `/en/jobs/{id}` for a Scout job with candidates
2. Click "📊 Evaluation Report" tab
3. Verify: 4 mini stat cards: Discovered | Passed | Emailed | Applied
4. Verify: status filter dropdown has options: All | Passed | Emailed | Failed
5. Select "Passed" → table filters to passed candidates only
6. Verify: candidate rows show Name, Title, Location, Score, Status, Email, Mailed, Summary, LinkedIn
7. Click a candidate row → verify navigates to `/en/candidates/{id}`
8. Click "View" link (cyan) → same navigation
9. If LinkedIn URL exists, verify "↗" link has correct href attribute

### JB18 — Export CSV (Evaluation Report)
1. In Evaluation Report tab, click "↓ Export CSV"
2. Verify: file download is initiated (Playwright download event)
3. Verify: downloaded filename contains "evaluation" or similar

### JB19 — SSE Live Stream (Evaluation Report)
1. In Evaluation Report tab, verify: green live badge visible
2. Monitor for a new candidate appearing without page reload (if scout is active)
   Note: If no active scout, just verify badge renders and SSE connection established (no WS error in console)

### JB20 — Audit Trail Tab
1. Navigate to `/en/jobs/{id}`, click "🔍 Audit Trail" tab
2. Verify: event count label renders
3. Verify: category filter dropdown: All | Talent Scout | Resume Screener | System
4. Verify: severity filter: All | Errors only | Warnings+
5. Select "Talent Scout" category → verify results filter
6. Click an event row expand arrow
7. Verify: detail JSON or text expands beneath the row
8. Click again → detail collapses
9. Click "↓ Export CSV" → verify download initiated

### JB22 — Job Spec Tab
1. Navigate to job detail, click "📋 Job Spec" tab
2. Verify all fields displayed: Job Title, Location, Work Type, Experience, Salary Range,
   Min. Score, Required Skills (tags), Hiring Manager, Job Reference (monospace), Description
3. Verify: Salary Range shows formatted currency (not raw numbers)
4. Verify: Job Reference is monospace font

### JB23 — Pause Job
1. Navigate to Scout job detail
2. Note current status badge (should be "Active")
3. Click "⏸ Pause"
4. Verify: status badge changes to "Paused"
5. Verify: button changes to "▶ Resume" or equivalent
6. Resume the job (click Resume) — verify status returns to Active

### JB24 — Re-run Scout
1. Navigate to Scout job detail (Active status)
2. Click "▶ Re-run Scout"
3. Verify: audit trail tab receives a new event within 30s (or SSE fires)
4. Verify: no error banner

### JB25 — Applications Tab (Screener Job)
1. Navigate to the screener job created in JB14
2. Verify: "📥 Applications" tab is present (not shown for Scout jobs)
3. Click the tab
4. Verify: table renders with columns: Name | Email | Resume Score | Status | Applied
5. Verify: empty state if no applications yet

### JB26 — Application Instructions Tab
1. In screener job detail, click "📨 Application Instructions" tab
2. Verify: instruction text code block rendered (dark background)
3. Click "📋 Copy Instructions" → verify "✓ Copied!" + clipboard contains text
4. Verify: suggested post text block rendered
5. Click "📋 Copy Post Text" → verify "✓ Copied!"

### JB27 — Help Page Sections
1. Navigate to `/en/help`
2. Verify: left sidebar has 8 buttons:
   Platform Overview | Getting Started | Talent Scout Pipeline |
   Resume Screener Pipeline | Settings & Configuration |
   Plans & Billing | GDPR & Compliance | Troubleshooting
3. Click each button in sequence → verify right panel content changes and is non-empty
4. Verify: active button has cyan background

### JB28 — Help Page Search
1. Navigate to `/en/help`
2. Type "screener" in the search input
3. Verify: results panel updates to show matching content sections
4. Verify: results are relevant (contain word "screener" or related terms)
5. Clear search → verify all 8 sections return to default view
6. Type a nonsense string ("xyzabc123") → verify "No results" message

---

## Verification Matrix

| ID    | Key Assertion |
|-------|---------------|
| JB01  | 4 stat cards, non-negative integers |
| JB02  | Kanban renders 5 columns |
| JB03  | Job filter updates Kanban cards |
| JB04  | Candidate card links to /candidates/{id} |
| JB05  | Activity feed events with severity icons |
| JB06  | 8-stage pipeline funnel visible |
| JB07  | Quick Start banner → /quickstart |
| JB08  | Active jobs table rows → /jobs/{id} |
| JB09  | Filter buttons update table, active = cyan |
| JB10  | View button → job detail |
| JB11  | 2 mode cards, correct navigation |
| JB12  | JD paste → Stage 2 with extracted title |
| JB13  | URL extraction → Stage 2 (or ENV_SKIP) |
| JB14  | All form fields editable, job created |
| JB15  | Both copy buttons work + clipboard |
| JB16  | View Job → /jobs/{id} |
| JB17  | Eval report tab: stats, filter, rows, links |
| JB18  | CSV download initiated |
| JB19  | Live badge renders, no SSE errors |
| JB20  | Audit filters work, event expands, CSV download |
| JB22  | All Job Spec fields rendered |
| JB23  | Pause toggles status badge |
| JB24  | Re-run Scout triggers audit event |
| JB25  | Applications tab visible on screener jobs only |
| JB26  | Both copy buttons on Application Instructions work |
| JB27  | All 8 help sections load with content |
| JB28  | Search filters results, no-results handled |
