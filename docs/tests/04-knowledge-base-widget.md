# Module 04 — Knowledge Base & Chat Widget Test Plan
Version: 1.0 | Date: 2026-05-01
Target: https://app.airecruiterz.com
Automation: Full

---

## Scope

Knowledge Base: website scraping, file upload (PDF/DOCX/TXT), document list and deletion.
Chat Widget: embed code, bot name, brand colour, live preview, widget chat interaction.

## Pre-conditions

- Logged in as test tenant
- Tenant is on Agency Small plan or above (required for Chat Widget — plan gate tested in W05)
- Firm website URL configured in General settings (for scrape test)
- Test files available locally: `e2e/fixtures/test.pdf`, `test.docx`, `test.txt`

---

## Test Scenarios

| ID   | Name | Automated |
|------|------|-----------|
| K01  | Knowledge Base — scrape website URL → document appears in list | Yes |
| K02  | Knowledge Base — upload PDF → appears in list with chunk count | Yes |
| K03  | Knowledge Base — upload DOCX → appears in list | Yes |
| K04  | Knowledge Base — upload TXT → appears in list | Yes |
| K05  | Knowledge Base — delete document → removed from list | Yes |
| K06  | Knowledge Base — document list: icon, label, meta, count correct | Yes |
| K07  | Chat Widget — plan gate notice shown on ineligible plan | Yes |
| K08  | Chat Widget — embed code visible and copyable | Yes |
| K09  | Chat Widget — bot name change → live preview reflects name | Yes |
| K10  | Chat Widget — brand colour change → preview bubble updates colour | Yes |
| K11  | Chat Widget — save settings → persist after page reload | Yes |
| K12  | Chat Widget — live chat interaction (widget embed on test page) | Yes |

---

## Scenario Detail

### K01 — Scrape Website URL
1. Navigate to `/en/settings`, click "Knowledge Base"
2. Locate "Website Scraper" card
3. Verify: firm website URL is shown (from General settings)
4. Click "Scrape Website Now"
5. Verify: button shows "Scraping…" during operation
6. Wait up to 30s for completion
7. Verify: green success message appears
8. Verify: a new document with 🌐 icon appears in the document list
9. Verify: document label contains the website URL

**Assertions:**
- `ragApi.scrapeWebsite(url)` called
- Document list count incremented by ≥ 1

### K02 — Upload PDF
1. In Knowledge Base section, locate file upload area
2. Attach `e2e/fixtures/test.pdf` to the hidden file input
3. Click "Upload Document"
4. Verify: button shows "Uploading…"
5. Verify: "✓ Uploaded" message appears
6. Verify: document appears in list with 📄 icon
7. Verify: chunk count displayed (e.g., "3 chunks")
8. Verify: "added [today's date]" in metadata

### K03 — Upload DOCX
Same flow as K02 using `e2e/fixtures/test.docx`.
Verify: DOCX file appears in list with correct filename.

### K04 — Upload TXT
Same flow as K02 using `e2e/fixtures/test.txt`.
Verify: TXT file appears in list.

### K05 — Delete Document
1. In document list, locate the TXT document uploaded in K04
2. Click the red "Delete" button next to it
3. Verify: document disappears from list
4. Verify: document count decremented
5. Verify: no error banner

**Assertions:**
- `ragApi.deleteDocument(id)` called with correct ID
- API returns 200

### K06 — Document List Metadata
1. In Knowledge Base section, review document list after K01–K04
2. For each document verify:
   - Icon is 🌐 (website) or 📄 (file) — correct per type
   - Label is non-empty (filename or URL)
   - "X chunks" count > 0
   - "added [date]" metadata present
3. Verify: list heading shows correct document count

### K07 — Widget Plan Gate
Pre-condition: Switch to a Recruiter plan account (no widget access).
1. Navigate to `/en/settings`, click "Chat Widget"
2. Verify: blue plan-gate banner is shown: "Upgrade required…"
3. Verify: "Upgrade" link (cyan) is present and navigates to billing section

### K08 — Embed Code Copy
Pre-condition: Tenant is on Agency Small or above.
1. Navigate to `/en/settings`, click "Chat Widget"
2. Verify: embed code block is visible with `<script>` tag content
3. Verify: `tenantSlug` in the script matches the tenant's slug
4. Click "📋 Copy Embed Code" button
5. Verify: button text changes to "✓ Copied!"
6. Read clipboard value (Playwright `readText`) — verify contains `AIRecruiterConfig`

### K09 — Bot Name Change
1. In Chat Widget section, locate Bot Name input
2. Clear existing value, type "Recruitment Bot"
3. Verify: live preview bubble/label updates (if name is displayed in preview)
4. Click "Save"
5. Verify: "✓ Saved" status appears
6. Reload page, navigate to Chat Widget
7. Verify: bot name input shows "Recruitment Bot"

### K10 — Brand Colour Change
1. In Chat Widget section, locate colour picker + hex input
2. Change hex input to `#FF5733`
3. Verify: preview bubble background colour updates to `#FF5733`
4. Click "Save"
5. Verify: "✓ Saved" status
6. Reload, verify hex input shows `#FF5733`

### K11 — Settings Persist After Reload
Combination test:
1. Set bot name = "TestBot", colour = `#123456`
2. Save
3. Hard reload (`Ctrl+F5` equivalent in Playwright)
4. Navigate to `/en/settings` → Chat Widget
5. Verify: bot name = "TestBot", colour hex = `#123456`

### K12 — Widget Chat Interaction
Mock approach: A static HTML fixture file is pre-built with the embed script and the test
tenant's slug. Playwright loads it directly — no manual copy/paste required. The widget
script loads from production and makes real API calls.

**Fixture file:** `e2e/fixtures/widget-test.html`
```html
<!DOCTYPE html>
<html><body>
<script>
  window.AIRecruiterConfig = {
    tenantSlug: process.env.PROD_TEST_TENANT_SLUG,
    primaryColor: '#00C2E0'
  };
</script>
<script src="https://app.airecruiterz.com/widget/widget.js" async></script>
</body></html>
```
The fixture is generated at test setup time with the real slug injected from `.env.production`.

Steps:
1. Test setup generates `widget-test.html` with the correct `tenantSlug`
2. Playwright navigates to `file://{absolute_path}/widget-test.html`
3. Verify: chat bubble element appears (bottom-right, correct brand colour from K10)
4. Click the bubble
5. Verify: chat window opens
6. Type: "What services do you offer?"
7. Wait up to 15s for AI response (live Claude API)
8. Verify: response is non-empty and does not contain an error message
9. Click the bubble again (or close button)
10. Verify: chat window closes

---

## Verification Matrix

| ID  | Key Assertion |
|-----|---------------|
| K01 | Scraped URL appears in document list with 🌐 icon + chunk count |
| K02 | PDF uploaded, appears with 📄 icon + chunk count > 0 |
| K03 | DOCX appears in list with correct filename |
| K04 | TXT appears in list |
| K05 | Deleted document removed from list, count decremented |
| K06 | All document rows have icon, label, chunk count, date |
| K07 | Plan gate banner visible for ineligible plan |
| K08 | Embed code visible, copy button works, clipboard contains correct script |
| K09 | Bot name persists after save and reload |
| K10 | Brand colour updates preview, persists after reload |
| K11 | Both bot name and colour persist together |
| K12 | HTML fixture loaded by Playwright → bubble renders → chat opens → AI responds |
