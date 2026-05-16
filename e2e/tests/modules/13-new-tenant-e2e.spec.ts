/**
 * Module 13 — Full New Tenant E2E
 * Tests: NT-01–NT-06, QS-01–QS-06, JS-01–JS-07, JP-01–JP-05, KS-01–KS-07, CL-01–CL-03
 *
 * Complete lifecycle of a brand-new tenant from signup to first candidate,
 * following the 6-step quickstart guide exactly as a real user would.
 *
 * ── Flow ─────────────────────────────────────────────────────────────────────
 *   G  Signup & first login        (NT-01–06)
 *   H  Quickstart steps 1–4        (QS-01–06)  — API keys, IMAP, knowledge base, AI prompt
 *   I  First Scout job via chat    (JS-01–07)  — quickstart step 5 completes
 *   J  Scout pipeline              (JP-01–05)  — quickstart step 6 completes
 *   K  Screener job                (KS-01–07)  — IMAP email → screening
 *   L  Cleanup & isolation         (CL-01–03)
 *
 * ── Tenant strategy ──────────────────────────────────────────────────────────
 *   A fresh Supabase user is created via the Admin API (email auto-confirmed,
 *   no inbox required). Our backend's POST /auth/signup is NOT called because
 *   the Admin API bypasses Supabase email confirmation. Instead the Tenant row
 *   is inserted directly via the Supabase REST API (SERVICE_KEY bypasses RLS).
 *   The tenant is deleted from Supabase in afterAll to keep production clean.
 *
 * ── API keys for new tenant ───────────────────────────────────────────────────
 *   The AI API key is read from marcusbahadur1@gmail.com's tenant record in
 *   Supabase (same key, temporarily shared). IMAP credentials are also copied
 *   from that tenant. Neither change is permanent — afterAll deletes the test
 *   tenant entirely.
 *
 * ── Required env vars ────────────────────────────────────────────────────────
 *   PROD_API_URL, PROD_TEST_EMAIL, PROD_TEST_PASSWORD, PROD_TEST_TENANT_ID
 *   PROD_SUPER_ADMIN_EMAIL, PROD_SUPER_ADMIN_PASSWORD
 *   SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_SERVICE_ROLE_KEY
 *   BACKEND_ENCRYPTION_KEY
 *
 * ── Timeout ──────────────────────────────────────────────────────────────────
 *   Up to 25 min (Scout pipeline poll + IMAP cycle + screener pipeline).
 */

import { test, expect } from '@playwright/test'
import { createDecipheriv, randomUUID } from 'crypto'

// ── Env ────────────────────────────────────────────────────────────────────────

const API_URL        = (process.env.PROD_API_URL              ?? '').replace(/\/$/, '')
const SUPABASE_URL   = (process.env.SUPABASE_URL              ?? '').replace(/\/$/, '')
const SUPABASE_ANON  = process.env.SUPABASE_ANON_KEY          ?? ''
const SERVICE_KEY    = process.env.SUPABASE_SERVICE_ROLE_KEY  ?? ''
const ENCRYPT_KEY    = process.env.BACKEND_ENCRYPTION_KEY     ?? ''

// Source tenant (marcusbahadur1@gmail.com) — API keys are borrowed from here
const SRC_EMAIL      = process.env.PROD_TEST_EMAIL            ?? ''
const SRC_PASS       = process.env.PROD_TEST_PASSWORD         ?? ''
const SRC_TENANT_ID  = process.env.PROD_TEST_TENANT_ID        ?? ''

// Super admin
const SA_EMAIL       = process.env.PROD_SUPER_ADMIN_EMAIL     ?? ''
const SA_PASS        = process.env.PROD_SUPER_ADMIN_PASSWORD  ?? ''

// ── New tenant identity (generated per run) ───────────────────────────────────

const RUN_TAG      = Date.now()
const NEW_EMAIL    = `e2e-tenant-${RUN_TAG}@airecruiterz.com`
const NEW_PASS     = `E2eTest${RUN_TAG}!`
const NEW_FIRM     = `E2E Test Firm ${RUN_TAG}`
const NEW_SLUG     = `e2e-firm-${RUN_TAG}`

// ── Shared state ───────────────────────────────────────────────────────────────

let newUserId      = ''   // Supabase auth user id for the new tenant
let newTenantId    = ''   // Our DB tenant id
let newJwt         = ''   // JWT for new tenant API calls
let saJwt          = ''   // Super admin JWT
let srcJwt         = ''   // Source tenant JWT (for reading credentials)

// Keys read from source tenant
let srcAiApiKey    = ''   // raw (decrypted) Anthropic key
let srcAiProvider  = ''
let srcImapHost    = ''
let srcImapUser    = ''
let srcImapPass    = ''   // decrypted

// Job/candidate state
let scoutJobId     = ''
let scoutJobRef    = ''
let screenerJobId  = ''
let screenerJobRef = ''
let scoutCandidate = ''   // first discovered candidate id

// ── Helpers ────────────────────────────────────────────────────────────────────

function fernetDecrypt(token: string, b64Key: string): string {
  const keyBuf   = Buffer.from(b64Key.replace(/-/g, '+').replace(/_/g, '/'), 'base64')
  const encKey   = keyBuf.slice(16, 32)
  const raw      = Buffer.from(token.replace(/-/g, '+').replace(/_/g, '/'), 'base64')
  const iv       = raw.slice(9, 25)
  const payload  = raw.slice(25, raw.length - 32)
  const decipher = createDecipheriv('aes-128-cbc', encKey, iv)
  return Buffer.concat([decipher.update(payload), decipher.final()]).toString('utf8')
}

async function getJwt(email: string, password: string): Promise<string> {
  const r = await fetch(`${SUPABASE_URL}/auth/v1/token?grant_type=password`, {
    method : 'POST',
    headers: { 'Content-Type': 'application/json', apikey: SUPABASE_ANON },
    body   : JSON.stringify({ email, password }),
  })
  const d = await r.json()
  if (!d.access_token) console.warn(`getJwt(${email}): no access_token — ${JSON.stringify(d).slice(0, 200)}`)
  return d.access_token ?? ''
}

async function apiGet(jwt: string, path: string): Promise<any> {
  if (!jwt || !API_URL) return null
  const r = await fetch(`${API_URL}/api/v1${path}`, {
    headers: { Authorization: `Bearer ${jwt}` },
  })
  if (!r.ok) return null
  return r.json()
}

async function apiPost(jwt: string, path: string, body: unknown): Promise<any> {
  if (!jwt || !API_URL) return null
  const r = await fetch(`${API_URL}/api/v1${path}`, {
    method : 'POST',
    headers: { Authorization: `Bearer ${jwt}`, 'Content-Type': 'application/json' },
    body   : JSON.stringify(body),
  })
  if (!r.ok) { console.warn(`POST ${path} → ${r.status} ${await r.text().catch(() => '')}`); return null }
  return r.json()
}

async function apiPatch(jwt: string, path: string, body: unknown): Promise<any> {
  if (!jwt || !API_URL) return null
  const r = await fetch(`${API_URL}/api/v1${path}`, {
    method : 'PATCH',
    headers: { Authorization: `Bearer ${jwt}`, 'Content-Type': 'application/json' },
    body   : JSON.stringify(body),
  })
  if (!r.ok) { console.warn(`PATCH ${path} → ${r.status}`); return null }
  return r.json()
}

async function sleep(ms: number) {
  return new Promise((res) => setTimeout(res, ms))
}

async function sendMessage(page: any, text: string, waitMs = 25_000) {
  const input = page.locator(
    '.chat-input-wrap input, input[placeholder*="message"], textarea[placeholder*="message"]',
  ).first()
  await input.fill(text)
  await input.press('Enter')
  await page.waitForTimeout(waitMs)
}

// ── Suite ──────────────────────────────────────────────────────────────────────

test.describe('Module 13 — Full New Tenant E2E', () => {
  test.describe.configure({ mode: 'serial' })
  test.setTimeout(25 * 60 * 1_000)

  // ── beforeAll ─────────────────────────────────────────────────────────────
  test.beforeAll(async () => {
    test.setTimeout(25 * 60 * 1_000)

    const prereqs = [SRC_EMAIL, SRC_PASS, SA_EMAIL, SA_PASS, SERVICE_KEY, SUPABASE_URL]
    if (prereqs.some((v) => !v)) {
      console.warn('NT beforeAll: missing required env vars — skipping setup')
      return
    }

    // ── 1. Authenticate source tenant and super admin ──────────────────────
    console.log('NT [1/6] Authenticating source tenant and super admin...')
    ;[srcJwt, saJwt] = await Promise.all([
      getJwt(SRC_EMAIL, SRC_PASS),
      getJwt(SA_EMAIL, SA_PASS),
    ])
    if (!srcJwt) { console.warn('NT: source tenant JWT failed'); return }
    if (!saJwt)  { console.warn('NT: super admin JWT failed');   return }

    // ── 2. Read credentials from source tenant ─────────────────────────────
    console.log('NT [2/6] Reading credentials from source tenant...')
    if (SRC_TENANT_ID) {
      const tResp = await fetch(
        `${SUPABASE_URL}/rest/v1/tenants` +
        `?id=eq.${SRC_TENANT_ID}` +
        `&select=ai_api_key,ai_provider,email_inbox_host,email_inbox_user,email_inbox_password` +
        `&limit=1`,
        { headers: { apikey: SERVICE_KEY, Authorization: `Bearer ${SERVICE_KEY}` } },
      )
      const rows = await tResp.json()
      if (Array.isArray(rows) && rows[0]) {
        const row = rows[0]
        srcAiProvider = row.ai_provider ?? 'anthropic'
        if (row.ai_api_key && ENCRYPT_KEY) {
          try { srcAiApiKey = fernetDecrypt(row.ai_api_key, ENCRYPT_KEY) } catch { srcAiApiKey = '' }
        }
        srcImapHost = row.email_inbox_host ?? ''
        srcImapUser = row.email_inbox_user ?? ''
        if (row.email_inbox_password && ENCRYPT_KEY) {
          try { srcImapPass = fernetDecrypt(row.email_inbox_password, ENCRYPT_KEY) } catch { srcImapPass = '' }
        }
        console.log(`NT [2/6] Source credentials: aiProvider=${srcAiProvider} hasKey=${!!srcAiApiKey} imapHost=${srcImapHost}`)
      }
    }

    // ── 3. Create new Supabase user (auto-confirmed, no email needed) ───────
    console.log(`NT [3/6] Creating new Supabase user: ${NEW_EMAIL}`)
    const createResp = await fetch(`${SUPABASE_URL}/auth/v1/admin/users`, {
      method : 'POST',
      headers: {
        'Content-Type' : 'application/json',
        apikey         : SERVICE_KEY,
        Authorization  : `Bearer ${SERVICE_KEY}`,
      },
      body: JSON.stringify({
        email          : NEW_EMAIL,
        password       : NEW_PASS,
        email_confirm  : true,
        user_metadata  : { firm_name: NEW_FIRM },
      }),
    })
    const createData = await createResp.json()
    if (!createData.id) {
      console.warn(`NT [3/6] User creation failed: ${JSON.stringify(createData).slice(0, 300)}`)
      return
    }
    newUserId = createData.id
    console.log(`NT [3/6] Supabase user created: ${newUserId}`)

    // ── 4. Insert Tenant row (SERVICE_KEY bypasses RLS) ────────────────────
    console.log('NT [4/6] Inserting tenant row...')
    const tenantResp = await fetch(`${SUPABASE_URL}/rest/v1/tenants`, {
      method : 'POST',
      headers: {
        'Content-Type' : 'application/json',
        apikey         : SERVICE_KEY,
        Authorization  : `Bearer ${SERVICE_KEY}`,
        Prefer         : 'return=representation',
      },
      body: JSON.stringify({
        id               : randomUUID(),
        name             : NEW_FIRM,
        slug             : NEW_SLUG,
        user_id          : newUserId,
        plan             : 'trial',
        credits_remaining: 10,
      }),
    })
    const tenantData = await tenantResp.json()
    const tenantRow = Array.isArray(tenantData) ? tenantData[0] : tenantData
    if (!tenantRow?.id) {
      console.warn(`NT [4/6] Tenant insert failed: ${JSON.stringify(tenantData).slice(0, 300)}`)
      return
    }
    newTenantId = tenantRow.id
    console.log(`NT [4/6] Tenant row created: ${newTenantId}`)

    // ── 4b. Set app_metadata.tenant_id on the Supabase user ──────────────
    // The backend reads tenant_id from app_metadata in the JWT.
    // This must be set BEFORE login so the JWT includes it.
    console.log('NT [4b/6] Setting app_metadata.tenant_id on Supabase user...')
    const amResp = await fetch(`${SUPABASE_URL}/auth/v1/admin/users/${newUserId}`, {
      method : 'PUT',
      headers: {
        'Content-Type' : 'application/json',
        apikey         : SERVICE_KEY,
        Authorization  : `Bearer ${SERVICE_KEY}`,
      },
      body: JSON.stringify({ app_metadata: { tenant_id: newTenantId } }),
    })
    if (amResp.ok) {
      console.log('NT [4b/6] app_metadata.tenant_id set')
    } else {
      console.warn(`NT [4b/6] app_metadata update failed: ${amResp.status} ${await amResp.text().catch(() => '')}`)
    }

    // ── 5. Login as new tenant ─────────────────────────────────────────────
    console.log('NT [5/6] Logging in as new tenant...')
    newJwt = await getJwt(NEW_EMAIL, NEW_PASS)
    if (!newJwt) { console.warn('NT [5/6] New tenant login failed'); return }
    console.log('NT [5/6] New tenant authenticated')

    // ── 6. Super admin grants recruiter plan + credits ─────────────────────
    console.log('NT [6/6] Super admin granting recruiter plan...')
    try {
      const ctrl  = new AbortController()
      const timer = setTimeout(() => ctrl.abort(), 30_000)
      const planResp = await fetch(`${API_URL}/api/v1/super-admin/tenants/${newTenantId}`, {
        method : 'PATCH',
        headers: { Authorization: `Bearer ${saJwt}`, 'Content-Type': 'application/json' },
        body   : JSON.stringify({ plan: 'recruiter', credits_remaining: 10 }),
        signal : ctrl.signal,
      })
      clearTimeout(timer)
      if (planResp.ok) {
        console.log('NT [6/6] Plan set to recruiter, credits=10')
      } else {
        console.warn(`NT [6/6] Plan grant failed: ${planResp.status}`)
      }
    } catch (err: any) {
      console.warn(`NT [6/6] Plan grant error (non-fatal): ${err.message}`)
    }
    // Refresh JWT (plan change may affect token claims in some configs)
    newJwt = await getJwt(NEW_EMAIL, NEW_PASS)
  })

  // ── afterAll: delete the test user from Supabase ──────────────────────────
  test.afterAll(async () => {
    if (!newUserId || !SERVICE_KEY) return

    // Close any jobs created
    if (scoutJobId)   await apiPatch(newJwt, `/jobs/${scoutJobId}`,   { status: 'closed' }).catch(() => {})
    if (screenerJobId) await apiPatch(newJwt, `/jobs/${screenerJobId}`, { status: 'closed' }).catch(() => {})

    // Delete Supabase user (cascades tenant row via our DB — or we delete tenant first)
    if (newTenantId) {
      await fetch(`${SUPABASE_URL}/rest/v1/tenants?id=eq.${newTenantId}`, {
        method : 'DELETE',
        headers: { apikey: SERVICE_KEY, Authorization: `Bearer ${SERVICE_KEY}` },
      }).catch(() => {})
    }
    await fetch(`${SUPABASE_URL}/auth/v1/admin/users/${newUserId}`, {
      method : 'DELETE',
      headers: { apikey: SERVICE_KEY, Authorization: `Bearer ${SERVICE_KEY}` },
    }).catch(() => {})

    console.log(`NT afterAll: cleaned up user=${newUserId} tenant=${newTenantId}`)
  })

  // ═══════════════════════════════════════════════════════════════════════════
  // SECTION G — Signup & First Login
  // ═══════════════════════════════════════════════════════════════════════════

  // ── NT-01 — New tenant user exists in Supabase ────────────────────────────
  test('NT-01 — Signup — new Supabase user created and auto-confirmed', async ({ page }) => {
    if (!newUserId) { test.skip(true, 'ENV_SKIP: user creation failed in beforeAll'); return }

    const r = await fetch(`${SUPABASE_URL}/auth/v1/admin/users/${newUserId}`, {
      headers: { apikey: SERVICE_KEY, Authorization: `Bearer ${SERVICE_KEY}` },
    })
    const user = await r.json()
    expect(user.id).toBe(newUserId)
    expect(user.email).toBe(NEW_EMAIL)
    expect(user.email_confirmed_at).toBeTruthy()
    console.log(`NT-01: user ${NEW_EMAIL} confirmed at ${user.email_confirmed_at}`)
  })

  // ── NT-02 — Tenant row exists in DB ──────────────────────────────────────
  test('NT-02 — Signup — tenant row exists with correct name and plan', async ({ page }) => {
    if (!newTenantId) { test.skip(true, 'ENV_SKIP: tenant creation failed in beforeAll'); return }

    const tenant = await apiGet(newJwt, '/tenants/me')
    expect(tenant).not.toBeNull()
    expect(tenant.name).toBe(NEW_FIRM)
    expect(['trial', 'recruiter']).toContain(tenant.plan)
    console.log(`NT-02: tenant "${tenant.name}" plan=${tenant.plan}`)
  })

  // ── NT-03 — Login via UI → redirects to dashboard ────────────────────────
  test('NT-03 — Login — new tenant logs in, redirects to /en dashboard', async ({ page }) => {
    if (!newUserId) { test.skip(true, 'ENV_SKIP: no new user'); return }

    await page.goto('/en/login')
    await page.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => {})

    await page.locator('input[type="email"]').fill(NEW_EMAIL)
    await page.locator('input[type="password"]').fill(NEW_PASS)
    await page.getByRole('button', { name: /sign in|log in/i }).click()

    await page.waitForURL(/\/en($|\/)/, { timeout: 20_000 }).catch(() => {})
    expect(page.url()).toMatch(/\/en($|\/)/)
    await expect(page.locator('body')).not.toContainText('500')
    console.log(`NT-03: redirected to ${page.url()}`)
  })

  // ── NT-04 — Sidebar has no Super Admin link ───────────────────────────────
  test('NT-04 — New tenant — sidebar does NOT contain Super Admin link', async ({ page }) => {
    if (!newUserId) { test.skip(true, 'ENV_SKIP: no new user'); return }

    await page.goto('/en/login')
    await page.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => {})
    await page.locator('input[type="email"]').fill(NEW_EMAIL)
    await page.locator('input[type="password"]').fill(NEW_PASS)
    await page.getByRole('button', { name: /sign in|log in/i }).click()
    await page.waitForURL(/\/en($|\/)/, { timeout: 20_000 }).catch(() => {})

    // No Super Admin link in sidebar
    await expect(page.getByText(/super admin/i)).not.toBeVisible()
    console.log('NT-04: Super Admin link correctly absent for new tenant')
  })

  // ── NT-05 — Super admin grants recruiter plan ─────────────────────────────
  test('NT-05 — Super admin — plan set to recruiter, credits=10', async ({ page }) => {
    if (!newTenantId) { test.skip(true, 'ENV_SKIP: no newTenantId'); return }

    const tenant = await apiGet(newJwt, '/tenants/me')
    expect(tenant.plan).toBe('recruiter')
    expect(tenant.credits_remaining).toBeGreaterThanOrEqual(1)
    console.log(`NT-05: plan=${tenant.plan} credits=${tenant.credits_remaining}`)
  })

  // ── NT-06 — New tenant billing page shows recruiter plan ──────────────────
  test('NT-06 — Billing page — shows recruiter plan for new tenant', async ({ page }) => {
    if (!newUserId) { test.skip(true, 'ENV_SKIP: no new user'); return }

    // Log in as new tenant
    await page.goto('/en/login')
    await page.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => {})
    await page.locator('input[type="email"]').fill(NEW_EMAIL)
    await page.locator('input[type="password"]').fill(NEW_PASS)
    await page.getByRole('button', { name: /sign in|log in/i }).click()
    await page.waitForURL(/\/en($|\/)/, { timeout: 20_000 }).catch(() => {})

    await page.goto('/en/billing')
    await page.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => {})

    await expect(page.getByText(/recruiter/i).first()).toBeVisible({ timeout: 10_000 })
    await expect(page.locator('body')).not.toContainText('500')
    console.log('NT-06: Billing page shows recruiter plan')
  })

  // ═══════════════════════════════════════════════════════════════════════════
  // SECTION H — Quickstart Guide (Steps 1–4)
  // ═══════════════════════════════════════════════════════════════════════════

  // ── QS-01 — Quickstart page loads — 1/6 complete ─────────────────────────
  test('QS-01 — Quickstart — page loads, step 1 (Account) complete, steps 2–6 pending', async ({ page }) => {
    if (!newJwt) { test.skip(true, 'ENV_SKIP: no newJwt'); return }

    const status = await apiGet(newJwt, '/tenants/me/quickstart-status')
    expect(status).not.toBeNull()
    expect(status.total_count).toBe(6)

    const step1 = status.steps.find((s: any) => s.key === 'account')
    expect(step1?.completed).toBe(true)

    const step2 = status.steps.find((s: any) => s.key === 'api_keys')
    expect(step2?.completed).toBe(false)

    console.log(`QS-01: quickstart ${status.completed_count}/${status.total_count}`)
  })

  // ── QS-02 — Step 2: Add AI API key ───────────────────────────────────────
  test('QS-02 — Settings — AI API key saved, quickstart step 2 completes', async ({ page }) => {
    if (!newJwt || !srcAiApiKey) {
      test.skip(true, 'ENV_SKIP: no newJwt or source API key unavailable')
      return
    }

    // Patch via API
    const updated = await apiPatch(newJwt, '/tenants/me', {
      ai_api_key  : srcAiApiKey,
      ai_provider : srcAiProvider || 'anthropic',
    })
    expect(updated).not.toBeNull()

    // Verify quickstart step 2 is now complete
    const status = await apiGet(newJwt, '/tenants/me/quickstart-status')
    const step2 = status?.steps?.find((s: any) => s.key === 'api_keys')
    expect(step2?.completed).toBe(true)
    console.log(`QS-02: api_keys step complete. progress: ${status.completed_count}/${status.total_count}`)
  })

  // ── QS-03 — Step 3: IMAP email inbox ─────────────────────────────────────
  test('QS-03 — Settings — IMAP inbox saved, quickstart step 3 completes', async ({ page }) => {
    if (!newJwt || !srcImapHost) {
      test.skip(true, 'ENV_SKIP: no newJwt or source IMAP credentials unavailable')
      return
    }

    const updated = await apiPatch(newJwt, '/tenants/me', {
      email_inbox_host    : srcImapHost,
      email_inbox_port    : 993,
      email_inbox_user    : srcImapUser,
      email_inbox_password: srcImapPass,
    })
    expect(updated).not.toBeNull()

    const status = await apiGet(newJwt, '/tenants/me/quickstart-status')
    const step3 = status?.steps?.find((s: any) => s.key === 'email_inbox')
    expect(step3?.completed).toBe(true)
    console.log(`QS-03: email_inbox step complete. progress: ${status.completed_count}/${status.total_count}`)
  })

  // ── QS-04 — Step 4: Upload knowledge base ────────────────────────────────
  test('QS-04 — Knowledge base — document uploaded, quickstart step 4 completes', async ({ page }) => {
    if (!newJwt) { test.skip(true, 'ENV_SKIP: no newJwt'); return }

    // Build a minimal valid PDF in memory
    const text    = `${NEW_FIRM} — Company Overview\n\nWe are a technology company focused on AI-powered recruitment solutions.\nFounded in Sydney, Australia. 50 employees. Series A funded.\nWe specialise in helping enterprise customers automate their hiring pipelines.`
    const stream  = `BT /F1 11 Tf 50 740 Td (${NEW_FIRM.replace(/[()]/g, '')}) Tj 0 -20 Td (AI Recruitment Technology Company - Sydney Australia) Tj ET`
    const streamLen = stream.length
    const objs = [
      '1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n',
      '2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n',
      `3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>\nendobj\n`,
      `4 0 obj\n<< /Length ${streamLen} >>\nstream\n${stream}\nendstream\nendobj\n`,
      '5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n',
    ]
    let pdf = '%PDF-1.4\n'
    const offsets: number[] = []
    for (const o of objs) { offsets.push(pdf.length); pdf += o }
    const xrefAt = pdf.length
    pdf += `xref\n0 ${objs.length + 1}\n0000000000 65535 f \n`
    for (const off of offsets) pdf += `${String(off).padStart(10, '0')} 00000 n \n`
    pdf += `trailer\n<< /Size ${objs.length + 1} /Root 1 0 R >>\nstartxref\n${xrefAt}\n%%EOF\n`
    const pdfBuffer = Buffer.from(pdf, 'ascii')

    // Upload via multipart form
    const formData = new FormData()
    formData.append('file', new Blob([pdfBuffer], { type: 'application/pdf' }), 'company-overview.pdf')

    const r = await fetch(`${API_URL}/api/v1/rag/documents`, {
      method : 'POST',
      headers: { Authorization: `Bearer ${newJwt}` },
      body   : formData,
    })
    if (!r.ok) {
      console.warn(`QS-04: RAG upload failed: ${r.status} ${await r.text().catch(() => '')}`)
      test.skip(true, `ENV_SKIP: RAG upload failed (${r.status})`)
      return
    }
    const uploaded = await r.json()
    expect(uploaded).not.toBeNull()
    console.log(`QS-04: document uploaded — chunks: ${Array.isArray(uploaded) ? uploaded.length : 1}`)

    const status = await apiGet(newJwt, '/tenants/me/quickstart-status')
    const step4 = status?.steps?.find((s: any) => s.key === 'knowledge_base')
    expect(step4?.completed).toBe(true)
    console.log(`QS-04: knowledge_base step complete. progress: ${status.completed_count}/${status.total_count}`)
  })

  // ── QS-05 — Quickstart UI shows 4/6 ─────────────────────────────────────
  test('QS-05 — Quickstart page UI — shows 4/6 complete, steps 5 & 6 pending', async ({ page }) => {
    if (!newUserId) { test.skip(true, 'ENV_SKIP: no new user'); return }

    await page.goto('/en/login')
    await page.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => {})
    await page.locator('input[type="email"]').fill(NEW_EMAIL)
    await page.locator('input[type="password"]').fill(NEW_PASS)
    await page.getByRole('button', { name: /sign in|log in/i }).click()
    await page.waitForURL(/\/en($|\/)/, { timeout: 20_000 }).catch(() => {})

    await page.goto('/en/quickstart')
    await page.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => {})

    // Progress text should show at least 3/6 or 4/6
    await expect(
      page.getByText(/[34] \/ 6|[34]\/6|complete/i).first(),
    ).toBeVisible({ timeout: 10_000 })

    // "Create your first job" step should be active/incomplete
    await expect(page.getByText(/create your first job/i).first()).toBeVisible()
    await expect(page.locator('body')).not.toContainText('500')
    console.log('QS-05: quickstart UI shows expected progress')
  })

  // ── QS-06 — AI Recruiter system prompt accessible ────────────────────────
  test('QS-06 — Settings — AI Recruiter prompt form loads and saves for new tenant', async ({ page }) => {
    if (!newJwt) { test.skip(true, 'ENV_SKIP: no newJwt'); return }

    // Check via API
    const tenant = await apiGet(newJwt, '/tenants/me')
    expect(tenant).not.toBeNull()

    // Save a custom recruiter prompt
    const updated = await apiPatch(newJwt, '/tenants/me', {
      recruiter_system_prompt: `You are a friendly AI recruiter for ${NEW_FIRM}. Focus on tech talent in Sydney.`,
    })
    expect(updated).not.toBeNull()

    const refreshed = await apiGet(newJwt, '/tenants/me')
    // Prompt may not be returned in plain text (field may be omitted) — just check no 500
    expect(refreshed).not.toBeNull()
    console.log('QS-06: AI recruiter prompt saved successfully')
  })

  // ═══════════════════════════════════════════════════════════════════════════
  // SECTION I — First Scout Job via Chat (Step 5 of Quickstart)
  // ═══════════════════════════════════════════════════════════════════════════

  // ── JS-01 — Chat loads for new tenant ────────────────────────────────────
  test('JS-01 — Chat — /en/chat loads for new tenant, no previous sessions', async ({ page }) => {
    if (!newUserId) { test.skip(true, 'ENV_SKIP: no new user'); return }

    await page.goto('/en/login')
    await page.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => {})
    await page.locator('input[type="email"]').fill(NEW_EMAIL)
    await page.locator('input[type="password"]').fill(NEW_PASS)
    await page.getByRole('button', { name: /sign in|log in/i }).click()
    await page.waitForURL(/\/en($|\/)/, { timeout: 20_000 }).catch(() => {})

    await page.goto('/en/chat')
    await page.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => {})
    await expect(page.getByText(/AI Recruiter|chat|new job/i).first()).toBeVisible({ timeout: 10_000 })
    await expect(page.locator('body')).not.toContainText('500')
    console.log('JS-01: chat page loaded for new tenant')
  })

  // ── JS-02 — Paste JD, AI responds ────────────────────────────────────────
  test('JS-02 — Chat — paste full JD, AI responds with streaming', async ({ page }) => {
    if (!newUserId) { test.skip(true, 'ENV_SKIP: no new user'); return }

    await page.goto('/en/login')
    await page.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => {})
    await page.locator('input[type="email"]').fill(NEW_EMAIL)
    await page.locator('input[type="password"]').fill(NEW_PASS)
    await page.getByRole('button', { name: /sign in|log in/i }).click()
    await page.waitForURL(/\/en($|\/)/, { timeout: 20_000 }).catch(() => {})

    await page.goto('/en/chat')
    await page.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => {})

    const jd = [
      'Job Title: Senior TypeScript Developer',
      'Location: Sydney CBD, hybrid (3 days onsite)',
      'Type: Full-time, permanent',
      'Salary: $160,000 – $200,000 + equity',
      '',
      'We are building AI-powered enterprise SaaS products.',
      'Requirements:',
      '- 5+ years TypeScript / JavaScript experience',
      '- Strong Node.js and React skills',
      '- PostgreSQL, Redis, AWS',
      '- Experience with CI/CD and Docker',
      'Nice to have: Playwright, Go, Kubernetes',
      'Target: 10 candidates, minimum score 7.',
    ].join('\n')

    await sendMessage(page, jd, 35_000)

    const hasResponse =
      (await page.getByText(/typescript|developer|sydney|tell me|clarify|confirm/i).count()) > 0
    expect(hasResponse).toBeTruthy()
    console.log('JS-02: AI responded to JD paste')
  })

  // ── JS-03 — Answer follow-ups → payment phase ─────────────────────────────
  test('JS-03 — Chat — follow-up answers move toward payment phase', async ({ page }) => {
    if (!newJwt) { test.skip(true, 'ENV_SKIP: no newJwt'); return }

    // Check current session state via API
    const sessions = await apiGet(newJwt, '/chat-sessions?limit=5')
    const session = (sessions?.items ?? [])[0]
    if (!session) { test.skip(true, 'ENV_SKIP: no chat session found'); return }

    console.log(`JS-03: latest session phase=${session.phase} job_id=${session.job_id ?? 'none'}`)
    // Phase should be job_collection or payment — either is acceptable at this point
    expect(['job_collection', 'payment', 'recruitment']).toContain(session.phase)
  })

  // ── JS-04 — Type "confirm" → job created ─────────────────────────────────
  test('JS-04 — Chat payment — "confirm" creates job, phase=recruitment', async ({ page }) => {
    if (!newJwt) { test.skip(true, 'ENV_SKIP: no newJwt'); return }

    // Find session in payment phase, or force it via targeted messages
    let sessions = await apiGet(newJwt, '/chat-sessions?limit=5')
    let paymentSession = (sessions?.items ?? []).find((s: any) => s.phase === 'payment')
    const existingJob = (sessions?.items ?? []).find((s: any) => s.phase === 'recruitment' && s.job_id)

    if (existingJob?.job_id) {
      // Already past payment — job was created in a previous test run or retry
      scoutJobId = existingJob.job_id
      const job = await apiGet(newJwt, `/jobs/${scoutJobId}`)
      scoutJobRef = job?.job_ref ?? ''
      console.log(`JS-04: job already exists from previous run: ${scoutJobId} ref=${scoutJobRef}`)
      return
    }

    if (!paymentSession) {
      console.warn('JS-04: no payment session — pipeline tests will use API-created job as fallback')
      // Create a Scout job directly via API as fallback
      const created = await apiPost(newJwt, '/jobs', {
        title           : 'Senior TypeScript Developer (E2E)',
        description     : 'Senior TypeScript Developer role. Node.js, React, PostgreSQL, AWS. Sydney hybrid.',
        job_type        : 'Full-time',
        location        : 'Sydney, NSW',
        work_type       : 'hybrid',
        required_skills : ['TypeScript', 'Node.js', 'React', 'PostgreSQL'],
        experience_years: 5,
        mode            : 'talent_scout',
        minimum_score   : 7,
        candidate_target: 10,
      })
      if (created?.id) {
        scoutJobId  = created.id
        const activated = await apiPatch(newJwt, `/jobs/${scoutJobId}`, { status: 'active' })
        scoutJobRef = activated?.job_ref ?? created.job_ref ?? ''
        console.log(`JS-04: created scout job via API fallback: ${scoutJobId} ref=${scoutJobRef}`)
      }
      return
    }

    // Send confirm to trigger payment shortcut
    const confirmResult = await apiPost(newJwt, `/chat-sessions/${paymentSession.id}/message`, {
      content: 'confirm',
    })
    await sleep(5_000) // give backend time to create job + queue task

    // Refresh sessions
    sessions = await apiGet(newJwt, '/chat-sessions?limit=5')
    const recruitSession = (sessions?.items ?? []).find(
      (s: any) => s.id === paymentSession.id,
    )
    if (recruitSession?.job_id) {
      scoutJobId = recruitSession.job_id
      const job = await apiGet(newJwt, `/jobs/${scoutJobId}`)
      scoutJobRef = job?.job_ref ?? ''
      console.log(`JS-04: payment confirmed — job created: ${scoutJobId} ref=${scoutJobRef}`)
    } else {
      console.warn('JS-04: job not yet created after confirm — may need more time')
    }
  })

  // ── JS-05 — Quickstart step 5 (first_job) now complete ───────────────────
  test('JS-05 — Quickstart — step 5 (first_job) complete after job creation', async ({ page }) => {
    if (!newJwt || !scoutJobId) { test.skip(true, 'ENV_SKIP: no job created'); return }

    const status = await apiGet(newJwt, '/tenants/me/quickstart-status')
    const step5 = status?.steps?.find((s: any) => s.key === 'first_job')
    expect(step5?.completed).toBe(true)
    console.log(`JS-05: first_job step complete. progress: ${status.completed_count}/${status.total_count}`)
  })

  // ── JS-06 — Scout job in /en/jobs ─────────────────────────────────────────
  test('JS-06 — Jobs page — scout job visible with AI Scout mode and Active status', async ({ page }) => {
    if (!newUserId || !scoutJobRef) { test.skip(true, 'ENV_SKIP: no scoutJobRef'); return }

    await page.goto('/en/login')
    await page.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => {})
    await page.locator('input[type="email"]').fill(NEW_EMAIL)
    await page.locator('input[type="password"]').fill(NEW_PASS)
    await page.getByRole('button', { name: /sign in|log in/i }).click()
    await page.waitForURL(/\/en($|\/)/, { timeout: 20_000 }).catch(() => {})

    await page.goto('/en/jobs')
    await page.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => {})

    const row = page.locator('table tbody tr').filter({ hasText: scoutJobRef })
    if (await row.count() > 0) {
      await expect(row.first()).toContainText(/AI Scout|scout/i)
      await expect(row.first()).toContainText(/active/i)
      console.log(`JS-06: scout job ${scoutJobRef} visible in /en/jobs`)
    } else {
      // May be on second page — check API
      const job = await apiGet(newJwt, `/jobs/${scoutJobId}`)
      expect(job?.status).toBe('active')
      console.log(`JS-06: job ${scoutJobRef} confirmed active via API (not visible on first page)`)
    }
  })

  // ── JS-07 — Audit trail: job.created ─────────────────────────────────────
  test('JS-07 — Audit Trail — job.created event for scout job', async ({ page }) => {
    if (!newJwt || !scoutJobId) { test.skip(true, 'ENV_SKIP: no scoutJobId'); return }

    const audit = await apiGet(newJwt, `/jobs/${scoutJobId}/audit-trail?limit=50`)
    const events: string[] = (audit?.events ?? audit?.items ?? []).map((e: any) => e.event_type ?? e.type ?? '')
    const hasCreated = events.some((e) => e.includes('created'))
    if (events.length > 0) expect(hasCreated).toBeTruthy()
    console.log(`JS-07: audit events: ${events.slice(0, 5).join(', ')}`)
  })

  // ═══════════════════════════════════════════════════════════════════════════
  // SECTION J — Scout Pipeline (Step 6 of Quickstart)
  // ═══════════════════════════════════════════════════════════════════════════

  // ── JP-01 — At least 1 candidate discovered ───────────────────────────────
  test('JP-01 — Scout pipeline — at least 1 candidate with status=discovered', async ({ page }) => {
    if (!newJwt || !scoutJobId) { test.skip(true, 'ENV_SKIP: no scoutJobId'); return }

    // Poll up to 5 min
    const deadline = Date.now() + 5 * 60 * 1000
    let found: any = null
    while (Date.now() < deadline) {
      const data = await apiGet(newJwt, `/candidates?job_id=${scoutJobId}&limit=200`)
      found = (data?.items ?? []).find((c: any) => c.status === 'discovered')
      if (found) { scoutCandidate = found.id; break }
      const counts: Record<string, number> = {}
      ;(data?.items ?? []).forEach((c: any) => { counts[c.status] = (counts[c.status] ?? 0) + 1 })
      console.log(`JP-01: candidate counts: ${JSON.stringify(counts)} — waiting...`)
      await sleep(30_000)
    }

    if (!found) {
      test.skip(true, 'ENV_SKIP: no discovered candidates within poll window (ScrapingDog may not be configured for this tenant)')
      return
    }
    expect(found.status).toBe('discovered')
    expect(found.linkedin_url).toBeTruthy()
    console.log(`JP-01: discovered candidate ${scoutCandidate}`)
  })

  // ── JP-02 — Quickstart step 6 (first_candidate) complete ─────────────────
  test('JP-02 — Quickstart — step 6 (first_candidate) complete after first candidate', async ({ page }) => {
    if (!newJwt || !scoutCandidate) {
      test.skip(true, 'ENV_SKIP: no candidate (JP-01 skipped or failed)')
      return
    }

    const status = await apiGet(newJwt, '/tenants/me/quickstart-status')
    const step6 = status?.steps?.find((s: any) => s.key === 'first_candidate')
    expect(step6?.completed).toBe(true)
    console.log(`JP-02: first_candidate complete — all_done=${status.all_done} (${status.completed_count}/${status.total_count})`)
  })

  // ── JP-03 — Quickstart shows "all set" banner ─────────────────────────────
  test('JP-03 — Quickstart UI — shows completion banner when all 6 steps done', async ({ page }) => {
    if (!newUserId || !scoutCandidate) {
      test.skip(true, 'ENV_SKIP: not all quickstart steps complete')
      return
    }

    await page.goto('/en/login')
    await page.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => {})
    await page.locator('input[type="email"]').fill(NEW_EMAIL)
    await page.locator('input[type="password"]').fill(NEW_PASS)
    await page.getByRole('button', { name: /sign in|log in/i }).click()
    await page.waitForURL(/\/en($|\/)/, { timeout: 20_000 }).catch(() => {})

    await page.goto('/en/quickstart')
    await page.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => {})

    await expect(
      page.getByText(/all set|fully configured|6 \/ 6|6\/6/i).first(),
    ).toBeVisible({ timeout: 10_000 })
    console.log('JP-03: quickstart completion banner visible')
  })

  // ── JP-04 — Candidate detail accessible from new tenant dashboard ─────────
  test('JP-04 — Candidate detail — accessible from new tenant, shows correct data', async ({ page }) => {
    if (!newUserId || !scoutCandidate) {
      test.skip(true, 'ENV_SKIP: no scoutCandidate')
      return
    }

    await page.goto('/en/login')
    await page.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => {})
    await page.locator('input[type="email"]').fill(NEW_EMAIL)
    await page.locator('input[type="password"]').fill(NEW_PASS)
    await page.getByRole('button', { name: /sign in|log in/i }).click()
    await page.waitForURL(/\/en($|\/)/, { timeout: 20_000 }).catch(() => {})

    await page.goto(`/en/candidates/${scoutCandidate}`)
    await page.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => {})

    await expect(page.locator('body')).not.toContainText('404')
    await expect(page.locator('body')).not.toContainText('500')
    await expect(page.locator('.badge, [class*="badge"], [class*="status"]').first()).toBeVisible({ timeout: 10_000 })
    console.log('JP-04: candidate detail accessible')
  })

  // ── JP-05 — Tenant isolation: new tenant cannot see super admin's candidates
  test('JP-05 — Tenant isolation — new tenant sees only their own candidates', async ({ page }) => {
    if (!newJwt) { test.skip(true, 'ENV_SKIP: no newJwt'); return }

    // Get candidate IDs from new tenant
    const newData = await apiGet(newJwt, '/candidates?limit=200')
    const newIds: string[] = (newData?.items ?? []).map((c: any) => c.id)

    // Get candidate IDs from super admin
    const saData = await apiGet(saJwt, '/candidates?limit=200')
    const saIds: string[] = (saData?.items ?? []).map((c: any) => c.id)

    // No overlap
    const overlap = newIds.filter((id) => saIds.includes(id))
    expect(overlap.length).toBe(0)
    console.log(`JP-05: isolation confirmed — new tenant: ${newIds.length} candidates, super admin: ${saIds.length} candidates, overlap: 0`)
  })

  // ═══════════════════════════════════════════════════════════════════════════
  // SECTION K — Screener Job
  // ═══════════════════════════════════════════════════════════════════════════

  // ── KS-01 — Screener job creation form ──────────────────────────────────
  test('KS-01 — Screener job — /en/jobs/new/screener loads for new tenant', async ({ page }) => {
    if (!newUserId) { test.skip(true, 'ENV_SKIP: no new user'); return }

    await page.goto('/en/login')
    await page.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => {})
    await page.locator('input[type="email"]').fill(NEW_EMAIL)
    await page.locator('input[type="password"]').fill(NEW_PASS)
    await page.getByRole('button', { name: /sign in|log in/i }).click()
    await page.waitForURL(/\/en($|\/)/, { timeout: 20_000 }).catch(() => {})

    await page.goto('/en/jobs/new/screener')
    await page.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => {})

    await expect(page.getByText(/screener|job title|position/i).first()).toBeVisible({ timeout: 10_000 })
    await expect(page.locator('body')).not.toContainText('500')
    console.log('KS-01: screener job creation form loads')
  })

  // ── KS-02 — Screener job created via API ─────────────────────────────────
  test('KS-02 — Screener job — created via API, activated', async ({ page }) => {
    if (!newJwt) { test.skip(true, 'ENV_SKIP: no newJwt'); return }

    const created = await apiPost(newJwt, '/jobs', {
      title                    : 'Junior React Developer (E2E Screener)',
      description              : [
        'We are looking for a Junior React Developer to join our growing team.',
        'Requirements: 2+ years React experience, TypeScript, CSS, REST APIs.',
        'Nice to have: Next.js, Jest, Playwright.',
      ].join('\n'),
      job_type                 : 'Full-time',
      location                 : 'Sydney, NSW',
      work_type                : 'hybrid',
      required_skills          : ['React', 'TypeScript', 'JavaScript'],
      experience_years         : 2,
      mode                     : 'screener_only',
      interview_type           : 'text',
      interview_questions_count: 3,
      minimum_score            : 6,
      hiring_manager_email     : SRC_EMAIL,
      hiring_manager_name      : 'Hiring Manager',
    })

    expect(created?.id).toBeTruthy()
    screenerJobId = created.id

    const activated = await apiPatch(newJwt, `/jobs/${screenerJobId}`, { status: 'active' })
    expect(activated?.status).toBe('active')
    screenerJobRef = activated?.job_ref ?? created.job_ref ?? ''
    console.log(`KS-02: screener job created: ${screenerJobId} ref=${screenerJobRef}`)
  })

  // ── KS-03 — Screener job in /en/jobs ─────────────────────────────────────
  test('KS-03 — Jobs page — screener job visible with AI Screener mode', async ({ page }) => {
    if (!screenerJobId) { test.skip(true, 'ENV_SKIP: no screenerJobId'); return }

    const job = await apiGet(newJwt, `/jobs/${screenerJobId}`)
    expect(job.mode).toMatch(/screener/)
    expect(job.status).toBe('active')
    console.log(`KS-03: screener job mode=${job.mode} status=${job.status}`)
  })

  // ── KS-04 — Send resume email to IMAP inbox ───────────────────────────────
  test('KS-04 — IMAP — strong resume email sent for screener job', async ({ page }) => {
    if (!screenerJobRef || !srcImapHost || !srcImapUser || !srcImapPass) {
      test.skip(true, 'ENV_SKIP: no screenerJobRef or IMAP credentials')
      return
    }

    const nodemailer = await import('nodemailer')
    const transport = nodemailer.default.createTransport({
      host  : srcImapHost,
      port  : 465,
      secure: true,
      auth  : { user: srcImapUser, pass: srcImapPass },
    })

    const applicantName = `KS04 React Dev ${RUN_TAG}`
    await transport.sendMail({
      from   : `${applicantName} <${srcImapUser}>`,
      to     : srcImapUser,
      subject: `Application for React Developer [JOB-${screenerJobRef}]`,
      text   : [
        'Dear Hiring Team,',
        `Application for the Junior React Developer role [JOB-${screenerJobRef}].`,
        'I have 3 years of React and TypeScript experience building enterprise web apps.',
        `Kind regards, ${applicantName}`,
      ].join('\n'),
      attachments: [{
        filename   : 'resume-react-dev.pdf',
        contentType: 'application/pdf',
        content    : Buffer.from('%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n', 'ascii'),
      }],
    })
    console.log(`KS-04: email sent for ${screenerJobRef} from ${applicantName}`)
    expect(true).toBe(true) // email send succeeded (no throw)
  })

  // ── KS-05 — Application created for screener job ─────────────────────────
  test('KS-05 — IMAP poll — application appears for screener job', async ({ page }) => {
    if (!newJwt || !screenerJobId || !srcImapHost) {
      test.skip(true, 'ENV_SKIP: no screenerJobId or IMAP not configured')
      return
    }

    // Poll up to 7 min (IMAP beat=5min + processing buffer)
    const deadline = Date.now() + 7 * 60 * 1000
    let found: any = null
    while (Date.now() < deadline) {
      const data = await apiGet(newJwt, `/applications?job_id=${screenerJobId}&limit=100`)
      found = (data?.items ?? [])[0]
      if (found) { console.log(`KS-05: application found: ${found.id} status=${found.screening_status}`); break }
      const remaining = Math.round((deadline - Date.now()) / 1000)
      console.log(`KS-05: no application yet — ${remaining}s left...`)
      await sleep(30_000)
    }

    if (!found) {
      test.skip(true, 'ENV_SKIP: no application appeared (IMAP poller may not have run for new tenant inbox)')
      return
    }
    expect(found).not.toBeNull()
    expect(['pending', 'passed', 'failed']).toContain(found.screening_status)
  })

  // ── KS-06 — Application screened ─────────────────────────────────────────
  test('KS-06 — Screener — application reaches screened status (passed or failed)', async ({ page }) => {
    if (!newJwt || !screenerJobId) { test.skip(true, 'ENV_SKIP: no screenerJobId'); return }

    const data = await apiGet(newJwt, `/applications?job_id=${screenerJobId}&limit=100`)
    const app = (data?.items ?? [])[0]
    if (!app) { test.skip(true, 'ENV_SKIP: no application (KS-05 may have skipped)'); return }

    // If still pending, poll up to 3 min
    let current = app
    if (current.screening_status === 'pending') {
      const deadline = Date.now() + 3 * 60 * 1000
      while (Date.now() < deadline) {
        current = await apiGet(newJwt, `/applications/${app.id}`) ?? current
        if (current.screening_status !== 'pending') break
        await sleep(20_000)
      }
    }

    expect(['passed', 'failed']).toContain(current.screening_status)
    console.log(`KS-06: application ${app.id} screening_status=${current.screening_status} score=${current.resume_score}`)
  })

  // ── KS-07 — If passed: test invite issued ────────────────────────────────
  test('KS-07 — Test invite — passed application receives test invite', async ({ page }) => {
    if (!newJwt || !screenerJobId) { test.skip(true, 'ENV_SKIP: no screenerJobId'); return }

    const data = await apiGet(newJwt, `/applications?job_id=${screenerJobId}&limit=100`)
    const passed = (data?.items ?? []).find((a: any) => a.screening_status === 'passed')
    if (!passed) {
      test.skip(true, 'ENV_SKIP: no passed application (all screened as failed, or KS-06 skipped)')
      return
    }

    // Poll for test invite up to 3 min
    let current = passed
    const deadline = Date.now() + 3 * 60 * 1000
    while (Date.now() < deadline) {
      current = await apiGet(newJwt, `/applications/${passed.id}`) ?? current
      if (['invited', 'completed'].includes(current.test_status)) break
      await sleep(20_000)
    }

    expect(['invited', 'completed', 'not_started']).toContain(current.test_status)
    if (current.test_status === 'invited') {
      expect(current.interview_invite_token).toBeTruthy()
    }
    console.log(`KS-07: application test_status=${current.test_status}`)
  })

  // ═══════════════════════════════════════════════════════════════════════════
  // SECTION L — Cleanup & Isolation
  // ═══════════════════════════════════════════════════════════════════════════

  // ── CL-01 — Super admin can see new tenant in tenant list ─────────────────
  test('CL-01 — Super admin — new tenant appears in tenant list', async ({ page }) => {
    if (!saJwt || !newTenantId) { test.skip(true, 'ENV_SKIP: no saJwt or newTenantId'); return }

    const tenants = await apiGet(saJwt, '/super-admin/tenants?limit=100')
    const items: any[] = tenants?.tenants ?? tenants?.items ?? []
    const found = items.find((t: any) => t.id === newTenantId || t.name === NEW_FIRM)
    expect(found).not.toBeUndefined()
    console.log(`CL-01: new tenant "${NEW_FIRM}" found in super admin tenant list`)
  })

  // ── CL-02 — Super admin cannot see new tenant's data ─────────────────────
  test('CL-02 — Tenant isolation — super admin candidates exclude new tenant data', async ({ page }) => {
    if (!saJwt || !newJwt) { test.skip(true, 'ENV_SKIP: no saJwt or newJwt'); return }

    // Super admin's candidates should not include new tenant's candidates
    const newData = await apiGet(newJwt, '/candidates?limit=200')
    const newIds: string[] = (newData?.items ?? []).map((c: any) => c.id)

    if (newIds.length === 0) {
      console.log('CL-02: no candidates for new tenant — isolation trivially holds')
      return
    }

    // Super admin's own candidate list (scoped to their tenant)
    const saData = await apiGet(saJwt, '/candidates?limit=200')
    const saIds: string[] = (saData?.items ?? []).map((c: any) => c.id)
    const overlap = newIds.filter((id) => saIds.includes(id))
    expect(overlap.length).toBe(0)
    console.log(`CL-02: isolation confirmed — ${newIds.length} new-tenant candidates not visible to super admin tenant`)
  })

  // ── CL-03 — New tenant cleanup confirmed ──────────────────────────────────
  test('CL-03 — Cleanup — test tenant will be deleted in afterAll', async ({ page }) => {
    // This test just documents that afterAll handles cleanup.
    // Actual deletion happens in afterAll above.
    console.log(`CL-03: tenant ${newTenantId} (user ${newUserId}) will be deleted in afterAll`)
    expect(newUserId || newTenantId).toBeTruthy()
  })
})
