import { defineConfig, devices } from '@playwright/test'

export default defineConfig({
  testDir: './scripts',
  timeout: 60_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  retries: 0,
  reporter: 'list',
  use: {
    baseURL: 'https://app.airecruiterz.com',
    screenshot: 'only-on-failure',
    headless: true,
    ...devices['Desktop Chrome'],
  },
})
