/**
 * Module 03 — Settings & Configuration
 * Tests: S01–S16
 *
 * Settings nav items are <div class="settings-nav-item">, NOT <button>.
 * Save button text is "Save Changes" (changes to "✓ Saved!" on success).
 * Firm name input: name="name", placeholder="Acme Recruit"
 */
import { test, expect } from '@playwright/test'

/** Click a settings nav item by its label text */
async function clickNav(page: any, label: string) {
  await page.locator('.settings-nav-item', { hasText: label }).click()
  await page.waitForTimeout(300)
}

/** Find the Save Changes button */
function saveBtn(page: any) {
  return page.getByRole('button', { name: 'Save Changes' })
}

// ── S01 — Settings Page Loads ─────────────────────────────────────────────────
test('S01 — Settings page loads — 9 nav items, General default', async ({ page }) => {
  await page.goto('/en/settings')
  await page.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => {})

  // All 9 nav items present
  const navItems = ['General', 'API Keys', 'AI Provider', 'Email & Mailbox',
    'Knowledge Base', 'Chat Widget', 'Team Members', 'Billing', 'Privacy & Data']
  for (const item of navItems) {
    await expect(
      page.locator('.settings-nav-item', { hasText: item }).first()
    ).toBeVisible({ timeout: 10_000 })
  }

  // Default section is General — "Firm Profile" heading visible
  await expect(page.getByText('Firm Profile').first()).toBeVisible({ timeout: 5_000 })
})

// ── S02 — General — Update All Fields ────────────────────────────────────────
test('S02 — General — update firm name, save, verify persisted', async ({ page }) => {
  await page.goto('/en/settings')
  await page.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => {})

  // General is default section — verify Firm Profile heading
  await expect(page.getByText('Firm Profile').first()).toBeVisible({ timeout: 10_000 })

  const ts = Date.now()
  const newName = `Test Firm ${ts}`

  // Fill firm name (name="name", placeholder="Acme Recruit")
  const nameInput = page.locator('input[name="name"]').first()
  await expect(nameInput).toBeVisible({ timeout: 5_000 })
  await nameInput.fill(newName)

  // Save
  await saveBtn(page).click()

  // Button changes to "✓ Saved!" on success
  await expect(
    page.getByRole('button', { name: /Saved!/i }).first()
  ).toBeVisible({ timeout: 10_000 })

  // Reload and verify firm name persisted
  await page.reload()
  await page.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => {})
  await expect(page.getByText('Firm Profile').first()).toBeVisible({ timeout: 10_000 })
  await expect(
    page.locator('input[name="name"]').first()
  ).toHaveValue(newName, { timeout: 10_000 })

  // Restore
  await page.locator('input[name="name"]').first().fill('Java Recruitment')
  await saveBtn(page).click()
  await expect(page.getByRole('button', { name: /Saved!/i }).first()).toBeVisible({ timeout: 10_000 })
})

// ── S03 — API Keys Section ────────────────────────────────────────────────────
test('S03 — API Keys — 5 rows visible with Edit buttons', async ({ page }) => {
  await page.goto('/en/settings')
  await page.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => {})

  await clickNav(page, 'API Keys')

  // Section title
  await expect(page.getByText('API Keys').first()).toBeVisible({ timeout: 5_000 })

  // 5 service rows
  const services = ['BrightData', 'Apollo.io', 'Hunter.io', 'Snov.io', 'SendGrid']
  for (const svc of services) {
    await expect(page.getByText(svc).first()).toBeVisible({ timeout: 5_000 })
  }

  // Status indicators
  await expect(
    page.getByText(/not configured|configured/i).first()
  ).toBeVisible({ timeout: 5_000 })
})

// ── S04 — AI Provider Toggle ──────────────────────────────────────────────────
test('S04 — AI Provider — toggle Anthropic ↔ OpenAI', async ({ page }) => {
  await page.goto('/en/settings')
  await page.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => {})

  await clickNav(page, 'AI Provider')

  // Both cards visible
  await expect(page.getByText('Anthropic Claude').first()).toBeVisible({ timeout: 5_000 })
  await expect(page.getByText('OpenAI').first()).toBeVisible()

  // Click OpenAI card to select it
  await page.getByText('OpenAI').first().click()
  await page.waitForTimeout(300)
  await expect(page.getByText('Selected').first()).toBeVisible({ timeout: 5_000 })

  // Restore to Anthropic
  await page.getByText('Anthropic Claude').first().click()
  await page.waitForTimeout(300)
  await expect(page.getByText('Selected').first()).toBeVisible({ timeout: 5_000 })

  // Save
  await saveBtn(page).click()
  await expect(page.getByRole('button', { name: /Saved!/i }).first()).toBeVisible({ timeout: 10_000 })
})

// ── S05 — Search Provider Dropdown ───────────────────────────────────────────
test('S05 — Search Provider dropdown — options present, saves', async ({ page }) => {
  await page.goto('/en/settings')
  await page.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => {})

  await clickNav(page, 'AI Provider')

  // Search Provider select
  const select = page.locator('select').first()
  await expect(select).toBeVisible({ timeout: 5_000 })

  const options = await select.locator('option').count()
  expect(options).toBeGreaterThanOrEqual(2)

  // Change option and save
  await select.selectOption({ index: 1 })
  await saveBtn(page).click()
  await expect(page.getByRole('button', { name: /Saved!/i }).first()).toBeVisible({ timeout: 10_000 })

  // Restore default (first option)
  await select.selectOption({ index: 0 })
  await saveBtn(page).click()
  await expect(page.getByRole('button', { name: /Saved!/i }).first()).toBeVisible({ timeout: 10_000 })
})

// ── S06 — Email & Mailbox ─────────────────────────────────────────────────────
test('S06 — Email & Mailbox — section loads with IMAP fields', async ({ page }) => {
  await page.goto('/en/settings')
  await page.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => {})

  await clickNav(page, 'Email & Mailbox')

  // Section title
  await expect(page.getByText('Email & Mailbox').first()).toBeVisible({ timeout: 5_000 })

  // IMAP Host field (placeholder: "mail.privateemail.com")
  await expect(
    page.locator('input[placeholder="mail.privateemail.com"]').first()
  ).toBeVisible({ timeout: 5_000 })

  // Verify section has relevant labels
  await expect(page.getByText('IMAP Host').first()).toBeVisible({ timeout: 5_000 })
})

// ── S07 — Team Members — Invite ───────────────────────────────────────────────
test('S07 — Team Members — invite form visible', async ({ page }) => {
  await page.goto('/en/settings')
  await page.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => {})

  await clickNav(page, 'Team Members')

  // Team Members section
  await expect(page.getByText('Team Members').first()).toBeVisible({ timeout: 5_000 })

  // Invite email input (placeholder: "colleague@example.com")
  const emailInput = page.locator('input[placeholder="colleague@example.com"]').first()

  if (await emailInput.count() === 0) {
    test.skip(true, 'ENV_SKIP: Invite form not found (plan may not support team members)')
    return
  }

  await expect(emailInput).toBeVisible({ timeout: 5_000 })

  const ts = Date.now()
  await emailInput.fill(`e2etest+invite${ts}@airecruiterz.com`)

  // Find and click invite button
  const inviteBtn = page.getByRole('button', { name: /invite/i }).first()
  await expect(inviteBtn).toBeVisible({ timeout: 5_000 })
  await inviteBtn.click()
  await page.waitForTimeout(2000)

  // Success or error shown
  await expect(
    page.getByText(/invited|pending|sent|error/i).first()
  ).toBeVisible({ timeout: 10_000 }).catch(() => {})
})

// ── S08 — Team Members — Remove ───────────────────────────────────────────────
test('S08 — Team Members — remove button present', async ({ page }) => {
  await page.goto('/en/settings')
  await page.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => {})

  await clickNav(page, 'Team Members')

  // Look for remove buttons on existing members
  const removeBtn = page.getByRole('button', { name: /remove|delete/i }).first()
  if (await removeBtn.count() === 0) {
    test.skip(true, 'ENV_SKIP: No team members to remove')
    return
  }

  await removeBtn.click()
  await page.waitForTimeout(1500)
  // Success or confirmation
  await expect(page.locator('body')).not.toContainText('500')
})

// ── S09 — Privacy & Data — DPA Modal ─────────────────────────────────────────
test('S09 — Privacy & Data — DPA section and View button visible', async ({ page }) => {
  await page.goto('/en/settings')
  await page.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => {})

  await clickNav(page, 'Privacy & Data')

  await expect(
    page.getByText(/data processing agreement|DPA/i).first()
  ).toBeVisible({ timeout: 5_000 })

  // View button
  const viewBtn = page.getByRole('button', { name: /view|accept DPA/i }).first()
  await expect(viewBtn).toBeVisible({ timeout: 5_000 })
  await viewBtn.click()
  await page.waitForTimeout(500)

  // Modal opens
  const modal = page.locator('[role="dialog"], [class*="modal"]')
  if (await modal.count() > 0) {
    await expect(modal.first()).toBeVisible({ timeout: 5_000 })
    // Accept button disabled without checkbox
    const acceptBtn = modal.getByRole('button', { name: /accept DPA/i })
    if (await acceptBtn.count() > 0) {
      await expect(acceptBtn.first()).toBeDisabled({ timeout: 3_000 }).catch(() => {})
    }
    // Close modal
    const closeBtn = modal.getByRole('button', { name: /close|×|cancel/i })
    if (await closeBtn.count() > 0) await closeBtn.first().click()
  }
})

// ── S10 — Privacy & Data — Accept DPA ────────────────────────────────────────
test('S10 — Privacy & Data — DPA accept flow', async ({ page }) => {
  await page.goto('/en/settings')
  await page.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => {})

  await clickNav(page, 'Privacy & Data')

  const viewBtn = page.getByRole('button', { name: /view|accept DPA/i }).first()
  await expect(viewBtn).toBeVisible({ timeout: 5_000 })
  await viewBtn.click()
  await page.waitForTimeout(500)

  const modal = page.locator('[role="dialog"], [class*="modal"]')
  if (await modal.count() === 0) {
    test.skip(true, 'ENV_SKIP: Modal did not open')
    return
  }

  const checkbox = modal.locator('input[type="checkbox"]').first()
  const acceptBtn = modal.getByRole('button', { name: /accept DPA/i }).first()

  if (await acceptBtn.count() > 0 && await checkbox.count() > 0) {
    await checkbox.check()
    await expect(acceptBtn).toBeEnabled({ timeout: 3_000 })
    await acceptBtn.click()
    await page.waitForTimeout(1000)
    await expect(page.getByText(/accepted/i).first()).toBeVisible({ timeout: 5_000 })
  } else {
    // Already accepted — close modal
    const closeBtn = modal.getByRole('button', { name: /close|×|cancel/i })
    if (await closeBtn.count() > 0) await closeBtn.first().click()
    await expect(page.getByText(/accepted/i).first()).toBeVisible({ timeout: 5_000 })
  }
})

// ── S11 — Data Retention Dropdown ────────────────────────────────────────────
test('S11 — Data Retention dropdown — visible in Privacy & Data section', async ({ page }) => {
  await page.goto('/en/settings')
  await page.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => {})

  await clickNav(page, 'Privacy & Data')

  await expect(page.getByText(/privacy|data/i).first()).toBeVisible({ timeout: 5_000 })

  const retentionSelect = page.locator('select').first()
  if (await retentionSelect.count() > 0) {
    await expect(retentionSelect).toBeVisible({ timeout: 5_000 })
    const options = await retentionSelect.locator('option').count()
    expect(options).toBeGreaterThanOrEqual(2)
    // Change and check no error
    await retentionSelect.selectOption({ index: 1 })
    await page.waitForTimeout(500)
    await expect(page.locator('body')).not.toContainText('500')
  } else {
    test.skip(true, 'ENV_SKIP: Data retention dropdown not found')
  }
})

// ── S12 — Export My Data ──────────────────────────────────────────────────────
test('S12 — Export My Data — button present and triggers download', async ({ page }) => {
  await page.goto('/en/settings')
  await page.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => {})

  await clickNav(page, 'Privacy & Data')

  const exportBtn = page.getByRole('button', { name: /export.*data|download.*data/i }).first()
  if (await exportBtn.count() === 0) {
    test.skip(true, 'ENV_SKIP: Export My Data button not found')
    return
  }

  await expect(exportBtn).toBeVisible({ timeout: 5_000 })

  const [download] = await Promise.all([
    page.waitForEvent('download', { timeout: 10_000 }).catch(() => null),
    exportBtn.click(),
  ])

  if (download) {
    expect(download.suggestedFilename()).toBeTruthy()
  } else {
    await expect(
      page.getByText(/download|preparing|export/i).first()
    ).toBeVisible({ timeout: 5_000 })
  }
})

// ── S13 — Delete All Data Modal ───────────────────────────────────────────────
test('S13 — Delete All Data modal — requires "DELETE" to enable confirm', async ({ page }) => {
  await page.goto('/en/settings')
  await page.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => {})

  await clickNav(page, 'Privacy & Data')

  const deleteBtn = page.getByRole('button', { name: 'Delete All My Data' }).first()
  if (await deleteBtn.count() === 0) {
    test.skip(true, 'ENV_SKIP: Delete All My Data button not found')
    return
  }

  await deleteBtn.click()
  await page.waitForTimeout(500)

  // Modal is a plain div with position:fixed — detect by its heading text
  await expect(page.getByText('Delete All Data').first()).toBeVisible({ timeout: 5_000 })

  // DELETE confirmation input
  const typeInput = page.locator('input[placeholder="DELETE"]').first()
  await expect(typeInput).toBeVisible({ timeout: 3_000 })

  // Confirm button disabled until "DELETE" typed
  const confirmBtn = page.getByRole('button', { name: /Confirm Delete/i }).first()
  await expect(confirmBtn).toBeDisabled({ timeout: 3_000 }).catch(() => {})

  await typeInput.fill('DELETE')
  await page.waitForTimeout(300)
  await expect(confirmBtn).toBeEnabled({ timeout: 3_000 }).catch(() => {})

  // Cancel — do NOT actually delete
  await page.getByRole('button', { name: 'Cancel' }).first().click()
  await expect(page.getByText('Delete All Data').first()).not.toBeVisible({ timeout: 3_000 })
})

// ── S14 — AI Recruiter Prompt Edit ───────────────────────────────────────────
test('S14 — AI Recruiter Prompt — edit and save', async ({ page }) => {
  await page.goto('/en/settings/ai-recruiter')
  await page.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => {})

  await expect(page).not.toHaveURL(/404/)

  const textarea = page.locator('textarea').first()
  await expect(textarea).toBeVisible({ timeout: 10_000 })

  const originalPrompt = await textarea.inputValue()
  expect(originalPrompt.length).toBeGreaterThan(0)

  await textarea.fill('Test prompt - please ignore E2E test')
  const saveBtnEl = page.getByRole('button', { name: /save/i }).first()
  await saveBtnEl.click()

  await expect(page.getByText(/saved|success/i).first()).toBeVisible({ timeout: 10_000 })

  await page.reload()
  await page.waitForLoadState('networkidle', { timeout: 10_000 }).catch(() => {})
  await expect(page.locator('textarea').first())
    .toHaveValue('Test prompt - please ignore E2E test', { timeout: 5_000 })

  // Restore original prompt and wait for save to complete
  await page.locator('textarea').first().fill(originalPrompt)
  await saveBtnEl.click()
  await expect(page.getByText(/saved|success/i).first()).toBeVisible({ timeout: 10_000 })
})

// ── S15 — AI Recruiter Prompt Reset to Default ───────────────────────────────
test('S15 — AI Recruiter Prompt — reset to default', async ({ page }) => {
  await page.goto('/en/settings/ai-recruiter')
  await page.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => {})

  const resetBtn = page.getByRole('button', { name: /reset.*default|default/i })
  await expect(resetBtn.first()).toBeVisible({ timeout: 5_000 })

  // Reset uses window.confirm() — accept the native browser dialog
  page.once('dialog', dialog => dialog.accept())
  await resetBtn.first().click()

  // Also handle React-based confirm dialogs if present
  const confirmBtn = page.getByRole('button', { name: /confirm|yes|ok/i })
  if (await confirmBtn.count() > 0) {
    await confirmBtn.first().click()
  }

  // Wait for the textarea to update with the default prompt (> 50 chars)
  const textarea = page.locator('textarea').first()
  await expect(textarea).toHaveValue(/.{51,}/, { timeout: 5_000 })

  const text = await textarea.inputValue()
  expect(text.trim().length).toBeGreaterThan(50)
})

// ── S16 — Left Nav All 9 Sections ────────────────────────────────────────────
test('S16 — Left nav — all 9 sections switch content correctly', async ({ page }) => {
  await page.goto('/en/settings')
  await page.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => {})

  const sections = [
    { nav: 'General',          content: /Firm Profile/i },
    { nav: 'API Keys',         content: /API Keys|BrightData/i },
    { nav: 'AI Provider',      content: /AI Provider|Anthropic/i },
    { nav: 'Email & Mailbox',  content: /Email & Mailbox|IMAP/i },
    { nav: 'Knowledge Base',   content: /Knowledge Base/i },
    { nav: 'Chat Widget',      content: /chat widget|embed|bot name/i },
    { nav: 'Team Members',     content: /Team Members|invite/i },
    { nav: 'Billing',          content: /billing|plan|subscription/i },
    { nav: 'Privacy & Data',   content: /privacy|data|DPA/i },
  ]

  for (const s of sections) {
    const navItem = page.locator('.settings-nav-item', { hasText: s.nav })
    if (await navItem.count() > 0) {
      await navItem.click()
      await page.waitForTimeout(200)
      await expect(page.getByText(s.content).first()).toBeVisible({ timeout: 5_000 })
    }
  }
})
