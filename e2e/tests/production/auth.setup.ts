/**
 * auth.setup.ts (production)
 *
 * Creates a fresh throw-away test account on every run:
 *  1. POST /api/v1/auth/signup  → backend creates Supabase user + tenant record
 *  2. PUT /auth/v1/admin/users/{id} → confirm email via Supabase admin API
 *     (bypasses the confirmation email so we don't need a real inbox)
 *  3. Log in via the browser UI → Supabase writes session into localStorage
 *  4. Save browser storage state to .auth/prod-user.json
 *  5. Save user_id to .auth/prod-test-meta.json for the global teardown to delete
 *
 * Required in e2e/.env.production:
 *   SUPABASE_SERVICE_KEY   — service_role key from Supabase project settings
 *
 * Optional overrides:
 *   SUPABASE_URL   — default: https://vigtvsdwbkspkqohvjna.supabase.co
 *   PROD_API_URL   — default: https://airecruiterz-api.fly.dev
 */
import { test as setup, expect } from '@playwright/test'
import * as fs from 'fs'
import * as path from 'path'

const AUTH_FILE      = path.join(__dirname, '../../.auth/prod-user.json')
const META_FILE      = path.join(__dirname, '../../.auth/prod-test-meta.json')

const API_URL        = (process.env.PROD_API_URL  ?? 'https://airecruiterz-api.fly.dev').replace(/\/$/, '')
const SUPABASE_URL   = (process.env.SUPABASE_URL  ?? 'https://vigtvsdwbkspkqohvjna.supabase.co').replace(/\/$/, '')
const SERVICE_KEY    = process.env.SUPABASE_SERVICE_KEY ?? ''

setup('create test account and authenticate', async ({ page }) => {
  if (!SERVICE_KEY) {
    throw new Error(
      'SUPABASE_SERVICE_KEY is required.\n' +
      'Add it to e2e/.env.production (gitignored).\n' +
      'Find it at: Supabase dashboard → Project Settings → API → service_role key'
    )
  }

  // ── 1. Generate unique credentials ─────────────────────────────────────────
  const ts       = Date.now()
  const email    = `e2e+${ts}@airecruiterz.com`
  const password = `E2eTest${ts}!`
  const firmName = `E2E Test Firm ${ts}`

  // ── 2. Create Supabase user + tenant via backend signup endpoint ────────────
  const signupRes  = await fetch(`${API_URL}/api/v1/auth/signup`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password, firm_name: firmName }),
  })
  const signupBody = await signupRes.json()
  expect(signupRes.status, `Signup failed: ${JSON.stringify(signupBody)}`).toBe(201)
  const userId: string = signupBody.user_id
  expect(userId, 'Signup response missing user_id').toBeTruthy()

  // ── 3. Confirm email via Supabase admin API ─────────────────────────────────
  const confirmRes = await fetch(`${SUPABASE_URL}/auth/v1/admin/users/${userId}`, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${SERVICE_KEY}`,
      'apikey': SERVICE_KEY,
    },
    body: JSON.stringify({ email_confirm: true }),
  })
  expect(
    confirmRes.status,
    `Email confirmation failed: ${await confirmRes.text()}`
  ).toBe(200)

  // ── 4. Log in via the browser so Supabase writes session into localStorage ──
  await page.goto('/en/login')
  await expect(page).toHaveURL(/login/, { timeout: 15_000 })

  await page.locator('input[type="email"]').fill(email)
  await page.locator('input[type="password"]').fill(password)
  await page.getByRole('button', { name: /sign in|log in/i }).click()

  await page.waitForURL((url) => !url.pathname.includes('/login'), { timeout: 20_000 })

  // ── 5. Save auth state + metadata for teardown ─────────────────────────────
  fs.mkdirSync(path.dirname(AUTH_FILE), { recursive: true })
  await page.context().storageState({ path: AUTH_FILE })

  fs.writeFileSync(META_FILE, JSON.stringify({ userId, email }))
  console.log(`Test account created: ${email} (user_id: ${userId})`)
})
