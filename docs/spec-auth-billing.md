# Spec §3–4: Authentication, Roles & Billing

*Full spec index: see [spec.md](spec.md)*

---

## 3. Authentication & User Roles

Authentication via Supabase Auth. On sign-up, tenant record created and user assigned `admin` role. One person can hold multiple roles simultaneously (admin + recruiter + hiring_manager for small firms).

### 3.1 Roles

| Role | Description |
|---|---|
| super_admin | Platform owner — view all tenants, manage platform API keys, billing, impersonate. Separate /super-admin route. |
| admin | Firm owner — full access to their tenant |
| recruiter | Can manage jobs, view reports, trigger searches. May also hold hiring_manager role. |
| hiring_manager | Receives daily summaries, approves interview invitations via email link. No dashboard login required. |

### 3.2 Self-Serve Sign-Up Flow

1. User selects plan on airecruiterz.com pricing page
2. Stripe Checkout completes
3. Webhook fires to `/webhooks/stripe` — tenant created, plan activated
4. Welcome email with magic link to set password
5. Onboarding wizard: firm name, phone, address, contact details, email inbox prefix, website URL, API keys
6. Background task scrapes website for RAG if website_url provided
7. GDPR DPA prompt — must accept before candidate search features activate

---

## 4. Stripe Billing & Plans

### 4.1 Plan Structure

| Plan | Price AUD/mo | Jobs | Candidates/Job | Modules |
|---|---|---|---|---|
| Trial | $0 (14-day) | 3 | 10 | Screener + Scout |
| Trial Expired | — | 0 | 0 | Locked — subscribe to continue |
| Recruiter | $499/mo | 5 | 20 | Screener + Scout |
| Agency Small | $999/mo | 20 | 40 | Screener + Scout + Chat Widget |
| Agency Medium | $2,999/mo | 75 | 60 | All features + priority support |
| Enterprise | Custom | Unlimited | Unlimited | All + SLA + custom onboarding |

### 4.2 Promo Codes

Stored in `promo_codes` table. Can grant: fixed credits, percentage discount, or full plan access for N days. Validated at AI Recruiter chat payment step.

### 4.3 Stripe Webhooks

- `checkout.session.completed` → activate subscription, create tenant
- `invoice.payment_succeeded` → renew monthly credits
- `invoice.payment_failed` → flag tenant, send warning email
- `customer.subscription.deleted` → downgrade to free
