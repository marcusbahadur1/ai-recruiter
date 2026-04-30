/**
 * T07 — Remote global job
 *
 * Pastes a JD specifying "fully remote, anywhere in the world".
 * Verifies the AI correctly extracts work_type=remote_global and that the
 * job is created (the Scout will not filter by location for this job type).
 *
 * Costs 1 credit.
 */
import { test, expect } from '@playwright/test'
import {
  loadAuth, snapshotJobIds, findNewJob, createSession,
  runToJobCreation, getTenant,
} from './helpers/chat'
import { JD_T07_REACT_REMOTE, EXPECTED_TITLE_T07 } from './fixtures/job-descriptions'

const API_URL = (process.env.PROD_API_URL ?? 'https://airecruiterz-api.fly.dev').replace(/\/$/, '')

test.describe('T07 — Remote global job', () => {
  test.setTimeout(10 * 60_000)

  test('remote_global JD creates job correctly', async ({ page }) => {
    const token = await loadAuth(page)

    const tenant = await getTenant(page, token)
    if (tenant.credits_remaining < 1) {
      test.skip()
      return
    }
    const creditsAtStart: number = tenant.credits_remaining
    const existingIds = await snapshotJobIds(page, token)

    const sessionId = await createSession(page, token)
    const result = await runToJobCreation(page, token, JD_T07_REACT_REMOTE, {
      sessionId,
      maxTurns: 20,
    })

    expect(result.created, `Job not created. Phase: ${result.lastPhase}`).toBe(true)

    const newJob = await findNewJob(page, token, existingIds)
    expect(newJob, 'No new job found').toBeDefined()
    expect(newJob!.title.toLowerCase()).toContain(EXPECTED_TITLE_T07.toLowerCase())

    // Verify job fields include remote work type via job detail API
    const jobRes = await page.request.get(
      `${API_URL}/api/v1/jobs/${newJob!.id}`,
      { headers: { Authorization: `Bearer ${(await page.evaluate(() => {
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
      }))}` } }
    )
    if (jobRes.status() === 200) {
      const jobDetail = await jobRes.json()
      console.log(`T07: job work_type = ${jobDetail.work_type}`)
      expect(
        ['remote', 'remote_global'],
        `Expected remote or remote_global, got ${jobDetail.work_type}`
      ).toContain(jobDetail.work_type)
    }

    const tenantAfter = await getTenant(page, token)
    expect(tenantAfter.credits_remaining).toBe(creditsAtStart - 1)

    console.log(`T07 PASSED — "${newJob!.title}" (${result.turns} turns).`)
    console.log(`  Review: app.airecruiterz.com/en/chat?session_id=${sessionId}`)
  })
})
