/**
 * 07-public-routes.spec.ts
 *
 * Verifies public-facing routes (no auth needed) respond correctly.
 */
import { test, expect } from '@playwright/test'

test.describe('Public routes', () => {
  test('subscribe page loads without auth', async ({ browser }) => {
    const ctx  = await browser.newContext()   // no auth state
    const page = await ctx.newPage()
    await page.goto('/subscribe')
    await expect(page.locator('text=Recruiter').first()).toBeVisible({ timeout: 10_000 })
    await ctx.close()
  })

  test('invalid test token returns a usable page (not 500)', async ({ browser }) => {
    const ctx  = await browser.newContext()
    const page = await ctx.newPage()
    await page.goto('/test/00000000-0000-0000-0000-000000000000/invalid-token')
    // Should show an error/expired message, not crash
    await expect(page.locator('body')).not.toBeEmpty()
    const bodyText = await page.locator('body').textContent()
    expect(bodyText).not.toContain('Application error')   // Next.js crash boundary text
    await ctx.close()
  })

  test('unsubscribe page loads without auth', async ({ browser }) => {
    const ctx  = await browser.newContext()
    const page = await ctx.newPage()
    await page.goto('/unsubscribe/00000000-0000-0000-0000-000000000000')
    await expect(page.locator('body')).not.toBeEmpty()
    await ctx.close()
  })

  test('billing success page loads', async ({ browser }) => {
    const ctx  = await browser.newContext()
    const page = await ctx.newPage()
    await page.goto('/billing/success')
    await expect(page.locator('body')).not.toBeEmpty()
    await ctx.close()
  })
})
