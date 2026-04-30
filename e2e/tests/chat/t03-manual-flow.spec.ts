/**
 * T03 — Manual / conversational flow (no paste)
 *
 * Recruiter describes the role verbally. Tests that the new 5-step flow
 * guides naturally through the conversation without feeling like a form.
 *
 * Costs 1 credit.
 */
import { test, expect } from '@playwright/test'
import {
  loadAuth, snapshotJobIds, findNewJob, createSession,
  sendTurn, getTenant, hasJobSummaryBlock,
} from './helpers/chat'
import {
  OPENING_T03, T03_ANSWERS, EXPECTED_TITLE_T03,
} from './fixtures/job-descriptions'

test.describe('T03 — Manual conversational flow', () => {
  test.setTimeout(10 * 60_000)

  test('5-step guided flow completes and creates job', async ({ page }) => {
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
    let summaryShown = false

    // Track which steps have been answered so we can provide targeted answers
    const stepAnswered = { roleBasics: false, location: false, hiring: false, assessment: false }

    const r0 = await sendTurn(page, token, sessionId, OPENING_T03)
    phase = r0.phase
    turns++
    console.log(`T03 turn 1: ${r0.message.substring(0, 120)}`)

    for (let i = 1; i <= 20; i++) {
      if (phase === 'recruitment') break
      if (phase === 'payment') {
        const r = await sendTurn(page, token, sessionId, 'confirm')
        phase = r.phase
        turns++
        continue
      }

      if (hasJobSummaryBlock(r0.message) || summaryShown) {
        const r = await sendTurn(page, token, sessionId, 'confirm')
        phase = r.phase
        turns++
        if (!summaryShown) summaryShown = true
        continue
      }

      // Route to the most appropriate fixture answer based on turn number
      let userMsg: string
      if (turns === 1) {
        userMsg = T03_ANSWERS.roleBasics
      } else if (turns === 2) {
        userMsg = T03_ANSWERS.location
      } else if (turns === 3) {
        userMsg = T03_ANSWERS.hiring
      } else if (turns === 4) {
        userMsg = T03_ANSWERS.assessment
      } else {
        userMsg = 'yes, that looks right, please continue'
      }

      const r = await sendTurn(page, token, sessionId, userMsg)
      phase = r.phase
      turns++

      if (!summaryShown && hasJobSummaryBlock(r.message)) {
        summaryShown = true
        // Confirm on the next iteration
      }

      console.log(`T03 turn ${turns}: phase=${phase}`)
    }

    expect(summaryShown, 'AI never produced a Job Summary block').toBe(true)
    expect(phase, `Expected recruitment, got ${phase}`).toBe('recruitment')

    const newJob = await findNewJob(page, token, existingIds)
    expect(newJob, 'No new job found').toBeDefined()
    expect(newJob!.title.toLowerCase()).toContain(EXPECTED_TITLE_T03.toLowerCase())

    const tenantAfter = await getTenant(page, token)
    expect(tenantAfter.credits_remaining).toBe(creditsAtStart - 1)

    console.log(`T03 PASSED — "${newJob!.title}" created in ${turns} turns.`)
    console.log(`  Review: app.airecruiterz.com/en/chat?session_id=${sessionId}`)
  })
})
