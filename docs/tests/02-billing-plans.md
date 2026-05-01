# Module 02 — Billing & Plans Test Plan
Version: 1.0 | Date: 2026-05-01
Target: https://app.airecruiterz.com
Automation: Full

---

## Scope

Billing page UI, plan display, credits counter, trial banners, Stripe customer portal,
plan comparison table, promo code application and rejection.

## Pre-conditions

- Logged in as test tenant (`marcusbahadur1@gmail.com`)
- Tenant is on `recruiter` plan (or trial for banner tests)
- Stripe in test mode

---

## Test Scenarios

| ID   | Name | Automated |
|------|------|-----------|
| B01  | Billing page loads — plan name, price, credits display | Yes |
| B02  | Plan comparison table — all 4 plans + current plan highlighted | Yes |
| B03  | Credits display — progress bar + remaining count | Yes |
| B04  | Trial countdown banner — visible, days remaining correct | Yes |
| B05  | Trial expired banner — shown when trial past end date | Yes |
| B06  | Manage Billing button → Stripe portal redirect | Yes |
| B07  | Promo code — valid code reduces displayed credit or price | Yes |
| B08  | Promo code — invalid code shows error | Yes |
| B09  | Renewal date — displayed when on paid plan | Yes |
| B10  | "View Plans" button → /subscribe (for trial tenants) | Yes |

---

## Scenario Detail

### B01 — Billing Page Loads
1. Navigate to `/en/billing`
2. Verify: page title "Billing" renders
3. Verify: current plan card shows plan name (non-empty)
4. Verify: price is displayed (e.g., "$499/mo")
5. Verify: no spinner stuck loading (page settles within 5s)

**Assertions:**
- `GET /api/v1/billing/status` returns 200
- Plan name on page matches API response `plan` field

### B02 — Plan Comparison Table
1. Navigate to `/en/billing`
2. Scroll to plan comparison table
3. Verify: table header has columns: Plan | Price | Jobs/mo | Candidates/job | Resumes/mo
4. Verify: 4 rows present (Recruiter, Agency Small, Agency Medium, Enterprise)
5. Verify: current plan row has cyan background + "Current" badge
6. Verify: non-current rows do NOT have "Current" badge

### B03 — Credits Display
1. Navigate to `/en/billing`
2. Verify: "Talent Scout Credits" section is visible
3. Verify: remaining credit count is a non-negative integer
4. Verify: progress bar renders (fill percentage ≤ 100%)
5. Cross-check: count matches `GET /api/v1/billing/status` → `credits_remaining`

### B04 — Trial Countdown Banner
Pre-condition: Use a tenant account that is in trial and has days remaining.
1. Navigate to `/en/billing` or any dashboard page
2. Verify: blue banner "⏰ X days remaining in your free trial. Subscribe now →" is visible
3. Verify: "Subscribe now →" link navigates to `/en/subscribe`
4. Verify: day count is a positive integer

### B05 — Trial Expired Banner
Pre-condition: Use a tenant whose trial end date has passed (set up via super admin or DB).
1. Navigate to `/en/billing`
2. Verify: red banner "Your free trial has ended. Subscribe to regain access →" is visible
3. Verify: CTA link navigates to `/en/subscribe`
4. Note: This may require a dedicated expired-trial test tenant to avoid breaking the main test account.

### B06 — Manage Billing → Stripe Portal
1. Navigate to `/en/billing`
2. Click "Manage Billing" button
3. Verify: `billingApi.getPortal()` is called (intercept network request)
4. Verify: browser navigates to a URL containing `billing.stripe.com`
5. Verify: no error message appears before redirect

**Assertions:**
- Network request to `/api/v1/billing/portal` returns 200 with a `url` field
- No console errors before redirect

### B07 — Promo Code Valid
Mock approach: Create the promo code via Stripe test API before the test runs. Playwright
then enters the code in the Stripe hosted checkout UI (a real web page in test mode).

```js
// Test setup helper — runs before B07
const coupon = await stripe.coupons.create({ percent_off: 20, duration: 'once' })
const promo = await stripe.promotionCodes.create({
  coupon: coupon.id,
  code: 'TESTPROMO20'
})
```

Steps:
1. Navigate to `/en/subscribe`, click "Get Started" on any plan
2. Verify: Stripe Checkout page loads (`checkout.stripe.com`)
3. Locate promo code / coupon code field in Stripe checkout UI
4. Enter `TESTPROMO20`
5. Verify: discount is applied (price display updates, e.g. "20% off")
6. Complete checkout with test card `4242 4242 4242 4242`
7. Verify: redirect to `/en/billing/success`
8. Clean up: deactivate the promo code via Stripe API after test

**Assertions:**
- Stripe checkout shows discount line item
- `GET /api/v1/billing/status` confirms subscription active

### B08 — Promo Code Invalid
Playwright enters an invalid code directly in Stripe's hosted checkout UI. No mock required.

Steps:
1. Navigate to `/en/subscribe`, click "Get Started"
2. On Stripe Checkout page, locate the promo code field
3. Enter `BADCODE999` (random invalid string)
4. Submit / apply the code
5. Verify: Stripe shows an error message (e.g., "This code is not valid")
6. Verify: checkout is NOT completed (user is still on the checkout page)
7. Verify: original price is unchanged (no discount applied)

### B09 — Renewal Date Display
1. Navigate to `/en/billing`
2. Verify: "Next renewal:" label + date string is visible (for paid plan tenants)
3. Verify: date format is human-readable (e.g., "1 June 2026")
4. Cross-check: date matches what Stripe reports for the subscription

### B10 — View Plans (Trial)
Pre-condition: Tenant on trial.
1. Navigate to `/en/billing`
2. Verify: "View Plans" button is visible (not "Manage Billing")
3. Click "View Plans"
4. Verify: navigates to `/en/subscribe`

---

## Verification Matrix

| ID  | Key Assertion |
|-----|---------------|
| B01 | Plan card renders with real plan name from API |
| B02 | 4-row comparison table, current plan highlighted in cyan |
| B03 | Credits count matches API, progress bar ≤ 100% |
| B04 | Trial banner visible with correct day count + link |
| B05 | Expired banner visible + CTA link |
| B06 | Stripe portal URL reached via `billingApi.getPortal()` |
| B07 | Stripe API creates promo code → Stripe UI shows discount → checkout succeeds |
| B08 | Invalid code entered in Stripe UI → error shown, price unchanged |
| B09 | Renewal date visible for paid tenant |
| B10 | "View Plans" → /subscribe for trial tenant |
