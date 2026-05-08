# Billing Domain

Stripe checkout, webhook handling, credits, promo codes, plan limits.

---

## Plans

| Plan | Credits/month | Jobs | Candidates/job |
|------|--------------|------|----------------|
| trial | 3 (one-time) | 1 | 20 |
| recruiter | 10 | 5 | 50 |
| agency_small | 30 | 15 | 100 |
| agency_medium | 100 | 50 | 200 |
| enterprise | 500 | unlimited | 200 |

(Verify actual values in `config.py::PLAN_LIMITS`)

## Checkout Flow

```
POST /api/v1/billing/create-checkout {plan}
  → stripe.checkout.Session.create(
      price_id = PLAN_PRICE_IDS[plan],
      metadata = {plan, tenant_id}
    )
  → return {session_id}
  → Frontend redirects to stripe.com/pay/{session_id}
```

**Test mode price IDs** (from dev-setup.md):
- Recruiter: `price_1TKTz6A5SiOfWjX1qr86cpx6`
- Agency Small: `price_1TKTzlA5SiOfWjX1l9f6GkTE`
- Agency Medium: `price_1TKU0PA5SiOfWjX18ycn5bTL`

## Webhook Events

**Must verify**: `stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)` — raises `ValueError` if signature invalid.

| Event | Action |
|-------|--------|
| `checkout.session.completed` | Set plan, add credits, set stripe_customer_id + subscription_id |
| `invoice.payment_succeeded` | Add monthly credits, extend subscription_ends_at |
| `invoice.payment_failed` | Send warning email |
| `customer.subscription.updated` | Update plan if changed |
| `customer.subscription.deleted` | Downgrade to free |

**Warning**: No event deduplication by `event.id` — Stripe retried webhooks could double-credit. See FRAGILE_ZONES.md F7.

## Credit System

- `tenant.credits_remaining`: integer, decremented by 1 per job created
- Credits added at checkout completion and monthly renewal
- No partial refund on job deletion
- Promo codes add credits directly: `UPDATE tenant SET credits_remaining += discount_amount`

## Promo Code Model

```
PromoCode:
  code: str (unique, case-insensitive lookup)
  is_active: bool
  discount_amount: int (credits to add)
  max_uses: int
  uses_remaining: int
  created_at
```

**Missing**: No `expires_at` field. Disable via `is_active=false`. See FRAGILE_ZONES.md F8.

## Billing Portal

`GET /api/v1/billing/portal` → Stripe customer portal URL → manage payment methods, view invoices.
