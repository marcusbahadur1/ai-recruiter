/**
 * T12 — Chat in recruitment phase (post job creation)
 *
 * Uses an existing job that is already in recruitment phase.
 * Verifies that /chat loads in recruitment mode and the AI responds
 * as a recruitment assistant — not restarting the job_collection flow.
 *
 * No credits consumed.
 */
import { test, expect } from '@playwright/test'
import { loadAuth, sendTurn } from './helpers/chat'

const API_URL = (process.env.PROD_API_URL ?? 'https://airecruiterz-api.fly.dev').replace(/\/$/, '')

test.describe('T12 — Post-creation recruitment chat', () => {
  test.setTimeout(5 * 60_000)

  test('AI responds as recruitment assistant after job is live', async ({ page }) => {
    const token = await loadAuth(page)

    // ── Find an existing recruitment-phase session ────────────────────────────
    const sessionsRes = await page.request.get(
      `${API_URL}/api/v1/chat-sessions?limit=50`,
      { headers: { Authorization: `Bearer ${token}` } }
    )
    expect(sessionsRes.status()).toBe(200)
    const sessions = await sessionsRes.json()

    const recruitmentSession = (sessions.items ?? []).find(
      (s: { phase: string; job_id: string | null }) =>
        s.phase === 'recruitment' && s.job_id !== null
    )

    if (!recruitmentSession) {
      console.log('T12: no recruitment-phase session found — skipping')
      test.skip()
      return
    }

    const sessionId = recruitmentSession.id
    const jobId     = recruitmentSession.job_id
    console.log(`T12: using session ${sessionId}, job ${jobId}`)

    // ── Ask a recruitment question ────────────────────────────────────────────
    const question = 'How many candidates have been discovered so far?'
    const r1 = await sendTurn(page, token, sessionId, question)

    console.log(`T12 AI reply: ${r1.message.substring(0, 200)}`)

    // Should stay in recruitment phase — not drop back to job_collection
    expect(r1.phase, 'Phase should remain recruitment').toBe('recruitment')

    // Reply should be helpful and relevant — not ask "what role are you looking to fill?"
    const lower = r1.message.toLowerCase()
    expect(
      lower,
      'AI should not restart job_collection after job is live'
    ).not.toMatch(/what (role|position|job) (are|do)/)
    expect(
      lower,
      'AI should not invite the recruiter to start a new job'
    ).not.toContain('paste a job description')

    // ── Ask a follow-up question ──────────────────────────────────────────────
    const followup = 'What is the current status of the search pipeline?'
    const r2 = await sendTurn(page, token, sessionId, followup)
    expect(r2.phase).toBe('recruitment')
    console.log(`T12 follow-up reply: ${r2.message.substring(0, 200)}`)

    // ── Verify via browser UI ──────────────────────────────────────────────────
    await page.goto(`/en/chat?session_id=${sessionId}`)
    await expect(page).not.toHaveURL(/login/)
    await expect(page.locator('.chat-input-wrap input')).toBeVisible({ timeout: 15_000 })

    // The page title / status should show active session context
    await expect(page.locator('body')).toContainText('Active session', { timeout: 10_000 })

    console.log(`T12 PASSED — recruitment chat working for session ${sessionId}.`)
    console.log(`  Review: app.airecruiterz.com/en/chat?session_id=${sessionId}`)
  })
})
