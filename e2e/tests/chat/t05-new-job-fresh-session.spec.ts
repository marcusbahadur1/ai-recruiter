/**
 * T05 — "+ New Job" button starts a clean session
 *
 * Establishes an in-progress session, then clicks the "+ New Job" button.
 * Verifies that:
 *   1. The chat clears (no previous messages shown)
 *   2. A new session ID is used (not the same as the old one)
 *   3. A new URL param (session_id) is set pointing to the new session
 *   4. The recruiter can start a fresh conversation without the old job reappearing
 *
 * No credits consumed.
 */
import { test, expect } from '@playwright/test'
import {
  loadAuth, createSession, sendTurn, openChatPage, getMessageCount,
} from './helpers/chat'

test.describe('T05 — New Job button starts a fresh session', () => {
  test.setTimeout(5 * 60_000)

  test('+ New Job clears chat and pins a new session_id in the URL', async ({ page }) => {
    const token = await loadAuth(page)

    // ── Establish an in-progress conversation ─────────────────────────────────
    const oldSessionId = await createSession(page, token)
    await sendTurn(page, token, oldSessionId, 'I need a senior data engineer in Melbourne')
    await sendTurn(page, token, oldSessionId, 'Hybrid, 5+ years, salary $150k–$180k')

    // Load this session in the browser
    await openChatPage(page, oldSessionId)
    const msgsBefore = await getMessageCount(page)
    console.log(`T05: messages in old session: ${msgsBefore}`)
    expect(msgsBefore).toBeGreaterThanOrEqual(2)

    // ── Click + New Job ───────────────────────────────────────────────────────
    await page.getByRole('button', { name: '+ New Job' }).click()

    // Wait for the URL to update with a new session_id
    await page.waitForFunction(
      (oldId) => {
        const params = new URLSearchParams(window.location.search)
        const sid = params.get('session_id')
        return sid !== null && sid !== oldId
      },
      oldSessionId,
      { timeout: 10_000 }
    )

    // ── Assert new session state ──────────────────────────────────────────────
    const newUrl    = page.url()
    const newParams = new URLSearchParams(newUrl.split('?')[1] ?? '')
    const newSid    = newParams.get('session_id')

    expect(newSid, 'URL should have new session_id after + New Job').toBeTruthy()
    expect(newSid, 'New session_id should differ from old session_id').not.toBe(oldSessionId)

    // Messages should be cleared (or only the welcome message shown)
    const msgsAfter = await getMessageCount(page)
    console.log(`T05: messages after + New Job: ${msgsAfter}`)
    // The welcome static message is not in .msg.bot/.msg.user so count should be 0
    expect(msgsAfter, 'Chat should be empty after + New Job').toBe(0)

    // Chat input should be ready
    await expect(page.locator('.chat-input-wrap input')).toBeEnabled()

    console.log(`T05 PASSED — new session ${newSid} started, old session ${oldSessionId} retained.`)
    console.log(`  Old session: app.airecruiterz.com/en/chat?session_id=${oldSessionId}`)
    console.log(`  New session: app.airecruiterz.com/en/chat?session_id=${newSid}`)
  })
})
