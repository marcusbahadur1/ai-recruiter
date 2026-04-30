/**
 * chat.ts — shared helpers for AI Chat test suite
 */
import { expect, type Page } from '@playwright/test'

const API_URL = (process.env.PROD_API_URL ?? 'https://airecruiterz-api.fly.dev').replace(/\/$/, '')

// ── Auth ───────────────────────────────────────────────────────────────────────

/** Extract the Supabase JWT from browser localStorage. */
export async function getToken(page: Page): Promise<string> {
  return page.evaluate(() => {
    for (let i = 0; i < localStorage.length; i++) {
      const key = localStorage.key(i) ?? ''
      if (key.includes('auth-token') || key.includes('supabase')) {
        try {
          const val = JSON.parse(localStorage.getItem(key) ?? '{}')
          const token = val?.access_token ?? val?.session?.access_token ?? ''
          if (token) return token
        } catch { /* skip */ }
      }
    }
    return ''
  }) as Promise<string>
}

/** Navigate to dashboard home and return the auth token. */
export async function loadAuth(page: Page): Promise<string> {
  await page.goto('/')
  const token = await getToken(page)
  expect(token, 'Auth token missing — login may have failed').toBeTruthy()
  return token
}

// ── API helpers ────────────────────────────────────────────────────────────────

export interface TurnResult {
  phase:   string
  message: string
}

/** Send one chat message, return phase + message text. */
export async function sendTurn(
  page: Page,
  token: string,
  sessionId: string,
  message: string,
): Promise<TurnResult> {
  const res = await page.request.post(
    `${API_URL}/api/v1/chat-sessions/${sessionId}/message`,
    {
      headers: { Authorization: `Bearer ${token}` },
      data:    { message },
    }
  )
  const status = res.status()
  expect(status, `sendTurn failed (${status}): ${await res.text()}`).toBe(200)
  const body = await res.json()
  return {
    phase:   body.phase   ?? 'unknown',
    message: body.message ?? '',
  }
}

/** Create a fresh chat session, return session ID. */
export async function createSession(page: Page, token: string): Promise<string> {
  const res = await page.request.post(
    `${API_URL}/api/v1/chat-sessions/new`,
    { headers: { Authorization: `Bearer ${token}` } }
  )
  expect(res.status()).toBe(201)
  const body = await res.json()
  expect(body.id, 'new session missing id').toBeTruthy()
  return body.id
}

/** Get tenant data (plan, credits). */
export async function getTenant(page: Page, token: string) {
  const res = await page.request.get(
    `${API_URL}/api/v1/tenants/me`,
    { headers: { Authorization: `Bearer ${token}` } }
  )
  expect(res.status()).toBe(200)
  return res.json()
}

// ── Conversation loop ──────────────────────────────────────────────────────────

export interface JobCreationResult {
  created:    boolean
  sessionId:  string
  turns:      number
  lastPhase:  string
}

/**
 * Drive a chat session to job creation.
 *
 * Turn 0:      send the opening message (job description or first question)
 * Payment:     auto-send 'confirm' when phase transitions to 'payment'
 * Job Summary: auto-send 'confirm' when the AI outputs a 📋 Job Summary block
 * Otherwise:   send the genericReply for all other AI turns
 *
 * Returns once phase = 'recruitment' or maxTurns is exhausted.
 */
export async function runToJobCreation(
  page: Page,
  token: string,
  openingMessage: string,
  options: {
    maxTurns?:     number
    genericReply?: string
    sessionId?:    string
  } = {}
): Promise<JobCreationResult> {
  const maxTurns     = options.maxTurns     ?? 30
  const genericReply = options.genericReply ?? 'yes, that looks good, please continue'
  const sessionId    = options.sessionId    ?? (await createSession(page, token))

  let currentPhase = 'job_collection'
  let turns        = 0

  for (let i = 0; i < maxTurns; i++) {
    let userMessage: string
    if (i === 0) {
      userMessage = openingMessage
    } else if (currentPhase === 'payment') {
      userMessage = 'confirm'
    } else {
      userMessage = genericReply
    }

    const result = await sendTurn(page, token, sessionId, userMessage)
    currentPhase = result.phase
    turns        = i + 1

    if (currentPhase === 'recruitment') {
      return { created: true, sessionId, turns, lastPhase: currentPhase }
    }
    if (currentPhase === 'post_recruitment') {
      return { created: false, sessionId, turns, lastPhase: currentPhase }
    }

    // If AI showed a Job Summary block and we're still in job_collection,
    // the next turn should confirm — handled automatically above via genericReply,
    // but we add explicit detection for robustness.
    if (hasJobSummaryBlock(result.message) && currentPhase === 'job_collection') {
      const confirmResult = await sendTurn(page, token, sessionId, 'confirm')
      turns++
      currentPhase = confirmResult.phase
      if (currentPhase === 'payment') continue   // will auto-confirm next turn
      if (currentPhase === 'recruitment') {
        return { created: true, sessionId, turns, lastPhase: currentPhase }
      }
    }
  }

  return { created: false, sessionId, turns, lastPhase: currentPhase }
}

/** True if the AI message contains a Job Summary block. */
export function hasJobSummaryBlock(message: string): boolean {
  return message.includes('📋') && message.includes('Job Summary')
}

// ── Job verification ───────────────────────────────────────────────────────────

/** Return the first job created after a snapshot of existing job IDs. */
export async function findNewJob(
  page: Page,
  token: string,
  existingIds: Set<string>
): Promise<{ id: string; title: string } | undefined> {
  const res = await page.request.get(
    `${API_URL}/api/v1/jobs?limit=100`,
    { headers: { Authorization: `Bearer ${token}` } }
  )
  expect(res.status()).toBe(200)
  const body = await res.json()
  return (body.items as Array<{ id: string; title: string }>)
    .find((j) => !existingIds.has(j.id))
}

/** Snapshot current job IDs. Pass to findNewJob after the test to diff. */
export async function snapshotJobIds(page: Page, token: string): Promise<Set<string>> {
  const res = await page.request.get(
    `${API_URL}/api/v1/jobs?limit=100`,
    { headers: { Authorization: `Bearer ${token}` } }
  )
  expect(res.status()).toBe(200)
  const body = await res.json()
  return new Set<string>((body.items as Array<{ id: string }>).map((j) => j.id))
}

// ── Browser UI helpers ─────────────────────────────────────────────────────────

/**
 * Navigate to the chat page and wait for it to be ready.
 * Pass sessionId to deep-link to a specific session.
 */
export async function openChatPage(page: Page, sessionId?: string): Promise<void> {
  const url = sessionId ? `/en/chat?session_id=${sessionId}` : '/en/chat'
  await page.goto(url)
  await expect(page).not.toHaveURL(/login/, { timeout: 15_000 })
  // Wait for the chat input to be visible
  await expect(page.locator('.chat-input-wrap input')).toBeVisible({ timeout: 15_000 })
}

/**
 * Type a message into the chat input and press Enter.
 * Waits for streaming to complete (cursor disappears) before returning.
 */
export async function sendMessageViaUI(page: Page, message: string): Promise<string> {
  const input = page.locator('.chat-input-wrap input')
  await input.fill(message)
  await input.press('Enter')

  // Wait for the streaming cursor to appear then disappear
  // (indicates AI started then finished responding)
  try {
    await page.locator('.streaming-cursor').waitFor({ state: 'visible',  timeout: 10_000 })
    await page.locator('.streaming-cursor').waitFor({ state: 'hidden',   timeout: 90_000 })
  } catch {
    // Cursor may have appeared and disappeared before we checked — that's fine
  }

  // Wait for input to be re-enabled (send button no longer disabled)
  await expect(page.locator('button.send-btn')).not.toBeDisabled({ timeout: 10_000 })

  // Return the last bot message text
  const botMessages = page.locator('.msg.bot .msg-bubble')
  const count = await botMessages.count()
  return count > 0 ? (await botMessages.nth(count - 1).innerText()) : ''
}

/**
 * Count the number of visible messages (user + assistant) in the chat UI.
 */
export async function getMessageCount(page: Page): Promise<number> {
  return page.locator('.msg.bot, .msg.user').count()
}

/**
 * Return text of all bot messages currently shown in the chat UI.
 */
export async function getBotMessages(page: Page): Promise<string[]> {
  const els = page.locator('.msg.bot .msg-bubble')
  const count = await els.count()
  const texts: string[] = []
  for (let i = 0; i < count; i++) {
    texts.push(await els.nth(i).innerText())
  }
  return texts
}
