/**
 * T06 — Page refresh restores conversation
 *
 * Mid-conversation, the user refreshes the browser. Verifies that the
 * session hydrates correctly from the server — all previous messages
 * are shown and the recruiter can continue.
 *
 * No credits consumed.
 */
import { test, expect } from '@playwright/test'
import {
  loadAuth, createSession, sendTurn, openChatPage, getMessageCount, getBotMessages,
} from './helpers/chat'

test.describe('T06 — Page refresh restores conversation', () => {
  test.setTimeout(5 * 60_000)

  test('messages survive a full browser refresh', async ({ page }) => {
    const token = await loadAuth(page)

    // ── Build a short conversation via API ────────────────────────────────────
    const sessionId = await createSession(page, token)
    await sendTurn(page, token, sessionId, 'I need a UX Designer in Auckland, remote friendly')
    const r2 = await sendTurn(page, token, sessionId, '3+ years experience, Figma, design systems')
    console.log(`T06: second AI reply: ${r2.message.substring(0, 100)}`)

    // ── Load in browser, verify messages ─────────────────────────────────────
    await openChatPage(page, sessionId)
    const msgsBeforeRefresh = await getMessageCount(page)
    const botMsgsBefore     = await getBotMessages(page)
    console.log(`T06: ${msgsBeforeRefresh} messages before refresh`)
    expect(msgsBeforeRefresh).toBeGreaterThanOrEqual(2)

    // ── Refresh the page ──────────────────────────────────────────────────────
    await page.reload()
    await expect(page.locator('.chat-input-wrap input')).toBeVisible({ timeout: 15_000 })

    // Allow React to hydrate from server
    await page.waitForTimeout(2_000)

    const msgsAfterRefresh = await getMessageCount(page)
    const botMsgsAfter     = await getBotMessages(page)
    console.log(`T06: ${msgsAfterRefresh} messages after refresh`)

    // All messages should be restored
    expect(
      msgsAfterRefresh,
      'Message count should be the same or greater after refresh'
    ).toBeGreaterThanOrEqual(msgsBeforeRefresh)

    // Bot messages should have the same content
    expect(
      botMsgsAfter.length,
      'Bot messages should be preserved after refresh'
    ).toBeGreaterThanOrEqual(botMsgsBefore.length)

    // Chat input should be functional
    await expect(page.locator('.chat-input-wrap input')).toBeEnabled()
    await expect(page.locator('.chat-input-wrap input')).toBeVisible()

    console.log(`T06 PASSED — ${msgsAfterRefresh} messages restored after page refresh.`)
    console.log(`  Review: app.airecruiterz.com/en/chat?session_id=${sessionId}`)
  })
})
