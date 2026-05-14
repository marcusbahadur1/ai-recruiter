# Manual Test Plan — Production (app.airecruiterz.com)

Last updated: 2026-05-14

**Environment:** Production — https://app.airecruiterz.com
**Super admin:** marcus@aiworkerz.com
**Normal tenant:** marcusbahadur1@gmail.com

Status key: ✅ Pass | ❌ Fail | ⚠️ Pass with note | 🐛 Bug filed | ⬜ Not yet tested

---

## SECTION A — CLIENT PIPELINE (Super Admin)

### A1 — Page Load & Plan Gating

| ID | Test | Status | Notes |
|---|---|---|---|
| CP-01 | Navigate to Client Pipeline in sidebar. All 6 tabs visible (Pipeline, Prospects, Signals, Sequences, Content, Settings). No upgrade wall for super admin. | ✅ | Sidebar item called "Client Pipeline" confirmed |
| CP-02 | No Client Pipeline onboarding banner visible for super admin. | ✅ | "Setup in progress" banner visible is the Quickstart banner — expected, unrelated |
| CP-03 | No amber "LinkedIn not connected" warning bar at top of Client Pipeline page for super admin. | ✅ | |

### A2 — Pipeline Tab

| ID | Test | Status | Notes |
|---|---|---|---|
| CP-04 | Pipeline tab: 5 metric cards render (Prospects Found, Connected, Replied, Demos Booked, Trials Started). All 0 — no errors. | ✅ | |
| CP-05 | Conversion funnel renders with 6 stages (Identified → Trial started). | ✅ | Shows 3 prospects in Identified after cleanup |
| CP-06 | Live Signals section renders (empty state message, no crash). | ✅ | Shows "no unactioned signals" |
| CP-07 | Recent Activity section renders (empty state, no crash). | ✅ | Shows the 3 recently added prospects |
| CP-08 | Active Sequences section renders (empty state, no crash). | ✅ | Shows "no active sequences" |
| CP-09 | No JS console errors on Pipeline tab. | ✅ | |

### A3 — Prospects Tab

| ID | Test | Status | Notes |
|---|---|---|---|
| CP-10 | Prospects tab: empty state renders (not a crash). | ✅ | |
| CP-11 | Add prospect manually: Name="Jane Smith", Company="Acme Recruiting", Title="Head of HR", LinkedIn URL="https://linkedin.com/in/janesmith". Confirm appears with stage `identified`. | ✅ | Gap found & fixed: no manual add existed — added "+ Add manually" modal + POST /prospects backend endpoint + DELETE endpoint |
| CP-12 | Click prospect. Detail view loads (name, company, title, ICP score, outreach log). | ✅ | ICP shows "—" for manual prospects (correct — score only computed via BrightData scrape) |
| CP-13 | Edit prospect stage to `connected`. Save. Stage badge updates. | ✅ | Auto-saves on dropdown change — no save button needed |
| CP-14 | "Enrich Email" with no Hunter key. Graceful error: "Hunter.io API key not configured". Not a 500. | ✅ | Shows "Hunter.io not configured" inline — no crash |
| CP-15 | "Scrape Prospects" with no BrightData key. Graceful: 0 inserted message, not a crash. | ✅ | Shows "Scrape complete — no prospects met the minimum ICP score" |
| CP-16 | Sort by ICP Score Descending. No error. | ✅ | |
| CP-17 | Sort by Date. No error. | ✅ | |
| CP-18 | Sort by Stage. No error. | ✅ | |
| CP-19 | Filter by stage `connected`. Only connected prospects shown. | ✅ | Bug found & fixed: company size inputs overflowed the filter dropdown panel (minWidth: 0 fix deployed) |

### A4 — Signals Tab

| ID | Test | Status | Notes |
|---|---|---|---|
| CP-20 | Signals tab: empty state renders (no crash). | ✅ | |
| CP-21 | If signals exist: Action → Outreach Now. Signal disappears. New prospect created in Prospects tab. | ⬜ | Skipped — no signals yet, revisit when BrightData signal scraping is active |
| CP-22 | If signals exist: Dismiss. Signal disappears (dismissed=true). | ⬜ | Skipped — no signals yet |
| CP-23 | Refresh. Actioned/dismissed signals do NOT reappear. | ⬜ | Skipped — no signals yet |

### A5 — Sequences Tab

| ID | Test | Status | Notes |
|---|---|---|---|
| CP-24 | Sequences tab: empty state renders. | ✅ | |
| CP-25 | Create sequence: Name="Recruitment Agency Outreach", Persona="HR Directors", Angle="ROI". Appears with status `draft`. | 🐛 | Bug found & fixed: sequences router missing super admin plan bypass — returned 403. Fixed _check_plan to match content/prospects routers. |
| CP-26 | Add Step 1: type=linkedin_connect, day=0, message="Hi, I'd love to connect with you about AI in recruitment." Step appears. | ⬜ | |
| CP-27 | Add Step 2: type=wait, day=2. Step appears. | ⬜ | |
| CP-28 | Add Step 3: type=linkedin_dm, day=2, message="Hi {{first_name}}, noticed {{company}} is scaling..." Step appears. | ⬜ | |
| CP-29 | Generate Steps with AI (enter persona + angle). 4 generated templates appear. No crash. | ⬜ | |
| CP-30 | Edit Step 1 message. Save. Reload. Edit persisted. | ⬜ | |
| CP-31 | Delete Step 2 (wait step). Disappears. | ⬜ | |
| CP-32 | Change sequence status to `live`. Badge shows "Live". | ⬜ | |
| CP-33 | Change sequence status to `paused`. Badge shows "Paused". | ⬜ | |
| CP-34 | Enroll prospect from CP-11. enrolled_count increments to 1. | ⬜ | |
| CP-35 | Re-enroll same prospect. "Already enrolled" response — no duplicate. | ⬜ | |
| CP-36 | View sequence stats. 0 sent/replied (expected). | ⬜ | |
| CP-37 | Delete sequence. Removed from list. | ⬜ | |

### A6 — Content Tab

| ID | Test | Status | Notes |
|---|---|---|---|
| CP-38 | Content tab: empty state renders (no crash). | ⬜ | |
| CP-39 | Generate Post with no LinkedIn account. Error: "No active LinkedIn account connected". Not a 500. | ⬜ | |
| CP-40 | Content Stats: avg_views, mix, upcoming render at zero — no crash. | ⬜ | |

### A7 — Settings Tab

| ID | Test | Status | Notes |
|---|---|---|---|
| CP-41 | Settings tab: ICP Config, Channel Config, Signal Config, Outreach Limits sections all render. | ⬜ | |
| CP-42 | Add target title "Head of HR" (tag input). Save. Reload. Tag persists. | ⬜ | |
| CP-43 | Add company type "Recruitment Agency". Save. Reload. Persists. | ⬜ | |
| CP-44 | Set ICP min score to 6. Save. Reload. Value is 6. | ⬜ | |
| CP-45 | Set linkedin_connects_per_day to 15. Save. Reload. Persists. | ⬜ | |
| CP-46 | Toggle skip_weekends off. Save. Reload. Off state persists. | ⬜ | |
| CP-47 | Disable monitor_pain_posts. Save. Reload. Persists. | ⬜ | |
| CP-48 | LinkedIn OAuth "Connect Account" button visible in Channel Config. | ⬜ | |
| CP-49 | (Super admin) Tenant Mode section visible with toggle and fields. | ⬜ | |
| CP-50 | (Super admin) Enable Tenant Mode. Set max_prospects_per_month=500, max_sequences=3. Save. Reload. Saved. | ⬜ | |

### A8 — Plan Gating (Normal Tenant)

| ID | Test | Status | Notes |
|---|---|---|---|
| CP-51 | Log in as marcusbahadur1@gmail.com. Navigate to Client Pipeline. Upgrade wall appears — tabs NOT accessible. | ⬜ | |
| CP-52 | Log back in as super admin. Pipeline tabs still fully accessible. | ⬜ | |

---

## SECTION B — SUPER ADMIN FULL APPLICATION

*Logged in as marcus@aiworkerz.com*

### B1 — Auth & Navigation

| ID | Test | Status | Notes |
|---|---|---|---|
| SA-01 | Navigate to https://app.airecruiterz.com. Redirects to /en/login. | ⬜ | |
| SA-02 | Log in. Redirects to /en dashboard. | ⬜ | |
| SA-03 | Sidebar contains all links: Dashboard, Chat, Jobs, Candidates, Applications, Client Pipeline, Settings, Billing, Super Admin. | ⬜ | |
| SA-04 | Click each sidebar link. No 404, blank page, or 500. | ⬜ | |

### B2 — Dashboard

| ID | Test | Status | Notes |
|---|---|---|---|
| SA-05 | Dashboard stat cards visible (jobs, candidates, applications, credits). | ⬜ | |
| SA-06 | Kanban board renders. | ⬜ | |
| SA-07 | Recent Activity feed renders. | ⬜ | |
| SA-08 | Candidate Pipeline funnel renders. | ⬜ | |

### B3 — Chat & Job Creation

| ID | Test | Status | Notes |
|---|---|---|---|
| SA-09 | Navigate to Chat. Session list renders. | ⬜ | |
| SA-10 | Start new chat. Type "I need to hire a senior Python developer in Sydney". AI responds. | ⬜ | |
| SA-11 | Answer 3–4 questions. Streaming works (text appears progressively, no timeout). | ⬜ | |
| SA-12 | Navigate to Chat History. New session appears. | ⬜ | |

### B4 — Jobs

| ID | Test | Status | Notes |
|---|---|---|---|
| SA-13 | Navigate to Jobs. Job list renders. | ⬜ | |
| SA-14 | Click job JIYVD3NU (Senior Java Developer). Detail page loads. | ⬜ | |
| SA-15 | All job tabs load: Overview, Candidates, Audit Trail. No blank pages. | ⬜ | |
| SA-16 | Audit Trail shows events (not empty/erroring). | ⬜ | |

### B5 — Candidates

| ID | Test | Status | Notes |
|---|---|---|---|
| SA-17 | Navigate to Candidates. List renders. | ⬜ | |
| SA-18 | Click a candidate. Detail page loads with profile data. | ⬜ | |
| SA-19 | Stage/status badges render correctly. | ⬜ | |

### B6 — Applications

| ID | Test | Status | Notes |
|---|---|---|---|
| SA-20 | Navigate to Applications. List renders. | ⬜ | |
| SA-21 | Click an application. Detail/workflow page loads. | ⬜ | |

### B7 — Settings

| ID | Test | Status | Notes |
|---|---|---|---|
| SA-22 | Navigate to Settings. Tabs render (AI Recruiter, Knowledge Base). | ⬜ | |
| SA-23 | AI Recruiter settings: form fields load with current values. | ⬜ | |
| SA-24 | Knowledge Base settings: file upload UI renders. | ⬜ | |

### B8 — Billing

| ID | Test | Status | Notes |
|---|---|---|---|
| SA-25 | Navigate to Billing. Current plan displayed. | ⬜ | |
| SA-26 | Plan cards and upgrade options render. | ⬜ | |

### B9 — Super Admin Panel

| ID | Test | Status | Notes |
|---|---|---|---|
| SA-27 | Super Admin stats page loads (total tenants, jobs, candidates, applications). | ⬜ | |
| SA-28 | Super Admin → Tenants. Tenant list renders with plan badges. | ⬜ | |
| SA-29 | Click/expand a tenant row. Tenant details visible. | ⬜ | |
| SA-30 | Super Admin → Marketing. Per-tenant marketing table renders. marcusbahadur1@gmail.com tenant listed. | ⬜ | |
| SA-31 | Expand normal tenant row. LinkedIn accounts shown (empty OK). | ⬜ | |
| SA-32 | "Not eligible" shown for any tenant below agency_small. | ⬜ | |

---

## SECTION C — NORMAL TENANT FULL APPLICATION

*Logged in as marcusbahadur1@gmail.com*

### C1 — Auth & Navigation

| ID | Test | Status | Notes |
|---|---|---|---|
| NT-01 | Log in at https://app.airecruiterz.com with marcusbahadur1@gmail.com. | ⬜ | |
| NT-02 | Redirects to /en dashboard (not /en/dashboard). | ⬜ | |
| NT-03 | Sidebar does NOT contain "Super Admin" link. | ⬜ | |
| NT-04 | Click each sidebar link. No 404, blank page, or 500. | ⬜ | |
| NT-05 | Log out. Redirect to login. Accessing /en unauthenticated redirects to login. | ⬜ | |

### C2 — Dashboard

| ID | Test | Status | Notes |
|---|---|---|---|
| NT-06 | Dashboard stat cards render (0 values OK for fresh account). | ⬜ | |
| NT-07 | Kanban board renders (empty state OK). | ⬜ | |

### C3 — Chat & Job Creation

| ID | Test | Status | Notes |
|---|---|---|---|
| NT-08 | Navigate to Chat. Empty history (fresh account). | ⬜ | |
| NT-09 | Start new chat. Type "I want to hire a marketing manager". AI responds. | ⬜ | |
| NT-10 | Answer 3–4 questions. Streaming works. | ⬜ | |
| NT-11 | Chat History. New session listed. | ⬜ | |

### C4 — Jobs

| ID | Test | Status | Notes |
|---|---|---|---|
| NT-12 | Navigate to Jobs. List renders (empty OK for fresh account). | ⬜ | |
| NT-13 | If a job exists, click it. Job detail page loads with all tabs. | ⬜ | |

### C5 — Candidates

| ID | Test | Status | Notes |
|---|---|---|---|
| NT-14 | Navigate to Candidates. List renders (empty OK). | ⬜ | |
| NT-15 | No cross-tenant data — must NOT see marcus@aiworkerz.com's candidates. | ⬜ | |

### C6 — Applications

| ID | Test | Status | Notes |
|---|---|---|---|
| NT-16 | Navigate to Applications. List renders (empty OK). | ⬜ | |
| NT-17 | No cross-tenant data leakage. | ⬜ | |

### C7 — Settings

| ID | Test | Status | Notes |
|---|---|---|---|
| NT-18 | Navigate to Settings. AI Recruiter and Knowledge Base tabs load. | ⬜ | |
| NT-19 | Settings form loads without errors (empty defaults OK). | ⬜ | |

### C8 — Billing

| ID | Test | Status | Notes |
|---|---|---|---|
| NT-20 | Navigate to Billing. Current plan shown. | ⬜ | |
| NT-21 | Upgrade options visible. | ⬜ | |
| NT-22 | Click an upgrade plan. Stripe checkout loads. (Do NOT complete payment.) | ⬜ | |

### C9 — Client Pipeline Plan Gate

| ID | Test | Status | Notes |
|---|---|---|---|
| NT-23 | Click Client Pipeline. Upgrade prompt / plan gate shown. Tabs NOT accessible. | ⬜ | |
| NT-24 | Upgrade prompt names the required plan (agency_small or above). | ⬜ | |

### C10 — Security

| ID | Test | Status | Notes |
|---|---|---|---|
| NT-25 | While logged in as normal tenant, navigate to /en/super-admin. Gets 403 or redirect — NOT the super admin panel. | ⬜ | |

---

## Bug Log

| ID | Area | What happened | Expected | Status |
|---|---|---|---|---|
| | | | | |
