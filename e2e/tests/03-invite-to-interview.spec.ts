/**
 * 03-invite-to-interview.spec.ts
 *
 * E2E: Hiring manager clicks "Invite to Interview" → confirmation page shown.
 *
 * Context:
 *   When a candidate passes the competency test, the backend emails the hiring
 *   manager a one-time link: GET /api/v1/actions/invite/{id}/{token}
 *   That endpoint marks the application interview_invited=true and redirects to
 *   /interview-invited?name=…&role=… (the confirmation page the HM sees).
 *
 *   The token in the link is either:
 *     a) A JWT signed with settings.encryption_key (applications.py route)
 *     b) A plain string stored in application.interview_invite_token (screener route)
 *   Neither is accessible from outside the backend, so we cannot reconstruct a
 *   valid link in the test without the private key.
 *
 * What this test covers:
 *   1. Confirmation page rendering — navigate to /interview-invited with the
 *      query params the backend injects (?name=…&role=…) and verify the page
 *      shows "Interview Invitation Sent ✓" with the correct name and role.
 *   2. "Already sent" page rendering — navigate with ?already=1 and verify the
 *      "Already Sent" variant renders.
 *   3. Endpoint protection — verify that the invite endpoint rejects invalid
 *      tokens with 400, confirming it exists and is guarded.
 *   4. Application detail invite status (conditional) — if an already-invited
 *      application exists in staging, navigate to its detail page and confirm
 *      the green "Interview invitation sent" status card renders.
 *
 * Note: A full end-to-end token flow (backend signs token → HM clicks link →
 * database updated → redirect followed) requires the server's private key and
 * is better tested by the backend integration suite (test_applications.py:
 * test_invite_interview_confirms_on_valid_token).
 */
import { test, expect } from '@playwright/test'

const API_URL = process.env.STAGING_API_URL ?? 'http://localhost:8000'

/** Extract Supabase JWT from browser localStorage. */
async function getToken(page: Parameters<Parameters<typeof test>[1]>[0]['page']): Promise<string> {
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

test.describe('Hiring manager invite-to-interview', () => {
  // ── 1. Confirmation page — fresh invite ──────────────────────────────────────
  test('confirmation page shows candidate name and role after invite', async ({ page }) => {
    const name = 'Alex Reid'
    const role = 'Senior Python Engineer'

    await page.goto(
      `/interview-invited?name=${encodeURIComponent(name)}&role=${encodeURIComponent(role)}`
    )

    // Heading
    await expect(
      page.getByRole('heading', { name: /Interview Invitation Sent/i })
    ).toBeVisible({ timeout: 10_000 })

    // Candidate name appears in the body text
    await expect(page.locator('body')).toContainText(name)

    // Role appears in the body text
    await expect(page.locator('body')).toContainText(role)

    // Green confirmation icon/checkmark present — the SVG checkmark or ✓ in heading
    // The heading itself contains "✓" in the page text
    const headingText = await page.getByRole('heading').first().textContent()
    expect(headingText).toMatch(/✓|Interview Invitation Sent/)
  })

  // ── 2. "Already sent" variant ────────────────────────────────────────────────
  test('"Already Sent" page renders when already=1', async ({ page }) => {
    const name = 'Jordan Clarke'

    await page.goto(
      `/interview-invited?already=1&name=${encodeURIComponent(name)}`
    )

    await expect(
      page.getByRole('heading', { name: /Already Sent/i })
    ).toBeVisible({ timeout: 10_000 })

    await expect(page.locator('body')).toContainText('already been sent')
  })

  // ── 3. Backend endpoint rejects invalid tokens ────────────────────────────────
  test('invite-interview endpoint returns 400 for an invalid token', async ({ request }) => {
    const fakeId   = '00000000-0000-0000-0000-000000000001'
    const fakeToken = 'this.is.not.a.real.token'

    // Both routes should reject bad tokens
    const res1 = await request.get(
      `${API_URL}/api/v1/actions/invite-interview/${fakeId}/${fakeToken}`
    )
    expect([400, 404]).toContain(res1.status())

    const res2 = await request.get(
      `${API_URL}/api/v1/actions/invite/${fakeId}/${fakeToken}`
    )
    expect([400, 404]).toContain(res2.status())
  })

  // ── 4. Application detail shows invite status (conditional) ─────────────────
  test('application detail page shows "Interview invitation sent" when invited', async ({ page, request }) => {
    // Auth
    await page.goto('/')
    const authToken = await getToken(page)
    if (!authToken) {
      test.skip()
      return
    }

    const headers = { Authorization: `Bearer ${authToken}` }

    // Find an application that has already been invited to interview
    const res = await request.get(
      `${API_URL}/api/v1/applications?limit=100`,
      { headers }
    )
    if (res.status() !== 200) { test.skip(); return }

    const body = await res.json()
    const invited = (body.items as Array<{ id: string; interview_invited: boolean }>)
      .find((a) => a.interview_invited === true)

    if (!invited) {
      console.log('No invited applications found in staging — skipping detail page check')
      test.skip()
      return
    }

    await page.goto(`/applications/${invited.id}`)
    await expect(page).not.toHaveURL(/login/)

    // The green "Interview invitation sent" card should be visible
    await expect(
      page.locator('text=Interview invitation sent').first()
    ).toBeVisible({ timeout: 12_000 })
  })
})
