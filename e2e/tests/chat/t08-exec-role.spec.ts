/**
 * T08 — Executive / non-tech role (CFO)
 *
 * Pastes a CFO job description. Verifies the AI does not over-populate the
 * tech_stack field for a non-technical role (finance/executive roles should
 * have sparse or empty tech_stack).
 *
 * Costs 1 credit.
 */
import { test, expect } from '@playwright/test'
import {
  loadAuth, snapshotJobIds, findNewJob, createSession,
  runToJobCreation, getTenant,
} from './helpers/chat'
import { JD_T08_CFO, EXPECTED_TITLE_T08 } from './fixtures/job-descriptions'

const API_URL = (process.env.PROD_API_URL ?? 'https://airecruiterz-api.fly.dev').replace(/\/$/, '')

test.describe('T08 — Executive / non-tech role', () => {
  test.setTimeout(10 * 60_000)

  test('CFO JD creates job without over-populating tech_stack', async ({ page }) => {
    const token = await loadAuth(page)

    const tenant = await getTenant(page, token)
    if (tenant.credits_remaining < 1) {
      test.skip()
      return
    }
    const creditsAtStart: number = tenant.credits_remaining
    const existingIds = await snapshotJobIds(page, token)

    const sessionId = await createSession(page, token)
    const result    = await runToJobCreation(page, token, JD_T08_CFO, {
      sessionId,
      maxTurns: 20,
    })

    expect(result.created, `Job not created. Phase: ${result.lastPhase}`).toBe(true)

    const newJob = await findNewJob(page, token, existingIds)
    expect(newJob, 'No new job found').toBeDefined()
    expect(newJob!.title.toLowerCase()).toContain(EXPECTED_TITLE_T08.toLowerCase())

    // Optionally check tech_stack via job detail API
    const authToken = await page.evaluate(() => {
      for (let i = 0; i < localStorage.length; i++) {
        const k = localStorage.key(i) ?? ''
        if (k.includes('auth-token') || k.includes('supabase')) {
          try {
            const v = JSON.parse(localStorage.getItem(k) ?? '{}')
            return v?.access_token ?? v?.session?.access_token ?? ''
          } catch { /* skip */ }
        }
      }
      return ''
    })

    const jobRes = await page.request.get(
      `${API_URL}/api/v1/jobs/${newJob!.id}`,
      { headers: { Authorization: `Bearer ${authToken}` } }
    )
    if (jobRes.status() === 200) {
      const jobDetail = await jobRes.json()
      const techStack: string[] = jobDetail.tech_stack ?? []
      console.log(`T08: tech_stack = ${JSON.stringify(techStack)}`)
      // Tech stack should not contain engineering tools for a CFO role
      const techKeywords = ['react', 'java', 'python', 'docker', 'kubernetes', 'node', 'aws', 'azure']
      const badTerms = techStack.filter(t =>
        techKeywords.some(k => t.toLowerCase().includes(k))
      )
      expect(
        badTerms.length,
        `Tech stack should not contain engineering tools for a CFO role. Got: ${JSON.stringify(badTerms)}`
      ).toBe(0)
    }

    const tenantAfter = await getTenant(page, token)
    expect(tenantAfter.credits_remaining).toBe(creditsAtStart - 1)

    console.log(`T08 PASSED — "${newJob!.title}" (${result.turns} turns).`)
    console.log(`  Review: app.airecruiterz.com/en/chat?session_id=${sessionId}`)
  })
})
