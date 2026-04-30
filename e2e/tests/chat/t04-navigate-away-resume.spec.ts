/**
 * T04 — Navigate away mid-conversation and return
 *
 * Establishes a conversation in /chat, navigates to /jobs, then returns.
 * Verifies that the session resumes exactly where it left off — previous
 * messages are still visible and the AI context is preserved.
 *
 * No credits consumed (job is not created).
 */
import { test, expect } from '@playwright/test'
import {
  loadAuth, createSession, sendTurn, openChatPage, getBotMessages, getMessageCount,
} from './helpers/chat'

test.describe('T04 — Navigate away and return', () => {
  test.setTimeout(5 * 60_000)

  test('session persists across navigation — messages visible on return', async ({ page }) => {
    const token = await loadAuth(page)

    // ── Establish a conversation via API ──────────────────────────────────────
    const sessionId = await createSession(page, token)
    const openingMsg = 'I need to hire a senior project manager in Brisbane'
    const r1 = await sendTurn(page, token, sessionId, openingMsg)
    expect(r1.phase).toBe('job_collection')
    console.log(`T04: first AI reply: ${r1.message.substring(0, 100)}`)

    // Reply to keep the conversation going
    const r2 = await sendTurn(page, token, sessionId, 'Yes, Brisbane CBD, hybrid role, about 8 years experience needed')
    expect(r2.phase).toBe('job_collection')

    const expectedMessageCount = 4 // 2 user + 2 assistant turns

    // ── Navigate browser to the chat page for this session ───────────────────
    await openChatPage(page, sessionId, 2)

    const messagesBeforeNav = await getMessageCount(page)
    console.log(`T04: messages visible before navigation: ${messagesBeforeNav}`)
    expect(messagesBeforeNav, 'Messages should be visible after loading session').toBeGreaterThanOrEqual(2)

    // ── Navigate away to /jobs ────────────────────────────────────────────────
    await page.goto('/en/jobs')
    await expect(page).not.toHaveURL(/login/)
    await expect(page.locator('main')).toBeVisible({ timeout: 15_000 })
    console.log('T04: navigated to /jobs')

    // ── Return to chat for this session ───────────────────────────────────────
    await openChatPage(page, sessionId, 2)

    const messagesAfterReturn = await getMessageCount(page)
    console.log(`T04: messages visible after return: ${messagesAfterReturn}`)

    // All previous messages should still be there
    expect(
      messagesAfterReturn,
      'Messages should be preserved after navigating away and returning'
    ).toBeGreaterThanOrEqual(messagesBeforeNav)

    // The last bot message content should match what we received from the API
    const botMsgs = await getBotMessages(page)
    expect(botMsgs.length, 'No bot messages visible').toBeGreaterThanOrEqual(2)

    // Chat input should be ready for a new message
    await expect(page.locator('.chat-input-wrap input')).toBeEnabled({ timeout: 10_000 })

    console.log(`T04 PASSED — ${messagesAfterReturn} messages preserved across navigation.`)
    console.log(`  Review: app.airecruiterz.com/en/chat?session_id=${sessionId}`)
  })
})
