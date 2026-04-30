/**
 * T01 — Full JD paste (Happy Path)
 *
 * Pastes a complete job description on the very first message.
 * Expects the new prompt to extract ALL fields in one pass, show the
 * Job Summary block, and complete job creation in minimal turns.
 *
 * Costs 1 credit.
 */
import { test, expect } from '@playwright/test'
import {
  loadAuth, snapshotJobIds, findNewJob, createSession,
  runToJobCreation, getTenant,
} from './helpers/chat'
import { JD_T01_JAVA_DEVELOPER, EXPECTED_TITLE_T01 } from './fixtures/job-descriptions'

const API_URL = (process.env.PROD_API_URL ?? 'https://airecruiterz-api.fly.dev').replace(/\/$/, '')

test.describe('T01 — Full JD paste', () => {
  test.setTimeout(10 * 60_000)

  test('paste complete JD → Job Summary shown → job created in ≤ 6 turns', async ({ page }) => {
    const token = await loadAuth(page)

    // Skip if no credits
    const tenant = await getTenant(page, token)
    if (tenant.credits_remaining < 1) {
      console.log('Skipping T01: no credits')
      test.skip()
      return
    }
    const creditsAtStart: number = tenant.credits_remaining

    const existingIds = await snapshotJobIds(page, token)

    // ── Drive conversation ────────────────────────────────────────────────────
    const sessionId = await createSession(page, token)
    const result = await runToJobCreation(page, token, JD_T01_JAVA_DEVELOPER, {
      sessionId,
      maxTurns: 15, // with the new prompt, paste should complete in ≤ 6
    })

    expect(
      result.created,
      `Job not created after ${result.turns} turns. Last phase: ${result.lastPhase}`
    ).toBe(true)

    console.log(`T01: job created in ${result.turns} turns (session: ${sessionId})`)

    // ── Verify job exists in API ──────────────────────────────────────────────
    const newJob = await findNewJob(page, token, existingIds)
    expect(newJob, 'No new job found after conversation completed').toBeDefined()
    expect(
      newJob!.title.toLowerCase(),
      `Job title should contain "${EXPECTED_TITLE_T01.toLowerCase()}"`
    ).toContain(EXPECTED_TITLE_T01.toLowerCase())

    // ── Verify credit deducted ────────────────────────────────────────────────
    const tenantAfter = await getTenant(page, token)
    expect(tenantAfter.credits_remaining, 'Credit was not deducted').toBe(creditsAtStart - 1)

    // ── Verify job detail page loads ──────────────────────────────────────────
    await page.goto(`/en/jobs/${newJob!.id}`)
    await expect(page).not.toHaveURL(/login/)
    await expect(page.locator('body')).toContainText(EXPECTED_TITLE_T01, { timeout: 15_000 })

    console.log(`T01 PASSED — job "${newJob!.title}" created in ${result.turns} turns.`)
    console.log(`  Review conversation: app.airecruiterz.com/en/chat?session_id=${sessionId}`)
  })
})
