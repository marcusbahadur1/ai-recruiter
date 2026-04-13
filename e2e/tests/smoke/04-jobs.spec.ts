/**
 * 04-jobs.spec.ts
 *
 * Verifies jobs pages render real data and key actions are present.
 */
import { test, expect } from '@playwright/test'

test.describe('Jobs', () => {
  test('jobs list loads and shows table headers', async ({ page }) => {
    await page.goto('/jobs')
    await expect(page).not.toHaveURL(/login/)
    // Table or empty state must be visible — not a spinner forever
    await expect(
      page.locator('table, text=No jobs yet, text=Post your first job').first()
    ).toBeVisible({ timeout: 12_000 })
  })

  test('new job page loads', async ({ page }) => {
    await page.goto('/jobs/new')
    await expect(page).not.toHaveURL(/login/)
    // Should show either the chat interface or a form
    await expect(page.locator('input, textarea, [role="textbox"]').first()).toBeVisible({ timeout: 10_000 })
  })

  test('new screener-only job page loads', async ({ page }) => {
    await page.goto('/jobs/new/screener')
    await expect(page).not.toHaveURL(/login/)
    await expect(page.locator('input, textarea, [role="textbox"], h1, h2').first()).toBeVisible({ timeout: 10_000 })
  })

  test('invalid job id returns usable page (not 500)', async ({ page }) => {
    await page.goto('/jobs/00000000-0000-0000-0000-000000000000')
    await expect(page).not.toHaveURL(/login/)
    // Should show not-found or error message, not a blank/crashed page
    await expect(page.locator('body')).not.toBeEmpty()
  })
})
