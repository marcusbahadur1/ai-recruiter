/**
 * 05-billing.spec.ts
 *
 * Verifies the billing page shows correct plan info and key actions are present.
 * Does NOT complete a Stripe checkout (that would charge a card).
 * Does NOT click "Manage Billing" to completion (that redirects off-site).
 */
import { test, expect } from '@playwright/test'

test.describe('Billing page', () => {
  test('billing page loads and shows current plan', async ({ page }) => {
    await page.goto('/billing')
    await expect(page).not.toHaveURL(/login/)
    await expect(page.locator('text=Current Plan').first()).toBeVisible({ timeout: 10_000 })
  })

  test('plan comparison table is visible', async ({ page }) => {
    await page.goto('/billing')
    await expect(page.locator('text=Compare Plans').first()).toBeVisible({ timeout: 10_000 })
    // All four paid plan names should appear
    for (const planName of ['Recruiter', 'Agency Small', 'Agency Medium', 'Enterprise']) {
      await expect(page.locator(`text=${planName}`).first()).toBeVisible()
    }
  })

  test('subscribed tenant sees Manage Billing button', async ({ page }) => {
    await page.goto('/billing')
    // The test account must be on a paid plan (recruiter+)
    // If it is, the Manage Billing button should be visible
    const planText = await page.locator('text=Current Plan').locator('..').textContent()
    const isTrial  = planText?.toLowerCase().includes('trial')
    if (!isTrial) {
      await expect(page.getByRole('button', { name: /manage billing/i })).toBeVisible()
    } else {
      // Trial users see subscribe/view plans link
      await expect(
        page.getByRole('button', { name: /view plans|subscribe/i })
          .or(page.getByRole('link', { name: /view plans|subscribe/i }))
          .first()
      ).toBeVisible()
    }
  })

  test('subscribe page renders plan cards', async ({ page }) => {
    await page.goto('/subscribe')
    await expect(page.locator('text=Recruiter').first()).toBeVisible({ timeout: 10_000 })
    await expect(page.locator('text=$499').first()).toBeVisible()
  })
})
