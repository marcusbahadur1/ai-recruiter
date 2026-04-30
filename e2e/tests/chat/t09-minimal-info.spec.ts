/**
 * T09 — Minimal info ("I need a developer")
 *
 * Starts with the most vague possible opening. Verifies the AI asks targeted
 * questions and collects all required fields before showing the Job Summary.
 * This is the stress test — the most turns, the slowest test.
 *
 * Costs 1 credit.
 */
import { test, expect } from '@playwright/test'
import {
  loadAuth, snapshotJobIds, findNewJob, createSession,
  sendTurn, getTenant, hasJobSummaryBlock,
} from './helpers/chat'
import { OPENING_T09, T09_FOLLOWUPS, EXPECTED_TITLE_T09 } from './fixtures/job-descriptions'

test.describe('T09 — Minimal info stress test', () => {
  test.setTimeout(10 * 60_000)

  test('AI collects all required fields from a vague opening', async ({ page }) => {
    const token = await loadAuth(page)

    const tenant = await getTenant(page, token)
    if (tenant.credits_remaining < 1) {
      test.skip()
      return
    }
    const creditsAtStart: number = tenant.credits_remaining
    const existingIds = await snapshotJobIds(page, token)

    const sessionId = await createSession(page, token)
    let phase   = 'job_collection'
    let turns   = 0
    let summaryShown = false

    // Turn 0: vague opener
    const r0 = await sendTurn(page, token, sessionId, OPENING_T09)
    phase = r0.phase
    turns++
    console.log(`T09 turn 1: ${r0.message.substring(0, 120)}`)

    // Provide follow-up answers based on turn number
    const followupIndex = [0, 1, 2, 3]
    let followupUsed = 0

    for (let i = 1; i <= 25; i++) {
      if (phase === 'recruitment') break
      if (phase === 'payment') {
        const r = await sendTurn(page, token, sessionId, 'confirm')
        phase = r.phase
        turns++
        continue
      }

      let userMsg: string
      if (summaryShown) {
        userMsg = 'confirm'
      } else if (followupUsed < T09_FOLLOWUPS.length) {
        userMsg = T09_FOLLOWUPS[followupUsed]
        followupUsed++
      } else {
        userMsg = 'yes, that looks correct, please proceed'
      }

      const r = await sendTurn(page, token, sessionId, userMsg)
      phase = r.phase
      turns++

      if (!summaryShown && hasJobSummaryBlock(r.message)) {
        summaryShown = true
        console.log(`T09: Job Summary block appeared at turn ${turns}`)
      }

      console.log(`T09 turn ${turns}: phase=${phase}`)
    }

    expect(summaryShown, 'AI should eventually produce a Job Summary block').toBe(true)
    expect(phase, `Expected recruitment, got ${phase}`).toBe('recruitment')

    const newJob = await findNewJob(page, token, existingIds)
    expect(newJob, 'No new job found').toBeDefined()
    // Title should be some kind of developer/engineer
    expect(
      newJob!.title.toLowerCase(),
      `Job title "${newJob!.title}" should contain developer/engineer`
    ).toMatch(/developer|engineer|programmer/)

    const tenantAfter = await getTenant(page, token)
    expect(tenantAfter.credits_remaining).toBeLessThan(creditsAtStart)

    console.log(`T09 PASSED — "${newJob!.title}" created in ${turns} turns from a vague opener.`)
    console.log(`  Review: app.airecruiterz.com/en/chat?session_id=${sessionId}`)
  })
})
