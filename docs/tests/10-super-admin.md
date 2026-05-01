# Module 10 — Super Admin Panel Test Plan
Version: 1.0 | Date: 2026-05-01
Target: https://app.airecruiterz.com
Login: marcus@aiworkerz.com (super admin account)
Automation: Full (all tests automated unless marked [MANUAL])

---

## Scope

Tenant list (stats, search), tenant impersonation (and exit), platform API key management,
promo code management (create, validate, deactivate), email test mode toggle,
system health monitoring (Celery queue depth, failed tasks), platform audit trail view,
Super Admin marketing analytics tab.

## Pre-conditions

- Logged in as `marcus@aiworkerz.com` (SUPER_ADMIN_EMAIL)
- Super admin access detected via `superAdminApi.getStats()` returning 200
- Test tenant (`marcusbahadur1@gmail.com`) exists and has activity
- `EMAIL_TEST_MODE` status known before running SA06 (so it can be restored)

---

## Test Scenarios

| ID   | Name | Automated |
|------|------|-----------|
| SA01 | Super admin page loads — tenant list with stats | Yes |
| SA02 | Tenant list — columns and data correct | Yes |
| SA03 | Tenant impersonation — session switches to tenant context | Yes |
| SA04 | Exit impersonation — session returns to super admin | Yes |
| SA05 | Platform API keys — view and update a key | Yes |
| SA06 | Email test mode toggle — ON → OFF → ON | Yes |
| SA07 | Promo code — create new code | Yes |
| SA08 | Promo code — validate code (usage tracking) | Yes |
| SA09 | Promo code — deactivate/delete code | Yes |
| SA10 | System health — Celery queue depth and failed tasks visible | Yes |
| SA11 | Platform audit trail — events visible, filterable | Yes |
| SA12 | Super Admin marketing analytics tab | Yes |
| SA13 | Non-super-admin cannot access /super-admin | Yes |

---

## Scenario Detail

### SA01 — Super Admin Page Loads
1. Log in as `marcus@aiworkerz.com`
2. Navigate to `/en/super-admin`
3. Verify: page renders without 403/404/500
4. Verify: "Super Admin" heading or equivalent visible
5. Verify: tenant list section loads

### SA02 — Tenant List Columns
1. On super admin page, locate tenant list/table
2. Verify: columns present — Name | Plan | Credits | Status | Last Active (or similar)
3. Verify: at least 1 tenant row (the test tenant)
4. For the test tenant row, verify:
   - Firm name is non-empty
   - Plan name matches the test tenant's plan
   - Credits value is a non-negative integer
   - Status is "active" or equivalent

### SA03 — Tenant Impersonation
1. On super admin page, find the test tenant row
2. Click "Impersonate" or equivalent button
3. Verify: loading state during impersonation
4. Verify: session context switches — navigates to the tenant's dashboard (`/en`)
5. Verify: the UI now reflects the test tenant's data (jobs, candidates, etc.)
6. Verify: an impersonation banner or indicator is visible (e.g., "Viewing as [Firm Name]")

**Assertions:**
- `GET /api/v1/settings` after impersonation returns the test tenant's firm name
- Super admin's own tenant data is NOT visible

### SA04 — Exit Impersonation
1. While in impersonated session (from SA03):
2. Click "Exit Impersonation" button or equivalent
3. Verify: session returns to super admin context
4. Verify: navigated back to `/en/super-admin`
5. Verify: impersonation banner disappears
6. Verify: `GET /api/v1/settings` returns super admin tenant data again

### SA05 — Platform API Keys
1. On super admin page, navigate to Platform Keys or API Keys section
2. Verify: platform-level API key fields are visible
   (e.g., default Anthropic key, SendGrid key, ScrapingDog key)
3. Edit one key field with a dummy value `test-platform-key-XXXX`
4. Save
5. Verify: success message
6. Restore original value and save again

### SA06 — Email Test Mode Toggle
1. Locate Email Test Mode toggle in super admin / Platform Keys section
2. Note current state (ON or OFF)
3. Toggle to opposite state
4. Verify: visual state updates (toggle/button reflects new state)
5. Verify: API confirms new state:
   `GET /api/v1/admin/settings` → `email_test_mode` field matches toggle state
6. Toggle back to original state
7. Verify: restored to original

### SA07 — Create Promo Code
1. Navigate to Promo Codes section in super admin
2. Click "Create" or "New Promo Code" button
3. Fill: code string (e.g., `TESTCODE2026`), discount %, usage limit
4. Click "Create"
5. Verify: new code appears in the promo code list
6. Verify: code row shows: code string, discount %, usage count (0), status (active)

### SA08 — Validate Promo Code
Pre-condition: Code `TESTCODE2026` exists from SA07.
1. In the promo code list, verify the code row
2. Verify: usage count = 0 initially
3. Apply the code via the subscribe/billing page as the test tenant
4. Return to super admin → Promo Codes
5. Verify: usage count incremented to 1

Note: If applying via billing UI is too complex for this test, verify using:
`GET /api/v1/admin/promo-codes` → confirm code exists with `usage_count = 0`

### SA09 — Deactivate / Delete Promo Code
1. In promo codes list, locate `TESTCODE2026`
2. Click "Deactivate" or "Delete"
3. Verify: confirmation handled (if any)
4. Verify: code status changes to "inactive" or code removed from list
5. Verify: the code can no longer be applied at billing/checkout

### SA10 — System Health
1. On super admin page, navigate to System Health or similar section
2. Verify: Celery queue depth is displayed (integer ≥ 0)
3. Verify: failed task count is displayed (integer ≥ 0)
4. Verify: section renders without error
5. Verify: data appears real-time or refreshes without full page reload

### SA11 — Platform Audit Trail
1. Navigate to audit trail or event log section in super admin
2. Verify: events list renders with ≥ 1 event
3. Verify: events have timestamps and event type/category
4. If filter controls exist: apply a filter, verify results update
5. If export exists: click export → verify download initiated

### SA12 — Super Admin Marketing Analytics
1. Navigate to `/en/super-admin/marketing`
2. Verify: page loads without 403/404/500
3. Verify: cross-tenant marketing analytics data visible (aggregate metrics)
4. Verify: at least one table or chart renders

### SA13 — Non-Super-Admin Access Blocked
1. Log in as the test tenant (`marcusbahadur1@gmail.com`) — not super admin
2. Navigate to `/en/super-admin`
3. Verify: page shows a 403 / access denied / redirect to dashboard
4. Verify: super admin data is NOT visible
5. Verify: `superAdminApi.getStats()` returns 403 for this user

---

## Verification Matrix

| ID   | Key Assertion |
|------|---------------|
| SA01 | Super admin page loads, tenant list visible |
| SA02 | Tenant list columns correct, test tenant row present |
| SA03 | Impersonation → session switches, impersonation banner shown |
| SA04 | Exit impersonation → super admin context restored |
| SA05 | Platform API key saved and restorable |
| SA06 | Email test mode toggle persists in API state |
| SA07 | New promo code created, appears in list with usage=0 |
| SA08 | Usage count increments after code applied |
| SA09 | Code deactivated/deleted, no longer usable |
| SA10 | Celery queue + failed task count visible |
| SA11 | Audit events visible, filterable |
| SA12 | Marketing analytics page loads with data |
| SA13 | Non-super-admin gets 403, no super admin data visible |

---

## Clean-up After Module 10

- Restore EMAIL_TEST_MODE to original state if changed
- Delete promo code `TESTCODE2026` if not already done in SA09
- Exit any active impersonation session
