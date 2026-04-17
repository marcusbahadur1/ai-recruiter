/**
 * 05-locale-switching.spec.ts
 *
 * E2E: Switching locale to DE / ES / FR renders translated UI.
 *
 * Routing: next-intl prefixes every route with the locale segment.
 *   /en/jobs  → English jobs page
 *   /de/jobs  → German  jobs page   (t('jobs.title') = "Stellen")
 *   /es/jobs  → Spanish jobs page   (t('jobs.title') = "Empleos")
 *   /fr/jobs  → French  jobs page   (t('jobs.title') = "Emplois")
 *
 * What is tested per locale:
 *   a. Login page (public, no auth needed): translated email label, sign-in
 *      button text, and "no account" link.
 *   b. Jobs page (authenticated): translated page heading.
 *   c. Candidates page (authenticated): translated page heading.
 *   d. Dashboard (authenticated): at least one translated stat card label.
 *
 * Note: the sidebar nav labels in layout.tsx are hardcoded English constants
 * (not wired to useTranslations), so they are deliberately NOT tested here.
 * Pages that use useTranslations() are the scope of this suite.
 */
import { test, expect } from '@playwright/test'

// ── Expected translations keyed by locale ────────────────────────────────────

const TRANSLATIONS = {
  de: {
    loginSignIn:     'Einloggen',
    loginEmail:      'E-Mail',
    loginNoAccount:  'Kein Konto',
    jobsTitle:       'Stellen',
    candidatesTitle: 'Kandidaten',
    dashboardActive: 'Aktive Stellen',
    settingsTitle:   'Einstellungen',
  },
  es: {
    loginSignIn:     'Iniciar sesión',
    loginEmail:      'Correo electrónico',
    loginNoAccount:  'No tiene cuenta',
    jobsTitle:       'Empleos',
    candidatesTitle: 'Candidatos',
    dashboardActive: 'Empleos activos',
    settingsTitle:   'Configuración',
  },
  fr: {
    loginSignIn:     'Se connecter',
    loginEmail:      'E-mail',
    loginNoAccount:  'Pas de compte',
    jobsTitle:       'Emplois',
    candidatesTitle: 'Candidats',
    dashboardActive: 'Emplois actifs',
    settingsTitle:   'Paramètres',
  },
} as const

type SupportedLocale = keyof typeof TRANSLATIONS

// ── Shared helpers ────────────────────────────────────────────────────────────

/** Wait for the body to contain visible text (not just a loading spinner). */
async function waitForContent(page: Parameters<Parameters<typeof test>[1]>[0]['page']): Promise<void> {
  await page.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => {
    // networkidle can time out on pages with long-polling — fall through
  })
}

// ── Test generator ────────────────────────────────────────────────────────────

for (const locale of ['de', 'es', 'fr'] as SupportedLocale[]) {
  const tr = TRANSLATIONS[locale]

  test.describe(`Locale: ${locale.toUpperCase()}`, () => {

    // ── a. Login page (public) ──────────────────────────────────────────────
    test(`/${locale}/login — sign-in button and email label are translated`, async ({ page }) => {
      await page.goto(`/${locale}/login`)
      await waitForContent(page)

      // The sign-in button text
      await expect(
        page.getByRole('button', { name: new RegExp(tr.loginSignIn, 'i') })
      ).toBeVisible({ timeout: 10_000 })

      // The email field label
      await expect(
        page.locator('label, [placeholder]').filter({ hasText: tr.loginEmail }).first()
      ).toBeVisible({ timeout: 5_000 })

      // "No account?" style link
      await expect(page.locator('body')).toContainText(tr.loginNoAccount)
    })

    // ── b. Jobs page (authenticated) ────────────────────────────────────────
    test(`/${locale}/jobs — page heading is translated`, async ({ page }) => {
      await page.goto(`/${locale}/jobs`)

      // Must not be redirected to login
      await expect(page).not.toHaveURL(/login/, { timeout: 5_000 })
      await waitForContent(page)

      // The jobs page sets <div class="section-title">{t('title')}</div>
      // which for DE = "Stellen", ES = "Empleos", FR = "Emplois"
      await expect(
        page.locator('.section-title, h1, h2').filter({ hasText: tr.jobsTitle }).first()
      ).toBeVisible({ timeout: 12_000 })
    })

    // ── c. Candidates page (authenticated) ──────────────────────────────────
    test(`/${locale}/candidates — page heading is translated`, async ({ page }) => {
      await page.goto(`/${locale}/candidates`)

      await expect(page).not.toHaveURL(/login/, { timeout: 5_000 })
      await waitForContent(page)

      await expect(
        page.locator('.section-title, h1, h2').filter({ hasText: tr.candidatesTitle }).first()
      ).toBeVisible({ timeout: 12_000 })
    })

    // ── d. Dashboard stat card (authenticated) ──────────────────────────────
    test(`/${locale}/ — dashboard stat card label is translated`, async ({ page }) => {
      await page.goto(`/${locale}`)

      await expect(page).not.toHaveURL(/login/, { timeout: 5_000 })
      await waitForContent(page)

      // The dashboard page renders stat-card labels via t('dashboard.activeJobs')
      // DE="Aktive Stellen", ES="Empleos activos", FR="Emplois actifs"
      await expect(page.locator('body')).toContainText(tr.dashboardActive, { timeout: 12_000 })
    })

    // ── e. Settings page (authenticated) ────────────────────────────────────
    test(`/${locale}/settings — page heading is translated`, async ({ page }) => {
      await page.goto(`/${locale}/settings`)

      await expect(page).not.toHaveURL(/login/, { timeout: 5_000 })
      await waitForContent(page)

      // t('settings.title') → DE="Einstellungen", ES="Configuración", FR="Paramètres"
      await expect(
        page.locator('.section-title, h1, h2').filter({ hasText: tr.settingsTitle }).first()
      ).toBeVisible({ timeout: 12_000 })
    })

  })
}

// ── Sanity: English route still renders English ──────────────────────────────
test.describe('Locale: EN (sanity check)', () => {
  test('/en/jobs — English heading renders', async ({ page }) => {
    await page.goto('/en/jobs')
    await expect(page).not.toHaveURL(/login/)
    await expect(
      page.locator('.section-title, h1, h2').filter({ hasText: 'Jobs' }).first()
    ).toBeVisible({ timeout: 12_000 })
  })

  test('/en/login — English sign-in button renders', async ({ page }) => {
    await page.goto('/en/login')
    await expect(
      page.getByRole('button', { name: /sign in/i })
    ).toBeVisible({ timeout: 10_000 })
  })
})
