/**
 * 01-job-via-chat.spec.ts
 *
 * E2E: Recruiter posts a job through the AI chat interface and verifies the job
 * is created in the database.
 *
 * Strategy:
 *  1. Create a fresh chat session via API.
 *  2. Send a complete job description so the AI has all required fields up-front.
 *  3. Loop through AI turns, replying "yes, looks good" to each question.
 *  4. When the AI presents the "📋 Job Summary" block (step 16), send "confirm" —
 *     the backend shortcut transitions the session to the payment phase without
 *     an AI round-trip.
 *  5. In the payment phase, send "confirm" — the backend shortcut creates the job,
 *     deducts one credit, and transitions to the recruitment phase.
 *  6. Assert that GET /jobs returns a job matching the title we submitted.
 *
 * Notes:
 *  - This test calls the backend API directly (no browser UI) using Playwright's
 *    `request` context, which respects the saved auth storage state.
 *  - Timeout is raised to 4 minutes to allow for up to 20 AI round-trips.
 *  - The test is skipped automatically when the tenant has 0 credits (no charge).
 */
import { test, expect } from '@playwright/test'

const API_URL = process.env.STAGING_API_URL ?? 'http://localhost:8000'

/** Extract Supabase JWT from browser localStorage (same helper as smoke suite). */
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

// ── The full job description we send as the first message ──────────────────────
const JOB_DESCRIPTION = `
I need to hire a Senior Python Engineer. Here are all the details:

Title: Senior Python Engineer
Location: London, UK (hybrid, 3 days in office)
Experience: 5+ years
Salary: £70,000 – £90,000 per year
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

// Title we expect to see on the created job (the AI normalises it)
const EXPECTED_TITLE_FRAGMENT = 'Python Engineer'

// Maximum number of AI turns before we give up and fail the test
const MAX_TURNS = 25

test.describe('Job creation via AI chat', () => {
  // Override default 30 s timeout — up to 20 AI round-trips at ~8 s each ≈ 240 s
  test.setTimeout(4 * 60_000)

  test('recruiter posts job via AI chat → job appears in /jobs', async ({ page, request }) => {
    // ── Auth ──────────────────────────────────────────────────────────────────
    await page.goto('/')
    const token = await getToken(page)
    expect(token, 'Auth token must be present — is the user logged in?').toBeTruthy()

    const headers = { Authorization: `Bearer ${token}` }

    // ── Check tenant has credits ──────────────────────────────────────────────
    const tenantRes = await request.get(`${API_URL}/api/v1/tenants/me`, { headers })
    expect(tenantRes.status()).toBe(200)
    const tenant = await tenantRes.json()
    if (tenant.credits_remaining < 1) {
      test.skip()
      return
    }
    const creditsAtStart: number = tenant.credits_remaining

    // ── Snapshot existing jobs so we can detect the newly-created one ─────────
    const jobsBefore = await request.get(`${API_URL}/api/v1/jobs?limit=500`, { headers })
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
    let lastAIMessage  = ''
    let jobCreated     = false

    for (let turn = 0; turn < MAX_TURNS; turn++) {
      // Decide what to send this turn
      let userMessage: string

      if (turn === 0) {
        // First turn: send the complete job description
        userMessage = JOB_DESCRIPTION
      } else if (currentPhase === 'payment') {
        // In payment phase the backend shortcut handles "confirm" without AI
        userMessage = 'confirm'
      } else if (hasJobSummaryBlock(lastAIMessage)) {
        // Step-16 job summary is visible → confirm it (backend shortcut to payment)
        userMessage = 'confirm'
      } else {
        // Intermediate turn: acknowledge and ask AI to proceed
        userMessage = 'yes, that looks good, please continue'
      }

      const turnRes = await request.post(
        `${API_URL}/api/v1/chat-sessions/${sessionId}/message`,
        { headers, data: { message: userMessage } }
      )

      // 422 = bad message, 404 = session gone — both are hard failures
      expect(turnRes.status(), `Turn ${turn}: unexpected status`).toBe(200)

      const turnBody = await turnRes.json()
      currentPhase  = turnBody.phase   ?? currentPhase
      lastAIMessage = turnBody.message ?? ''

      // Recruitment phase means payment was confirmed and job was created
      if (currentPhase === 'recruitment') {
        jobCreated = true
        break
      }

      // Safety: post_recruitment means the user cancelled — fail the test
      if (currentPhase === 'post_recruitment') {
        throw new Error('Session transitioned to post_recruitment — job was cancelled')
      }
    }

    expect(jobCreated, `Job was not created after ${MAX_TURNS} turns`).toBe(true)

    // ── Verify the job appears in the jobs list ───────────────────────────────
    const jobsAfter = await request.get(`${API_URL}/api/v1/jobs?limit=500`, { headers })
    expect(jobsAfter.status()).toBe(200)
    const newJobs: Array<{ id: string; title: string }> = (await jobsAfter.json()).items.filter(
      (j: { id: string }) => !jobIdsBefore.has(j.id)
    )

    expect(
      newJobs.length,
      'Expected at least one new job to have been created'
    ).toBeGreaterThanOrEqual(1)

    const createdJob = newJobs.find((j) =>
      j.title.toLowerCase().includes(EXPECTED_TITLE_FRAGMENT.toLowerCase())
    )
    expect(
      createdJob,
      `Expected a new job with title containing "${EXPECTED_TITLE_FRAGMENT}". Found: ${JSON.stringify(newJobs.map((j) => j.title))}`
    ).toBeDefined()

    // ── Verify credit was deducted ────────────────────────────────────────────
    const tenantAfterRes = await request.get(`${API_URL}/api/v1/tenants/me`, { headers })
    expect(tenantAfterRes.status()).toBe(200)
    const tenantAfter = await tenantAfterRes.json()
    expect(tenantAfter.credits_remaining).toBe(creditsAtStart - 1)
  })
})

// ── Helpers ───────────────────────────────────────────────────────────────────

/** Return true when the AI message contains the step-16 📋 Job Summary block. */
function hasJobSummaryBlock(message: string): boolean {
  return message.includes('📋') && message.includes('Job Summary')
}
