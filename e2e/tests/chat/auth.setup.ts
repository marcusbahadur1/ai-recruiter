/**
 * auth.setup.ts (chat tests)
 *
 * Logs in with the fixed production account (PROD_TEST_EMAIL / PROD_TEST_PASSWORD)
 * and saves the browser storage state to .auth/chat-user.json.
 *
 * Unlike the throwaway-account setup used in auth.setup.ts (production smoke suite),
 * this uses a real persistent account so that all test conversations are stored
 * permanently and can be reviewed via the chat history UI.
 */
import { test as setup, expect } from '@playwright/test'
import * as fs from 'fs'
import * as path from 'path'

const AUTH_FILE = path.join(__dirname, '../../.auth/chat-user.json')
const EMAIL     = process.env.PROD_TEST_EMAIL    ?? ''
const PASSWORD  = process.env.PROD_TEST_PASSWORD ?? ''

setup('login with fixed test account', async ({ page }) => {
  if (!EMAIL || !PASSWORD) {
    throw new Error(
      'PROD_TEST_EMAIL and PROD_TEST_PASSWORD must be set in e2e/.env.production'
    )
  }

  await page.goto('/en/login')
  await expect(page).toHaveURL(/login/, { timeout: 15_000 })

  await page.locator('input[type="email"]').fill(EMAIL)
  await page.locator('input[type="password"]').fill(PASSWORD)
  await page.getByRole('button', { name: /sign in|log in/i }).click()

  // Wait until we leave the login page
  await page.waitForURL((url) => !url.pathname.includes('/login'), { timeout: 20_000 })

  fs.mkdirSync(path.dirname(AUTH_FILE), { recursive: true })
  await page.context().storageState({ path: AUTH_FILE })
  console.log(`Logged in as: ${EMAIL}`)
})
