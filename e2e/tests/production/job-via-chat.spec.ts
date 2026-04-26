/**
 * job-via-chat.spec.ts (production)
 *
 * Full end-to-end: recruiter posts a job via the AI chat → verifies the job
 * appears in /jobs → verifies /jobs/{id} detail page loads.
 *
 * ⚠️  This test COSTS ONE CREDIT on the production account.
 *     Run deliberately: npm run prod:chat
 *
 * The test is skipped automatically if the tenant has 0 credits.
 *
 * Strategy:
 *  1. Snapshot existing jobs.
 *  2. Create a new chat session.
 *  3. Send a complete job description on turn 0.
 *  4. Loop through AI turns, replying "yes, looks good" until the Job Summary
 *     block appears (step 16 of the flow).
 *  5. Send "confirm" — backend shortcut transitions to payment phase.
 *  6. Send "confirm" again — backend shortcut creates the job, deducts credit,
 *     transitions to recruitment phase.
 *  7. Assert job appears in GET /jobs.
 *  8. Navigate to /jobs/{id} and assert the page loads.
 *  9. Assert credit was deducted by 1.
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

// ── Job description sent on turn 0 ───────────────────────────────────────────
const JOB_DESCRIPTION = `
I need to hire a Senior Python Engineer. Here are all the details:

Title: Senior Python Engineer
Location: Sydney, AU (hybrid, 3 days in office)
Experience: 5+ years
Salary: $130,000 – $160,000 AUD per year
Required skills: Python, FastAPI, PostgreSQL, Docker
Tech stack: Python, FastAPI, PostgreSQL, Redis, Docker, AWS
Team size: 8 engineers
Hiring manager: Alex Smith, alex.smith@example.com
Candidate target: 20
Minimum suitability score: 7
Interview type: text
Number of test questions: 5

Please use all of this information to create the job listing.
`.trim()

const EXPECTED_TITLE_FRAGMENT = 'Python Engineer'
const MAX_TURNS = 25

test.describe('Production: job creation via AI chat', () => {
  test.setTimeout(5 * 60_000) // 5 min — up to 25 AI round-trips at ~8 s each

  test('post job via AI chat → appears in /jobs → /jobs/{id} loads', async ({ page, request }) => {
    // ── Auth ──────────────────────────────────────────────────────────────────
    await page.goto('/')
    const token = await getToken(page)
    expect(token, 'Auth token missing — check PROD_TEST_EMAIL / PROD_TEST_PASSWORD').toBeTruthy()

    const headers = { Authorization: `Bearer ${token}` }

    // ── Skip if no credits ────────────────────────────────────────────────────
    const tenantRes = await request.get(`${API_URL}/api/v1/tenants/me`, { headers })
    expect(tenantRes.status()).toBe(200)
    const tenant = await tenantRes.json()

    if (tenant.credits_remaining < 1) {
      console.log('Skipping: tenant has 0 credits')
      test.skip()
      return
    }
    const creditsAtStart: number = tenant.credits_remaining

    // ── Snapshot existing jobs ────────────────────────────────────────────────
    const jobsBefore = await request.get(`${API_URL}/api/v1/jobs?limit=100`, { headers })
    expect(jobsBefore.status()).toBe(200)
    const jobIdsBefore = new Set<string>(
      (await jobsBefore.json()).items.map((j: { id: string }) => j.id)
    )

    // ── Create a fresh chat session ───────────────────────────────────────────
    const newSessionRes = await request.post(`${API_URL}/api/v1/chat-sessions/new`, { headers })
    expect(newSessionRes.status()).toBe(201)
    const { id: sessionId } = await newSessionRes.json()
    expect(sessionId).toBeTruthy()

    // ── Conversation loop ─────────────────────────────────────────────────────
    let currentPhase = 'job_collection'
    let lastAIMessage = ''
    let jobCreated = false

    for (let turn = 0; turn < MAX_TURNS; turn++) {
      let userMessage: string

      if (turn === 0) {
        userMessage = JOB_DESCRIPTION
      } else if (currentPhase === 'payment') {
        userMessage = 'confirm'
      } else if (hasJobSummaryBlock(lastAIMessage)) {
        userMessage = 'confirm'
      } else {
        userMessage = 'yes, that looks good, please continue'
      }

      const turnRes = await request.post(
        `${API_URL}/api/v1/chat-sessions/${sessionId}/message`,
        { headers, data: { message: userMessage } }
      )

      expect(turnRes.status(), `Turn ${turn}: unexpected status ${turnRes.status()}`).toBe(200)

      const body = await turnRes.json()
      currentPhase  = body.phase   ?? currentPhase
      lastAIMessage = body.message ?? ''

      if (currentPhase === 'recruitment') {
        jobCreated = true
        break
      }

      if (currentPhase === 'post_recruitment') {
        throw new Error('Session transitioned to post_recruitment — job was cancelled')
      }
    }

    expect(jobCreated, `Job not created after ${MAX_TURNS} turns. Last phase: ${currentPhase}`).toBe(true)

    // ── Verify job in API ─────────────────────────────────────────────────────
    const jobsAfter = await request.get(`${API_URL}/api/v1/jobs?limit=100`, { headers })
    expect(jobsAfter.status()).toBe(200)

    const newJobs: Array<{ id: string; title: string }> = (await jobsAfter.json()).items.filter(
      (j: { id: string }) => !jobIdsBefore.has(j.id)
    )

    expect(
      newJobs.length,
      'No new jobs found after chat flow completed'
    ).toBeGreaterThanOrEqual(1)

    const createdJob = newJobs.find((j) =>
      j.title.toLowerCase().includes(EXPECTED_TITLE_FRAGMENT.toLowerCase())
    )
    expect(
      createdJob,
      `Expected a job with title containing "${EXPECTED_TITLE_FRAGMENT}". Got: ${JSON.stringify(newJobs.map((j) => j.title))}`
    ).toBeDefined()

    // ── Verify /jobs/{id} page loads in the browser ───────────────────────────
    await page.goto(`/en/jobs/${createdJob!.id}`)
    await expect(page).not.toHaveURL(/login/)
    await expect(page.locator('main')).toBeVisible({ timeout: 15_000 })
    // Job title should appear somewhere on the page
    await expect(page.locator('body')).toContainText(EXPECTED_TITLE_FRAGMENT, { timeout: 15_000 })

    // ── Verify credit deducted ────────────────────────────────────────────────
    const tenantAfterRes = await request.get(`${API_URL}/api/v1/tenants/me`, { headers })
    expect(tenantAfterRes.status()).toBe(200)
    const tenantAfter = await tenantAfterRes.json()
    expect(tenantAfter.credits_remaining, 'Credit was not deducted').toBe(creditsAtStart - 1)
  })
})

// ── Helpers ───────────────────────────────────────────────────────────────────
function hasJobSummaryBlock(message: string): boolean {
  return message.includes('📋') && message.includes('Job Summary')
}
