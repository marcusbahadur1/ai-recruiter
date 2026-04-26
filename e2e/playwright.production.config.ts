/**
 * playwright.production.config.ts
 *
 * Run the production smoke suite against app.airecruiterz.com.
 *
 * Required env vars (export or add to e2e/.env.production):
 *   PROD_TEST_EMAIL      — email of a test account on production
 *   PROD_TEST_PASSWORD   — its password
 *
 * Optional overrides:
 *   PROD_URL     — default: https://app.airecruiterz.com
 *   PROD_API_URL — default: https://airecruiterz-api.fly.dev
 *
 * Usage:
 *   npm run prod:smoke          — all production smoke tests
 *   npm run prod:smoke:headed   — same, with a visible browser
 *   npm run prod:chat           — full job-via-chat flow only (costs 1 credit)
 */
import { defineConfig, devices } from '@playwright/test'
import * as dotenv from 'dotenv'
import * as path from 'path'

// Load .env.production if present next to this config file
dotenv.config({ path: path.join(__dirname, '.env.production') })

const BASE_URL = (process.env.PROD_URL ?? 'https://app.airecruiterz.com').replace(/\/$/, '')
const API_URL  = (process.env.PROD_API_URL ?? 'https://airecruiterz-api.fly.dev').replace(/\/$/, '')

export default defineConfig({
  testDir: './tests/production',
  timeout: 60_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  retries: 1,
  reporter: process.env.CI ? 'github' : 'list',

  use: {
    baseURL: BASE_URL,
    extraHTTPHeaders: { 'x-e2e-test': '1' },
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    trace: 'retain-on-failure',
  },

  projects: [
    // Step 1 — log in once and save auth state
    {
      name: 'prod-setup',
      testMatch: /auth\.setup\.ts/,
    },

    // Step 2 — smoke tests (fast, no credits consumed)
    {
      name: 'prod-smoke',
      use: {
        ...devices['Desktop Chrome'],
        storageState: '.auth/prod-user.json',
      },
      dependencies: ['prod-setup'],
      testMatch: /smoke\.spec\.ts/,
    },

    // Step 3 — full job-via-chat flow (costs 1 credit — run deliberately)
    {
      name: 'prod-chat',
      use: {
        ...devices['Desktop Chrome'],
        storageState: '.auth/prod-user.json',
      },
      dependencies: ['prod-setup'],
      testMatch: /job-via-chat\.spec\.ts/,
    },
  ],
})

export { BASE_URL, API_URL }
