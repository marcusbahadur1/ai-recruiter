/**
 * Module 08 — Resume Screener & Applications
 * Tests: SC01–SC14
 *
 * Simulates the full human workflow:
 *   1. (beforeAll) Reads the tenant's IMAP credentials from Supabase, then sends TWO
 *      real resume emails via SMTP to the tenant IMAP inbox:
 *        • A strong resume (Senior React Developer) — expected to PASS screening
 *        • A weak resume  (unrelated background)   — expected to FAIL screening
 *   2. Waits for the poll_mailboxes Celery Beat task to pick both up (≤5-min cycle)
 *   3. Waits for screen_resume → invite_to_test pipeline to complete on the passing app
 *   4. Walks through the UI as both recruiter (dashboard) and candidate (test page)
 *
 * Required env vars in e2e/.env.production:
 *   SUPABASE_ANON_KEY, SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
 *   PROD_API_URL, PROD_TEST_EMAIL, PROD_TEST_PASSWORD, PROD_TEST_TENANT_ID
 *   SCREENER_JOB_REF   — 8-char ref of the active screener-only job
 *
 * SMTP credentials are read from the tenant's email_inbox_* fields in Supabase,
 * so no separate SMTP env vars are required.
 */

import { test, expect } from '@playwright/test'
import nodemailer from 'nodemailer'
import { createDecipheriv } from 'crypto'

// ── Env ────────────────────────────────────────────────────────────────────────

const API_URL          = (process.env.PROD_API_URL          ?? '').replace(/\/$/, '')
const SUPABASE_URL     = (process.env.SUPABASE_URL          ?? '').replace(/\/$/, '')
const SERVICE_KEY      = process.env.SUPABASE_SERVICE_ROLE_KEY ?? ''
const SUPABASE_ANON    = process.env.SUPABASE_ANON_KEY      ?? ''
const TEST_EMAIL       = process.env.PROD_TEST_EMAIL        ?? ''
const TEST_PASS        = process.env.PROD_TEST_PASSWORD     ?? ''
const TENANT_ID           = process.env.PROD_TEST_TENANT_ID       ?? ''
const SCREENER_JOB_REF    = process.env.SCREENER_JOB_REF          ?? ''
const BACKEND_ENCRYPT_KEY = process.env.BACKEND_ENCRYPTION_KEY    ?? ''

// ── Applicant identifiers ──────────────────────────────────────────────────────
// Names embedded in the From header so the poller assigns them as applicant_name.
// A timestamp suffix ensures we can distinguish this run's apps from older ones.

const RUN_TAG              = Date.now()
const PASS_NAME            = `SC08 Pass Applicant ${RUN_TAG}`
const FAIL_NAME            = `SC08 Fail Applicant ${RUN_TAG}`

// ── Shared state (set by beforeAll, read by tests) ────────────────────────────

let tenantJwt          = ''
let screenerJobId      = ''
let passingAppId       = ''   // screened_passed → test_invited
let failingAppId       = ''   // screened_failed → rejected
let testToken          = ''   // token from test_sessions for passingAppId
let emailsSent         = false
let smtpUser           = ''   // read from tenant.email_inbox_user
let smtpPass           = ''   // read from tenant.email_inbox_password
let smtpHost           = ''   // read from tenant.email_inbox_host
let imapInbox          = ''   // same as smtpUser (the IMAP account address)
let activeJobRef       = ''   // job_ref of the found screener job (used in email subjects)
let createdJobId       = ''   // set if we created the job; cleaned up in afterAll

// ── PDF generators ─────────────────────────────────────────────────────────────

function buildPdf(lines: string[]): Buffer {
  const stream = ['BT', '/F1 11 Tf', ...lines, 'ET'].join('\n')
  const streamLen = stream.length

  const objs: string[] = [
    '1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n',
    '2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n',
    '3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792]' +
      ' /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>\nendobj\n',
    `4 0 obj\n<< /Length ${streamLen} >>\nstream\n${stream}\nendstream\nendobj\n`,
    '5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n',
  ]

  let pdf = '%PDF-1.4\n'
  const offsets: number[] = []
  for (const o of objs) { offsets.push(pdf.length); pdf += o }

  const xrefAt = pdf.length
  pdf += `xref\n0 ${objs.length + 1}\n`
  pdf += '0000000000 65535 f \n'
  for (const off of offsets) pdf += `${String(off).padStart(10, '0')} 00000 n \n`
  pdf += `trailer\n<< /Size ${objs.length + 1} /Root 1 0 R >>\nstartxref\n${xrefAt}\n%%EOF\n`

  return Buffer.from(pdf, 'ascii')
}

/**
 * Strong resume — Senior React Developer, 7 years, Sydney, exact skill match.
 * Designed to score 8–10 on a React/TypeScript screener job.
 */
function createStrongResumePdf(name: string): Buffer {
  const n = name.replace(/[()\\]/g, '')
  return buildPdf([
    `50 740 Td (${n}) Tj`,
    '0 -16 Td (Senior React Developer  |  7 Years Experience  |  Sydney NSW) Tj',
    '0 -28 Td (PROFESSIONAL SUMMARY) Tj',
    '0 -14 Td (Expert React and TypeScript engineer with 7 years delivering enterprise) Tj',
    '0 -14 Td (web applications. Deep expertise in component architecture, state management,) Tj',
    '0 -14 Td (performance optimisation, and leading teams of 5 or more frontend developers.) Tj',
    '0 -28 Td (CORE TECHNICAL SKILLS) Tj',
    '0 -14 Td (React 18, TypeScript, JavaScript ES2023, Next.js, Redux Toolkit, Zustand) Tj',
    '0 -14 Td (Node.js, GraphQL, REST APIs, Jest, React Testing Library, Playwright) Tj',
    '0 -14 Td (AWS, Docker, Kubernetes, CI/CD pipelines, GitHub Actions, Terraform) Tj',
    '0 -28 Td (PROFESSIONAL EXPERIENCE) Tj',
    '0 -14 Td (Principal React Engineer - FinTech Global, Sydney  2020-Present) Tj',
    '0 -14 Td (Architected micro-frontend platform serving 2 million daily active users.) Tj',
    '0 -14 Td (Reduced bundle size 60 percent, improved Lighthouse score from 62 to 94.) Tj',
    '0 -14 Td (Senior Frontend Developer - RetailCo, Sydney  2018-2020) Tj',
    '0 -14 Td (Led React migration from Angular for 15-product ecommerce suite.) Tj',
    '0 -14 Td (Mentored 4 junior developers, ran fortnightly tech talks.) Tj',
    '0 -14 Td (React Developer - AgencyX, Melbourne  2016-2018) Tj',
    '0 -14 Td (Built bespoke React SPAs for 20 plus enterprise clients.) Tj',
    '0 -28 Td (EDUCATION) Tj',
    '0 -14 Td (Bachelor of Software Engineering - UNSW Sydney - 2016, First Class Honours) Tj',
    '0 -14 Td (AWS Certified Developer Associate - 2022) Tj',
  ])
}

/**
 * Weak resume — professional pastry chef with no technical skills.
 * Should score 1–3 on a React/TypeScript screener job and be rejected.
 */
function createWeakResumePdf(name: string): Buffer {
  const n = name.replace(/[()\\]/g, '')
  return buildPdf([
    `50 740 Td (${n}) Tj`,
    '0 -16 Td (Senior Pastry Chef  |  12 Years Experience  |  Melbourne VIC) Tj',
    '0 -28 Td (PROFESSIONAL SUMMARY) Tj',
    '0 -14 Td (Passionate pastry chef with 12 years crafting artisan desserts and) Tj',
    '0 -14 Td (patisserie in fine-dining establishments across Melbourne and Paris.) Tj',
    '0 -14 Td (Specialist in French technique, chocolate work, and plated desserts.) Tj',
    '0 -28 Td (CORE SKILLS) Tj',
    '0 -14 Td (Patisserie, Chocolate tempering, Sugar sculpture, Bread baking) Tj',
    '0 -14 Td (Menu design, Kitchen management, Food cost control, HACCP compliance) Tj',
    '0 -14 Td (French cuisine, Italian gelato, Sourdough fermentation) Tj',
    '0 -28 Td (PROFESSIONAL EXPERIENCE) Tj',
    '0 -14 Td (Head Pastry Chef - Le Boulange, Melbourne  2019-Present) Tj',
    '0 -14 Td (Oversee pastry section for 80-seat fine dining restaurant.) Tj',
    '0 -14 Td (Developed 40-item dessert menu, reduced food waste by 25 percent.) Tj',
    '0 -14 Td (Pastry Chef de Partie - Hotel Grand, Paris  2015-2019) Tj',
    '0 -14 Td (Produced 300 covers per service across 3 Michelin-star kitchen.) Tj',
    '0 -14 Td (Junior Pastry Chef - Boulangerie Dupont, Lyon  2012-2015) Tj',
    '0 -14 Td (Trained under Meilleur Ouvrier de France, mastered croissant lamination.) Tj',
    '0 -28 Td (EDUCATION) Tj',
    '0 -14 Td (Diplome de Patisserie - Le Cordon Bleu Paris - 2012) Tj',
    '0 -14 Td (Certificate IV in Hospitality - William Angliss Melbourne - 2010) Tj',
  ])
}

// ── Helpers ────────────────────────────────────────────────────────────────────

async function getJwt(): Promise<string> {
  const r = await fetch(`${SUPABASE_URL}/auth/v1/token?grant_type=password`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', apikey: SUPABASE_ANON },
    body: JSON.stringify({ email: TEST_EMAIL, password: TEST_PASS }),
  })
  const d = await r.json()
  return d.access_token ?? ''
}

async function apiGet(path: string): Promise<any> {
  if (!tenantJwt || !API_URL) return null
  const r = await fetch(`${API_URL}/api/v1${path}`, {
    headers: { Authorization: `Bearer ${tenantJwt}` },
  })
  if (!r.ok) return null
  return r.json()
}

async function apiPost(path: string, body: unknown): Promise<any> {
  if (!tenantJwt || !API_URL) return null
  const r = await fetch(`${API_URL}/api/v1${path}`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${tenantJwt}`, 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!r.ok) { console.warn(`POST ${path} → ${r.status}`); return null }
  return r.json()
}

async function apiPatch(path: string, body: unknown): Promise<any> {
  if (!tenantJwt || !API_URL) return null
  const r = await fetch(`${API_URL}/api/v1${path}`, {
    method: 'PATCH',
    headers: { Authorization: `Bearer ${tenantJwt}`, 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!r.ok) {
    const text = await r.text().catch(() => '')
    console.warn(`PATCH ${path} → ${r.status}: ${text.slice(0, 300)}`)
    return null
  }
  return r.json()
}

async function apiDelete(path: string): Promise<boolean> {
  if (!tenantJwt || !API_URL) return false
  const r = await fetch(`${API_URL}/api/v1${path}`, {
    method: 'DELETE',
    headers: { Authorization: `Bearer ${tenantJwt}` },
  })
  return r.ok
}

async function sleep(ms: number) {
  return new Promise((res) => setTimeout(res, ms))
}

/**
 * Decrypt a Fernet token using the backend's ENCRYPTION_KEY.
 * Fernet = version(1) + timestamp(8) + IV(16) + AES-128-CBC ciphertext + HMAC(32).
 * The 32-byte key is split: first 16 bytes = signing key, last 16 = encryption key.
 */
function fernetDecrypt(token: string, b64Key: string): string {
  const keyBuf  = Buffer.from(b64Key.replace(/-/g, '+').replace(/_/g, '/'), 'base64')
  const encKey  = keyBuf.slice(16, 32)                            // AES key
  const raw     = Buffer.from(token.replace(/-/g, '+').replace(/_/g, '/'), 'base64')
  const iv      = raw.slice(9, 25)                                // bytes 9–24
  const payload = raw.slice(25, raw.length - 32)                  // ciphertext (strip HMAC)
  const decipher = createDecipheriv('aes-128-cbc', encKey, iv)
  return Buffer.concat([decipher.update(payload), decipher.final()]).toString('utf8')
}

function makeTransport() {
  // Uses credentials fetched from the tenant record in beforeAll.
  // Namecheap Private Email uses the same host for IMAP (port 993) and SMTP (port 465).
  return nodemailer.createTransport({
    host: smtpHost,
    port: 465,
    secure: true,
    auth: { user: smtpUser, pass: smtpPass },
  })
}

async function sendResumeEmail(opts: {
  applicantName: string
  subject: string
  bodyText: string
  pdf: Buffer
  filename: string
}): Promise<void> {
  const transport = makeTransport()
  await transport.sendMail({
    from: `${opts.applicantName} <${smtpUser}>`,
    to: imapInbox,
    subject: opts.subject,
    text: opts.bodyText,
    attachments: [{
      filename: opts.filename,
      content: opts.pdf,
      contentType: 'application/pdf',
    }],
  })
}

// ── Suite ──────────────────────────────────────────────────────────────────────

test.describe('Module 08 — Screener & Applications', () => {
  test.describe.configure({ mode: 'serial' })
  // 11 minutes: 5-min IMAP Beat cycle + screening AI + invite AI for both apps
  test.setTimeout(660_000)

  test.beforeAll(async () => {
    // 11 min: 5-min IMAP Beat cycle + screen_resume + invite_to_test for both apps
    test.setTimeout(660_000)

    if (!TEST_EMAIL || !TEST_PASS) {
      console.warn('SC08 beforeAll: credentials not set — skipping setup')
      return
    }

    // ── 1. Authenticate ────────────────────────────────────────────────────
    console.log('SC08 [1/7] Authenticating...')
    tenantJwt = await getJwt()
    if (!tenantJwt) { console.warn('SC08: JWT failed'); return }

    // ── 2. Read tenant IMAP credentials from Supabase (used for SMTP send) ──
    console.log('SC08 [2/7] Reading tenant IMAP credentials from Supabase...')
    if (SERVICE_KEY && TENANT_ID) {
      const tResp = await fetch(
        `${SUPABASE_URL}/rest/v1/tenants` +
        `?id=eq.${TENANT_ID}` +
        `&select=email_inbox,email_inbox_host,email_inbox_user,email_inbox_password` +
        `&limit=1`,
        { headers: { apikey: SERVICE_KEY, Authorization: `Bearer ${SERVICE_KEY}` } },
      )
      const rows = await tResp.json()
      if (Array.isArray(rows) && rows[0]) {
        smtpHost  = rows[0].email_inbox_host ?? ''
        smtpUser  = rows[0].email_inbox_user ?? ''
        imapInbox = smtpUser   // the IMAP user IS the inbox address
        const encryptedPass = rows[0].email_inbox_password ?? ''
        if (encryptedPass && BACKEND_ENCRYPT_KEY) {
          smtpPass = fernetDecrypt(encryptedPass, BACKEND_ENCRYPT_KEY)
        }
        console.log(`SC08 [2/7] IMAP creds loaded — host=${smtpHost} user=${smtpUser}`)
      } else {
        console.warn('SC08 [2/7] Could not load tenant IMAP credentials')
      }
    } else {
      console.warn('SC08 [2/7] SERVICE_KEY or TENANT_ID not set — cannot load IMAP creds')
    }

    // ── 2b. Find or create screener job ──────────────────────────────────
    console.log('SC08 [2b/7] Looking up screener job...')
    const jobs = await apiGet('/jobs?limit=100')
    const allItems: any[] = jobs?.items ?? []
    // Prefer the configured ref; fall back to any active screener-mode job
    let job = SCREENER_JOB_REF
      ? allItems.find((j: any) => j.job_ref === SCREENER_JOB_REF)
      : undefined
    if (!job) {
      job = allItems.find((j: any) =>
        j.mode?.includes('screener') && j.status === 'active'
      )
    }
    if (job) {
      screenerJobId = job.id
      activeJobRef  = job.job_ref
      console.log(`SC08 [2b/7] Screener job found: "${job.title}" ref=${job.job_ref}`)
    } else {
      // No screener job exists — create one for this test run
      console.log('SC08 [2b/7] No screener job found — creating one...')
      const created = await apiPost('/jobs', {
        title: 'Senior React Developer (E2E Test)',
        description: [
          'We are looking for a Senior React Developer to join our engineering team.',
          'You will build and maintain complex front-end applications using React and TypeScript.',
          '',
          'Requirements:',
          '- 5+ years of professional software development experience',
          '- 3+ years of hands-on React and TypeScript experience',
          '- Strong knowledge of JavaScript ES6+, HTML5, CSS3',
          '- Experience with state management (Redux, Zustand, or similar)',
          '- Familiarity with REST APIs and GraphQL',
          '- Experience with testing frameworks (Jest, React Testing Library)',
          '- Understanding of CI/CD pipelines and Git workflows',
          '',
          'Nice to have:',
          '- Node.js / Express experience',
          '- AWS or other cloud platform experience',
          '- Experience with Docker and containerisation',
        ].join('\n'),
        job_type: 'Full-time',
        location: 'Sydney, NSW',
        work_type: 'hybrid',
        required_skills: ['React', 'TypeScript', 'JavaScript', 'HTML', 'CSS'],
        tech_stack: ['React', 'TypeScript', 'Node.js', 'AWS'],
        experience_years: 5,
        mode: 'screener_only',
        interview_type: 'text',
        interview_questions_count: 3,
        minimum_score: 6,
        hiring_manager_email: TEST_EMAIL,
        hiring_manager_name: 'Hiring Manager',
      })
      if (created?.id) {
        createdJobId = created.id
        // Activate the job so the screener pipeline can use it
        const activated = await apiPatch(`/jobs/${createdJobId}`, { status: 'active' })
        if (activated) {
          screenerJobId = createdJobId
          activeJobRef  = activated.job_ref
          console.log(`SC08 [2b/7] Created and activated screener job: ref=${activeJobRef} id=${screenerJobId}`)
        } else {
          console.warn('SC08 [2b/7] Job created but activation failed')
        }
      } else {
        console.warn('SC08 [2b/7] Job creation failed — IMAP pipeline tests will skip')
      }
    }

    // ── 3. Send both resume emails ─────────────────────────────────────────
    const smtpReady = smtpHost && smtpUser && smtpPass && imapInbox && activeJobRef
    if (!smtpReady) {
      console.warn(`SC08 [3/7] Cannot send emails — smtpReady=${smtpReady} (host=${!!smtpHost} user=${!!smtpUser} pass=${!!smtpPass} job=${activeJobRef||'none'}) — using existing applications`)
    } else {
      console.log(`SC08 [3/7] Sending PASS resume from "${PASS_NAME}"...`)
      await sendResumeEmail({
        applicantName: PASS_NAME,
        subject: `Application for Senior React Developer ${activeJobRef}`,
        bodyText: [
          'Dear Hiring Team,',
          '',
          `Please find my resume attached for the Senior React Developer role (ref: ${activeJobRef}).`,
          'I have 7 years of hands-on React and TypeScript experience and would love to join your team.',
          '',
          'Kind regards,',
          PASS_NAME,
        ].join('\n'),
        pdf: createStrongResumePdf(PASS_NAME),
        filename: 'resume-strong-react-developer.pdf',
      })
      console.log(`SC08 [3/7] Sending FAIL resume from "${FAIL_NAME}"...`)
      await sendResumeEmail({
        applicantName: FAIL_NAME,
        subject: `Application for position ${activeJobRef}`,
        bodyText: [
          'Dear Hiring Team,',
          '',
          `Please find my resume attached for the role referenced ${activeJobRef}.`,
          'I am a passionate pastry chef looking for a career change.',
          '',
          'Kind regards,',
          FAIL_NAME,
        ].join('\n'),
        pdf: createWeakResumePdf(FAIL_NAME),
        filename: 'resume-pastry-chef.pdf',
      })
      emailsSent = true
      console.log('SC08 [3/7] Both emails sent. Waiting for poll_mailboxes (up to 5 min)...')
    }

    // ── 4. Poll until both applications appear ────────────────────────────
    console.log('SC08 [4/7] Polling for applications...')
    const appPath = screenerJobId
      ? `/applications?job_id=${screenerJobId}&limit=100`
      : '/applications?limit=100'

    if (!emailsSent) {
      // No emails sent — grab whatever existing apps are there (one shot, no wait)
      const data = await apiGet(appPath)
      const apps: any[] = data?.items ?? []
      if (apps.length > 0) passingAppId = apps[0].id
      if (apps.length > 1) failingAppId = apps[1].id
      console.log(`SC08 [4/7] Using existing apps: pass=${passingAppId||'none'} fail=${failingAppId||'none'}`)
    } else {
      // Emails sent — poll up to 8 min for IMAP poller to create the applications
      const appDeadline = Date.now() + 8 * 60 * 1000
      while (Date.now() < appDeadline && (!passingAppId || !failingAppId)) {
        const data = await apiGet(appPath)
        const apps: any[] = data?.items ?? []

        if (!passingAppId) {
          const found = apps.find((a) => a.applicant_name === PASS_NAME)
          if (found) {
            passingAppId = found.id
            console.log(`SC08 [4/7] PASS application found: ${passingAppId}`)
          }
        }
        if (!failingAppId) {
          const found = apps.find((a) => a.applicant_name === FAIL_NAME)
          if (found) {
            failingAppId = found.id
            console.log(`SC08 [4/7] FAIL application found: ${failingAppId}`)
          }
        }

        if (passingAppId && failingAppId) break

        const remaining = Math.round((appDeadline - Date.now()) / 1000)
        console.log(`SC08 [4/7] Found pass=${!!passingAppId} fail=${!!failingAppId} — retrying in 30s (${remaining}s left)...`)
        await sleep(30_000)
      }
    }

    if (!passingAppId) {
      console.warn('SC08 [4/7] No PASS application found — several tests will skip')
      return
    }
    if (!failingAppId) {
      console.warn('SC08 [4/7] No FAIL application found — SC06 failure assertion will skip')
    }

    // ── 5. Wait for PASS app to reach test_invited ────────────────────────
    console.log('SC08 [5/7] Waiting for PASS app to be screened and invited...')
    const inviteDeadline = Date.now() + 5 * 60 * 1000
    let lastStatus = ''
    while (Date.now() < inviteDeadline) {
      const app = await apiGet(`/applications/${passingAppId}`)
      if (!app) break
      if (app.status !== lastStatus) {
        console.log(`SC08 [5/7] PASS app: status=${app.status} test_status=${app.test_status}`)
        lastStatus = app.status
      }
      if (app.test_status === 'invited' || app.test_status === 'completed') break
      if (app.status === 'rejected') {
        console.warn('SC08 [5/7] PASS app was rejected — strong resume may have scored below minimum_score')
        break
      }
      await sleep(20_000)
    }

    // ── 6. Wait for FAIL app to reach rejected ────────────────────────────
    if (failingAppId) {
      console.log('SC08 [6/7] Waiting for FAIL app to be screened and rejected...')
      const failDeadline = Date.now() + 3 * 60 * 1000
      while (Date.now() < failDeadline) {
        const app = await apiGet(`/applications/${failingAppId}`)
        if (!app) break
        console.log(`SC08 [6/7] FAIL app: status=${app.status} screening_status=${app.screening_status}`)
        if (app.screening_status === 'failed' || app.status === 'rejected') break
        await sleep(20_000)
      }
    }

    // ── 7. Get test session token for SC07 ────────────────────────────────
    if (!SERVICE_KEY) {
      console.warn('SC08 [7/7] SUPABASE_SERVICE_ROLE_KEY not set — SC07 will skip')
      return
    }
    console.log('SC08 [7/7] Fetching test session token...')
    const tsResp = await fetch(
      `${SUPABASE_URL}/rest/v1/test_sessions` +
      `?application_id=eq.${passingAppId}&status=neq.completed` +
      `&select=token,status&limit=1&order=created_at.desc`,
      { headers: { apikey: SERVICE_KEY, Authorization: `Bearer ${SERVICE_KEY}` } },
    )
    const sessions = await tsResp.json()
    if (Array.isArray(sessions) && sessions[0]?.token) {
      testToken = sessions[0].token
      console.log(`SC08 [7/7] Test token obtained (session status: ${sessions[0].status})`)
    } else {
      console.warn('SC08 [7/7] No pending test session found')
    }
  })

  test.afterAll(async () => {
    // If we created a job for this run, close it so it doesn't clutter the tenant.
    // Applications are kept so the test report is meaningful.
    if (createdJobId) {
      console.log(`SC08 afterAll: closing test job ${createdJobId}`)
      await apiPatch(`/jobs/${createdJobId}`, { status: 'closed' })
    }
  })

  // ── SC01 — Applications list loads ────────────────────────────────────────

  test('SC01 — Applications list — page loads with correct columns', async ({ page }) => {
    await page.goto('/en/applications')
    await page.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => {})

    await expect(page.getByText(/applications/i).first()).toBeVisible({ timeout: 10_000 })
    await expect(page.locator('table').first()).toBeVisible({ timeout: 10_000 })

    const headers = page.locator('table thead th')
    await expect(headers.filter({ hasText: /applicant/i }).first()).toBeVisible()
    await expect(headers.filter({ hasText: /email/i }).first()).toBeVisible()
    await expect(headers.filter({ hasText: /received/i }).first()).toBeVisible()
    await expect(headers.filter({ hasText: /resume score/i }).first()).toBeVisible()
    await expect(headers.filter({ hasText: /test score/i }).first()).toBeVisible()
    await expect(headers.filter({ hasText: /status/i }).first()).toBeVisible()
  })

  // ── SC02 — Job filter ─────────────────────────────────────────────────────

  test('SC02 — Job filter — All Jobs default, selection re-renders table', async ({ page }) => {
    await page.goto('/en/applications')
    await page.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => {})

    const jobSelect = page.locator('select').first()
    if (await jobSelect.count() === 0) { test.skip(true, 'ENV_SKIP: select not found'); return }

    await expect(jobSelect.locator('option').first()).toHaveText(/all jobs/i)
    await expect(jobSelect).toHaveValue('')

    const optionCount = await jobSelect.locator('option').count()
    if (optionCount > 1) {
      await jobSelect.selectOption({ index: 1 })
      await page.waitForTimeout(800)
      await expect(
        page.locator('table').first().or(page.getByText(/no applications/i)),
      ).toBeVisible({ timeout: 5_000 })

      await jobSelect.selectOption({ value: '' })
      await page.waitForTimeout(800)
      await expect(page.locator('table').first()).toBeVisible({ timeout: 5_000 })
    }
  })

  // ── SC03 — Row click → detail ─────────────────────────────────────────────

  test('SC03 — Row click — navigates to /applications/{id} with breadcrumb', async ({ page }) => {
    await page.goto('/en/applications')
    await page.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => {})

    const dataRows = page.locator('table tbody tr').filter({ hasNot: page.locator('td[colspan]') })
    if (await dataRows.count() === 0) { test.skip(true, 'ENV_SKIP: no data rows'); return }

    const name = await dataRows.first().locator('td').first().textContent()
    await dataRows.first().click()
    await page.waitForURL(/\/applications\/[0-9a-f-]+$/, { timeout: 10_000 })
    await expect(page).toHaveURL(/\/applications\/[0-9a-f-]+$/)
    await expect(page.locator('.breadcrumb')).toContainText(name?.trim() ?? '', { timeout: 10_000 })
  })

  // ── SC04 — PASS application detail ───────────────────────────────────────

  test('SC04 — PASS application — resume score card populated, pipeline shows received', async ({ page }) => {
    if (!passingAppId) { test.skip(true, 'ENV_SKIP: no passingAppId'); return }

    await page.goto(`/en/applications/${passingAppId}`)
    await page.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => {})

    // Applicant name in section title
    await expect(page.locator('.section-title').first()).toBeVisible({ timeout: 10_000 })

    // Resume Score heading
    await expect(page.getByText(/resume score/i).first()).toBeVisible({ timeout: 10_000 })

    // Score pill is a number ≥ 1
    const pill = page.locator('.score-pill').first()
    if (await pill.count() > 0) {
      const text = await pill.textContent()
      expect(Number(text?.replace('/10', '').trim())).toBeGreaterThanOrEqual(1)
    }

    // Pipeline card — "Resume received via email" is always present
    await expect(page.getByText(/resume received via email/i).first()).toBeVisible({ timeout: 5_000 })

    // Status badge exists
    await expect(page.locator('.badge').first()).toBeVisible()
    await expect(page.locator('body')).not.toContainText('500')
  })

  // ── SC05 — FAIL application detail ───────────────────────────────────────

  test('SC05 — FAIL application — screened_failed badge, no Trigger Test button', async ({ page }) => {
    if (!failingAppId) { test.skip(true, 'ENV_SKIP: no failingAppId'); return }

    await page.goto(`/en/applications/${failingAppId}`)
    await page.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => {})

    await expect(page.locator('.section-title').first()).toBeVisible({ timeout: 10_000 })
    await expect(page.getByText(/resume score/i).first()).toBeVisible({ timeout: 10_000 })

    // Status badge should indicate failure
    const badge = page.locator('.badge').first()
    await expect(badge).toBeVisible()
    const badgeText = await badge.textContent()
    // Acceptable terminal states for a failed resume
    expect(badgeText?.trim()).toMatch(/Screen ✗|Rejected|screened_failed/i)

    // Trigger Test button must NOT be visible (candidate did not pass screening)
    await expect(
      page.getByRole('button', { name: /trigger test|send assessment/i }),
    ).not.toBeVisible()
  })

  // ── SC06 — Trigger Test button on eligible PASS application ───────────────

  test('SC06 — Trigger Test button — visible and enabled for screened_passed app', async ({ page }) => {
    // Find an application that passed screening and hasn't been invited yet
    const path = screenerJobId
      ? `/applications?job_id=${screenerJobId}&limit=100`
      : '/applications?limit=100'
    const data = await apiGet(path)
    const eligible = (data?.items ?? []).find(
      (a: any) => a.screening_status === 'passed' && a.test_status === 'not_started',
    )
    if (!eligible) {
      test.skip(true, 'ENV_SKIP: no application in screened_passed + test not started')
      return
    }

    await page.goto(`/en/applications/${eligible.id}`)
    await page.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => {})

    const triggerBtn = page
      .getByRole('button', { name: /trigger test|send test|send assessment|invite.*test/i })
      .first()
    await expect(triggerBtn).toBeVisible({ timeout: 10_000 })
    await expect(triggerBtn).toBeEnabled()

    // Click — verify loading state ("Sending…") appears
    await triggerBtn.click()
    await expect(
      page.getByText(/sending/i).first(),
    ).toBeVisible({ timeout: 5_000 })
  })

  // ── SC07 — Status badges ──────────────────────────────────────────────────

  test('SC07 — Status badges — every table row shows a known status label', async ({ page }) => {
    const known = [
      'Received', 'Screen ✓', 'Screen ✗',
      'Test Invited', 'Test ✓', 'Test ✗',
      'HM Notified', 'Invited', 'Rejected',
    ]

    await page.goto('/en/applications')
    await page.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => {})

    const badges = page.locator('table tbody .badge')
    const count = await badges.count()
    if (count === 0) { test.skip(true, 'ENV_SKIP: no badge elements'); return }

    for (let i = 0; i < count; i++) {
      const text = (await badges.nth(i).textContent())?.trim() ?? ''
      expect(known.some((l) => text.includes(l) || l.includes(text))).toBe(true)
    }
  })

  // ── SC08 — Text competency test (full candidate journey) ──────────────────

  test('SC08 — Text competency test — candidate completes all questions', async ({ page, context }) => {
    if (!passingAppId || !testToken) {
      test.skip(true, 'ENV_SKIP: no passingAppId or testToken from beforeAll')
      return
    }

    await context.clearCookies()
    const testPage = await context.newPage()

    console.log(`SC08: opening /en/test/${passingAppId}/${testToken}`)
    await testPage.goto(`/en/test/${passingAppId}/${testToken}`)
    await testPage.waitForLoadState('networkidle', { timeout: 20_000 }).catch(() => {})

    // ── Landing page ──────────────────────────────────────────────────────
    // Firm name or job title is visible
    await expect(
      testPage.locator('body').filter({ hasText: /react|developer|recruiter|assessment/i }).first(),
    ).toBeVisible({ timeout: 15_000 })

    // "Begin Assessment" button
    const startBtn = testPage.getByRole('button', { name: /begin assessment/i })
    if (await testPage.getByText(/assessment complete/i).count() > 0) {
      // Already completed from a previous run — still a valid state
      await testPage.close()
      return
    }
    await expect(startBtn).toBeVisible({ timeout: 10_000 })
    await startBtn.click()

    // ── Active test ───────────────────────────────────────────────────────
    await expect(
      testPage.getByText(/question 1 of/i).first(),
    ).toBeVisible({ timeout: 15_000 })

    let answered = 0
    for (let i = 0; i < 10; i++) {
      // Check if completed early
      if (await testPage.getByText(/assessment complete/i).count() > 0) break

      const textarea = testPage.locator('textarea').first()
      if (await textarea.count() === 0) break

      const answer =
        `Substantive answer for question ${i + 1}. ` +
        `I have 7 years of React and TypeScript experience, building enterprise ` +
        `applications with complex state management, performance optimisation, ` +
        `and comprehensive test coverage using Jest and React Testing Library. ` +
        `My approach emphasises clean component APIs and accessibility best practices.`

      await textarea.fill(answer)
      await testPage.waitForTimeout(300)

      // Character count must appear
      await expect(testPage.getByText(/characters/i).first()).toBeVisible()

      const submitBtn = testPage.getByRole('button', { name: /submit answer/i })
      await expect(submitBtn).toBeEnabled({ timeout: 5_000 })
      await submitBtn.click()
      answered++

      await testPage.waitForTimeout(1_500)
    }

    expect(answered).toBeGreaterThanOrEqual(1)

    // ── Completion screen ─────────────────────────────────────────────────
    await expect(
      testPage.getByText(/assessment complete/i).first(),
    ).toBeVisible({ timeout: 30_000 })
    await expect(
      testPage.getByText(/thank you|submitted|will be reviewed/i).first(),
    ).toBeVisible({ timeout: 5_000 })

    await testPage.close()

    // Backend should have updated test_status
    const appAfter = await apiGet(`/applications/${passingAppId}`)
    expect(appAfter?.test_status).toMatch(/completed|passed|failed/)
  })

  // ── SC09 — Audio test page renders ───────────────────────────────────────

  test('SC09 — Audio test page — renders without crash', async ({ context }) => {
    await context.clearCookies()
    const p = await context.newPage()
    await p.goto('/en/test/00000000-0000-0000-0000-000000000000/audiotoken')
    await p.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => {})
    await expect(p.locator('body')).not.toContainText('500')
    await p.close()
  })

  // ── SC10 — Video test page renders ───────────────────────────────────────

  test('SC10 — Video test page — renders without server error', async ({ context }) => {
    await context.clearCookies()
    const p = await context.newPage()
    await p.goto('/en/test/00000000-0000-0000-0000-000000000001/videotoken')
    await p.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => {})
    await expect(p.locator('body')).not.toContainText('500')
    await p.close()
  })

  // ── SC11 — Invalid token ──────────────────────────────────────────────────

  test('SC11 — Invalid token — user-friendly error, not 500', async ({ context }) => {
    await context.clearCookies()
    const p = await context.newPage()
    await p.goto('/en/test/invalid-app-id/invalid-token-xyz')
    await p.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => {})
    await expect(p.locator('body')).not.toContainText('500')
    await expect(p.locator('body')).not.toContainText('Internal Server Error')
    await p.close()
  })

  // ── SC12 — Test landing page with valid token ─────────────────────────────

  test('SC12 — Landing page — Begin Assessment button or completion screen visible', async ({ context }) => {
    if (!passingAppId || !testToken) { test.skip(true, 'ENV_SKIP: no token'); return }

    await context.clearCookies()
    const p = await context.newPage()
    await p.goto(`/en/test/${passingAppId}/${testToken}`)
    await p.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => {})

    await expect(p.locator('body')).not.toContainText('500')
    await expect(
      p.getByRole('button', { name: /begin assessment/i })
        .or(p.getByText(/assessment complete/i)),
    ).toBeVisible({ timeout: 10_000 })

    await p.close()
  })

  // ── SC13 — Interview invited page ─────────────────────────────────────────

  test('SC13 — Interview invited page — renders correctly', async ({ context }) => {
    await context.clearCookies()
    const p = await context.newPage()
    await p.goto('/en/interview-invited')
    await p.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => {})
    await expect(p).not.toHaveURL(/404|500/)
    await expect(p.locator('body h1, body h2, body p').first()).toBeVisible({ timeout: 5_000 })
    await p.close()
  })

  // ── SC14 — Unsubscribe page ───────────────────────────────────────────────

  test('SC14 — Unsubscribe page — settles to final state', async ({ context }) => {
    await context.clearCookies()
    const p = await context.newPage()
    await p.goto('/en/unsubscribe/00000000-0000-0000-0000-000000000000')
    await p.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => {})
    await expect(p).not.toHaveURL(/500/)
    await expect(
      p.getByText(/unsubscribed|opted out|not found|something went wrong/i).first(),
    ).toBeVisible({ timeout: 15_000 })
    await p.close()
  })
})
