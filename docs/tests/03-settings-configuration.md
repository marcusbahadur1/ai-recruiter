# Module 03 — Settings & Configuration Test Plan
Version: 1.0 | Date: 2026-05-01
Target: https://app.airecruiterz.com
Automation: Full (all tests automated unless marked [MANUAL])

---

## Scope

All 9 settings sections: General, API Keys, AI Provider, Email & Mailbox, Knowledge Base
(link only — full tests in module 04), Chat Widget (link only — full tests in module 04),
Team Members, Billing (link only — tested in module 02), Privacy & Data.
Also covers the standalone AI Recruiter Prompt page.

## Pre-conditions

- Logged in as test tenant
- Settings nav is accessible (sidebar visible)

---

## Test Scenarios

| ID   | Name | Automated |
|------|------|-----------|
| S01  | Settings page loads — left nav has 9 items, default section is General | Yes |
| S02  | General — update all 6 fields, save, reload, verify persisted | Yes |
| S03  | API Keys — edit each of 6 service key rows, save, verify status indicator updates | Yes |
| S04  | AI Provider — toggle Anthropic ↔ OpenAI, verify card selection state | Yes |
| S05  | AI Provider — search provider dropdown (ScrapingDog / BrightData / Both) | Yes |
| S06  | Email & Mailbox — fill IMAP fields, save, verify no error | Yes |
| S07  | Team Members — invite new member, verify pending badge in member list | Yes |
| S08  | Team Members — remove member, verify removed from list | Yes |
| S09  | Privacy & Data — DPA not accepted: button shows "View & Accept", modal opens | Yes |
| S10  | Privacy & Data — accept DPA: scroll content, tick checkbox, click Accept, verify accepted date | Yes |
| S11  | Privacy & Data — data retention dropdown: change value, verify saved status | Yes |
| S12  | Privacy & Data — Export My Data: button click → download starts | Yes |
| S13  | Privacy & Data — Delete All Data: modal, type DELETE to enable confirm button | Yes |
| S14  | AI Recruiter Prompt — edit prompt text, save, verify persisted | Yes |
| S15  | AI Recruiter Prompt — reset to default, verify prompt reverts | Yes |
| S16  | Left nav — click each of the 9 sections, verify correct content loads | Yes |

---

## Scenario Detail

### S01 — Settings Page Loads
1. Navigate to `/en/settings`
2. Verify: left sidebar visible with items:
   General | API Keys | AI Provider | Email & Mailbox | Knowledge Base |
   Chat Widget | Team Members | Billing | Privacy & Data
3. Verify: default section is "General" (Firm Profile card visible)
4. Verify: no 404/500

### S02 — General Section
1. Click "General" in left nav
2. Fill all 6 fields: Firm Name, Phone, Main Contact Name, Contact Email, Address, Website
3. Click "Save"
4. Verify: success status message appears
5. Reload page, navigate back to General
6. Verify: all 6 values persisted (match what was entered)

**Assertions:**
- `settingsApi.updateTenant(data)` called on save
- API returns 200

### S03 — API Keys Section
1. Click "API Keys" in left nav
2. Verify: 6 rows visible (BrightData, Apollo.io, Hunter.io, Snov.io, SendGrid, AI Provider Key)
3. For each row:
   a. Verify "⚠ Not configured" status (or "✓ Configured" if already set)
   b. Click "Edit"
   c. Type a dummy key string (e.g., `test-key-XXXXX`)
   d. Save the row
   e. Verify status indicator changes to "✓ Configured"
4. Verify no console errors during save

### S04 — AI Provider Toggle
1. Click "AI Provider" in left nav
2. Verify: 2 cards visible — Anthropic Claude and OpenAI
3. Click the OpenAI card
4. Verify: OpenAI card shows "Selected" badge, Anthropic shows "Not selected"
5. Click Anthropic card
6. Verify: Anthropic card shows "Selected" again
7. Save (if there's a save action)

### S05 — Search Provider Dropdown
1. In "AI Provider" section, locate Search Provider dropdown
2. Verify: 3 options exist — ScrapingDog | BrightData | Both
3. Select each option, verify selection updates
4. Save, reload, verify selection persisted

### S06 — Email & Mailbox
1. Click "Email & Mailbox" in left nav
2. Fill: Jobs Email Address, IMAP Host (`mail.test.com`), IMAP Username, Port (`993`),
   IMAP Password (`TestPassword123`)
3. Save
4. Verify: success message appears
5. Reload, verify fields retain values

### S07 — Team Members — Invite
1. Click "Team Members" in left nav
2. Fill invite form: email (unique test alias), Role = "Recruiter"
3. Click "Send Invite"
4. Verify: loading state "Inviting…" appears
5. Verify: new member appears in member list with "pending" status badge
6. Verify: role shown as "Recruiter"

### S08 — Team Members — Remove
1. In "Team Members" section, locate the member added in S07
2. Click "Remove" button for that member
3. Verify: member disappears from list
4. Verify: member count decremented

### S09 — Privacy & Data — DPA Not Accepted
1. Click "Privacy & Data" in left nav
2. Locate Data Processing Agreement card
3. If DPA not yet accepted: verify status "Not yet accepted" + "View & Accept DPA" button
4. Click "View & Accept DPA"
5. Verify: modal opens with DPA text content
6. Verify: scrollable content visible (monospace dark background)
7. Verify: "Accept DPA" button is disabled until checkbox is ticked

### S10 — Privacy & Data — Accept DPA
1. In DPA modal (from S09):
2. Scroll to bottom of DPA content
3. Tick checkbox "I have read and agree to the DPA"
4. Verify: "Accept DPA" button becomes enabled
5. Click "Accept DPA"
6. Verify: modal closes
7. Verify: status now shows "✓ Accepted on [today's date]" in green
8. Verify: "View DPA" button (read-only) is present

### S11 — Data Retention Dropdown
1. In "Privacy & Data" section, locate Data Retention card
2. Verify: dropdown shows current value (default 12 months)
3. Change to 6 months
4. Verify: "✓ Saved" status appears
5. Reload, verify dropdown still shows 6 months

### S12 — Export My Data
1. In "Privacy & Data" section, click "Export My Data"
2. Verify: loading state "Preparing…" appears
3. Verify: "✓ Download started" success message appears
4. Verify: a JSON file download is initiated (Playwright intercepts download event)

### S13 — Delete All Data Modal
1. In "Privacy & Data" section, click "Delete All My Data"
2. Verify: confirmation modal opens with warning message
3. Verify: "Confirm Delete" button is disabled initially
4. Type any text other than "DELETE" — verify button stays disabled
5. Clear and type exactly "DELETE"
6. Verify: "Confirm Delete" button becomes enabled
7. Click "Cancel" — verify modal closes without action
   (Do NOT actually confirm deletion on the main test account)

### S14 — AI Recruiter Prompt Edit
1. Navigate to `/en/settings/ai-recruiter`
2. Verify: prompt editor textarea is visible with current prompt text
3. Clear the text, type a test prompt: `Test prompt - please ignore`
4. Click save
5. Verify: success message appears
6. Reload page
7. Verify: textarea contains the test prompt text

### S15 — AI Recruiter Prompt Reset
1. Navigate to `/en/settings/ai-recruiter`
2. Click "Reset to Default" button
3. Verify: confirmation prompt (if any) accepted
4. Verify: textarea reverts to the default system prompt text
5. Verify: default text is non-empty

### S16 — Left Nav All Sections
1. Navigate to `/en/settings`
2. Click each of the 9 nav items in sequence
3. For each: verify the correct section title/card appears within 2s
4. Verify: active nav item has cyan background

---

## Verification Matrix

| ID  | Key Assertion |
|-----|---------------|
| S01 | 9 nav items visible, General is default |
| S02 | All 6 firm profile fields persist after reload |
| S03 | All 6 API key rows save without error, status indicator updates |
| S04 | AI provider card selection toggles correctly |
| S05 | Search provider dropdown saves and persists |
| S06 | IMAP fields save, reload retains values |
| S07 | Invited member appears in list with "pending" badge |
| S08 | Removed member disappears from list |
| S09 | DPA modal opens, Accept button disabled without checkbox |
| S10 | DPA accepted → accepted date shown in green |
| S11 | Retention dropdown saves and persists after reload |
| S12 | JSON download initiated |
| S13 | Confirm button disabled without "DELETE" typed, cancel closes modal |
| S14 | Custom prompt persists after reload |
| S15 | Prompt resets to non-empty default text |
| S16 | All 9 sections load without error |
