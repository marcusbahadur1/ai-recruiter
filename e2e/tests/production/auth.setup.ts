/**
 * auth.setup.ts (production)
 *
 * Logs in with the production test account and saves browser storage state
 * to .auth/prod-user.json so all production smoke tests can reuse it.
 *
 * Required env vars:
 *   PROD_TEST_EMAIL
 *   PROD_TEST_PASSWORD
 *
 * Set these in e2e/.env.production (gitignored) or export them in your shell.
 */
import { test as setup, expect } from '@playwright/test'
import * as fs from 'fs'
import * as path from 'path'

const AUTH_FILE = path.join(__dirname, '../../.auth/prod-user.json')

setup('authenticate against production', async ({ page }) => {
  const email    = process.env.PROD_TEST_EMAIL    ?? ''
  const password = process.env.PROD_TEST_PASSWORD ?? ''

  if (!email || !password) {
    throw new Error(
      'PROD_TEST_EMAIL and PROD_TEST_PASSWORD must be set.\n' +
      'Add them to e2e/.env.production or export them in your shell.'
    )
  }

  await page.goto('/en/login')
  await expect(page).toHaveURL(/login/, { timeout: 15_000 })

  await page.locator('input[type="email"]').fill(email)
  await page.locator('input[type="password"]').fill(password)
  await page.getByRole('button', { name: /sign in|log in/i }).click()

  // Wait until we land on the dashboard (not on a login or auth page)
  await page.waitForURL((url) => !url.pathname.includes('/login'), { timeout: 20_000 })

  fs.mkdirSync(path.dirname(AUTH_FILE), { recursive: true })
  await page.context().storageState({ path: AUTH_FILE })
})
