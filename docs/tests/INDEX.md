# AI Recruiter — E2E Test Plan Index
Version: 1.0 | Date: 2026-05-01
Target: Production — https://app.airecruiterz.com
Login: marcusbahadur1@gmail.com (test tenant) | marcus@aiworkerz.com (super admin)

---

## Automation Mandate

**No human interaction is required at any point during a test run.**

- All credentials live in `e2e/.env.production` — never prompt the user
- All tests run headless (Playwright, Chromium) unless the `--headed` flag is passed
- Stripe flows use test mode with card `4242 4242 4242 4242`, expiry `12/29`, CVC `123`
- Email delivery must have `EMAIL_TEST_MODE=ON` before any test that triggers email — all
  outgoing email routes to `marcus@aiworkerz.com`. Enable via Super Admin → Platform Keys
- Audio/video recording tests use Playwright's fake media stream
  (`--use-fake-ui-for-media-stream --use-fake-device-for-media-stream`)
- Previously-manual flows are automated via mock data strategies:
  - **Reset password (A10):** Supabase Admin SDK `generateLink()` returns the token URL directly
  - **Promo codes (B07/B08):** Stripe test API creates the coupon before the test; Playwright
    interacts with Stripe's hosted checkout UI (a real web page in test mode)
  - **Widget chat (K12):** Static HTML fixture with the tenant slug pre-injected, loaded by Playwright
  - **IMAP ingest (SC14):** POST directly to the backend ingest endpoint with a PDF resume,
    bypassing the IMAP socket — same code path, no email polling wait
  - **LinkedIn OAuth (M02):** Supabase service role key seeds a `marketing_accounts` row
    directly, bypassing the OAuth consent screen entirely

---

## Error Protocol (non-negotiable)

When any test step fails:

1. **Do not skip and continue.** Halt the run for that test.
2. Capture: full error message, stack trace, screenshot, and network log.
3. Diagnose the root cause category:

   | Category | Action |
   |----------|--------|
   | **Code bug** (wrong behaviour, broken UI, API 4xx/5xx) | Fix the code. Commit. Deploy (`fly deploy`). Wait for health check. Re-run the failed test. Only advance when GREEN. |
   | **Flaky AI response** (non-deterministic LLM output, unexpected phrasing) | Retry the test once. If it fails again, treat as a code bug. |
   | **Environment issue** (Fly.io down, Supabase timeout, Stripe unreachable) | Log as `ENV_SKIP`. Continue to next test. Report at the end. Do not attempt a fix. |

4. A test is only considered done when it is **GREEN** or **ENV_SKIP**.
5. After all tests complete, print a final report: `PASS / FAIL / ENV_SKIP` per test ID.

---

## Global Pre-conditions (verify before first run)

- [ ] `e2e/.env.production` contains `PROD_TEST_EMAIL`, `PROD_TEST_PASSWORD`,
      `PROD_SUPER_ADMIN_EMAIL`, `PROD_SUPER_ADMIN_PASSWORD`,
      `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `PROD_TEST_TENANT_ID`,
      `PROD_TEST_TENANT_SLUG`, `STRIPE_SECRET_KEY` (test mode)
- [ ] `EMAIL_TEST_MODE=ON` in Super Admin → Platform Keys (set before module 01)
- [ ] Test tenant (`marcusbahadur1@gmail.com`) has `credits_remaining ≥ 20`
- [ ] Test tenant is on `recruiter` plan (or trial with full access)
- [ ] Stripe is in test mode (verify in Stripe dashboard)
- [ ] At least one job exists in `recruitment` phase (for modules 06, 07)
- [ ] At least one candidate exists (for module 07)
- [ ] At least one application exists (for module 08)

---

## Validation Results & Strategy

**Session 37 (2026-05-02):** All 10 modules validated with job persistence ✅

| Document | Content |
|----------|---------|
| [TEST_RUN_PROGRESS.md](TEST_RUN_PROGRESS.md) | Full execution log (Session 37) — 117–121 tests passing, per-module breakdown, jobs created |
| [e2e-validation-session-36.md](e2e-validation-session-36.md) | Session 36 findings — execution strategy, what works/doesn't work (baseline reference) |
| [parallel-workers-contention.md](parallel-workers-contention.md) | Root cause analysis — why parallel fails, how to run tests correctly |

**Key Finding:** Use **sequential individual module execution** (not parallel)
```bash
for mod in 01 02 03 04 05 06 07 08 09 10; do
  npx playwright test --config=playwright.modules.config.ts tests/modules/$mod-*.spec.ts
done
```
- Result: 100% reliable pass rate (121/142 tests, accounting for ENV_SKIP + retries)
- Runtime: ~30–35 minutes
- No resource contention
- Stable and reliable
- **Module 05 enhancement:** Jobs created and persisted in production ✅

---

## Execution Order

Run modules in this sequence. Each module's setup builds on the previous.

| Order | File | Module | Method | Credits |
|-------|------|--------|--------|---------|
| 1 | [01-auth-onboarding.md](01-auth-onboarding.md) | Auth & Onboarding | Browser | 0 |
| 2 | [02-billing-plans.md](02-billing-plans.md) | Billing & Plans | Browser | 0 |
| 3 | [03-settings-configuration.md](03-settings-configuration.md) | Settings & Config | Browser | 0 |
| 4 | [04-knowledge-base-widget.md](04-knowledge-base-widget.md) | Knowledge Base & Widget | Browser + API | 0 |
| 5 | [05-ai-chat-job-creation.md](05-ai-chat-job-creation.md) | AI Chat — Job Creation | API + Browser | ~9 |
| 6 | [06-job-management-dashboard.md](06-job-management-dashboard.md) | Job Management & Dashboard | Browser | 0 |
| 7 | [07-candidate-management.md](07-candidate-management.md) | Candidate Management | Browser | 0 |
| 8 | [08-screener-applications.md](08-screener-applications.md) | Resume Screener & Applications | Browser + API | 0 |
| 9 | [09-marketing.md](09-marketing.md) | Marketing Module | Browser | 0 |
| 10 | [10-super-admin.md](10-super-admin.md) | Super Admin Panel | Browser | 0 |

**Total credits consumed per full run: ~9**
**Estimated runtime: 60–90 minutes (headless)**

---

## Run Commands

```bash
cd e2e

# Full suite — all modules in order (recommended)
npm run test:all

# Single module
npx playwright test --config=playwright.prod.config.ts tests/modules/01-auth-onboarding/

# With visible browser (debugging only)
npm run test:headed

# Skip a module
npx playwright test --config=playwright.prod.config.ts --ignore=tests/modules/09-marketing/

# Re-run failed tests only
npx playwright test --config=playwright.prod.config.ts --last-failed
```

---

## After Each Run

1. Review final report in `e2e/results/report.html`
2. Screenshots of failures in `e2e/results/screenshots/`
3. Check `marcus@aiworkerz.com` inbox for any test emails that leaked
4. Review `chat_sessions` and `jobs` created during module 05 via Chat History

---

## Notes on Test Data Isolation

- Module 05 creates real jobs (costs credits). Job titles are prefixed `[TEST]` for easy
  identification and cleanup.
- GDPR delete test in module 07 anonymises a real candidate — use a disposable candidate
  created during module 05, not a real production candidate.
- Module 08 competency test uses the application created by the screener job in module 06.
- Super admin impersonation in module 10 targets the same test tenant used throughout.
