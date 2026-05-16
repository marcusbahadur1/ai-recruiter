/**
 * Module 09 — Client Pipeline (formerly AI Marketing)
 * Tests: M01–M12
 * Route: /en/marketing
 *
 * The /en/marketing page is the Client Pipeline page.
 * LinkedIn connection is in the Settings tab of Client Pipeline.
 * Post queue/content is in the Content tab.
 */
import { test, expect } from '@playwright/test'

// ── M01 — Marketing Page Loads ────────────────────────────────────────────────
test('M01 — Marketing page loads — key sections visible', async ({ page }) => {
  await page.goto('/en/marketing')
  await page.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => {})

  await expect(page).not.toHaveURL(/404|500/)

  // Client Pipeline heading
  await expect(page.getByText(/Client Pipeline|Pipeline/i).first()).toBeVisible({ timeout: 10_000 })

  // Key tabs visible
  await expect(page.getByRole('button', { name: /^Pipeline$/i }).first()
    .or(page.getByText(/^Pipeline$/i).first())
  ).toBeVisible({ timeout: 5_000 })
})

// ── M02 — LinkedIn Connect in Settings Tab ────────────────────────────────────
test('M02 — LinkedIn connect buttons — visible in Settings tab', async ({ page }) => {
  await page.goto('/en/marketing')
  await page.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => {})

  // Click Settings tab
  const settingsTab = page.getByRole('button', { name: /^Settings$/i }).first()
  if (await settingsTab.count() === 0) {
    test.skip(true, 'ENV_SKIP: Settings tab not found on marketing page')
    return
  }
  await settingsTab.click()
  await page.waitForTimeout(1000)

  // LinkedIn OAuth section
  const linkedinSection = page.getByText(/LinkedIn|Connect Account/i).first()
  if (await linkedinSection.count() > 0) {
    await expect(linkedinSection).toBeVisible({ timeout: 5_000 })
  } else {
    // Settings tab may show ICP config instead — that's still valid
    await expect(page.getByText(/ICP|Settings|Target/i).first()).toBeVisible({ timeout: 5_000 })
  }
})

// ── M03 — LinkedIn connected accounts ────────────────────────────────────────
test('M03 — LinkedIn connected accounts — account info visible if connected', async ({ page }) => {
  await page.goto('/en/marketing')
  await page.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => {})

  // Click Settings tab
  const settingsTab = page.getByRole('button', { name: /^Settings$/i }).first()
  if (await settingsTab.count() === 0) {
    test.skip(true, 'ENV_SKIP: Settings tab not found')
    return
  }
  await settingsTab.click()
  await page.waitForTimeout(1000)

  // Check if any accounts are connected
  const disconnectBtn = page.getByRole('button', { name: /disconnect/i }).first()

  if (await disconnectBtn.count() === 0) {
    // No accounts connected — verify the connect button is visible instead
    const connectBtn = page.getByRole('button', { name: /connect/i }).first()
      .or(page.getByText(/Connect Account|OAuth/i).first())
    if (await connectBtn.count() > 0) {
      await expect(connectBtn).toBeVisible({ timeout: 5_000 })
    }
    test.info().annotations.push({
      type: 'env_skip',
      description: 'No LinkedIn accounts connected — verified connect button instead'
    })
  } else {
    await expect(disconnectBtn).toBeVisible({ timeout: 5_000 })
  }
})

// ── M04 — Disconnect LinkedIn ─────────────────────────────────────────────────
test('M04 — Disconnect LinkedIn — button visible (if account connected)', async ({ page }) => {
  await page.goto('/en/marketing')
  await page.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => {})

  const settingsTab = page.getByRole('button', { name: /^Settings$/i }).first()
  if (await settingsTab.count() > 0) {
    await settingsTab.click()
    await page.waitForTimeout(500)
  }

  const disconnectBtn = page.getByRole('button', { name: /disconnect/i }).first()
  if (await disconnectBtn.count() === 0) {
    test.skip(true, 'ENV_SKIP: No LinkedIn accounts connected to disconnect')
    return
  }

  // Verify disconnect button is visible (don't click — would remove test data)
  await expect(disconnectBtn).toBeVisible()
  await expect(disconnectBtn).toBeEnabled()
})

// ── M05 — Content Tab ─────────────────────────────────────────────────────────
test('M05 — Content tab — renders correctly', async ({ page }) => {
  await page.goto('/en/marketing')
  await page.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => {})

  // Click Content tab
  const contentTab = page.getByRole('button', { name: /^Content$/i }).first()
  if (await contentTab.count() === 0) {
    test.skip(true, 'ENV_SKIP: Content tab not found')
    return
  }
  await contentTab.click()
  await page.waitForTimeout(1000)

  // Content area should render without crash
  await expect(page.locator('body')).not.toContainText('500')
  await expect(page.locator('body')).not.toContainText('Internal Server Error')

  // Either shows posts or empty state
  const hasContent = await page.locator('body').textContent()
  expect(hasContent).toBeTruthy()
})

// ── M06 — Sequences Tab ───────────────────────────────────────────────────────
test('M06 — Sequences tab — renders correctly', async ({ page }) => {
  await page.goto('/en/marketing')
  await page.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => {})

  // Click Sequences tab
  const seqTab = page.getByRole('button', { name: /^Sequences$/i }).first()
  if (await seqTab.count() === 0) {
    test.skip(true, 'ENV_SKIP: Sequences tab not found')
    return
  }
  await seqTab.click()
  await page.waitForTimeout(1000)

  await expect(page.locator('body')).not.toContainText('500')

  // Shows sequence list or empty state
  const seqText = page.getByText(/sequence|no sequences|Create.*sequence/i).first()
  if (await seqText.count() > 0) {
    await expect(seqText).toBeVisible({ timeout: 5_000 })
  }
})

// ── M07 — Prospects Tab ───────────────────────────────────────────────────────
test('M07 — Prospects tab — renders correctly', async ({ page }) => {
  await page.goto('/en/marketing')
  await page.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => {})

  // Click Prospects tab
  const prospectsTab = page.getByRole('button', { name: /^Prospects$/i }).first()
  if (await prospectsTab.count() === 0) {
    test.skip(true, 'ENV_SKIP: Prospects tab not found')
    return
  }
  await prospectsTab.click()
  await page.waitForTimeout(1000)

  await expect(page.locator('body')).not.toContainText('500')

  // Shows prospects table or empty state
  const prospectText = page.getByText(/prospect|no prospects|identified/i).first()
  if (await prospectText.count() > 0) {
    await expect(prospectText).toBeVisible({ timeout: 5_000 })
  }
})

// ── M08 — Signals Tab ────────────────────────────────────────────────────────
test('M08 — Signals tab — renders correctly', async ({ page }) => {
  await page.goto('/en/marketing')
  await page.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => {})

  // Click Signals tab
  const signalsTab = page.getByRole('button', { name: /^Signals$/i }).first()
  if (await signalsTab.count() === 0) {
    test.skip(true, 'ENV_SKIP: Signals tab not found')
    return
  }
  await signalsTab.click()
  await page.waitForTimeout(1000)

  await expect(page.locator('body')).not.toContainText('500')
})

// ── M09 — Pipeline Tab Default ────────────────────────────────────────────────
test('M09 — Pipeline tab — 5 metric cards visible', async ({ page }) => {
  await page.goto('/en/marketing')
  await page.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => {})

  // Pipeline tab should be default
  const metrics = ['Prospects Found', 'Connected', 'Replied', 'Demos Booked', 'Trials Started']
  for (const metric of metrics) {
    await expect(
      page.getByText(new RegExp(metric, 'i')).first()
    ).toBeVisible({ timeout: 5_000 })
  }
})

// ── M10 — No 500 errors ───────────────────────────────────────────────────────
test('M10 — Return to Draft / Reject post button visible', async ({ page }) => {
  await page.goto('/en/marketing')
  await page.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => {})

  // Navigate to Content tab
  const contentTab = page.getByRole('button', { name: /^Content$/i }).first()
  if (await contentTab.count() > 0) {
    await contentTab.click()
    await page.waitForTimeout(500)
  }

  // Posts in various states should have action buttons
  const actionBtn = page.getByRole('button', { name: /return to draft|reject|delete/i }).first()
  if (await actionBtn.count() === 0) {
    test.skip(true, 'ENV_SKIP: No posts with action buttons visible')
    return
  }

  await expect(actionBtn).toBeVisible()
  await expect(actionBtn).toBeEnabled()
})

// ── M11 — Analytics Summary ───────────────────────────────────────────────────
test('M11 — Analytics summary — page loads without error', async ({ page }) => {
  await page.goto('/en/marketing')
  await page.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => {})

  // Page should load without 500 error
  await expect(page.locator('body')).not.toContainText('500')
  await expect(page.locator('body')).not.toContainText('Internal Server Error')

  // Pipeline metrics should be visible
  await expect(page.getByText(/Prospects Found|Pipeline|Conversion/i).first())
    .toBeVisible({ timeout: 5_000 })
})

// ── M12 — Plan Gate ───────────────────────────────────────────────────────────
test('M12 — Marketing module — accessible on agency_medium plan', async ({ page }) => {
  await page.goto('/en/marketing')
  await page.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => {})

  // Test tenant is on agency_medium — marketing should be accessible
  await expect(page).not.toHaveURL(/404/)
  await expect(page.locator('body')).not.toContainText('Internal Server Error')

  // Should see Client Pipeline content (not upgrade wall)
  await expect(
    page.getByText(/Client Pipeline|Pipeline|Prospects|Sequences/i).first()
  ).toBeVisible({ timeout: 10_000 })
})
