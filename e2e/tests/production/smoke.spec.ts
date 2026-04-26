/**
 * smoke.spec.ts (production)
 *
 * Fast production smoke tests — no credits consumed.
 * Covers: API health, all dashboard pages, key API endpoints.
 *
 * Run with: npm run prod:smoke
 */
import { test, expect } from '@playwright/test'

const API_URL = (process.env.PROD_API_URL ?? 'https://airecruiterz-api.fly.dev').replace(/\/$/, '')

// ── Helper: extract Supabase JWT from localStorage ────────────────────────────
async function getToken(page: Parameters<Parameters<typeof test>[1]>[0]['page']): Promise<string> {
  return page.evaluate(() => {
    for (let i = 0; i < localStorage.length; i++) {
      const key = localStorage.key(i) ?? ''
      if (key.includes('auth-token') || key.includes('supabase')) {
        try {
          const val = JSON.parse(localStorage.getItem(key) ?? '{}')
          const token = val?.access_token ?? val?.session?.access_token ?? ''
          if (token) return token
        } catch { /* skip */ }
      }
    }
    return ''
  }) as Promise<string>
}

// ── API health ────────────────────────────────────────────────────────────────
test.describe('API health', () => {
  test('GET /health returns ok', async ({ request }) => {
    const res = await request.get(`${API_URL}/health`)
    expect(res.status()).toBe(200)
    const body = await res.json()
    expect(body.status).toBe('ok')
    expect(body.db).toBe('ok')
  })
})

// ── Dashboard pages ───────────────────────────────────────────────────────────
test.describe('Dashboard pages', () => {
  test('home / dashboard loads', async ({ page }) => {
    await page.goto('/')
    // Should redirect to /en or /en/... (locale prefix)
    await expect(page).not.toHaveURL(/login/)
    // Sidebar or main content visible
    await expect(page.locator('nav, main, [data-testid="dashboard"]').first()).toBeVisible({ timeout: 15_000 })
  })

  test('/chat loads and shows input', async ({ page }) => {
    await page.goto('/en/chat')
    await expect(page).not.toHaveURL(/login/)
    // Chat input has no explicit type attribute — match any non-hidden, non-password input
    await expect(page.locator('input:not([type="hidden"]):not([type="password"]), textarea').first()).toBeVisible({ timeout: 15_000 })
  })

  test('/jobs loads', async ({ page }) => {
    await page.goto('/en/jobs')
    await expect(page).not.toHaveURL(/login/)
    // Either a jobs list or "no jobs" empty state — both are valid
    await expect(page.locator('main')).toBeVisible({ timeout: 15_000 })
  })

  test('/candidates loads', async ({ page }) => {
    await page.goto('/en/candidates')
    await expect(page).not.toHaveURL(/login/)
    await expect(page.locator('main')).toBeVisible({ timeout: 15_000 })
  })

  test('/applications loads', async ({ page }) => {
    await page.goto('/en/applications')
    await expect(page).not.toHaveURL(/login/)
    await expect(page.locator('main')).toBeVisible({ timeout: 15_000 })
  })

  test('/settings loads', async ({ page }) => {
    await page.goto('/en/settings')
    await expect(page).not.toHaveURL(/login/)
    await expect(page.locator('main')).toBeVisible({ timeout: 15_000 })
  })

  test('/billing loads', async ({ page }) => {
    await page.goto('/en/billing')
    await expect(page).not.toHaveURL(/login/)
    await expect(page.locator('main')).toBeVisible({ timeout: 15_000 })
  })
})

// ── Key API endpoints ─────────────────────────────────────────────────────────
test.describe('Authenticated API', () => {
  test('GET /tenants/me returns tenant data', async ({ page, request }) => {
    await page.goto('/')
    const token = await getToken(page)
    expect(token, 'Auth token missing — login may have failed').toBeTruthy()

    const res = await request.get(`${API_URL}/api/v1/tenants/me`, {
      headers: { Authorization: `Bearer ${token}` },
    })
    expect(res.status()).toBe(200)
    const body = await res.json()
    expect(body).toHaveProperty('id')
    expect(body).toHaveProperty('plan')
    expect(body).toHaveProperty('credits_remaining')
  })

  test('GET /jobs returns paginated list', async ({ page, request }) => {
    await page.goto('/')
    const token = await getToken(page)

    const res = await request.get(`${API_URL}/api/v1/jobs`, {
      headers: { Authorization: `Bearer ${token}` },
    })
    expect(res.status()).toBe(200)
    const body = await res.json()
    expect(body).toHaveProperty('items')
    expect(Array.isArray(body.items)).toBe(true)
  })

  test('GET /candidates returns paginated list', async ({ page, request }) => {
    await page.goto('/')
    const token = await getToken(page)

    const res = await request.get(`${API_URL}/api/v1/candidates`, {
      headers: { Authorization: `Bearer ${token}` },
    })
    expect(res.status()).toBe(200)
    const body = await res.json()
    expect(body).toHaveProperty('items')
  })

  test('GET /chat-sessions/current returns session or 404', async ({ page, request }) => {
    await page.goto('/')
    const token = await getToken(page)

    const res = await request.get(`${API_URL}/api/v1/chat-sessions/current`, {
      headers: { Authorization: `Bearer ${token}` },
    })
    // 200 = active session, 404 = none yet — both are correct
    expect([200, 404]).toContain(res.status())
  })

  test('/jobs/{id} detail page loads when a job exists', async ({ page, request }) => {
    await page.goto('/')
    const token = await getToken(page)

    const res = await request.get(`${API_URL}/api/v1/jobs?limit=1`, {
      headers: { Authorization: `Bearer ${token}` },
    })
    expect(res.status()).toBe(200)
    const body = await res.json()

    if (body.items.length === 0) {
      test.skip() // No jobs yet — skip rather than fail
      return
    }

    const jobId = body.items[0].id
    await page.goto(`/en/jobs/${jobId}`)
    await expect(page).not.toHaveURL(/login/)
    await expect(page.locator('main')).toBeVisible({ timeout: 15_000 })
  })
})
