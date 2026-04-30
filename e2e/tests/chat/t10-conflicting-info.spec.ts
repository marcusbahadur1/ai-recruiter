/**
 * T10 — Conflicting / ambiguous info
 *
 * Pastes a JD with three deliberate contradictions:
 *   1. Dual location (Melbourne AND Sydney — impossible onsite)
 *   2. Salary ambiguity ($80k OR equity-only)
 *   3. Experience vs seniority mismatch (2 yrs experience + leads 15 seniors)
 *
 * Verifies the AI asks clarifying questions for the contradictions rather
 * than silently picking one option.
 *
 * Costs 1 credit (job created after contradictions are resolved).
 */
import { test, expect } from '@playwright/test'
import {
  loadAuth, snapshotJobIds, findNewJob, createSession,
  sendTurn, getTenant, hasJobSummaryBlock,
} from './helpers/chat'
import { JD_T10_CONFLICTING, EXPECTED_TITLE_T10 } from './fixtures/job-descriptions'

test.describe('T10 — Conflicting info in JD', () => {
  test.setTimeout(10 * 60_000)

  test('AI asks clarifying questions for contradictions', async ({ page }) => {
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
    let summaryShown    = false
    let askedClarifying = false

    // Turn 0: paste conflicting JD
    const r0 = await sendTurn(page, token, sessionId, JD_T10_CONFLICTING)
    phase = r0.phase
    turns++
    console.log(`T10 first reply: ${r0.message.substring(0, 200)}`)

    // Check if AI immediately asked about contradictions
    const lowerR0 = r0.message.toLowerCase()
    if (
      lowerR0.includes('both') ||
      lowerR0.includes('clarif') ||
      lowerR0.includes('which') ||
      lowerR0.includes('either') ||
      lowerR0.includes('conflict') ||
      lowerR0.includes('contradict')
    ) {
      askedClarifying = true
      console.log('T10: AI detected contradictions immediately ✓')
    }

    // Resolutions to contradictions
    const resolutions = [
      'Melbourne CBD onsite. Salary is $80k base, not equity-only. 2 years experience is minimum for a mid-level role, not a team lead.',
      'The team of 15 will be managed by a senior manager, this role is individual contributor.',
      'marcus@aiworkerz.com, Marcus Bahadur. Min score 6, 20 candidates.',
    ]
    let resIdx = 0

    for (let i = 1; i <= 20; i++) {
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
      } else if (resIdx < resolutions.length) {
        userMsg = resolutions[resIdx]
        resIdx++
      } else {
        userMsg = 'yes, please proceed'
      }

      const r = await sendTurn(page, token, sessionId, userMsg)
      phase = r.phase
      turns++

      const lowerReply = r.message.toLowerCase()
      if (!askedClarifying && (
        lowerReply.includes('clarif') ||
        lowerReply.includes('which') ||
        lowerReply.includes('either') ||
        lowerReply.includes('confirm')
      )) {
        askedClarifying = true
      }

      if (!summaryShown && hasJobSummaryBlock(r.message)) {
        summaryShown = true
      }

      console.log(`T10 turn ${turns}: phase=${phase}`)
    }

    // The key assertion: AI asked clarifying questions at some point
    expect(
      askedClarifying,
      'AI should have asked clarifying questions for the contradictory information'
    ).toBe(true)

    expect(phase, `Expected recruitment, got ${phase}`).toBe('recruitment')

    const newJob = await findNewJob(page, token, existingIds)
    expect(newJob, 'No new job found').toBeDefined()
    expect(newJob!.title.toLowerCase()).toContain(EXPECTED_TITLE_T10.toLowerCase())

    const tenantAfter = await getTenant(page, token)
    expect(tenantAfter.credits_remaining).toBe(creditsAtStart - 1)

    console.log(`T10 PASSED — contradictions handled, "${newJob!.title}" created in ${turns} turns.`)
    console.log(`  Review: app.airecruiterz.com/en/chat?session_id=${sessionId}`)
  })
})
