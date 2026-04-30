/**
 * playwright.chat.config.ts
 *
 * Runs the AI Chat / Talent Scout test suite against production.
 * Uses the fixed test account (PROD_TEST_EMAIL / PROD_TEST_PASSWORD) rather than
 * creating throwaway accounts — we want the conversations stored permanently
 * so the user can review them in the chat history UI.
 *
 * Pre-conditions (set in e2e/.env.production):
 *   PROD_TEST_EMAIL      — marcusbahadur1@gmail.com
 *   PROD_TEST_PASSWORD   — see .env.production
 *
 * ⚠️  Enable EMAIL_TEST_MODE in Super Admin before running API tests that
 *     trigger the Scout (T01-T03, T07-T10) — otherwise outreach goes to
 *     real LinkedIn profiles.
 *
 * Usage:
 *   npm run chat:all        — all chat tests  (costs up to 9 credits)
 *   npm run chat:browser    — UI-only tests   (T04, T05, T06 — no credits)
 *   npm run chat:api        — API conv tests  (T01-T03, T07-T10, T12)
 *   npm run chat:headed     — visible browser (any of the above + --headed)
 */
import { defineConfig, devices } from '@playwright/test'
import * as dotenv from 'dotenv'
import * as path from 'path'

dotenv.config({ path: path.join(__dirname, '.env.production') })

const BASE_URL = (process.env.PROD_URL    ?? 'https://app.airecruiterz.com').replace(/\/$/, '')
const API_URL  = (process.env.PROD_API_URL ?? 'https://airecruiterz-api.fly.dev').replace(/\/$/, '')

export default defineConfig({
  testDir: './tests/chat',
  timeout: 10 * 60_000,   // 10 min — AI can be slow
  expect:  { timeout: 30_000 },
  fullyParallel: false,   // chat sessions must be sequential — they share an account
  retries: 0,             // AI responses are non-deterministic; don't auto-retry
  reporter: [
    ['list'],
    ['html', { outputFolder: 'chat-report', open: 'never' }],
  ],

  use: {
    baseURL: BASE_URL,
    extraHTTPHeaders: { 'x-e2e-test': '1' },
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    trace: 'retain-on-failure',
  },

  projects: [
    // Step 1 — log in with the fixed account and save session state
    {
      name: 'chat-auth',
      testMatch: /auth\.setup\.ts/,
    },

    // Step 2a — API-based conversation tests (create real jobs, cost credits)
    {
      name: 'chat-api',
      use: {
        ...devices['Desktop Chrome'],
        storageState: '.auth/chat-user.json',
      },
      dependencies: ['chat-auth'],
      testMatch: /t0[1-3].*\.spec\.ts|t0[7-9].*\.spec\.ts|t10.*\.spec\.ts|t12.*\.spec\.ts/,
    },

    // Step 2b — browser UI tests (no credits consumed)
    {
      name: 'chat-browser',
      use: {
        ...devices['Desktop Chrome'],
        storageState: '.auth/chat-user.json',
      },
      dependencies: ['chat-auth'],
      testMatch: /t0[4-6].*\.spec\.ts/,
    },
  ],
})

export { BASE_URL, API_URL }
