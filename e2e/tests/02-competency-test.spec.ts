/**
 * 02-competency-test.spec.ts
 *
 * E2E: Candidate completes a competency test → test_status updated to "completed".
 *
 * Strategy:
 *  1. Find an application with screening_status="passed" and test_status="not_started".
 *     Skip the test if none exists in the staging environment.
 *  2. POST /applications/{id}/trigger-test → generates AI questions, marks status
 *     "invited", returns a test_url containing the signed JWT token.
 *  3. Parse the token from test_url and call GET /test/{id}/{token} (public) →
 *     transitions the test to "in_progress" and confirms the question count.
 *  4. Loop through all questions by posting answers to POST /test/{id}/message.
 *     If the AI examiner rejects an answer, send a more detailed follow-up
 *     (up to MAX_RETRIES_PER_QUESTION retries before hard-failing the test).
 *  5. Assert that GET /applications/{id} shows test_status = "completed".
 *
 * Notes:
 *  - The public test endpoints (/test/…) do not require an auth header — only
 *    the signed JWT token that comes back in the trigger-test response.
 *  - Timeout is raised to 3 minutes to allow for AI examiner round-trips.
 *  - This test mutates staging data (marks an application as tested). It is
 *    idempotent in the sense that re-running picks a different "not_started"
 *    application each time (or skips if none remain).
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

// ── Canned answers — sufficiently detailed to satisfy the AI examiner ─────────

const DETAILED_ANSWER = `
I have over five years of experience in this area. In my most recent role I built
and maintained large-scale Python services using FastAPI and PostgreSQL, serving
several million requests per day. A concrete example: I led the re-architecture
of our monolithic application into focused microservices, which reduced average
API latency by 40% and made deployments fully independent across teams.
I applied test-driven development throughout, achieving 95% code coverage on all
critical paths, and used Docker and GitHub Actions for containerised CI/CD.
I am comfortable with both synchronous and asynchronous patterns (asyncio, aiohttp,
SQLAlchemy async), and I have deep experience debugging production incidents under
pressure and writing clear post-mortems.
`.trim()

const FOLLOWUP_ANSWER = `
To elaborate further with a specific technical example: when we encountered a
performance bottleneck in our database layer I profiled the queries with EXPLAIN
ANALYZE, added composite indexes on the most-queried columns, and introduced a
Redis caching layer for idempotent reads. This reduced database CPU by 60%
without any application-layer changes. I documented the approach in an
architecture decision record so the team could repeat the process independently.
I am also comfortable with code review, mentoring junior engineers, and
communicating technical trade-offs clearly to non-technical stakeholders.
`.trim()

const MAX_RETRIES_PER_QUESTION = 3

test.describe('Candidate competency test', () => {
  test.setTimeout(3 * 60_000)

  test('candidate completes competency test → test_status becomes "completed"', async ({ page, request }) => {
    // ── Auth ──────────────────────────────────────────────────────────────────
    await page.goto('/')
    const authToken = await getToken(page)
    expect(authToken, 'Auth token must be present — is the user logged in?').toBeTruthy()

    const authHeaders = { Authorization: `Bearer ${authToken}` }

    // ── Find an eligible application ──────────────────────────────────────────
    // Look for applications that have passed screening and haven't started a test
    const appsRes = await request.get(
      `${API_URL}/api/v1/applications?screening_status=passed&limit=100`,
      { headers: authHeaders }
    )
    expect(appsRes.status()).toBe(200)
    const appsBody = await appsRes.json()

    const eligible = (appsBody.items as Array<{
      id: string
      test_status: string
      applicant_name: string
    }>).filter((a) => a.test_status === 'not_started')

    if (eligible.length === 0) {
      console.log(
        'No applications with screening_status=passed and test_status=not_started found. ' +
        'Skipping — run the screener pipeline first to generate eligible applications.'
      )
      test.skip()
      return
    }

    const application = eligible[0]
    console.log(`Using application ${application.id} (${application.applicant_name})`)

    // ── Trigger the competency test ───────────────────────────────────────────
    const triggerRes = await request.post(
      `${API_URL}/api/v1/applications/${application.id}/trigger-test`,
      { headers: authHeaders }
    )
    expect(triggerRes.status(), 'trigger-test should return 202').toBe(202)

    const triggerBody = await triggerRes.json()
    expect(triggerBody).toHaveProperty('test_url')

    // Extract application_id and token from the test_url
    // Format: https://app.airecruiterz.com/test/{uuid}/{jwt}
    const testUrl: string = triggerBody.test_url
    const testPathParts = testUrl.split('/test/')[1]?.split('/')
    expect(testPathParts?.length, 'test_url should contain /test/{id}/{token}').toBeGreaterThanOrEqual(2)
    const testAppId = testPathParts![0]
    const testToken = testPathParts!.slice(1).join('/')  // token may contain slashes (unlikely but safe)

    // ── Open the test (public — no auth header) ───────────────────────────────
    const openRes = await request.get(
      `${API_URL}/api/v1/test/${testAppId}/${testToken}`
    )
    expect(openRes.status(), 'GET /test/{id}/{token} should return 200').toBe(200)

    const openBody = await openRes.json()
    expect(openBody.test_status).toBe('in_progress')
    const totalQuestions: number = openBody.questions_total
    expect(totalQuestions, 'Test should have at least 1 question').toBeGreaterThanOrEqual(1)
    console.log(`Test has ${totalQuestions} question(s)`)

    // ── Answer all questions ──────────────────────────────────────────────────
    let answeredCount = 0

    for (let q = 0; q < totalQuestions; q++) {
      let accepted = false

      for (let attempt = 0; attempt < MAX_RETRIES_PER_QUESTION; attempt++) {
        const answer = attempt === 0 ? DETAILED_ANSWER : FOLLOWUP_ANSWER

        const msgRes = await request.post(
          `${API_URL}/api/v1/test/${testAppId}/message`,
          { data: { token: testToken, answer } }
        )
        expect(msgRes.status(), `Q${q + 1} attempt ${attempt + 1}: unexpected status`).toBe(200)

        const msgBody = await msgRes.json()
        answeredCount = msgBody.answered ?? answeredCount

        if (msgBody.answer_accepted !== false) {
          // answer_accepted is true, or field is absent (examiner always advances)
          accepted = true
        }

        if (msgBody.completed) {
          // All questions answered — exit both loops
          q = totalQuestions  // break outer loop
          accepted = true
          break
        }

        if (accepted) break
      }

      expect(
        accepted,
        `Q${q + 1}: examiner did not accept the answer after ${MAX_RETRIES_PER_QUESTION} attempts`
      ).toBe(true)
    }

    // ── Verify test_status in the application record ──────────────────────────
    // Poll briefly — score_test Celery task may update status asynchronously,
    // but the test completion itself is synchronous.
    const appRes = await request.get(
      `${API_URL}/api/v1/applications/${application.id}`,
      { headers: authHeaders }
    )
    expect(appRes.status()).toBe(200)

    const appBody = await appRes.json()
    expect(
      ['completed', 'passed', 'failed'],
      'test_status should be completed (or passed/failed if scoring ran synchronously)'
    ).toContain(appBody.test_status)

    console.log(
      `Test finished: ${answeredCount}/${totalQuestions} questions answered, ` +
      `final test_status = "${appBody.test_status}"`
    )
  })
})
