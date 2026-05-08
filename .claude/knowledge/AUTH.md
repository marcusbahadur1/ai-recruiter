# AUTH Domain

Supabase JWT auth, tenant resolution, plan limits, trial expiry middleware.

---

## Auth Flow

1. **Sign up**: `POST /auth/signup` → Supabase creates user → backend creates `Tenant` row → trial starts
2. **Login**: `POST /auth/login` → Supabase validates → returns `{access_token, refresh_token}`
3. **Token use**: All API requests carry `Authorization: Bearer {access_token}`
4. **Tenant resolution**: `get_current_tenant()` FastAPI dependency:
   - Decode JWT with Supabase secret
   - Extract `sub` (Supabase user UUID)
   - `SELECT * FROM tenants WHERE user_id = sub`
   - Returns `Tenant` ORM object — injected into every protected route

## Trial Expiry Middleware

- Runs on every request before route handler
- If `tenant.plan == "trial"` and `tenant.trial_ends_at < now()`:
  - Returns 402 for all routes except `/billing`, `/webhooks`, `/auth`
- Production: 14-day trial from `trial_started_at`

## Plan Limits

Defined in `config.py` as `PLAN_LIMITS` dict:
```
trial:          {credits: 3,   jobs: 1,  candidates_per_job: 20,  posts_per_week: 0}
recruiter:      {credits: 10,  jobs: 5,  candidates_per_job: 50,  posts_per_week: 5}
agency_small:   {credits: 30,  jobs: 15, candidates_per_job: 100, posts_per_week: 10}
agency_medium:  {credits: 100, jobs: 50, candidates_per_job: 200, posts_per_week: 20}
enterprise:     {credits: 500, jobs: unlimited, ...}
```
(Verify actual values in `config.py` — these are approximate from analysis.)

## Super Admin

- Detected via API probe in `layout.tsx` (`superAdminApi.getStats()` → 200 = admin)
- `SUPER_ADMIN_EMAIL = marcus@aiworkerz.com`
- Access to `/super-admin/*` endpoints — list tenants, health check, reset tenant
- No special JWT claim — identified purely by tenant email

## Tenant Sensitive Fields (Encrypted via Fernet)

All of these are stored encrypted in the `tenants` table:
- `ai_api_key` — tenant's own OpenAI/Anthropic key
- `scrapingdog_api_key`, `brightdata_api_key`
- `apollo_api_key`, `hunter_api_key`, `snov_api_key`, `sendgrid_api_key`
- `email_inbox_password` — IMAP password
- LinkedIn OAuth tokens (`MarketingAccount.access_token`, `refresh_token`)

## Multi-Tenancy Rule

**Every DB query must include `tenant_id`**. This is the primary isolation mechanism — there is no row-level security in SQLAlchemy queries (Supabase RLS is not relied upon for application-level isolation). Violating this rule causes data leakage between tenants.
