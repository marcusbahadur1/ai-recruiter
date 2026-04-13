/**
 * 02-auth.spec.ts
 *
 * Verifies the login/logout cycle and that unauthenticated users
 * are redirected to /login.
 */
import { test, expect } from '@playwright/test'

// These tests verify the auth state saved by auth.setup.ts is working
test.describe('Authentication', () => {
  test('dashboard is accessible with saved auth state', async ({ page }) => {
    await page.goto('/')
    // Should NOT be redirected to login
    await expect(page).not.toHaveURL(/login/)
    // Should show dashboard content
    await expect(page.locator('text=Dashboard').first()).toBeVisible({ timeout: 10_000 })
  })

  test('unauthenticated browser is redirected to login', async ({ browser }) => {
    // Use a fresh context with no auth state
    const ctx  = await browser.newContext()
    const page = await ctx.newPage()
    await page.goto('/')
    await page.waitForURL(/login/, { timeout: 10_000 })
    await expect(page).toHaveURL(/login/)
    await ctx.close()
  })

  test('login page renders email + password fields', async ({ browser }) => {
    const ctx  = await browser.newContext()
    const page = await ctx.newPage()
    await page.goto('/login')
    await expect(page.getByLabel(/email/i)).toBeVisible()
    await expect(page.getByLabel(/password/i)).toBeVisible()
    await expect(page.getByRole('button', { name: /sign in|log in/i })).toBeVisible()
    await ctx.close()
  })

  test('signup page renders without errors', async ({ browser }) => {
    const ctx  = await browser.newContext()
    const page = await ctx.newPage()
    await page.goto('/signup')
    // Should show some form fields — not a blank page or 500
    await expect(page.locator('input').first()).toBeVisible({ timeout: 8_000 })
    await ctx.close()
  })
})
