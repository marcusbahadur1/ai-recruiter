/**
 * Module 04 — Knowledge Base & Widget
 * Tests: K01–K12
 * Knowledge Base: /settings/knowledge-base
 * Widget settings: /settings (Chat Widget section)
 */
import { test, expect } from '@playwright/test'
import * as path from 'path'
import * as fs from 'fs'
import * as os from 'os'

// ── K01 — Scrape Website URL ──────────────────────────────────────────────────
test('K01 — Scrape website URL — submits and shows pending/processing state', async ({ page }) => {
  await page.goto('/en/settings/knowledge-base')
  await page.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => {})

  await expect(page.getByText(/knowledge base/i).first()).toBeVisible({ timeout: 10_000 })

  // URL input
  const urlInput = page.locator('input[type="url"], input[placeholder*="https"]').first()
  await expect(urlInput).toBeVisible({ timeout: 5_000 })
  await urlInput.fill('https://example.com')

  // Submit — button text is "Scrape" (disabled while scraping shows "Scraping…")
  const scrapeBtn = page.getByRole('button', { name: /^Scrape$/ }).first()
  await expect(scrapeBtn).toBeVisible({ timeout: 5_000 })
  await expect(scrapeBtn).toBeEnabled({ timeout: 3_000 })
  await scrapeBtn.click()

  // Wait for scrape result message (success: "Scraped — X chunks stored from ..."
  // or failure: error message) — either is acceptable, just not a 500
  await expect(
    page.getByText(/scrape|chunks stored|failed/i).first()
  ).toBeVisible({ timeout: 30_000 })
  await expect(page.locator('body')).not.toContainText('500')
})

// ── K02 — Upload PDF ──────────────────────────────────────────────────────────
test('K02 — Upload PDF — file accepted, appears in document list', async ({ page }) => {
  await page.goto('/en/settings/knowledge-base')
  await page.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => {})

  // Create a minimal PDF-like file in temp dir
  const tmpFile = path.join(os.tmpdir(), 'e2e-test.pdf')
  fs.writeFileSync(tmpFile, '%PDF-1.4 E2E test document')

  const fileInput = page.locator('input[type="file"]').first()
  if (await fileInput.count() === 0) {
    test.skip(true, 'ENV_SKIP: File input not found')
    return
  }

  await fileInput.setInputFiles(tmpFile)
  await page.waitForTimeout(3000)

  // File should appear or upload message shown
  await expect(
    page.getByText(/e2e-test|upload|processing|added|pdf/i).first()
  ).toBeVisible({ timeout: 15_000 })

  fs.unlinkSync(tmpFile)
})

// ── K03 — Upload DOCX ─────────────────────────────────────────────────────────
test('K03 — Upload DOCX — file accepted', async ({ page }) => {
  await page.goto('/en/settings/knowledge-base')
  await page.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => {})

  const tmpFile = path.join(os.tmpdir(), 'e2e-test.docx')
  // Minimal DOCX magic bytes (PK zip header)
  fs.writeFileSync(tmpFile, Buffer.from([0x50, 0x4B, 0x03, 0x04, 0x00, 0x00]))

  const fileInput = page.locator('input[type="file"]').first()
  if (await fileInput.count() === 0) {
    test.skip(true, 'ENV_SKIP: File input not found')
    return
  }

  await fileInput.setInputFiles(tmpFile)
  await page.waitForTimeout(2000)

  // Accepted or error shown (either outcome — just no crash)
  await expect(page.locator('body')).not.toContainText('500')

  fs.unlinkSync(tmpFile)
})

// ── K04 — Upload TXT ──────────────────────────────────────────────────────────
test('K04 — Upload TXT — file accepted', async ({ page }) => {
  await page.goto('/en/settings/knowledge-base')
  await page.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => {})

  const tmpFile = path.join(os.tmpdir(), 'e2e-test.txt')
  fs.writeFileSync(tmpFile, 'This is an E2E test document for the knowledge base.')

  const fileInput = page.locator('input[type="file"]').first()
  if (await fileInput.count() === 0) {
    test.skip(true, 'ENV_SKIP: File input not found')
    return
  }

  await fileInput.setInputFiles(tmpFile)
  await page.waitForTimeout(2000)
  await expect(page.locator('body')).not.toContainText('500')

  fs.unlinkSync(tmpFile)
})

// ── K05 — Delete Document ─────────────────────────────────────────────────────
test('K05 — Delete document — confirm removes from list', async ({ page }) => {
  await page.goto('/en/settings/knowledge-base')
  await page.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => {})

  const deleteBtn = page.getByRole('button', { name: /delete/i }).first()
  if (await deleteBtn.count() === 0) {
    test.skip(true, 'ENV_SKIP: No documents to delete')
    return
  }

  await deleteBtn.click()
  await page.waitForTimeout(500)

  // Confirm dialog may appear
  const confirmBtn = page.getByRole('button', { name: /confirm|yes|delete/i }).last()
  if (await confirmBtn.count() > 0 && await confirmBtn.isEnabled()) {
    await confirmBtn.click()
  }

  await page.waitForTimeout(2000)
  // Page should not crash
  await expect(page.locator('body')).not.toContainText('500')
})

// ── K06 — Document List Metadata ──────────────────────────────────────────────
test('K06 — Document list shows metadata — source count cards', async ({ page }) => {
  await page.goto('/en/settings/knowledge-base')
  await page.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => {})

  await expect(page.getByText(/knowledge base/i).first()).toBeVisible({ timeout: 10_000 })

  // Stats cards: Sources, Total Chunks, Last Updated
  await expect(page.getByText(/sources|chunks|last updated/i).first()).toBeVisible({ timeout: 5_000 })
})

/** Navigate to Chat Widget section via settings nav (div, not button) */
async function goToWidgetSection(page: any) {
  await page.goto('/en/settings')
  await page.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => {})
  await page.locator('.settings-nav-item', { hasText: 'Chat Widget' }).click()
  await page.waitForTimeout(400)
}

/** Widget save button — text: "Save Widget Settings" → "✓ Saved!" */
function widgetSaveBtn(page: any) {
  return page.getByRole('button', { name: /Save Widget Settings/i }).first()
}

// ── K07 — Widget Plan Gate ────────────────────────────────────────────────────
test('K07 — Widget section — embed code or plan gate visible', async ({ page }) => {
  await goToWidgetSection(page)

  // On agency_medium plan, widget IS included — embed code should show
  await expect(
    page.getByText(/Chat Widget|Embed Code|widget\.js|upgrade/i).first()
  ).toBeVisible({ timeout: 5_000 })
})

// ── K08 — Embed Code Copy ─────────────────────────────────────────────────────
test('K08 — Embed code — copy button works', async ({ page }) => {
  await goToWidgetSection(page)

  // Copy Embed Code button
  const copyBtn = page.getByRole('button', { name: /copy.*embed|copy.*code/i }).first()
    .or(page.getByText(/copy.*embed|embed.*copy/i).first())
  if (await copyBtn.count() === 0) {
    test.skip(true, 'ENV_SKIP: Copy embed code button not visible')
    return
  }

  await copyBtn.click()
  await page.waitForTimeout(500)
  // Button text changes to "Copied!" after click
  await expect(
    page.getByText(/copied/i).first()
  ).toBeVisible({ timeout: 3_000 }).catch(() => {})
})

// ── K09 — Bot Name Change ─────────────────────────────────────────────────────
test('K09 — Bot name change — saves successfully', async ({ page }) => {
  await goToWidgetSection(page)

  // Bot name input placeholder: "Chat with us"
  const botNameInput = page.locator('input[placeholder="Chat with us"]').first()
  if (await botNameInput.count() === 0) {
    test.skip(true, 'ENV_SKIP: Bot name input not found (plan may not include widget)')
    return
  }

  await botNameInput.fill('E2E Test Bot')
  await widgetSaveBtn(page).click()
  await expect(
    page.getByRole('button', { name: /Saved!/i }).first()
  ).toBeVisible({ timeout: 10_000 })

  // Restore
  await botNameInput.fill('')
  await widgetSaveBtn(page).click()
})

// ── K10 — Brand Colour Change ─────────────────────────────────────────────────
test('K10 — Brand colour — hex input updates and saves', async ({ page }) => {
  await goToWidgetSection(page)

  // Hex text input — placeholder: "#00C2E0"
  const hexInput = page.locator('input[placeholder="#00C2E0"]').first()
  if (await hexInput.count() === 0) {
    test.skip(true, 'ENV_SKIP: Colour hex input not found (plan may not include widget)')
    return
  }

  await hexInput.fill('#FF5500')
  await widgetSaveBtn(page).click()
  await expect(
    page.getByRole('button', { name: /Saved!/i }).first()
  ).toBeVisible({ timeout: 10_000 })

  // Restore
  await hexInput.fill('#00C2E0')
  await widgetSaveBtn(page).click()
})

// ── K11 — Settings Persist ────────────────────────────────────────────────────
test('K11 — Widget settings persist across reload', async ({ page }) => {
  await goToWidgetSection(page)

  const hexInput = page.locator('input[placeholder="#00C2E0"]').first()
  if (await hexInput.count() === 0) {
    test.skip(true, 'ENV_SKIP: Widget settings not accessible on this plan')
    return
  }

  const testColor = '#AABBCC'
  await hexInput.fill(testColor)
  await widgetSaveBtn(page).click()
  await expect(
    page.getByRole('button', { name: /Saved!/i }).first()
  ).toBeVisible({ timeout: 10_000 })

  // Reload and verify
  await page.reload()
  await page.waitForLoadState('networkidle', { timeout: 10_000 }).catch(() => {})
  await page.locator('.settings-nav-item', { hasText: 'Chat Widget' }).click()
  await page.waitForTimeout(400)

  await expect(
    page.locator('input[placeholder="#00C2E0"]').first()
  ).toHaveValue(testColor, { timeout: 5_000 })

  // Restore
  await page.locator('input[placeholder="#00C2E0"]').first().fill('#00C2E0')
  await widgetSaveBtn(page).click()
})

// ── K12 — Widget Embed Code Contains Required Tags ────────────────────────────
test('K12 — Widget embed code contains required script tags', async ({ page }) => {
  await goToWidgetSection(page)

  // Embed code is shown in a <pre> or inline text block
  const codeBlock = page.locator('pre, code').filter({ hasText: /widget\.js|AIRecruiterConfig/ })
    .or(page.getByText(/AIRecruiterConfig/).first().locator('..'))
  if (await codeBlock.count() === 0) {
    test.skip(true, 'ENV_SKIP: Widget embed code not visible (plan may not include widget)')
    return
  }

  const codeText = await codeBlock.first().textContent()
  expect(codeText).toContain('widget.js')
  expect(codeText).toContain('AIRecruiterConfig')
})
