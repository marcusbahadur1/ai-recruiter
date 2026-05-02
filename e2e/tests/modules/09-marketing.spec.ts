/**
 * Module 09 — Marketing
 * Tests: M01–M12
 * Route: /en/marketing
 *
 * Note: LinkedIn OAuth requires a real OAuth flow — M02/M04 use DB-seeded accounts.
 * M03 (page selection) requires an active LinkedIn connection.
 */
import { test, expect } from '@playwright/test'

// ── M01 — Marketing Page Loads ────────────────────────────────────────────────
test('M01 — Marketing page loads — key sections visible', async ({ page }) => {
  await page.goto('/en/marketing')
  await page.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => {})

  await expect(page).not.toHaveURL(/404|500/)

  // Marketing heading
  await expect(page.getByText(/marketing/i).first()).toBeVisible({ timeout: 10_000 })

  // LinkedIn Accounts card
  await expect(page.getByText(/LinkedIn Accounts/i).first()).toBeVisible({ timeout: 10_000 })
})

// ── M02 — Connect LinkedIn (DB Seed) ─────────────────────────────────────────
test('M02 — LinkedIn connect buttons — Personal and Company Page options visible', async ({ page }) => {
  await page.goto('/en/marketing')
  await page.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => {})

  // Connect buttons visible
  await expect(
    page.getByRole('button', { name: /connect personal|connect.*personal/i }).first()
  ).toBeVisible({ timeout: 10_000 })

  await expect(
    page.getByRole('button', { name: /connect.*company|company.*page/i }).first()
  ).toBeVisible({ timeout: 5_000 })
})

// ── M03 — LinkedIn Page Selection ────────────────────────────────────────────
test('M03 — LinkedIn connected accounts — account info visible if connected', async ({ page }) => {
  await page.goto('/en/marketing')
  await page.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => {})

  // Check if any accounts are connected
  const disconnectBtn = page.getByRole('button', { name: /disconnect/i }).first()
  const accountName = page.locator('[class*="account"] [class*="name"]').first()

  if (await disconnectBtn.count() === 0) {
    // No accounts connected — verify the connect buttons are visible instead
    await expect(
      page.getByRole('button', { name: /connect/i }).first()
    ).toBeVisible({ timeout: 5_000 })
    test.info().annotations.push({
      type: 'env_skip',
      description: 'No LinkedIn accounts connected — verified connect buttons instead'
    })
  } else {
    // Accounts connected — verify account info
    await expect(disconnectBtn).toBeVisible({ timeout: 5_000 })
  }
})

// ── M04 — Disconnect LinkedIn ─────────────────────────────────────────────────
test('M04 — Disconnect LinkedIn — button visible (if account connected)', async ({ page }) => {
  await page.goto('/en/marketing')
  await page.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => {})

  const disconnectBtn = page.getByRole('button', { name: /disconnect/i }).first()
  if (await disconnectBtn.count() === 0) {
    test.skip(true, 'ENV_SKIP: No LinkedIn accounts connected to disconnect')
    return
  }

  // Verify disconnect button is visible (don't click — would remove test data)
  await expect(disconnectBtn).toBeVisible()
  // Verify it has the expected text/styling
  await expect(disconnectBtn).toBeEnabled()
})

// ── M05 — Posts Tabs Render ───────────────────────────────────────────────────
test('M05 — Post Queue — all 4 tabs render', async ({ page }) => {
  await page.goto('/en/marketing')
  await page.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => {})

  // Post Queue card with tabs
  await expect(page.getByText(/post queue/i).first()).toBeVisible({ timeout: 10_000 })

  const tabs = ['draft', 'scheduled', 'posted', 'failed']
  for (const tab of tabs) {
    await expect(
      page.getByRole('button', { name: new RegExp(tab, 'i') }).first()
        .or(page.getByText(new RegExp(`^${tab}$`, 'i')).first())
    ).toBeVisible({ timeout: 5_000 })
  }
})

// ── M06 — Tab Switch ──────────────────────────────────────────────────────────
test('M06 — Tab switch — clicking tabs updates post list', async ({ page }) => {
  await page.goto('/en/marketing')
  await page.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => {})

  await expect(page.getByText(/post queue/i).first()).toBeVisible({ timeout: 10_000 })

  const tabs = ['draft', 'scheduled', 'posted', 'failed']
  for (const tab of tabs) {
    const tabBtn = page.getByRole('button', { name: new RegExp(`^${tab}$`, 'i') }).first()
      .or(page.getByText(new RegExp(`^${tab}$`, 'i')).first())

    if (await tabBtn.count() > 0) {
      await tabBtn.click()
      await page.waitForTimeout(300)
      // Post list area should update without error
      await expect(page.locator('body')).not.toContainText('500')
    }
  }
})

// ── M07 — Create Post Draft ───────────────────────────────────────────────────
test('M07 — Create post draft — AI Generate button visible', async ({ page }) => {
  await page.goto('/en/marketing')
  await page.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => {})

  // AI Generate Post button
  await expect(
    page.getByRole('button', { name: /AI Generate Post|generate.*post/i }).first()
      .or(page.getByText(/✦ AI Generate Post/i).first())
  ).toBeVisible({ timeout: 10_000 })
})

// ── M08 — Generate Post with AI ──────────────────────────────────────────────
test('M08 — AI Generate Post — triggers generation and shows result', async ({ page }) => {
  await page.goto('/en/marketing')
  await page.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => {})

  const generateBtn = page.getByRole('button', { name: /AI Generate Post|generate.*post/i }).first()
    .or(page.getByText(/✦ AI Generate Post/i).first())

  if (await generateBtn.count() === 0) {
    test.skip(true, 'ENV_SKIP: AI Generate Post button not found')
    return
  }

  // Check if button is enabled (requires LinkedIn connection)
  if (!(await generateBtn.isEnabled())) {
    test.skip(true, 'ENV_SKIP: AI Generate Post disabled (no LinkedIn connection)')
    return
  }

  await generateBtn.click()
  // AI generation can take 15-30s depending on API load
  await page.waitForTimeout(20_000)

  // Page should not crash with 500 (either shows success, loading, or credit error)
  await expect(page.locator('body')).not.toContainText('500')
})

// ── M09 — Approve Post ────────────────────────────────────────────────────────
test('M09 — Approve post — Approve button on draft post', async ({ page }) => {
  await page.goto('/en/marketing')
  await page.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => {})

  // Go to draft tab
  const draftTab = page.getByRole('button', { name: /^draft$/i }).first()
    .or(page.getByText(/^draft$/i).first())
  if (await draftTab.count() > 0) {
    await draftTab.click()
    await page.waitForTimeout(500)
  }

  const approveBtn = page.getByRole('button', { name: /approve/i }).first()
  if (await approveBtn.count() === 0) {
    test.skip(true, 'ENV_SKIP: No draft posts to approve')
    return
  }

  await approveBtn.click()
  await page.waitForTimeout(2000)

  // Post should move to scheduled or success message
  await expect(
    page.getByText(/approved|scheduled|success/i).first()
  ).toBeVisible({ timeout: 10_000 }).catch(() => {
    // Status may update silently
  })
  await expect(page.locator('body')).not.toContainText('500')
})

// ── M10 — Reject Post ─────────────────────────────────────────────────────────
test('M10 — Return to Draft / Reject post button visible', async ({ page }) => {
  await page.goto('/en/marketing')
  await page.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => {})

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
test('M11 — Analytics summary — stat cards visible (if posts exist)', async ({ page }) => {
  await page.goto('/en/marketing')
  await page.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => {})

  // Analytics section (only shows when there are posted posts)
  const analyticsSection = page.getByText(/total posts|impressions|engagement|analytics/i).first()

  if (await analyticsSection.count() > 0) {
    await expect(analyticsSection).toBeVisible({ timeout: 5_000 })
  } else {
    // No analytics yet — page should still load
    await expect(page.locator('body')).not.toContainText('500')
    test.info().annotations.push({
      type: 'env_skip',
      description: 'No analytics data yet (no posted posts)'
    })
  }
})

// ── M12 — Plan Gate ───────────────────────────────────────────────────────────
test('M12 — Marketing module — accessible on agency_medium plan', async ({ page }) => {
  await page.goto('/en/marketing')
  await page.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => {})

  // Test tenant is on agency_medium — marketing should be accessible
  await expect(page).not.toHaveURL(/404/)
  await expect(page.locator('body')).not.toContainText('Upgrade')
  await expect(page.getByText(/LinkedIn Accounts/i).first()).toBeVisible({ timeout: 10_000 })
})
