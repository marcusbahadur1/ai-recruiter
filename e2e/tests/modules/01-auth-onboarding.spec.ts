/**
 * Module 01 — Auth & Onboarding
 * Tests: A01–A10
 */
import * as path from 'path'
import { test, expect } from '@playwright/test'

const API_URL      = (process.env.PROD_API_URL ?? 'https://airecruiterz-api.fly.dev').replace(/\/$/, '')
const SUPABASE_URL = (process.env.SUPABASE_URL ?? 'https://vigtvsdwbkspkqohvjna.supabase.co').replace(/\/$/, '')
const SERVICE_KEY  = process.env.SUPABASE_SERVICE_ROLE_KEY ?? process.env.SUPABASE_SERVICE_KEY ?? ''
const TEST_EMAIL   = process.env.PROD_TEST_EMAIL    ?? ''
const TEST_PASS    = process.env.PROD_TEST_PASSWORD ?? ''

const ts           = Date.now()
const SIGNUP_EMAIL = `e2emod01+${ts}@airecruiterz.com`
const SIGNUP_PASS  = `E2eTest${ts}!`

// ── A01 — Sign Up ─────────────────────────────────────────────────────────────
test('A01 — Sign up new account', async ({ page }) => {
  const firmName = `E2E Test Firm ${ts}`

  const res = await fetch(`${API_URL}/api/v1/auth/signup`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email: SIGNUP_EMAIL, password: SIGNUP_PASS, firm_name: firmName }),
  })
  const body = await res.json()
  // Skip gracefully if DB circuit breaker is open (transient Supabase infrastructure issue)
  if (res.status === 500 && JSON.stringify(body).includes('ECIRCUITBREAKER')) {
    test.skip(true, 'ENV_SKIP: DB circuit breaker open — Supabase temporarily blocking new connections')
    return
  }
  expect(res.status, `Signup API failed: ${JSON.stringify(body)}`).toBe(201)
  const userId: string = body.user_id
  expect(userId, 'Signup response missing user_id').toBeTruthy()

  // Confirm email via Supabase admin API
  const confirmRes = await fetch(`${SUPABASE_URL}/auth/v1/admin/users/${userId}`, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${SERVICE_KEY}`,
      'apikey': SERVICE_KEY,
    },
    body: JSON.stringify({ email_confirm: true }),
  })
  expect(confirmRes.status, `Email confirm failed: ${await confirmRes.text()}`).toBe(200)

  // Login via browser
  await page.goto('/en/login')
  await page.locator('input[type="email"]').fill(SIGNUP_EMAIL)
  await page.locator('input[type="password"]').fill(SIGNUP_PASS)
  await page.getByRole('button', { name: /sign in|log in/i }).click()
  await page.waitForURL((url) => !url.pathname.includes('/login'), { timeout: 20_000 })

  // Verify Supabase session exists
  const token = await page.evaluate(() => {
    for (let i = 0; i < localStorage.length; i++) {
      const k = localStorage.key(i)!
      if (k.startsWith('sb-') && k.endsWith('-auth-token')) {
        return JSON.parse(localStorage.getItem(k)!).access_token
      }
    }
    return null
  })
  expect(token, 'No Supabase session token found').toBeTruthy()

  // Verify tenant row was created
  const settingsRes = await fetch(`${API_URL}/api/v1/tenants/me`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  expect(settingsRes.status).toBe(200)
  const settings = await settingsRes.json()
  expect(settings.name).toBe(firmName)
})

// ── A02 — Subscribe Page ──────────────────────────────────────────────────────
test('A02 — Subscribe page — plan cards render', async ({ page }) => {
  await page.goto('/en/subscribe')
  await expect(page).toHaveURL(/subscribe/, { timeout: 15_000 })

  // Heading "Choose your plan"
  await expect(page.getByText(/choose your plan/i).first()).toBeVisible({ timeout: 10_000 })

  // Plan names visible
  await expect(page.getByText(/recruiter/i).first()).toBeVisible()

  // "Start Plan" buttons present (actual button text in the app)
  const startPlanBtns = page.getByRole('button', { name: /start plan/i })
  await expect(startPlanBtns.first()).toBeVisible({ timeout: 10_000 })
  expect(await startPlanBtns.count()).toBeGreaterThanOrEqual(3)
})

// ── A03 — Quick Start Wizard ──────────────────────────────────────────────────
test('A03 — Quick Start wizard renders', async ({ page }) => {
  await page.goto('/en/quickstart')

  // Wait for the page to settle (API call for steps)
  await page.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => {})

  // The heading is a div (not an h element) — use text matcher
  const heading = page.getByText(/quick start|you're all set/i)
  await expect(heading.first()).toBeVisible({ timeout: 15_000 })

  // Progress indicator "X / Y complete"
  await expect(page.getByText(/\d+\s*\/\s*\d+\s*complete/i).first()).toBeVisible({ timeout: 10_000 })

  // Refresh button
  await expect(page.getByRole('button', { name: /↻ refresh|refresh status/i }).first()).toBeVisible()
})

// ── A04 — Login Valid ─────────────────────────────────────────────────────────
test('A04 — Login with valid credentials → dashboard', async ({ page }) => {
  await page.goto('/en/login')
  await page.locator('input[type="email"]').fill(TEST_EMAIL)
  await page.locator('input[type="password"]').fill(TEST_PASS)
  await page.getByRole('button', { name: /sign in|log in/i }).click()
  await page.waitForURL((url) => !url.pathname.includes('/login'), { timeout: 20_000 })

  await expect(page.locator('body')).not.toContainText('Internal Server Error')
})

// ── A05 — Login Wrong Password ────────────────────────────────────────────────
test('A05 — Login wrong password → error banner', async ({ page }) => {
  await page.goto('/en/login')
  await page.locator('input[type="email"]').fill(TEST_EMAIL)
  await page.locator('input[type="password"]').fill('WrongPass999!')
  await page.getByRole('button', { name: /sign in|log in/i }).click()

  await expect(page).toHaveURL(/login/, { timeout: 10_000 })
  const errorEl = page.locator('[class*="error"], [role="alert"], [class*="alert"]')
  await expect(errorEl.first()).toBeVisible({ timeout: 10_000 })
  await expect(page.getByRole('button', { name: /sign in|log in/i })).toBeEnabled({ timeout: 5_000 })
})

// ── A06 — Login Non-existent Email ───────────────────────────────────────────
test('A06 — Login non-existent email → error banner', async ({ page }) => {
  await page.goto('/en/login')
  await page.locator('input[type="email"]').fill('nobody@doesnotexist.invalid')
  await page.locator('input[type="password"]').fill('AnyPass123!')
  await page.getByRole('button', { name: /sign in|log in/i }).click()

  await expect(page).toHaveURL(/login/, { timeout: 10_000 })
  const errorEl = page.locator('[class*="error"], [role="alert"], [class*="alert"]')
  await expect(errorEl.first()).toBeVisible({ timeout: 10_000 })
})

// ── A07 — Logout ──────────────────────────────────────────────────────────────
test('A07 — Logout clears session', async ({ page }) => {
  // Login first
  await page.goto('/en/login')
  await page.locator('input[type="email"]').fill(TEST_EMAIL)
  await page.locator('input[type="password"]').fill(TEST_PASS)
  await page.getByRole('button', { name: /sign in|log in/i }).click()
  await page.waitForURL((url) => !url.pathname.includes('/login'), { timeout: 20_000 })

  // Find and click logout
  let logoutEl = page.getByRole('button', { name: /logout|sign out/i })
    .or(page.getByRole('link', { name: /logout|sign out/i }))

  if (await logoutEl.count() === 0) {
    // Try user avatar/menu
    const userMenu = page.locator('[class*="avatar"], [class*="user-menu"]')
    if (await userMenu.count() > 0) {
      await userMenu.first().click()
      await page.waitForTimeout(500)
    }
    logoutEl = page.getByRole('button', { name: /logout|sign out/i })
      .or(page.getByRole('link', { name: /logout|sign out/i }))
  }

  await expect(logoutEl.first()).toBeVisible({ timeout: 5_000 })
  await logoutEl.first().click()

  // Wait for logout to complete and redirect to login
  await page.waitForURL(/login/, { timeout: 15_000 })
  await page.waitForLoadState('networkidle', { timeout: 10_000 }).catch(() => {})
  await page.waitForTimeout(1_000)

  // Dashboard should redirect to login
  await page.goto('/en', { waitUntil: 'networkidle' })
  await expect(page).toHaveURL(/login/, { timeout: 10_000 })
})

// ── A08 — Forgot Password ─────────────────────────────────────────────────────
test('A08 — Forgot password sends email', async ({ page }) => {
  await page.goto('/en/forgot-password')
  await expect(page).not.toHaveURL(/404|500/)

  await page.locator('input[type="email"]').fill(TEST_EMAIL)
  await page.getByRole('button', { name: /send reset link/i }).click()

  // "Check your email" success state — use .first() to avoid strict-mode violation
  await expect(
    page.getByText('Check your email').first()
  ).toBeVisible({ timeout: 15_000 })
})

// ── A09 & A10 run with NO existing auth session ───────────────────────────────
test.describe('Password reset flows (fresh context)', () => {
  test.use({ storageState: { cookies: [], origins: [] } })

  // ── A09 — Reset Password Invalid Token ────────────────────────────────────
  test('A09 — Reset password invalid token → error state', async ({ page }) => {
    await page.goto('/en/reset-password#access_token=invalid-token-xyz&type=recovery')

    // Supabase getSession() returns null → error state renders
    await expect(
      page.getByText(/invalid or has expired/i).first()
    ).toBeVisible({ timeout: 15_000 })

    // "Request a new reset link" link
    await expect(
      page.getByRole('link', { name: /request a new reset link/i })
    ).toBeVisible({ timeout: 5_000 })
  })

  // ── A10 — Reset Password Valid Token ──────────────────────────────────────
  test('A10 — Reset password valid token → set new password → login', async ({ page }) => {
    if (!SERVICE_KEY) {
      test.skip(true, 'SUPABASE_SERVICE_ROLE_KEY not set — skipping A10')
      return
    }

    // Generate reset link via Supabase admin API
    const genRes = await fetch(`${SUPABASE_URL}/auth/v1/admin/generate_link`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${SERVICE_KEY}`,
        'apikey': SERVICE_KEY,
      },
      body: JSON.stringify({
        type: 'recovery',
        email: TEST_EMAIL,
        options: { redirectTo: 'https://app.airecruiterz.com/en/reset-password' },
      }),
    })
    const genBody = await genRes.json()
    // Supabase admin API returns action_link at top level
    const resetUrl: string = genBody?.action_link ?? genBody?.properties?.action_link ?? ''
    expect(resetUrl, `generateLink failed: ${JSON.stringify(genBody)}`).toBeTruthy()

    // Navigate to the reset URL — Supabase verifies token and redirects to our app with hash
    await page.goto(resetUrl)
    // Wait for Supabase to redirect to the app (may land on /en# with access_token hash)
    await page.waitForURL(/app\.airecruiterz\.com\/en/, { timeout: 20_000 })

    // Capture the access_token from the current URL hash
    const currentUrl = page.url()
    const hashMatch = currentUrl.match(/#(.+)/)
    const hash = hashMatch ? hashMatch[1] : ''
    expect(hash, 'No hash/token in redirect URL').toBeTruthy()

    // Navigate directly to reset-password with the token hash
    await page.goto(`/en/reset-password#${hash}`)

    // Password form should appear (Supabase session established via URL token)
    await expect(
      page.locator('input[type="password"]').first()
    ).toBeVisible({ timeout: 20_000 })

    // Use a different temp password (Supabase rejects same-as-current)
    const tempPass = `E2eReset${ts}!`
    const inputs = page.locator('input[type="password"]')
    await inputs.nth(0).fill(tempPass)
    if (await inputs.count() > 1) {
      await inputs.nth(1).fill(tempPass)
    }

    await page.getByRole('button', { name: /set new password/i }).click()

    // Should redirect to /en?reset=1 on success
    await page.waitForURL(/reset=1/, { timeout: 20_000 })

    // Verify login works with new password
    await page.goto('/en/login')
    await page.locator('input[type="email"]').fill(TEST_EMAIL)
    await page.locator('input[type="password"]').fill(tempPass)
    await page.getByRole('button', { name: /sign in|log in/i }).click()
    await page.waitForURL((url) => !url.pathname.includes('/login'), { timeout: 20_000 })

    // Restore original password using another generateLink cycle
    const genRes2 = await fetch(`${SUPABASE_URL}/auth/v1/admin/generate_link`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${SERVICE_KEY}`,
        'apikey': SERVICE_KEY,
      },
      body: JSON.stringify({
        type: 'recovery',
        email: TEST_EMAIL,
        options: { redirectTo: 'https://app.airecruiterz.com/en/reset-password' },
      }),
    })
    const genBody2 = await genRes2.json()
    const resetUrl2: string = genBody2?.action_link ?? ''
    if (resetUrl2) {
      await page.goto(resetUrl2)
      await page.waitForURL(/app\.airecruiterz\.com\/en/, { timeout: 20_000 })
      const currentUrl2 = page.url()
      const hashMatch2 = currentUrl2.match(/#(.+)/)
      if (hashMatch2) {
        await page.goto(`/en/reset-password#${hashMatch2[1]}`)
        await expect(page.locator('input[type="password"]').first()).toBeVisible({ timeout: 20_000 })
        const inputs2 = page.locator('input[type="password"]')
        await inputs2.nth(0).fill(TEST_PASS)
        if (await inputs2.count() > 1) await inputs2.nth(1).fill(TEST_PASS)
        await page.getByRole('button', { name: /set new password/i }).click()
        // Supabase may reject if tempPass == TEST_PASS, which it isn't — so this should succeed
        await page.waitForURL(/reset=1|en(\?|#|$)/, { timeout: 20_000 }).catch(() => {})
      }
    }
  })
})

// ── Re-authenticate after module 01 ──────────────────────────────────────────
// A07 (signOut) and A10 (password reset) revoke Supabase sessions server-side.
// Re-login with original credentials and save fresh tokens so modules 02–10
// start with a valid session (storageState is loaded fresh per test context).
test.afterAll(async ({ browser }) => {
  if (!TEST_EMAIL || !TEST_PASS) return
  const ctx = await browser.newContext()
  const pg  = await ctx.newPage()
  try {
    await pg.goto(process.env.PROD_URL ?? 'https://app.airecruiterz.com/en/login')
    await pg.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => {})
    // If redirected away from login (already authed), go directly
    if (!pg.url().includes('/login')) {
      await pg.goto((process.env.PROD_URL ?? 'https://app.airecruiterz.com') + '/en/login')
      await pg.waitForLoadState('networkidle', { timeout: 10_000 }).catch(() => {})
    }
    await pg.locator('input[type="email"]').fill(TEST_EMAIL)
    await pg.locator('input[type="password"]').fill(TEST_PASS)
    await pg.getByRole('button', { name: /sign in|log in/i }).click()
    await pg.waitForURL((url) => !url.pathname.includes('/login'), { timeout: 20_000 })
    await ctx.storageState({ path: path.join(__dirname, '../../.auth/test-user.json') })
  } catch (e) {
    console.warn('⚠️  Module 01 afterAll re-auth failed:', e)
  } finally {
    await ctx.close()
  }
})
