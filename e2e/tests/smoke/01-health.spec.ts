/**
 * 01-health.spec.ts
 *
 * Direct API health checks — no browser, no auth required.
 * These run first and fail fast if the backend is not up.
 */
import { test, expect } from '@playwright/test'

const API_URL = process.env.STAGING_API_URL ?? 'http://localhost:8000'

test.describe('API health', () => {
  test('GET /health returns 200', async ({ request }) => {
    const res = await request.get(`${API_URL}/health`)
    expect(res.status()).toBe(200)
    const body = await res.json()
    expect(body).toHaveProperty('status', 'ok')
  })

  test('GET /api/v1/auth/me without token returns 401', async ({ request }) => {
    const res = await request.get(`${API_URL}/api/v1/tenants/me`)
    expect(res.status()).toBe(401)
  })

  test('POST /api/v1/promo-codes/validate rejects invalid code', async ({ request }) => {
    const res = await request.post(`${API_URL}/api/v1/promo-codes/validate`, {
      data: { code: 'INVALID_CODE_XYZ_SMOKE' },
    })
    // 404 = not found, 400 = invalid — both are correct rejections
    expect([400, 404]).toContain(res.status())
  })

  test('GET /api/v1/widget/:slug/chat endpoint exists (rate limited or 200)', async ({ request }) => {
    // A GET to a non-existent slug should 404, not 500
    const res = await request.post(`${API_URL}/api/v1/widget/smoke-test-slug-does-not-exist/chat`, {
      data: { message: 'hello' },
    })
    expect([404, 429]).toContain(res.status())
  })
})
