/**
 * playwright.modules.config.ts
 *
 * Full 10-module E2E test suite against production (app.airecruiterz.com).
 *
 * Required in e2e/.env.production:
 *   PROD_TEST_EMAIL, PROD_TEST_PASSWORD
 *   PROD_SUPER_ADMIN_EMAIL, PROD_SUPER_ADMIN_PASSWORD
 *   PROD_TEST_TENANT_ID, PROD_TEST_TENANT_SLUG
 *   SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
 *   STRIPE_SECRET_KEY (test mode)
 *
 * Usage:
 *   npx playwright test --config=playwright.modules.config.ts
 *   npx playwright test --config=playwright.modules.config.ts tests/modules/01-auth/
 *   npx playwright test --config=playwright.modules.config.ts --last-failed
 */
import { defineConfig, devices } from '@playwright/test'
import * as dotenv from 'dotenv'
import * as path from 'path'

dotenv.config({ path: path.join(__dirname, '.env.production') })

const BASE_URL = (process.env.PROD_URL ?? 'https://app.airecruiterz.com').replace(/\/$/, '')
const API_URL  = (process.env.PROD_API_URL ?? 'https://airecruiterz-api.fly.dev').replace(/\/$/, '')

export default defineConfig({
  testDir: './tests/modules',
  timeout: 120_000,
  expect: { timeout: 20_000 },
  fullyParallel: false,
  workers: 1,
  retries: 1,
  reporter: [['list'], ['html', { outputFolder: 'results/html-report', open: 'never' }]],

  use: {
    baseURL: BASE_URL,
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    trace: 'retain-on-failure',
  },

  projects: [
    // Auth setup — creates .auth/test-user.json and .auth/super-admin.json
    {
      name: 'modules-setup',
      testMatch: /modules-auth\.setup\.ts/,
    },

    // Modules 01-10 — all depend on auth setup
    {
      name: 'modules',
      use: {
        ...devices['Desktop Chrome'],
        storageState: '.auth/test-user.json',
      },
      dependencies: ['modules-setup'],
      testMatch: /tests\/modules\/.+\.spec\.ts/,
    },
  ],
})

export { BASE_URL, API_URL }
