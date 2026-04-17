/**
 * 03-dashboard-pages.spec.ts
 *
 * Verifies every protected dashboard page loads without a JS crash,
 * white screen, or error boundary. Uses the saved auth state.
 */
import { test, expect } from '@playwright/test'

// Pages that must load with no console errors
const PAGES: { name: string; path: string; contains: string }[] = [
  { name: 'Home / Dashboard',   path: '/',              contains: 'Dashboard' },
  { name: 'AI Recruiter Chat',  path: '/chat',          contains: 'AI Recruiter' },
  { name: 'Jobs list',          path: '/jobs',          contains: 'Jobs' },
  { name: 'Candidates list',    path: '/candidates',    contains: 'Candidates' },
  { name: 'Applications list',  path: '/applications',  contains: 'Applications' },
  { name: 'Billing',            path: '/billing',       contains: 'Current Plan' },
  { name: 'Settings',           path: '/settings',      contains: 'Settings' },
  { name: 'Help',               path: '/help',          contains: 'Help' },
  { name: 'Quick Start',        path: '/quickstart',    contains: 'Quick Start' },
  { name: 'Super Admin',        path: '/super-admin',   contains: 'Super Admin' },
]

for (const { name, path, contains } of PAGES) {
  test(`${name} (${path}) loads`, async ({ page }) => {
    const errors: string[] = []
    page.on('console', (msg) => {
      if (msg.type() === 'error') errors.push(msg.text())
    })
    page.on('pageerror', (err) => errors.push(err.message))

    await page.goto(path)

    // Must not redirect to login
    await expect(page).not.toHaveURL(/login/, { timeout: 8_000 })

    // Must show expected content
    await expect(page.locator(`text=${contains}`).first()).toBeVisible({ timeout: 10_000 })

    // No unhandled JS errors (filter out known third-party noise)
    const criticalErrors = errors.filter(
      (e) => !e.includes('favicon') &&
             !e.includes('extension') &&
             !e.includes('fonts.gstatic.com') &&
             !e.includes('fonts.googleapis.com') &&
             // Bare ERR_FAILED lines are font/external resource CORS failures from
             // the x-e2e-test header being sent cross-origin — not app errors
             !(e.trim() === 'Failed to load resource: net::ERR_FAILED')
    )
    expect(criticalErrors, `JS errors on ${path}: ${criticalErrors.join('\n')}`).toHaveLength(0)
  })
}

test('sidebar navigation links are all present', async ({ page }) => {
  await page.goto('/')
  const expectedLinks = ['/chat', '/jobs', '/candidates', '/applications', '/billing', '/settings']
  for (const href of expectedLinks) {
    await expect(
      page.locator(`a[href*="${href}"]`).first(),
      `Sidebar link to ${href} missing`
    ).toBeVisible()
  }
})
