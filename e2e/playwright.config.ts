import { defineConfig, devices } from '@playwright/test'

const BASE_URL = process.env.STAGING_URL ?? 'http://localhost:3000'
const API_URL  = process.env.STAGING_API_URL ?? 'http://localhost:8000'

export default defineConfig({
  testDir: './tests',
  timeout: 30_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,     // smoke tests run sequentially to avoid auth races
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? 'github' : 'list',

  use: {
    baseURL: BASE_URL,
    extraHTTPHeaders: { 'x-e2e-test': '1' },
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    trace: 'retain-on-failure',
  },

  projects: [
    // Setup: log in once, save auth state
    {
      name: 'setup',
      testMatch: /.*\.setup\.ts/,
    },
    // Smoke tests run with saved auth state
    {
      name: 'smoke-chromium',
      use: {
        ...devices['Desktop Chrome'],
        storageState: '.auth/user.json',
      },
      dependencies: ['setup'],
      testMatch: /smoke\/.+\.spec\.ts/,
    },
  ],

  // Export these so test files can import them
  globalSetup: undefined,
})

export { BASE_URL, API_URL }
