# Module 01 — Auth & Onboarding Test Plan
Version: 1.0 | Date: 2026-05-01
Target: https://app.airecruiterz.com
Automation: Full

---

## Scope

Sign-up, plan selection (Stripe checkout), billing success, Quick Start wizard,
login, logout, forgot password, reset password.

## Pre-conditions

- A fresh throw-away email address for sign-up tests (generated per run via a
  random alias or Mailosaur/similar inbox API)
- Stripe in test mode; card `4242 4242 4242 4242`, expiry `12/29`, CVC `123`
- `EMAIL_TEST_MODE=ON` (all system emails → marcus@aiworkerz.com)

---

## Test Scenarios

| ID   | Name | Automated |
|------|------|-----------|
| A01  | Sign up — new account created | Yes |
| A02  | Subscribe page — select plan, Stripe checkout, billing success | Yes |
| A03  | Quick Start wizard — all steps, progress bar, completion state | Yes |
| A04  | Login — valid credentials → dashboard | Yes |
| A05  | Login — wrong password → error banner | Yes |
| A06  | Login — non-existent email → error banner | Yes |
| A07  | Logout — session cleared, redirect to /login | Yes |
| A08  | Forgot password — sends email, shows success state | Yes |
| A09  | Reset password — invalid/expired token → error state + re-request link | Yes |
| A10  | Reset password — valid token → set new password → login succeeds | Yes |

---

## Scenario Detail

### A01 — Sign Up
1. Navigate to `/en/signup`
2. Fill: Firm Name (random), Email (unique test alias), Password (`Test1234!`), Confirm Password
3. Click "Start free trial"
4. Verify: redirect to `/en` (dashboard) or email verification screen
5. If verification required: check inbox (EMAIL_TEST_MODE), click confirm link, verify dashboard loads

**Assertions:**
- No error banner visible
- Supabase session cookie set (check `sb-*` cookie in browser storage)
- Tenant row exists: `GET /api/v1/settings` returns 200 with the new firm name

### A02 — Subscribe Page (Stripe)
1. Navigate to `/en/subscribe`
2. Verify: 3 plan cards render (Recruiter, Agency Small, Agency Medium)
3. Verify: "MOST POPULAR" badge on Agency Small
4. Click "Get Started" on Recruiter plan
5. Verify: Stripe Checkout redirects (URL contains `checkout.stripe.com`)
6. Fill Stripe test card details (`4242 4242 4242 4242`, `12/29`, `123`)
7. Submit payment
8. Verify: redirect to `/en/billing/success`
9. Verify: success page renders (no 404/500)
10. Verify: `GET /api/v1/billing/status` returns plan = `recruiter`

**Assertions:**
- Each plan card "Get Started" button fires `billingApi.createCheckoutSession(plan)`
- No JS errors in console during checkout redirect

### A03 — Quick Start Wizard
1. Navigate to `/en/quickstart`
2. Verify: page title "Quick Start" + progress bar renders
3. Verify: steps list shows ≥ 4 steps with numbered circles
4. For each incomplete step: verify "Go →" button is present and navigates correctly
5. Complete step (e.g., navigate to Settings → General → save)
6. Return to `/en/quickstart`, click "↻ Refresh status"
7. Verify: completed step shows green checkmark
8. When all steps done: verify "🎉 You're all set!" title + "Go to Dashboard →" button
9. Click "Go to Dashboard →" → verify redirect to `/en`

**Assertions:**
- `tenantApi.getQuickStartStatus()` called on load and on refresh click
- Progress bar percentage matches steps completed / total

### A04 — Login Valid
1. Navigate to `/en/login`
2. Fill email + password (test tenant credentials from `.env.production`)
3. Click "Sign in"
4. Verify: redirect to `/en` (dashboard loads)
5. Verify: no error banner

### A05 — Login Wrong Password
1. Navigate to `/en/login`
2. Fill valid email, wrong password (`WrongPass999!`)
3. Click "Sign in"
4. Verify: red error banner appears with a message
5. Verify: still on `/en/login`
6. Verify: "Sign in" button re-enabled (not stuck in loading)

### A06 — Login Non-existent Email
1. Navigate to `/en/login`
2. Fill `nobody@doesnotexist.invalid`, any password
3. Click "Sign in"
4. Verify: red error banner appears
5. Verify: still on `/en/login`

### A07 — Logout
1. Login as test tenant
2. Locate user/logout control (nav bar or user menu)
3. Click logout
4. Verify: redirect to `/en/login`
5. Attempt to navigate to `/en` directly
6. Verify: redirected back to `/en/login` (not dashboard)
7. Verify: `sb-*` session cookie cleared

### A08 — Forgot Password
1. Navigate to `/en/forgot-password`
2. Fill the test tenant email
3. Click "Send reset link"
4. Verify: loading state "Sending..." appears
5. Verify: success state shows "Check your email" message
6. Verify: EMAIL_TEST_MODE routes the reset email to `marcus@aiworkerz.com`

### A09 — Reset Password Invalid Token
1. Navigate to `/en/reset-password` with a fake/expired token in the URL hash
2. Verify: "Verifying link..." loading state appears briefly
3. Verify: error state renders: "This reset link is invalid or has expired"
4. Verify: "Request a new reset link" link is present and navigates to `/en/forgot-password`

### A10 — Reset Password Valid
Mock approach: Supabase Admin SDK `generateLink()` returns the reset URL directly without
sending an email. No inbox interaction required.

Pre-condition: `SUPABASE_SERVICE_ROLE_KEY` available in `e2e/.env.production`.

```js
// Test helper — called before navigating
const { data } = await supabase.auth.admin.generateLink({
  type: 'recovery',
  email: PROD_TEST_EMAIL,
  options: { redirectTo: 'https://app.airecruiterz.com/en/reset-password' }
})
const resetUrl = data.properties.action_link
```

Steps:
1. Call the helper above to generate the reset link programmatically
2. Navigate Playwright directly to `resetUrl`
3. Verify: "Verifying link..." loading state appears, then the password form loads
4. Fill: New password (`NewTest1234!`), Confirm password
5. Click "Set new password"
6. Verify: success message + redirect to `/en?reset=1`
7. Log out
8. Log in with `NewTest1234!` — verify dashboard loads
9. Reset password back to original using the same generateLink helper

---

## Verification Matrix

| ID  | Key Assertion |
|-----|---------------|
| A01 | Supabase session exists + tenant row created |
| A02 | Stripe checkout reached + billing/success renders + plan updated in API |
| A03 | All steps complete → completion state shown |
| A04 | Dashboard loads, no errors |
| A05 | Error banner visible, button re-enabled |
| A06 | Error banner visible |
| A07 | Cookie cleared, `/en` redirects to login |
| A08 | Success state shown (no server error) |
| A09 | Invalid token error + re-request link present |
| A10 | generateLink() produces token → password form loads → new password accepted → login succeeds |
