import { test } from '@playwright/test'

const BASE_URL = 'https://app.airecruiterz.com'
const EMAIL    = 'marcus@aiworkerz.com'
const PASSWORD = "ww^#i:Fi,DUD4'q"

const PROSPECTS = [
  { name: 'Tom Baker',  company: 'TalentFirst',     title: 'Managing Director',       location: 'Melbourne' },
  { name: 'Sarah Lee',  company: 'PeopleEdge',       title: 'Talent Acquisition Lead', location: 'Brisbane'  },
  { name: 'Jane Smith', company: 'Acme Recruiting',  title: 'Head of HR',              location: 'Sydney, Australia', linkedin: 'https://linkedin.com/in/janesmith' },
]

test('add test prospects via UI', async ({ page }) => {
  // Login
  await page.goto(`${BASE_URL}/en/login`)
  await page.locator('input[type="email"]').fill(EMAIL)
  await page.locator('input[type="password"]').fill(PASSWORD)
  await page.getByRole('button', { name: /sign in|log in/i }).click()
  await page.waitForURL(url => !url.pathname.includes('/login'), { timeout: 20_000 })
  console.log('Logged in ✓')

  // Navigate to Prospects tab
  await page.goto(`${BASE_URL}/en/marketing`)
  await page.waitForLoadState('networkidle')
  await page.getByRole('button', { name: 'Prospects' }).click()
  await page.waitForTimeout(1000)
  console.log('On Prospects tab ✓')

  // Add each prospect
  for (const p of PROSPECTS) {
    console.log(`Adding ${p.name}…`)
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
    await page.waitForSelector('text=Add prospect manually', { state: 'hidden', timeout: 15_000 })
    console.log(`  ✓ ${p.name} added`)
    await page.waitForTimeout(500)
  }
})
