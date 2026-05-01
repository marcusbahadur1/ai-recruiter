# Module 09 — Marketing Module Test Plan
Version: 1.0 | Date: 2026-05-01
Target: https://app.airecruiterz.com
Automation: Full (LinkedIn OAuth bypassed via database seed using Supabase service role key)

---

## Scope

Marketing dashboard: LinkedIn accounts (connect/disconnect), Posts management
(Draft/Scheduled/Posted/Failed tabs, create, generate with AI, approve, reject),
Analytics summary, LinkedIn page selection. Super Admin marketing analytics.

## Pre-conditions

- Logged in as test tenant on Agency Small or above (marketing module requires it)
- `EMAIL_TEST_MODE=ON` (any notification emails)
- LinkedIn account seeded before running M03–M11 (M02 seeds it automatically via DB)

---

## Test Scenarios

| ID   | Name | Automated |
|------|------|-----------|
| M01  | Marketing page loads — LinkedIn section visible | Yes |
| M02  | Connect LinkedIn account — OAuth flow (DB seed) | Yes |
| M03  | LinkedIn page selection — /marketing/linkedin/select-page | Yes |
| M04  | Disconnect LinkedIn account | Yes |
| M05  | Posts list — all 4 tabs render (Draft/Scheduled/Posted/Failed) | Yes |
| M06  | Posts list — tab switch updates content | Yes |
| M07  | Create post form — fill fields, save as draft | Yes |
| M08  | Generate post with AI — button triggers generation | Yes |
| M09  | Approve post — post moves from Draft to Scheduled tab | Yes |
| M10  | Reject post — post removed from Draft tab | Yes |
| M11  | Analytics summary — engagement metrics visible | Yes |
| M12  | Plan gate — marketing page blocked on Recruiter plan | Yes |

---

## Scenario Detail

### M01 — Marketing Page Loads
1. Navigate to `/en/marketing`
2. Verify: page loads without 404/500
3. Verify: "LinkedIn Accounts" or equivalent section heading visible
4. Verify: "Connect Account" button present (if no account connected)
5. Verify: posts section visible below LinkedIn accounts

### M02 — Connect LinkedIn Account (DB Seed)
Mock approach: LinkedIn's OAuth requires user consent on linkedin.com which actively
detects automation. Instead of attempting to drive the OAuth UI, we seed a fake but
structurally valid LinkedIn account row directly into the database using the Supabase
service role key — bypassing OAuth entirely. This allows all downstream tests
(M03–M11) to run against a real connected account record.

```js
// Test setup helper — runs before M02 assertions
const { createClient } = require('@supabase/supabase-js')
const admin = createClient(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

await admin.from('marketing_accounts').insert({
  tenant_id: TEST_TENANT_ID,
  platform: 'linkedin',
  account_name: 'Test LinkedIn Account',
  account_id: 'test-li-account-001',
  access_token: 'mock-access-token',   // will fail on actual LinkedIn API calls — see note
  refresh_token: 'mock-refresh-token',
  token_expires_at: new Date(Date.now() + 3600000).toISOString(),
  is_active: true
})
```

**Note:** The seeded access token is fake. Tests that verify the UI connected state
(M02–M06) will pass. Tests that attempt to actually post to LinkedIn (M09 Approve) only
verify the draft→scheduled transition in our database — they do not assert that LinkedIn's
API was called successfully, since that would require a real token.

Steps (verify the seed worked):
1. Navigate to `/en/marketing`
2. Verify: "Test LinkedIn Account" appears in the LinkedIn accounts section (not "Connect Account")
3. Verify: account status shows connected / active
4. Verify: "Connect Account" primary button is no longer the only option

### M03 — LinkedIn Page Selection
Pre-condition: LinkedIn account connected (via M02 or pre-existing).
1. Navigate to `/en/marketing/linkedin/select-page`
2. Verify: page renders with account/page selection UI
3. Verify: dropdown or list shows available LinkedIn pages/profiles
4. Select a page
5. Verify: selection is saved and reflected back on the marketing page

### M04 — Disconnect LinkedIn Account
Pre-condition: LinkedIn account connected (via M02 or pre-existing).
1. On marketing page, locate connected account entry
2. Click "Disconnect" button
3. Verify: confirmation prompt handled (if any)
4. Verify: account removed from the accounts list
5. Verify: "Connect Account" button reappears

### M05 — Posts Tabs Render
1. Navigate to `/en/marketing`
2. Locate posts section
3. Verify: 4 tabs visible — Draft | Scheduled | Posted | Failed
4. Verify: each tab has a label and is clickable

### M06 — Tab Switch
1. Click "Scheduled" tab
2. Verify: content area updates (shows scheduled posts or empty state)
3. Click "Posted" tab → verify updates
4. Click "Failed" tab → verify updates
5. Click "Draft" tab → verify returns to draft content
6. Verify: active tab has visual indicator (bold/underline/background)

### M07 — Create Post: Save as Draft
1. Locate "Create Post" button or form on marketing page
2. Click to open the create post form/modal
3. Fill in post content text field (≥ 10 chars)
4. Select target LinkedIn account/page (if required)
5. Choose schedule: "Save as Draft" (not scheduled)
6. Click "Save" / "Create"
7. Verify: post appears in "Draft" tab
8. Verify: post content visible in the draft row

### M08 — Generate Post with AI
1. Open create post form
2. Click "Generate with AI" button (or equivalent)
3. Verify: loading state during generation
4. Verify: textarea populates with AI-generated post content (non-empty)
5. Verify: content is editable after generation
6. Save as draft to complete

### M09 — Approve Post
Pre-condition: At least 1 post in Draft tab (from M07 or M08).
1. In "Draft" tab, locate a draft post
2. Click "Approve" button for that post
3. Verify: post disappears from Draft tab
4. Click "Scheduled" tab
5. Verify: the approved post appears in Scheduled

### M10 — Reject Post
Pre-condition: At least 1 post in Draft tab.
1. In "Draft" tab, locate a draft post
2. Click "Reject" button
3. Verify: post is removed from Draft tab
4. Verify: post does not appear in Scheduled
5. Verify: total draft count decremented

### M11 — Analytics Summary
1. On marketing page, locate analytics/engagement summary section
2. Verify: section renders with engagement metrics visible (impressions, clicks, etc.)
3. Verify: numbers are non-negative integers or "—" for no data
4. Verify: no loading spinner stuck

### M12 — Plan Gate
Pre-condition: Use a tenant on the Recruiter plan (no marketing access).
1. Navigate to `/en/marketing`
2. Verify: page shows an upgrade/plan gate notice rather than the full dashboard
   OR: API returns 403 and the page renders an appropriate error state
3. Verify: upgrade CTA or message is displayed

---

## Verification Matrix

| ID  | Key Assertion |
|-----|---------------|
| M01 | Marketing page loads, LinkedIn section + Connect button visible |
| M02 | DB seed inserts account row → UI shows connected account |
| M03 | Page selection UI loads, selection saves |
| M04 | Disconnect removes account, Connect button returns |
| M05 | 4 tabs visible and labelled correctly |
| M06 | Tab switch updates content area, active tab highlighted |
| M07 | Post saved in Draft tab with correct content |
| M08 | AI generation populates textarea |
| M09 | Approved post moves Draft → Scheduled |
| M10 | Rejected post removed from Draft |
| M11 | Analytics section renders with metrics |
| M12 | Plan gate shown for ineligible tenant |

---

## Known Limitations

- M02 uses a DB-seeded fake account. The access token is invalid for real LinkedIn API
  calls, but all UI state tests pass.
- M09 (Approve) results in an attempt to post to LinkedIn. In test environments, this
  may fail if the LinkedIn account is not a real page. Verify the draft→scheduled
  transition only (do not check that LinkedIn API was actually called).
- M08 (AI generation) uses live Claude API — response is non-deterministic. Retry once
  if the generated text is empty or an error occurs.
