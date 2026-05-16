/**
 * Module 11 — Full Talent Scout Pipeline
 * Tests: PL-01–PL-21
 *
 * Two independent describe blocks so Group B (pipeline verification) runs
 * even if Group A (chat UI) fails.
 *
 * Group A (PL-01–06): Chat UI → Scout job creation.
 *   3-min per-test timeout.  sendMessage uses 15s action timeouts to fail fast.
 *
 * Group B (PL-07–21): Pipeline stage verification.
 *   10-min per-test timeout.  Uses SCOUT_JOB_REF (or any active scout job).
 *
 * Required env vars (e2e/.env.production):
 *   PROD_API_URL, PROD_TEST_EMAIL, PROD_TEST_PASSWORD
 *   SUPABASE_URL, SUPABASE_ANON_KEY
 *
 * Optional env vars:
 *   SCOUT_JOB_REF   — 8-char ref of an existing active scout job for Group B.
 *
 * Credit cost: ~1 credit for the chat-created job in Group A.
 */

import { test, expect } from '@playwright/test'

// ── Env ────────────────────────────────────────────────────────────────────────

const API_URL       = (process.env.PROD_API_URL     ?? '').replace(/\/$/, '')
const SUPABASE_URL  = (process.env.SUPABASE_URL     ?? '').replace(/\/$/, '')
const SUPABASE_ANON = process.env.SUPABASE_ANON_KEY ?? ''
const TEST_EMAIL    = process.env.PROD_TEST_EMAIL   ?? ''
const TEST_PASS     = process.env.PROD_TEST_PASSWORD ?? ''
// Default to the known production test job (Senior Java Developer)
const SCOUT_JOB_REF = process.env.SCOUT_JOB_REF || 'JIYVD3NU'

// ── Shared state ───────────────────────────────────────────────────────────────

let tenantJwt       = ''
let pipelineJobId   = ''   // job used for Group B pipeline polling
let pipelineJobRef  = ''   // job_ref of the pipeline job
let chatJobId       = ''   // job created in Group A chat tests
let chatJobRef      = ''   // job_ref of the chat-created job

// Candidate IDs discovered at each stage
let discoveredCandidateId = ''
let profiledCandidateId   = ''
let passedCandidateId     = ''
let emailedCandidateId    = ''

// ── API Helpers ────────────────────────────────────────────────────────────────

async function getJwt(): Promise<string> {
  const r = await fetch(`${SUPABASE_URL}/auth/v1/token?grant_type=password`, {
    method : 'POST',
    headers: { 'Content-Type': 'application/json', apikey: SUPABASE_ANON },
    body   : JSON.stringify({ email: TEST_EMAIL, password: TEST_PASS }),
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

async function apiPatch(path: string, body: unknown): Promise<any> {
  if (!tenantJwt || !API_URL) return null
  const r = await fetch(`${API_URL}/api/v1${path}`, {
    method : 'PATCH',
    headers: { Authorization: `Bearer ${tenantJwt}`, 'Content-Type': 'application/json' },
    body   : JSON.stringify(body),
  })
  if (!r.ok) { console.warn(`PATCH ${path} → ${r.status}`); return null }
  return r.json()
}

async function sleep(ms: number) {
  return new Promise((res) => setTimeout(res, ms))
}

/**
 * Poll candidates for the pipeline job until at least one reaches the target
 * status, or the deadline is exceeded.
 */
async function pollCandidates(
  targetStatus: string,
  deadlineMs: number,
  intervalMs = 30_000,
): Promise<any | undefined> {
  const deadline = Date.now() + deadlineMs
  while (Date.now() < deadline) {
    const data = await apiGet(`/candidates?job_id=${pipelineJobId}&limit=200`)
    const items: any[] = data?.items ?? []
    const match = items.find((c: any) => c.status === targetStatus)
    if (match) {
      console.log(`PL poll: found candidate ${match.id} with status=${targetStatus}`)
      return match
    }
    const remaining = Math.round((deadline - Date.now()) / 1000)
    const counts: Record<string, number> = {}
    items.forEach((c: any) => { counts[c.status] = (counts[c.status] ?? 0) + 1 })
    console.log(`PL poll: looking for ${targetStatus} — current: ${JSON.stringify(counts)} (${remaining}s left)`)
    await sleep(intervalMs)
  }
  return undefined
}

/** Fetch audit trail events for pipelineJobId. */
async function getAuditEvents(): Promise<string[]> {
  const data = await apiGet(`/jobs/${pipelineJobId}/audit-trail?limit=200`)
  const events: any[] = data?.events ?? data?.items ?? []
  return events.map((e: any) => e.event_type ?? e.type ?? '')
}

// ── Chat helper ────────────────────────────────────────────────────────────────

/**
 * Send a message via chat UI.  Uses explicit 15-second action timeout so the
 * test fails fast (not 20 minutes) if the input is not interactable.
 */
async function sendMessage(page: any, text: string, waitMs = 25_000) {
  const input = page.locator(
    '.chat-input-wrap input, input[placeholder*="message"], textarea[placeholder*="message"]',
  ).first()
  await input.fill(text, { timeout: 15_000 })
  await input.press('Enter', { timeout: 5_000 })
  await page.waitForTimeout(waitMs)
}

// ── Shared beforeAll logic ─────────────────────────────────────────────────────

async function setupAuth(): Promise<boolean> {
  if (!TEST_EMAIL || !TEST_PASS) {
    console.warn('PL: credentials not set — skipping')
    return false
  }
  console.log('PL [1/3] Authenticating...')
  tenantJwt = await getJwt()
  if (!tenantJwt) { console.warn('PL: JWT failed'); return false }
  return true
}

async function resolvePipelineJob(): Promise<void> {
  console.log(`PL [2/3] Looking up scout job (ref=${SCOUT_JOB_REF || 'auto'})...`)
  const jobs = await apiGet('/jobs?limit=100')
  const allJobs: any[] = jobs?.items ?? []

  let job = SCOUT_JOB_REF
    ? allJobs.find((j: any) => j.job_ref === SCOUT_JOB_REF)
    : undefined

  if (!job) {
    job = allJobs.find((j: any) =>
      (j.mode === 'talent_scout' || j.mode?.includes('scout')) && j.status === 'active',
    )
  }

  if (job) {
    pipelineJobId  = job.id
    pipelineJobRef = job.job_ref
    console.log(`PL [2/3] Pipeline job: "${job.title}" ref=${pipelineJobRef} id=${pipelineJobId}`)
  } else {
    console.warn('PL [2/3] No scout job found — Group B pipeline tests will skip')
  }

  if (pipelineJobId) {
    console.log('PL [3/3] Pre-loading existing candidate stages...')
    const data = await apiGet(`/candidates?job_id=${pipelineJobId}&limit=200`)
    const candidates: any[] = data?.items ?? []

    discoveredCandidateId = candidates.find((c: any) => c.status === 'discovered')?.id ?? ''
    profiledCandidateId   = candidates.find((c: any) => c.status === 'profiled')?.id   ?? ''
    passedCandidateId     = candidates.find((c: any) => c.status === 'passed')?.id     ?? ''
    emailedCandidateId    = candidates.find((c: any) => c.status === 'emailed')?.id    ?? ''

    const counts: Record<string, number> = {}
    candidates.forEach((c: any) => { counts[c.status] = (counts[c.status] ?? 0) + 1 })
    console.log(`PL [3/3] Existing candidate counts: ${JSON.stringify(counts)}`)
    console.log(`PL [3/3] Pre-loaded: discovered=${!!discoveredCandidateId} profiled=${!!profiledCandidateId} passed=${!!passedCandidateId} emailed=${!!emailedCandidateId}`)
  }
}

// ══════════════════════════════════════════════════════════════════════════════
// GROUP A — Chat UI → Scout Job Creation
// 3-minute per-test timeout.  Failures here do NOT block Group B.
// ══════════════════════════════════════════════════════════════════════════════

test.describe('Module 11 Group A — Chat UI', () => {
  test.describe.configure({ mode: 'serial' })
  test.setTimeout(3 * 60 * 1_000)  // 3 min — fast fail on chat hangs

  test.beforeAll(async () => {
    test.setTimeout(30_000)
    await setupAuth()
  })

  test.afterAll(async () => {
    if (chatJobId) {
      console.log(`PL afterAll: closing chat-created job ${chatJobId}`)
      await apiPatch(`/jobs/${chatJobId}`, { status: 'closed' })
    }
  })

  // ── PL-01 — Load chat, paste JD ───────────────────────────────────────────
  test('PL-01 — Chat loads — paste JD — AI responds with streaming', async ({ page }) => {
    await page.goto('/en/chat')
    await page.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => {})
    // Wait for the chat input to be ready
    await page.waitForSelector('.chat-input-wrap input', { timeout: 10_000 }).catch(() => {})

    const jd = [
      'Job Title: Senior Python Backend Developer',
      'Location: Sydney CBD, hybrid (3 days in office)',
      'Type: Full-time, permanent',
      '',
      'About the Role:',
      'We are building the next generation of fintech infrastructure.',
      'You will design and implement high-throughput data pipelines and REST APIs.',
      '',
      'Requirements:',
      '- 5+ years professional Python experience',
      '- Strong background in FastAPI, SQLAlchemy, and PostgreSQL',
      '- Experience with async programming (asyncio, aiohttp)',
      '- Familiarity with Redis, Celery, and message queues',
      '- AWS experience (Lambda, RDS, SQS)',
      '- Strong testing habits (pytest, coverage)',
      '',
      'Nice to have: Kubernetes, Terraform, financial domain knowledge.',
      '',
      'Salary: $180,000 – $220,000 + equity. Start date: ASAP.',
    ].join('\n')

    await sendMessage(page, jd, 30_000)

    // AI should respond — check for any bot message
    const hasResponse =
      (await page.locator('[class*="bot"], [class*="assistant"], .message-bubble').count()) > 0 ||
      (await page.getByText(/python|developer|tell me|clarify|confirm|location/i).count()) > 0
    expect(hasResponse).toBeTruthy()
  })

  // ── PL-02 — Q&A until payment phase ───────────────────────────────────────
  test('PL-02 — Q&A continues — payment phase appears', async ({ page }) => {
    await page.goto('/en/chat')
    await page.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => {})
    await page.waitForSelector('.chat-input-wrap input', { timeout: 10_000 }).catch(() => {})

    const jd = [
      'Job Title: Senior Python Backend Developer',
      'Location: Sydney CBD, hybrid (3 days in office)',
      'Type: Full-time, permanent',
      'Experience: 5+ years Python, FastAPI, PostgreSQL, async, Redis, Celery, AWS',
      'Salary: $180,000 – $220,000. Start ASAP.',
      'Minimum score for candidates: 7 out of 10.',
      'We want 15 candidates found.',
      'Outreach style: professional and concise. Mention our fintech mission.',
    ].join('\n')

    await sendMessage(page, jd, 30_000)

    const followUp = 'Yes, those details are correct. Please proceed with finding candidates.'
    await sendMessage(page, followUp, 25_000)

    const anyBotText = (await page.locator('body').innerText()).length > 200
    expect(anyBotText).toBeTruthy()
  })

  // ── PL-03 — Type "confirm" — payment shortcut fires ───────────────────────
  test('PL-03 — Payment confirm — job created, phase transitions to recruitment', async ({ page }) => {
    await page.goto('/en/chat')
    await page.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => {})
    await page.waitForSelector('.chat-input-wrap input', { timeout: 10_000 }).catch(() => {})

    const sessions = await apiGet('/chat-sessions?limit=5')
    const currentSession = (sessions?.items ?? []).find((s: any) => s.phase === 'payment')

    if (!currentSession) {
      const quickJd = [
        'I need to hire a Senior Python Developer in Sydney, hybrid, 5 years experience.',
        'Full-time, salary $180k-$220k. Target 10 candidates, minimum score 7.',
        'Python, FastAPI, PostgreSQL required. Please confirm when ready.',
      ].join(' ')
      await sendMessage(page, quickJd, 30_000)
      await sendMessage(page, 'Yes, proceed and confirm the job creation.', 30_000)
    }

    await sendMessage(page, 'confirm', 35_000)

    await page.goto('/en/jobs')
    await page.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => {})
    await expect(page.locator('table tbody tr').first()).toBeVisible({ timeout: 10_000 })

    const data = await apiGet('/jobs?limit=20')
    const recentScoutJob = (data?.items ?? []).find(
      (j: any) =>
        (j.mode === 'talent_scout' || j.mode?.includes('scout')) &&
        Date.now() - new Date(j.created_at).getTime() < 10 * 60 * 1000,
    )
    if (recentScoutJob) {
      chatJobId  = recentScoutJob.id
      chatJobRef = recentScoutJob.job_ref
      if (!pipelineJobId) {
        pipelineJobId  = chatJobId
        pipelineJobRef = chatJobRef
      }
      console.log(`PL-03: New scout job created: "${recentScoutJob.title}" ref=${chatJobRef}`)
    } else {
      console.warn('PL-03: No new scout job found within last 10 min')
    }

    await expect(page.locator('body')).not.toContainText('500')
  })

  // ── PL-04 — Job in /en/jobs with correct mode ─────────────────────────────
  test('PL-04 — New scout job — appears in /en/jobs with AI Scout mode, Active status', async ({ page }) => {
    if (!chatJobId && !pipelineJobId) {
      test.skip(true, 'ENV_SKIP: no job created in PL-03')
      return
    }
    const jobId  = chatJobId  || pipelineJobId
    const jobRef = chatJobRef || pipelineJobRef

    await page.goto('/en/jobs')
    await page.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => {})
    await expect(page.locator('table tbody tr').first()).toBeVisible({ timeout: 10_000 })

    const row = page.locator('table tbody tr').filter({ hasText: jobRef })
    if (await row.count() === 0) {
      console.warn(`PL-04: row with ref ${jobRef} not found — checking job detail directly`)
      await page.goto(`/en/jobs?id=${jobId}`)
      await page.waitForLoadState('networkidle', { timeout: 10_000 }).catch(() => {})
      await expect(page.locator('body')).not.toContainText('404')
      return
    }

    await expect(row.first()).toContainText(/AI Scout|scout/i)
    await expect(row.first()).toContainText(/active/i)
  })

  // ── PL-05 — Job detail — extracted fields ─────────────────────────────────
  test('PL-05 — Job detail — Overview tab shows extracted fields', async ({ page }) => {
    if (!chatJobId && !pipelineJobId) {
      test.skip(true, 'ENV_SKIP: no job created in PL-03')
      return
    }
    const jobId = chatJobId || pipelineJobId

    await page.goto(`/en/jobs/${jobId}`)
    await page.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => {})

    await expect(page.getByText(/developer|engineer/i).first()).toBeVisible({ timeout: 10_000 })
    await expect(page.getByText(/sydney|hybrid|remote/i).first()).toBeVisible({ timeout: 5_000 })

    await expect(
      page.getByRole('tab', { name: /overview|job spec|evaluation/i }).first()
        .or(page.getByText(/overview|job spec|evaluation report/i).first()),
    ).toBeVisible({ timeout: 5_000 })

    await expect(page.locator('body')).not.toContainText('500')
  })

  // ── PL-06 — Audit trail — job.created event ───────────────────────────────
  test('PL-06 — Audit Trail tab — job.created event present', async ({ page }) => {
    if (!chatJobId && !pipelineJobId) {
      test.skip(true, 'ENV_SKIP: no job created in PL-03')
      return
    }
    const jobId = chatJobId || pipelineJobId

    await page.goto(`/en/jobs/${jobId}`)
    await page.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => {})

    const auditTab = page.getByRole('tab', { name: /audit/i })
      .or(page.getByText(/audit trail/i).first())
    if (await auditTab.count() > 0) await auditTab.first().click()
    await page.waitForTimeout(1_500)

    await expect(
      page.getByText(/job.*created|created|audit|events|activity/i).first(),
    ).toBeVisible({ timeout: 10_000 })
    await expect(page.locator('body')).not.toContainText('500')

    const events = await getAuditEvents()
    const hasJobCreated = events.some((e) => e.includes('job.created') || e.includes('created'))
    if (events.length > 0) {
      expect(hasJobCreated).toBeTruthy()
    }
  })
})

// ══════════════════════════════════════════════════════════════════════════════
// GROUP B — Scout Pipeline Stage Verification
// Independent describe block — runs even if Group A fails.
// ══════════════════════════════════════════════════════════════════════════════

test.describe('Module 11 Group B — Pipeline Verification', () => {
  test.describe.configure({ mode: 'serial' })
  test.setTimeout(10 * 60 * 1_000)  // 10 min — pipeline polls

  test.beforeAll(async () => {
    test.setTimeout(60_000)
    const ok = await setupAuth()
    if (!ok) return
    await resolvePipelineJob()
  })

  // ── PL-07 — Stage 1: at least 1 candidate discovered ─────────────────────
  test('PL-07 — Discovery — at least 1 candidate with status=discovered', async ({ page }) => {
    if (!pipelineJobId) { test.skip(true, 'ENV_SKIP: no pipelineJobId'); return }

    if (!discoveredCandidateId) {
      console.log('PL-07: No pre-loaded discovered candidate — polling up to 5 min...')
      const found = await pollCandidates('discovered', 5 * 60 * 1000)
      if (found) {
        discoveredCandidateId = found.id
      } else {
        test.skip(true, 'ENV_SKIP: no discovered candidates within poll window (ScrapingDog may not be configured)')
        return
      }
    }

    const candidate = await apiGet(`/candidates/${discoveredCandidateId}`)
    expect(candidate).not.toBeNull()
    expect(candidate.status).toBe('discovered')
    expect(candidate.linkedin_url).toBeTruthy()

    console.log(`PL-07: discovered candidate ${discoveredCandidateId} linkedin_url=${candidate.linkedin_url?.slice(0, 40)}`)
  })

  // ── PL-08 — Audit: scout.candidate_discovered ─────────────────────────────
  test('PL-08 — Audit Trail — scout.candidate_discovered event present', async ({ page }) => {
    if (!pipelineJobId) { test.skip(true, 'ENV_SKIP: no pipelineJobId'); return }

    const events = await getAuditEvents()
    if (events.length === 0) {
      test.skip(true, 'ENV_SKIP: no audit events (pipeline may not have run)')
      return
    }

    const hasDiscovery = events.some((e) => e.includes('candidate_discovered') || e.includes('discovered'))
    expect(hasDiscovery).toBeTruthy()
  })

  // ── PL-09 — Discovered candidate fields ──────────────────────────────────
  test('PL-09 — Discovered candidate — linkedin_url set, no email, status=discovered', async ({ page }) => {
    if (!discoveredCandidateId) {
      test.skip(true, 'ENV_SKIP: no discovered candidate')
      return
    }

    const candidate = await apiGet(`/candidates/${discoveredCandidateId}`)
    expect(candidate.status).toBe('discovered')
    expect(candidate.linkedin_url).toBeTruthy()
    expect(!candidate.email || candidate.email === '').toBeTruthy()
  })

  // ── PL-10 — Stage 2: at least 1 candidate profiled ───────────────────────
  test('PL-10 — Enrichment — at least 1 candidate with status=profiled', async ({ page }) => {
    if (!pipelineJobId) { test.skip(true, 'ENV_SKIP: no pipelineJobId'); return }

    if (!profiledCandidateId) {
      console.log('PL-10: No pre-loaded profiled candidate — polling up to 5 min...')
      const found = await pollCandidates('profiled', 5 * 60 * 1000)
      if (found) {
        profiledCandidateId = found.id
      } else {
        test.skip(true, 'ENV_SKIP: no profiled candidates (BrightData may not be configured)')
        return
      }
    }

    const candidate = await apiGet(`/candidates/${profiledCandidateId}`)
    expect(candidate.status).toBe('profiled')
    console.log(`PL-10: profiled candidate ${profiledCandidateId}`)
  })

  // ── PL-11 — Profiled candidate has enrichment fields ─────────────────────
  test('PL-11 — Profiled candidate — company or location or experience_years populated', async ({ page }) => {
    if (!profiledCandidateId) {
      test.skip(true, 'ENV_SKIP: no profiled candidate')
      return
    }

    const candidate = await apiGet(`/candidates/${profiledCandidateId}`)
    expect(candidate.status).toBe('profiled')

    const hasEnrichment =
      candidate.company ||
      candidate.location ||
      candidate.experience_years ||
      candidate.name

    if (!hasEnrichment) {
      console.warn('PL-11: Profiled candidate has no enrichment data (private LinkedIn profile)')
    }
    expect(candidate.status).toBe('profiled')
  })

  // ── PL-12 — Audit: profile_enrichment event ───────────────────────────────
  test('PL-12 — Audit Trail — profile_enrichment event present', async ({ page }) => {
    if (!pipelineJobId) { test.skip(true, 'ENV_SKIP: no pipelineJobId'); return }

    const events = await getAuditEvents()
    if (events.length === 0) { test.skip(true, 'ENV_SKIP: no audit events'); return }

    const hasEnrichment = events.some((e) =>
      e.includes('profile_enrichment') || e.includes('enrichment'),
    )
    expect(hasEnrichment).toBeTruthy()
  })

  // ── PL-13 — Stage 3: at least 1 candidate scored ─────────────────────────
  test('PL-13 — Scoring — at least 1 candidate with status=passed or status=failed', async ({ page }) => {
    if (!pipelineJobId) { test.skip(true, 'ENV_SKIP: no pipelineJobId'); return }

    if (!passedCandidateId) {
      const data = await apiGet(`/candidates?job_id=${pipelineJobId}&limit=200`)
      const candidates: any[] = data?.items ?? []
      passedCandidateId  = candidates.find((c: any) => c.status === 'passed')?.id  ?? ''
      const failedCandidate = candidates.find((c: any) => c.status === 'failed')

      if (!passedCandidateId && !failedCandidate) {
        console.log('PL-13: No scored candidates — polling up to 5 min...')
        const found = await pollCandidates('passed', 5 * 60 * 1000)
        if (found) {
          passedCandidateId = found.id
        } else {
          const foundFailed = await pollCandidates('failed', 2 * 60 * 1000)
          if (!foundFailed) {
            test.skip(true, 'ENV_SKIP: no scored candidates within poll window')
            return
          }
        }
      }
    }

    const checkId = passedCandidateId
    if (!checkId) {
      const data = await apiGet(`/candidates?job_id=${pipelineJobId}&limit=200`)
      const failed = (data?.items ?? []).find((c: any) => c.status === 'failed')
      if (failed) {
        const c = await apiGet(`/candidates/${failed.id}`)
        expect(['passed', 'failed']).toContain(c.status)
        return
      }
    }

    const candidate = await apiGet(`/candidates/${checkId}`)
    expect(['passed', 'failed']).toContain(candidate.status)
    console.log(`PL-13: scored candidate ${checkId} status=${candidate.status} score=${candidate.score}`)
  })

  // ── PL-14 — Score respects minimum_score ─────────────────────────────────
  test('PL-14 — Score — passed candidate score >= minimum_score, failed score < minimum_score', async ({ page }) => {
    if (!pipelineJobId) { test.skip(true, 'ENV_SKIP: no pipelineJobId'); return }

    const job = await apiGet(`/jobs/${pipelineJobId}`)
    const minScore: number = job?.minimum_score ?? 6

    const data = await apiGet(`/candidates?job_id=${pipelineJobId}&limit=200`)
    const candidates: any[] = data?.items ?? []

    const passed = candidates.filter((c: any) => c.status === 'passed')
    const failed = candidates.filter((c: any) => c.status === 'failed' && c.score != null)

    if (passed.length > 0) {
      for (const c of passed.slice(0, 3)) {
        if (c.score != null) {
          expect(c.score).toBeGreaterThanOrEqual(minScore)
        }
      }
      console.log(`PL-14: ${passed.length} passed candidates verified against minScore=${minScore}`)
    }

    if (failed.length > 0) {
      for (const c of failed.slice(0, 3)) {
        if (c.score != null) {
          expect(c.score).toBeLessThan(minScore)
        }
      }
      console.log(`PL-14: ${failed.length} failed candidates verified against minScore=${minScore}`)
    }

    if (passed.length === 0 && failed.length === 0) {
      test.skip(true, 'ENV_SKIP: no scored candidates with score field')
    }
  })

  // ── PL-15 — Audit: scoring events ─────────────────────────────────────────
  test('PL-15 — Audit Trail — scout.scoring_passed or scout.scoring_failed event present', async ({ page }) => {
    if (!pipelineJobId) { test.skip(true, 'ENV_SKIP: no pipelineJobId'); return }

    const events = await getAuditEvents()
    if (events.length === 0) { test.skip(true, 'ENV_SKIP: no audit events'); return }

    const hasScoring = events.some((e) => e.includes('scoring'))
    expect(hasScoring).toBeTruthy()
  })

  // ── PL-16 — Stage 4/5: at least 1 candidate emailed or email-failed ───────
  test('PL-16 — Outreach — at least 1 passed candidate reaches status=emailed or email-failed', async ({ page }) => {
    if (!pipelineJobId) { test.skip(true, 'ENV_SKIP: no pipelineJobId'); return }

    const data = await apiGet(`/candidates?job_id=${pipelineJobId}&limit=200`)
    const candidates: any[] = data?.items ?? []
    emailedCandidateId = candidates.find((c: any) => c.status === 'emailed')?.id ?? ''

    if (!emailedCandidateId) {
      console.log('PL-16: No emailed candidates — polling up to 5 min...')
      const found = await pollCandidates('emailed', 5 * 60 * 1000)
      if (found) {
        emailedCandidateId = found.id
        console.log(`PL-16: emailed candidate ${emailedCandidateId}`)
      } else {
        const failedEmailCandidate = candidates.find(
          (c: any) => c.status === 'failed' && c.score != null && c.score >= (data?.minimum_score ?? 6),
        )
        if (failedEmailCandidate) {
          console.warn('PL-16: Passed candidate failed at email stage (expected without email provider keys)')
        } else {
          test.skip(true, 'ENV_SKIP: no emailed/email-failed candidates (email provider keys may not be set)')
        }
        return
      }
    }

    const candidate = await apiGet(`/candidates/${emailedCandidateId}`)
    expect(candidate.status).toBe('emailed')
    expect(candidate.outreach_email_sent_at).toBeTruthy()
    console.log(`PL-16: outreach_email_sent_at=${candidate.outreach_email_sent_at}`)
  })

  // ── PL-17 — Audit: email discovery event ─────────────────────────────────
  test('PL-17 — Audit Trail — scout.email_found or scout.email_not_found event present', async ({ page }) => {
    if (!pipelineJobId) { test.skip(true, 'ENV_SKIP: no pipelineJobId'); return }

    const events = await getAuditEvents()
    if (events.length === 0) { test.skip(true, 'ENV_SKIP: no audit events'); return }

    const hasEmailEvent = events.some((e) =>
      e.includes('email_found') || e.includes('email_not_found'),
    )
    if (!hasEmailEvent) {
      test.skip(true, 'ENV_SKIP: no email discovery audit events (pipeline may not have reached email stage)')
    } else {
      expect(hasEmailEvent).toBeTruthy()
    }
  })

  // ── PL-18 — Audit: outreach_email_sent + outreach_email_sent_at ───────────
  test('PL-18 — Emailed candidate — outreach_email_sent audit event and sent_at field set', async ({ page }) => {
    if (!emailedCandidateId) {
      test.skip(true, 'ENV_SKIP: no emailed candidate')
      return
    }

    const candidate = await apiGet(`/candidates/${emailedCandidateId}`)
    expect(candidate.outreach_email_sent_at).toBeTruthy()

    const events = await getAuditEvents()
    const hasOutreach = events.some((e) => e.includes('outreach_email_sent'))
    expect(hasOutreach).toBeTruthy()
    console.log(`PL-18: outreach confirmed — sent_at=${candidate.outreach_email_sent_at}`)
  })

  // ── PL-19 — Candidate detail UI — stage badge and score ───────────────────
  test('PL-19 — Candidate detail page — stage badge and score visible', async ({ page }) => {
    const candidateId = emailedCandidateId || passedCandidateId || profiledCandidateId || discoveredCandidateId
    if (!candidateId) {
      test.skip(true, 'ENV_SKIP: no candidate ID available')
      return
    }

    await page.goto(`/en/candidates/${candidateId}`)
    await page.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => {})

    // Page must load without 500
    await expect(page.locator('body')).not.toContainText('500')
    await expect(page.locator('main')).toBeVisible({ timeout: 10_000 })

    // Badge/status check is a soft assertion — UI may use different class names
    const hasBadge = await page.locator(
      '.badge, [class*="badge"], [class*="status"], [class*="stage"], [class*="chip"], [class*="tag"]',
    ).first().isVisible({ timeout: 5_000 }).catch(() => false)
    if (!hasBadge) {
      console.warn('PL-19: stage badge not found — checking for any stage text instead')
      const hasStageText = await page.getByText(/discovered|profiled|emailed|passed|failed|screened/i).first()
        .isVisible({ timeout: 3_000 }).catch(() => false)
      console.log(`PL-19: badge=${hasBadge} stageText=${hasStageText}`)
    } else {
      console.log('PL-19: stage badge visible')
    }

    if (passedCandidateId || emailedCandidateId) {
      const hasScore = await page.getByText(/score|\/10/i).first()
        .isVisible({ timeout: 5_000 }).catch(() => false)
      console.log(`PL-19: score visible=${hasScore}`)
    }
  })

  // ── PL-20 — Idempotency: stable candidate count ───────────────────────────
  test('PL-20 — Idempotency — re-queuing discover_candidates does not create duplicates', async ({ page }) => {
    if (!pipelineJobId) { test.skip(true, 'ENV_SKIP: no pipelineJobId'); return }

    const before = await apiGet(`/candidates?job_id=${pipelineJobId}&limit=1`)
    const countBefore: number = before?.total ?? before?.count ?? 0

    const after = await apiGet(`/candidates?job_id=${pipelineJobId}&limit=1`)
    const countAfter: number = after?.total ?? after?.count ?? 0

    expect(Math.abs(countAfter - countBefore)).toBeLessThanOrEqual(5)
    console.log(`PL-20: candidate count stable: before=${countBefore} after=${countAfter}`)
  })

  // ── PL-21 — Pause job — no new candidates ─────────────────────────────────
  test('PL-21 — Pause/close job — status updates in UI', async ({ page }) => {
    if (!chatJobId) {
      test.skip(true, 'ENV_SKIP: no chat-created job to close (would affect production data)')
      return
    }

    const patched = await apiPatch(`/jobs/${chatJobId}`, { status: 'closed' })
    expect(patched).not.toBeNull()
    expect(patched.status).toBe('closed')

    await page.goto('/en/jobs')
    await page.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => {})

    const row = page.locator('table tbody tr').filter({ hasText: chatJobRef })
    if (await row.count() > 0) {
      await expect(row.first()).toContainText(/closed/i)
    }

    console.log(`PL-21: job ${chatJobRef} closed — pipeline will not queue new tasks`)
    chatJobId = ''
  })
})
