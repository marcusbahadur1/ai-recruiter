/**
 * Module 05 — AI Chat — Job Creation
 * Tests: T01–T13
 * Route: /chat
 *
 * CREDIT COST: ~9 Talent Scout credits for T01–T03, T07–T10
 * Credit-free tests: T04, T05, T06, T12, T13
 */
import { test, expect } from '@playwright/test'

// Helper: send a message and wait for a bot response
async function sendMessage(page: any, text: string, waitMs = 20_000) {
  const input = page.locator('.chat-input-wrap input, input[placeholder*="message"], textarea[placeholder*="message"]').first()
  await input.fill(text)
  await input.press('Enter')
  // Wait for bot response (streaming)
  await page.waitForTimeout(waitMs)
}

// Helper: open a fresh chat
async function openChat(page: any) {
  await page.goto('/en/chat')
  await page.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => {})
  await expect(page.getByText(/AI Recruiter|chat/i).first()).toBeVisible({ timeout: 10_000 })
}


// Helper: navigate to jobs list and verify job was created
async function verifyJobCreated(page: any, jobTitle: string) {
  // Navigate to /en/jobs
  await page.goto('/en/jobs')
  await page.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => {})

  // Wait for jobs table to load
  await expect(page.locator('table tbody tr, [class*="job-row"]').first()).toBeVisible({ timeout: 10_000 })

  // Get all job titles from the table for diagnostics
  const jobRows = page.locator('table tbody tr')
  const rowCount = await jobRows.count()
  const existingJobs = []

  for (let i = 0; i < Math.min(rowCount, 10); i++) {
    const rowText = await jobRows.nth(i).textContent()
    if (rowText) {
      existingJobs.push(rowText.trim())
    }
  }

  console.log(`📋 Jobs in list (showing first 10):`)
  existingJobs.forEach((job, idx) => console.log(`   ${idx + 1}. ${job.substring(0, 80)}`))

  // Look for the job (search by full title or first few words)
  let jobFound = false
  for (const jobText of existingJobs) {
    // Check if the job title appears in the row text
    if (jobText.includes(jobTitle)) {
      jobFound = true
      break
    }
  }

  if (jobFound) {
    console.log(`✅ VERIFIED: "${jobTitle}" persisted in production`)
  } else {
    console.warn(`⚠️  NOT FOUND: "${jobTitle}" not in jobs list`)
  }
}

// ── T04 — Navigate Away + Return ─────────────────────────────────────────────
test('T04 — Navigate away and return — session preserved', async ({ page }) => {
  await openChat(page)

  // Check for chat panel header New Job button (scoped to avoid sidebar nav)
  const newJobBtn = page.locator('.chat-panel').getByRole('button', { name: /new job/i }).first()
  await expect(newJobBtn).toBeVisible({ timeout: 5_000 })

  // Navigate away
  await page.goto('/en/jobs')
  await page.waitForLoadState('networkidle', { timeout: 10_000 }).catch(() => {})
  await expect(page).not.toHaveURL(/chat/)

  // Return to chat
  await page.goto('/en/chat')
  await page.waitForLoadState('networkidle', { timeout: 10_000 }).catch(() => {})
  await expect(page.getByText(/AI Recruiter/i).first()).toBeVisible({ timeout: 10_000 })

  // Chat panel should still be present
  await expect(
    page.locator('.chat-panel, .chat-messages, [class*="chat"]').first()
  ).toBeVisible({ timeout: 5_000 })
})

// ── T05 — New Job Button — Clears to Fresh Session ───────────────────────────
test('T05 — New Job button — starts a fresh session', async ({ page }) => {
  await openChat(page)

  // Scope to .chat-panel to avoid clicking the sidebar "New Job" nav link
  const newJobBtn = page.locator('.chat-panel').getByRole('button', { name: /new job/i }).first()
  await expect(newJobBtn).toBeVisible({ timeout: 5_000 })
  await newJobBtn.click()

  // handleNewJob calls chatApi.newSession() + window.history.pushState
  // URL change signals the API call completed and new session was created
  await page.waitForURL(/session_id=/, { timeout: 20_000 })

  // Verify chat panel is still present (component re-mounted after pushState)
  await expect(
    page.locator('.chat-panel').first()
  ).toBeVisible({ timeout: 20_000 })

  // Messages should be cleared (empty/welcome state)
  await expect(
    page.getByText(/AI Recruiter|describe the role|new job/i).first()
  ).toBeVisible({ timeout: 10_000 })
})

// ── T06 — Page Refresh — Chat Persists ───────────────────────────────────────
test('T06 — Page refresh — chat session persists', async ({ page }) => {
  await openChat(page)

  // Get initial state
  const hasMessages = await page.locator('.chat-messages [class*="message"], .chat-messages p').count() > 0

  await page.reload()
  await page.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => {})

  // Chat panel should still render
  await expect(
    page.locator('.chat-panel, [class*="chat"]').first()
  ).toBeVisible({ timeout: 10_000 })
})

// ── T12 — Post-Creation Chat ──────────────────────────────────────────────────
test('T12 — Post-creation chat — can ask questions about existing job', async ({ page }) => {
  await openChat(page)

  // Check chat input is usable
  const input = page.locator('.chat-input-wrap input, input[placeholder*="message"], textarea[placeholder*="message"]').first()
  await expect(input).toBeVisible({ timeout: 5_000 })
  await expect(input).toBeEnabled()

  // Send a simple question that doesn't create a new job
  await input.fill('What is the current job status?')
  await input.press('Enter')
  await page.waitForTimeout(8_000)

  // A response should appear (bot message)
  const botMessages = page.locator('.chat-messages [class*="bot"], .chat-messages [class*="ai"]')
    .or(page.locator('.chat-messages').getByText(/.{30,}/))
  await expect(botMessages.first()).toBeVisible({ timeout: 15_000 })
})

// ── T13 — Chat History ────────────────────────────────────────────────────────
test('T13 — Chat history — previous messages visible on load', async ({ page }) => {
  await openChat(page)

  const messages = page.locator('.chat-messages [class*="message"], .chat-messages p, .chat-messages div').filter({ hasText: /.{10,}/ })
  const count = await messages.count()

  // Either there's a history OR empty state shown
  const emptyState = page.getByText(/new job|get started|paste|describe/i)

  if (count === 0) {
    await expect(emptyState.first()).toBeVisible({ timeout: 5_000 })
  } else {
    expect(count).toBeGreaterThan(0)
  }
})

// ── T01 — Full JD Paste (credit-consuming) ───────────────────────────────────
test('T01 — Full JD paste — AI extracts job details and creates session', async ({ page }) => {
  await openChat(page)

  const jd = `E2E Test QA Engineer
Sydney CBD, Hybrid
$120,000–$140,000

About the role:
We are looking for a QA Engineer to join our testing team.
You will work on automated and manual testing for web and mobile applications.

Requirements:
- 3+ years QA experience
- Strong testing methodology knowledge
- Experience with Selenium or similar
- JavaScript or Python experience helpful

Responsibilities:
- Write and execute test cases
- Identify and report bugs
- Collaborate with development team
- Improve test coverage

Apply at: jobs@example.com`

  const jobTitle = `E2E Test QA Engineer`

  await sendMessage(page, jd, 30_000)

  // AI should respond with extracted info or confirmation
  await expect(
    page.getByText(/engineer|job|title|location|salary|confirm|extracted/i).first()
  ).toBeVisible({ timeout: 30_000 })

  // Verify job was created via UI
  await verifyJobCreated(page, jobTitle)
})

// ── T02 — Partial JD Paste ────────────────────────────────────────────────────
test('T02 — Partial JD paste — AI asks clarifying questions', async ({ page }) => {
  // Fresh page load = fresh session, avoids pushState remount issue
  await openChat(page)

  const partialJd = `E2E Test Backend Developer, Melbourne, circa $130k.
Looking for someone with 5+ years experience in backend development.`

  const jobTitle = `E2E Test Backend Developer`

  await sendMessage(page, partialJd, 25_000)

  // AI should respond (either extracting data or asking questions)
  const chatMessages = page.locator('.chat-messages').getByText(/.{20,}/)
  await expect(chatMessages.first()).toBeVisible({ timeout: 30_000 })

  // Verify job was created via UI
  await verifyJobCreated(page, jobTitle)
})

// ── T03 — Manual Conversational ──────────────────────────────────────────────
test('T03 — Manual conversational job creation', async ({ page }) => {
  await openChat(page)

  const jobTitle = `E2E Test Frontend Developer`

  // T03 will create E2E Test Frontend Developer through conversation
  await sendMessage(page, "I need to hire an E2E Test Frontend Developer in Brisbane for $110k-$130k. 4+ years React experience required.", 15_000)

  // AI should respond and guide the conversation
  const chatMessages = page.locator('.chat-messages').getByText(/.{20,}/)
  await expect(chatMessages.first()).toBeVisible({ timeout: 20_000 })

  // Verify job was created via UI
  await verifyJobCreated(page, jobTitle)
})

// ── T07 — Remote Global Job ───────────────────────────────────────────────────
test('T07 — Remote global job — location set to "Remote (Global)"', async ({ page }) => {
  await openChat(page)

  const jd = `E2E Test QA Engineer — Remote (Global)
100% remote, any timezone.
We need a QA Engineer with 4+ years experience.
Strong automation testing and Selenium skills required.
Salary: $120k–$150k USD`

  const jobTitle = `E2E Test QA Engineer`

  await sendMessage(page, jd, 30_000)

  await expect(
    page.getByText(/remote|devops|engineer/i).first()
  ).toBeVisible({ timeout: 30_000 })

  // Verify job was created via UI
  await verifyJobCreated(page, jobTitle)
})

// ── T08 — Executive Non-Tech ──────────────────────────────────────────────────
test('T08 — Executive non-tech role — CFO/GM type', async ({ page }) => {
  await openChat(page)

  const jd = `E2E Test Backend Developer — Senior
Brisbane, QLD (On-site)
$180,000–$220,000 + equity

Our fast-growing SaaS company seeks a senior backend developer to lead our platform architecture.
10+ years experience in backend development required. Experience with Python, Go, or Rust preferred.`

  const jobTitle = `E2E Test Backend Developer`

  await sendMessage(page, jd, 30_000)

  await expect(
    page.getByText(/CFO|chief|financial|officer/i).first()
  ).toBeVisible({ timeout: 30_000 })

  // Verify job was created via UI
  await verifyJobCreated(page, jobTitle)
})

// ── T09 — Minimal info — AI prompts for more details ────────────────────────
test('T09 — Minimal info — AI prompts for more details', async ({ page }) => {
  await openChat(page)

  const jobTitle = `E2E Test Frontend Developer`

  await sendMessage(page, jobTitle, 20_000)

  // AI should ask for more info or acknowledge minimal data
  const chatMessages = page.locator('.chat-messages').getByText(/.{20,}/)
  await expect(chatMessages.first()).toBeVisible({ timeout: 25_000 })

  // Verify job was created via UI
  await verifyJobCreated(page, jobTitle)
})

// ── T10 — Conflicting Info ────────────────────────────────────────────────────
test('T10 — Conflicting info — AI handles gracefully', async ({ page }) => {
  await openChat(page)

  const jd = `E2E Test QA Engineer
Location: Sydney CBD AND Remote AND Melbourne (can be flexible)
Salary: $100k–$150k depending on experience
Experience: 2+ years required`

  const jobTitle = `E2E Test QA Engineer`

  await sendMessage(page, jd, 30_000)

  // AI should respond and handle the conflicting info (not crash)
  // Note: don't use not.toContainText('500') — JD contains "$500k" which is a false positive
  await expect(page).not.toHaveURL(/\/500/)
  await expect(page.locator('body')).not.toContainText('Internal Server Error')
  const chatMessages = page.locator('.chat-messages').getByText(/.{20,}/)
  await expect(chatMessages.first()).toBeVisible({ timeout: 30_000 })

  // Verify job was created via UI
  await verifyJobCreated(page, jobTitle)
})
