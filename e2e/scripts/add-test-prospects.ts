/**
 * add-test-prospects.ts
 *
 * One-off script: logs in as super admin and adds 3 test prospects
 * via the "Add manually" modal on the Prospects tab.
 *
 * Run: npx ts-node --esm scripts/add-test-prospects.ts
 * Or:  npx playwright test --config=scripts/playwright.script.config.ts
 */
import { chromium } from '@playwright/test'

const BASE_URL = 'https://app.airecruiterz.com'
const EMAIL    = 'marcus@aiworkerz.com'
const PASSWORD = 'Brisbane1!'

const PROSPECTS = [
  { name: 'Tom Baker',   company: 'TalentFirst',  title: 'Managing Director',       location: 'Melbourne' },
  { name: 'Sarah Lee',   company: 'PeopleEdge',   title: 'Talent Acquisition Lead', location: 'Brisbane'  },
  { name: 'Jane Smith',  company: 'Acme Recruiting', title: 'Head of HR',           location: 'Sydney, Australia', linkedin: 'https://linkedin.com/in/janesmith' },
]

async function main() {
  const browser = await chromium.launch({ headless: true })
  const page    = await browser.newPage()

  // ── 1. Log in ──────────────────────────────────────────────────────────────
  console.log('Logging in…')
  await page.goto(`${BASE_URL}/en/login`)
  await page.locator('input[type="email"]').fill(EMAIL)
  await page.locator('input[type="password"]').fill(PASSWORD)
  await page.getByRole('button', { name: /sign in|log in/i }).click()
  await page.waitForURL(url => !url.pathname.includes('/login'), { timeout: 20_000 })
  console.log('Logged in ✓')

  // ── 2. Navigate to Client Pipeline → Prospects tab ────────────────────────
  await page.goto(`${BASE_URL}/en/marketing`)
  await page.waitForLoadState('networkidle')
  await page.getByRole('button', { name: 'Prospects' }).click()
  await page.waitForTimeout(1000)
  console.log('On Prospects tab ✓')

  // ── 3. Add each prospect ───────────────────────────────────────────────────
  for (const p of PROSPECTS) {
    console.log(`Adding: ${p.name}…`)

    await page.getByRole('button', { name: '+ Add manually' }).click()
    await page.waitForTimeout(500)

    await page.getByPlaceholder('e.g. Jane Smith').fill(p.name)
    await page.getByPlaceholder('e.g. Acme Recruiting').fill(p.company)
    await page.getByPlaceholder('e.g. Head of HR').fill(p.title)
    await page.getByPlaceholder('e.g. Sydney, Australia').fill(p.location)
    if (p.linkedin) {
      await page.getByPlaceholder('https://linkedin.com/in/...').fill(p.linkedin)
    }

    await page.getByRole('button', { name: 'Add prospect' }).click()

    // Wait for modal to close (prospect added successfully)
    await page.waitForSelector('text=Add prospect manually', { state: 'hidden', timeout: 15_000 })
    console.log(`  ✓ ${p.name} added`)
    await page.waitForTimeout(500)
  }

  console.log('\nAll prospects added successfully.')
  await browser.close()
}

main().catch(err => { console.error(err); process.exit(1) })
