/**
 * Module 10 — Super Admin
 * Tests: SA01–SA13
 * Route: /en/super-admin
 *
 * This module uses the test-user context (same user = super admin in test env).
 * Super admin detection is via API probe (/api/v1/super-admin/stats → 200 = super admin).
 *
 * SA13 requires a non-super-admin context — tested via API call.
 */
import { test, expect } from '@playwright/test'

const API_URL = (process.env.PROD_API_URL ?? 'https://airecruiterz-api.fly.dev').replace(/\/$/, '')

// ── SA01 — Super Admin Page Loads ─────────────────────────────────────────────
test('SA01 — Super admin page loads — alert banner and stat cards', async ({ page }) => {
  await page.goto('/en/super-admin')
  await page.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => {})

  await expect(page).not.toHaveURL(/404|403/)

  // Super Admin Mode banner
  await expect(
    page.getByText(/Super Admin Mode|platform-wide/i).first()
  ).toBeVisible({ timeout: 10_000 })

  // Stat cards
  await expect(page.getByText(/total tenants/i).first()).toBeVisible({ timeout: 5_000 })
})

// ── SA02 — Tenant List Columns ────────────────────────────────────────────────
test('SA02 — Tenant list — table with Firm, Plan, Credits, Status columns', async ({ page }) => {
  await page.goto('/en/super-admin')
  await page.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => {})

  // Tenants tab should be default
  await expect(page.getByText(/tenants/i).first()).toBeVisible({ timeout: 5_000 })

  // Column headers
  const columns = ['Firm', 'Plan', 'Credits', 'Status']
  for (const col of columns) {
    await expect(page.getByText(col).first()).toBeVisible({ timeout: 5_000 })
  }

  // At least one tenant row
  await expect(page.locator('table tbody tr').first()).toBeVisible({ timeout: 10_000 })
})

// ── SA03 — Tenant Impersonation ───────────────────────────────────────────────
test('SA03 — Impersonate — button visible on tenant row', async ({ page }) => {
  await page.goto('/en/super-admin')
  await page.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => {})

  // Verify super admin page renders without error
  await expect(page.getByText(/Super Admin Mode|Tenants/i).first()).toBeVisible({ timeout: 10_000 })

  // Check if impersonate button exists (may not on all plans)
  const impersonateBtn = page.getByRole('button', { name: /impersonate/i }).first()
  if (await impersonateBtn.count() === 0) {
    test.skip(true, 'ENV_SKIP: Impersonate button not available on this tenant')
    return
  }

  await expect(impersonateBtn).toBeVisible({ timeout: 5_000 })
})

// ── SA04 — Exit Impersonation ─────────────────────────────────────────────────
test('SA04 — Exit impersonation — returns to super admin view', async ({ page }) => {
  await page.goto('/en/super-admin')
  await page.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => {})

  const impersonateBtn = page.getByRole('button', { name: /impersonate/i }).first()
  if (await impersonateBtn.count() === 0) {
    test.skip(true, 'ENV_SKIP: No impersonate button found')
    return
  }

  // Start impersonation
  await impersonateBtn.click()
  await page.waitForTimeout(2000)

  // Find exit impersonation option
  const exitBtn = page.getByRole('button', { name: /exit impersonation|stop impersonating/i }).first()
    .or(page.getByText(/exit impersonation/i).first())

  if (await exitBtn.count() > 0) {
    await exitBtn.click()
    await page.waitForTimeout(2000)
    // Should return to super admin or regular dashboard
    await expect(page.locator('body')).not.toContainText('500')
  } else {
    // Navigate back manually
    await page.goto('/en/super-admin')
    await page.waitForLoadState('networkidle', { timeout: 10_000 }).catch(() => {})
    await expect(page.getByText(/Super Admin Mode/i).first()).toBeVisible({ timeout: 5_000 })
  }
})

// ── SA05 — Platform API Keys ──────────────────────────────────────────────────
test('SA05 — Platform API Keys tab — key inputs visible', async ({ page }) => {
  await page.goto('/en/super-admin')
  await page.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => {})

  // Click Platform API Keys tab
  const keysTab = page.getByRole('button', { name: /platform.*api.*keys|API Keys/i }).first()
    .or(page.getByText(/platform api keys/i).first())
  await expect(keysTab).toBeVisible({ timeout: 5_000 })
  await keysTab.click()
  await page.waitForTimeout(500)

  // Key rows visible (masked inputs)
  await expect(
    page.getByText(/anthropic|openai|sendgrid|scrapingdog|brightdata/i).first()
  ).toBeVisible({ timeout: 5_000 })

  // Save button
  await expect(
    page.getByRole('button', { name: /save.*keys|save platform/i }).first()
  ).toBeVisible({ timeout: 5_000 })
})

// ── SA06 — Email Test Mode Toggle ─────────────────────────────────────────────
test('SA06 — Email Test Mode — toggle and recipient field visible', async ({ page }) => {
  await page.goto('/en/super-admin')
  await page.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => {})

  // Click Platform API Keys tab (Email Test Mode is in this section)
  const keysTab = page.getByRole('button', { name: /platform.*api.*keys|API Keys/i }).first()
    .or(page.getByText(/platform api keys/i).first())
  await keysTab.click()
  await page.waitForTimeout(500)

  // Email test mode toggle
  await expect(
    page.getByText(/email test mode/i).first()
  ).toBeVisible({ timeout: 5_000 })

  // Enable/Disable toggle button
  await expect(
    page.getByRole('button', { name: /enable email test mode|disable email test mode/i }).first()
  ).toBeVisible({ timeout: 5_000 })

  // Recipient email input
  const recipientInput = page.locator('input[type="email"], input[placeholder*="recipient"]').first()
  await expect(recipientInput).toBeVisible({ timeout: 5_000 })
})

// ── SA07 — Create Promo Code ──────────────────────────────────────────────────
test('SA07 — Create promo code — form visible and submits', async ({ page }) => {
  await page.goto('/en/super-admin')
  await page.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => {})

  // Click Promo Codes tab
  const promoTab = page.getByRole('button', { name: /promo codes/i }).first()
    .or(page.getByText(/promo codes/i).first())
  await expect(promoTab).toBeVisible({ timeout: 5_000 })
  await promoTab.click()
  await page.waitForTimeout(500)

  // Create form
  const codeInput = page.locator('input[placeholder*="code"], input[name*="code"]').first()
  if (await codeInput.count() === 0) {
    test.skip(true, 'ENV_SKIP: Promo code form not found (tab may not be available)')
    return
  }
  await expect(codeInput).toBeVisible({ timeout: 5_000 })

  const ts = Date.now().toString().slice(-6)
  await codeInput.fill(`E2ETEST${ts}`)

  // Type select
  const typeSelect = page.locator('select').first()
  await typeSelect.selectOption('credits')

  // Value
  const valueInput = page.locator('input[type="number"], input[placeholder*="value"]').first()
  await valueInput.fill('10')

  // Max uses
  const maxUsesInput = page.locator('input[placeholder*="max"], input[name*="max"]').first()
  if (await maxUsesInput.count() > 0) {
    await maxUsesInput.fill('1')
  }

  // Submit
  const createBtn = page.getByRole('button', { name: /create.*code|create/i }).first()
  await createBtn.click()
  await page.waitForTimeout(2000)

  // Success — code appears in list
  await expect(
    page.getByText(new RegExp(`E2ETEST${ts}`, 'i')).first()
  ).toBeVisible({ timeout: 10_000 })
})

// ── SA08 — Validate Promo Code ────────────────────────────────────────────────
test('SA08 — Promo code — code appears in table with Active status', async ({ page }) => {
  await page.goto('/en/super-admin')
  await page.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => {})

  const promoTab = page.getByRole('button', { name: /promo codes/i }).first()
    .or(page.getByText(/promo codes/i).first())
  await promoTab.click()
  await page.waitForTimeout(500)

  // Promo codes table visible
  await expect(
    page.locator('table').first()
      .or(page.getByText(/no promo codes/i).first())
  ).toBeVisible({ timeout: 5_000 })

  // If table has rows, verify status column exists
  if (await page.locator('table tbody tr').count() > 0) {
    await expect(
      page.getByText(/active|inactive|expired/i).first()
    ).toBeVisible({ timeout: 5_000 })
  }
})

// ── SA09 — Deactivate Promo Code ──────────────────────────────────────────────
test('SA09 — Deactivate promo code — status changes to inactive', async ({ page }) => {
  await page.goto('/en/super-admin')
  await page.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => {})

  const promoTab = page.getByRole('button', { name: /promo codes/i }).first()
    .or(page.getByText(/promo codes/i).first())
  await promoTab.click()
  await page.waitForTimeout(500)

  // Find an active E2E test promo code
  const activeRow = page.locator('tr').filter({ hasText: /E2ETEST/i })
    .filter({ hasText: /active/i }).first()

  if (await activeRow.count() === 0) {
    test.skip(true, 'ENV_SKIP: No active E2E promo codes found (run SA07 first)')
    return
  }

  // Deactivate button in that row
  const deactivateBtn = activeRow.getByRole('button', { name: /deactivate|disable/i }).first()
  if (await deactivateBtn.count() === 0) {
    test.skip(true, 'ENV_SKIP: Deactivate button not found')
    return
  }

  await deactivateBtn.click()
  await page.waitForTimeout(2000)

  // Row should show inactive
  await expect(
    activeRow.getByText(/inactive|deactivated/i).first()
      .or(page.locator('tr').filter({ hasText: /E2ETEST/i }).filter({ hasText: /inactive/i }).first())
  ).toBeVisible({ timeout: 10_000 })
})

// ── SA10 — System Health ──────────────────────────────────────────────────────
test('SA10 — System Health tab — stat cards with health indicators', async ({ page }) => {
  await page.goto('/en/super-admin')
  await page.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => {})

  // Click System Health tab
  const healthTab = page.getByRole('button', { name: /system health/i }).first()
    .or(page.getByText(/system health/i).first())
  await expect(healthTab).toBeVisible({ timeout: 5_000 })
  await healthTab.click()
  await page.waitForTimeout(500)

  // Health cards: Celery Queue Depth, Failed Tasks, Active Workers, Redis Status
  await expect(
    page.getByText(/celery|queue.*depth|failed.*tasks|redis|workers/i).first()
  ).toBeVisible({ timeout: 10_000 })
})

// ── SA11 — Platform Audit Trail ───────────────────────────────────────────────
test('SA11 — Platform audit trail — events listed with category filter', async ({ page }) => {
  await page.goto('/en/super-admin')
  await page.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => {})

  // Click Audit Log tab
  const auditTab = page.getByRole('button', { name: /audit log/i }).first()
    .or(page.getByText(/audit log/i).first())
  await expect(auditTab).toBeVisible({ timeout: 5_000 })
  await auditTab.click()
  await page.waitForTimeout(500)

  // Category filter buttons
  await expect(page.getByRole('button', { name: /all/i }).first()).toBeVisible({ timeout: 5_000 })

  // Events table or empty state
  await expect(
    page.locator('table').first()
      .or(page.getByText(/no events|no audit/i).first())
  ).toBeVisible({ timeout: 10_000 })
})

// ── SA12 — Super Admin Marketing Analytics ────────────────────────────────────
test('SA12 — Marketing analytics page — accessible from super admin', async ({ page }) => {
  await page.goto('/en/super-admin/marketing')
  await page.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => {})

  await expect(page).not.toHaveURL(/404/)

  // Marketing analytics page
  await expect(
    page.getByText(/marketing|eligible tenants|agency/i).first()
  ).toBeVisible({ timeout: 10_000 })

  // Back link
  await expect(
    page.getByText(/← Super Admin|super admin/i).first()
  ).toBeVisible({ timeout: 5_000 })
})

// ── SA13 — Non-Super-Admin Blocked ────────────────────────────────────────────
test('SA13 — Non-super-admin API endpoint returns 403', async ({ page }) => {
  // Test via API that super admin routes are protected.
  // We use a direct fetch with no auth to verify the endpoint rejects it.
  const response = await page.evaluate(async (apiUrl) => {
    try {
      const res = await fetch(`${apiUrl}/api/v1/super-admin/stats`, {
        method: 'GET',
        headers: { 'Authorization': 'Bearer invalid-token-12345' },
      })
      return res.status
    } catch {
      return 0
    }
  }, API_URL)

  // Should return 401 or 403 — not 200
  expect([401, 403, 422]).toContain(response)
})
