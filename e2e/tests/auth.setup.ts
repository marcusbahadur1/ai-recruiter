/**
 * auth.setup.ts
 *
 * Logs in with the staging test account once and saves browser storage state
 * to .auth/user.json so all smoke tests can reuse it without re-logging in.
 *
 * Required env vars:
 *   STAGING_URL          — e.g. https://staging.app.airecruiterz.com
 *   STAGING_TEST_EMAIL   — pre-created test tenant admin email
 *   STAGING_TEST_PASSWORD
 */
import { test as setup, expect } from '@playwright/test'
import * as fs from 'fs'
import * as path from 'path'

const AUTH_FILE = path.join(__dirname, '../.auth/user.json')

setup('authenticate', async ({ page }) => {
  const email    = process.env.STAGING_TEST_EMAIL    ?? ''
  const password = process.env.STAGING_TEST_PASSWORD ?? ''

  if (!email || !password) {
    throw new Error(
      'STAGING_TEST_EMAIL and STAGING_TEST_PASSWORD must be set.\n' +
      'Add them as GitHub secrets or export them locally before running.'
    )
  }

  await page.goto('/login')
  await expect(page).toHaveURL(/login/)

  await page.locator('input[type="email"]').fill(email)
  await page.locator('input[type="password"]').fill(password)
  await page.getByRole('button', { name: /sign in|log in/i }).click()

  // Wait until we land on the dashboard (not login)
  await page.waitForURL((url) => !url.pathname.includes('/login'), { timeout: 15_000 })

  // Save auth state
  fs.mkdirSync(path.dirname(AUTH_FILE), { recursive: true })
  await page.context().storageState({ path: AUTH_FILE })
})
