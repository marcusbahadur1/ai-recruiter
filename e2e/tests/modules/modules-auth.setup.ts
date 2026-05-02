/**
 * modules-auth.setup.ts
 *
 * Logs in as both the test tenant and super admin, saves auth state files:
 *   .auth/test-user.json       — used by modules 01–09
 *   .auth/super-admin.json     — used by module 10
 */
import { test as setup, expect } from '@playwright/test'
import * as fs from 'fs'
import * as path from 'path'

const TEST_EMAIL    = process.env.PROD_TEST_EMAIL    ?? ''
const TEST_PASS     = process.env.PROD_TEST_PASSWORD ?? ''
const ADMIN_EMAIL   = process.env.PROD_SUPER_ADMIN_EMAIL    ?? ''
const ADMIN_PASS    = process.env.PROD_SUPER_ADMIN_PASSWORD ?? ''

const AUTH_DIR      = path.join(__dirname, '../../.auth')
const USER_FILE     = path.join(AUTH_DIR, 'test-user.json')
const ADMIN_FILE    = path.join(AUTH_DIR, 'super-admin.json')

setup.describe.configure({ mode: 'serial' })

setup('login as test tenant', async ({ page }) => {
  if (!TEST_EMAIL || !TEST_PASS) {
    throw new Error('PROD_TEST_EMAIL and PROD_TEST_PASSWORD must be set in e2e/.env.production')
  }

  await page.goto('/en/login')
  await expect(page).toHaveURL(/login/, { timeout: 15_000 })

  await page.locator('input[type="email"]').fill(TEST_EMAIL)
  await page.locator('input[type="password"]').fill(TEST_PASS)
  await page.getByRole('button', { name: /sign in|log in/i }).click()

  await page.waitForURL((url) => !url.pathname.includes('/login'), { timeout: 20_000 })

  fs.mkdirSync(AUTH_DIR, { recursive: true })
  await page.context().storageState({ path: USER_FILE })
  console.log(`Test user auth saved: ${TEST_EMAIL}`)
})

setup('login as super admin', async ({ page }) => {
  if (!ADMIN_EMAIL || !ADMIN_PASS) {
    throw new Error('PROD_SUPER_ADMIN_EMAIL and PROD_SUPER_ADMIN_PASSWORD must be set in e2e/.env.production')
  }

  await page.goto('/en/login')
  await expect(page).toHaveURL(/login/, { timeout: 15_000 })

  await page.locator('input[type="email"]').fill(ADMIN_EMAIL)
  await page.locator('input[type="password"]').fill(ADMIN_PASS)
  await page.getByRole('button', { name: /sign in|log in/i }).click()

  await page.waitForURL((url) => !url.pathname.includes('/login'), { timeout: 20_000 })

  fs.mkdirSync(AUTH_DIR, { recursive: true })
  await page.context().storageState({ path: ADMIN_FILE })
  console.log(`Super admin auth saved: ${ADMIN_EMAIL}`)
})
