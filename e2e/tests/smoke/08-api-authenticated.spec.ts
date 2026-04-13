/**
 * 08-api-authenticated.spec.ts
 *
 * Verifies key API endpoints return correct shapes for an authenticated user.
 * Extracts the JWT from browser storage after login and calls the API directly.
 * This is faster than navigating pages and confirms the backend contract.
 */
import { test, expect } from '@playwright/test'

const API_URL = process.env.STAGING_API_URL ?? 'http://localhost:8000'

// Helper: extract the Supabase access token from localStorage
async function getToken(page: ConstructorParameters<typeof import('@playwright/test').Page>[0] extends never ? never : InstanceType<typeof import('@playwright/test')['Page']>): Promise<string> {
  const token = await page.evaluate(() => {
    for (let i = 0; i < localStorage.length; i++) {
      const key = localStorage.key(i) ?? ''
      if (key.includes('auth-token') || key.includes('supabase')) {
        try {
          const val = JSON.parse(localStorage.getItem(key) ?? '{}')
          return val?.access_token ?? val?.session?.access_token ?? ''
        } catch { /* skip */ }
      }
    }
    return ''
  })
  return token as string
}

test.describe('Authenticated API', () => {
  test('GET /tenants/me returns tenant data', async ({ page, request }) => {
    await page.goto('/')
    const token = await getToken(page as never)

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
    const token = await getToken(page as never)

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
    const token = await getToken(page as never)

    const res = await request.get(`${API_URL}/api/v1/candidates`, {
      headers: { Authorization: `Bearer ${token}` },
    })
    expect(res.status()).toBe(200)
    const body = await res.json()
    expect(body).toHaveProperty('items')
  })

  test('GET /chat-sessions/current returns session or 404', async ({ page, request }) => {
    await page.goto('/')
    const token = await getToken(page as never)

    const res = await request.get(`${API_URL}/api/v1/chat-sessions/current`, {
      headers: { Authorization: `Bearer ${token}` },
    })
    // 200 = active session exists, 404 = no session yet — both are correct
    expect([200, 404]).toContain(res.status())
  })

  test('GET /promo-codes returns list', async ({ page, request }) => {
    await page.goto('/')
    const token = await getToken(page as never)

    const res = await request.get(`${API_URL}/api/v1/promo-codes`, {
      headers: { Authorization: `Bearer ${token}` },
    })
    expect(res.status()).toBe(200)
    const body = await res.json()
    expect(body).toHaveProperty('items')
  })

  test('GET /billing/portal requires subscribed plan (200 or 402)', async ({ page, request }) => {
    await page.goto('/')
    const token = await getToken(page as never)

    const res = await request.get(`${API_URL}/api/v1/billing/portal`, {
      headers: { Authorization: `Bearer ${token}` },
    })
    // 200 = URL returned, 402 = not subscribed, 400 = no Stripe customer yet
    expect([200, 400, 402]).toContain(res.status())
  })
})
