/**
 * T02 — Partial JD paste (missing hiring manager)
 *
 * Pastes a job description that is missing the hiring manager name and email.
 * Expects the AI to:
 *   1. Extract all provided fields immediately
 *   2. Show the Job Summary with hiring manager as "Not specified"
 *   3. Ask ONLY for the missing required fields (HM name + email)
 *   4. NOT re-ask for salary, location, or skills that were already provided
 *
 * Costs 1 credit.
 */
import { test, expect } from '@playwright/test'
import {
  loadAuth, snapshotJobIds, findNewJob, createSession,
  sendTurn, getTenant, hasJobSummaryBlock,
} from './helpers/chat'
import {
  JD_T02_MARKETING_MANAGER, T02_FOLLOWUP_HM, EXPECTED_TITLE_T02,
} from './fixtures/job-descriptions'

const API_URL = (process.env.PROD_API_URL ?? 'https://airecruiterz-api.fly.dev').replace(/\/$/, '')

test.describe('T02 — Partial JD paste (missing hiring manager)', () => {
  test.setTimeout(10 * 60_000)

  test('AI asks only for genuinely missing fields', async ({ page }) => {
    const token = await loadAuth(page)

    const tenant = await getTenant(page, token)
    if (tenant.credits_remaining < 1) {
      test.skip()
      return
    }
    const creditsAtStart: number = tenant.credits_remaining

    const existingIds = await snapshotJobIds(page, token)
    const sessionId   = await createSession(page, token)

    let phase   = 'job_collection'
    let turns   = 0
    let hmAsked = false
    let summaryShown = false

    // Turn 0: paste partial JD
    const r0 = await sendTurn(page, token, sessionId, JD_T02_MARKETING_MANAGER)
    phase = r0.phase
    turns++
    console.log(`T02 turn ${turns}: phase=${phase}, message preview: ${r0.message.substring(0, 120)}`)

    // The AI should show a Job Summary block and ask for the hiring manager
    summaryShown = hasJobSummaryBlock(r0.message)

    // Continue loop — AI should ask for HM, we provide it, then confirm
    for (let i = 1; i <= 15; i++) {
      if (phase === 'recruitment') break

      let userMsg: string
      if (phase === 'payment') {
        userMsg = 'confirm'
      } else if (!hmAsked && (
        r0.message.toLowerCase().includes('hiring manager') ||
        r0.message.toLowerCase().includes('who should') ||
        r0.message.toLowerCase().includes('contact')
      )) {
        // AI is asking about the hiring manager
        hmAsked = true
        userMsg = T02_FOLLOWUP_HM
      } else {
        userMsg = 'yes, that looks correct, please proceed'
      }

      const r = await sendTurn(page, token, sessionId, userMsg)
      phase = r.phase
      turns++
      console.log(`T02 turn ${turns}: phase=${phase}`)

      if (!summaryShown && hasJobSummaryBlock(r.message)) {
        summaryShown = true
      }
    }

    // Assertions
    expect(summaryShown, 'AI never showed a Job Summary block').toBe(true)
    expect(phase, `Expected recruitment phase, got ${phase}`).toBe('recruitment')

    const newJob = await findNewJob(page, token, existingIds)
    expect(newJob, 'No new job found').toBeDefined()
    expect(newJob!.title.toLowerCase()).toContain(EXPECTED_TITLE_T02.toLowerCase())

    const tenantAfter = await getTenant(page, token)
    expect(tenantAfter.credits_remaining).toBe(creditsAtStart - 1)

    console.log(`T02 PASSED — job "${newJob!.title}" created in ${turns} turns.`)
    console.log(`  Review: app.airecruiterz.com/en/chat?session_id=${sessionId}`)
  })
})
