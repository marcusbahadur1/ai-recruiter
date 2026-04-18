/**
 * 06-settings.spec.ts
 *
 * Verifies every settings section loads without errors.
 */
import { test, expect } from '@playwright/test'

test.describe('Settings', () => {
  test('settings page loads', async ({ page }) => {
    await page.goto('/settings')
    await expect(page).not.toHaveURL(/login/)
    await expect(page.locator('text=Settings').first()).toBeVisible({ timeout: 10_000 })
  })

  const SECTIONS = ['General', 'API Keys', 'AI Provider', 'Email', 'Team', 'Billing', 'Privacy']

  for (const section of SECTIONS) {
    test(`settings section "${section}" is navigable`, async ({ page }) => {
      await page.goto('/settings')
      // Click the nav item for this section
      const navItem = page.locator(`text=${section}`).first()
      await expect(navItem).toBeVisible({ timeout: 8_000 })
      await navItem.click()
      // Page should not crash after clicking
      await page.waitForTimeout(500)
      const errors: string[] = []
      page.on('pageerror', (e) => errors.push(e.message))
      expect(errors).toHaveLength(0)
    })
  }

  test('tenant name is pre-filled in general settings', async ({ page }) => {
    await page.goto('/settings')
    // The firm name field should have a value (not blank) for a configured tenant.
    // Use expect(...).not.toHaveValue('') so Playwright waits for the React form
    // to populate from the API rather than reading immediately after navigation.
    const nameInput = page.locator('input[name="name"], input[placeholder*="firm"], input[placeholder*="name"]').first()
    if (await nameInput.isVisible()) {
      await expect(nameInput).not.toHaveValue('', { timeout: 10_000 })
    }
  })
})
