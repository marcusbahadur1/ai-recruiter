# Spec §13: Backend API Routes

*Full spec index: see [spec.md](spec.md)*

---

## 13. Backend API Routes (FastAPI)

All routes prefixed `/api/v1`. Require JWT Bearer unless marked public.

### 13.1 Auth & Tenant
- `GET /health` (public — returns `{"status": "ok"}`)
- `POST /auth/signup` (public)
- `POST /auth/login` (public)
- `GET /tenants/me`
- `PATCH /tenants/me`
- `GET /super-admin/tenants` (super_admin only)
- `POST /super-admin/impersonate/{tenant_id}` (super_admin only, logged)
- `GET /super-admin/email-test-mode` (super_admin only)
- `POST /super-admin/email-test-mode` (super_admin only — sets Redis-backed toggle)

### 13.2 Chat Sessions
- `GET /chat-sessions/current`
- `POST /chat-sessions/{id}/message`
- `POST /chat-sessions/{id}/message/stream` (SSE)
- `POST /chat-sessions/new`

### 13.3 Jobs
- `GET /jobs`
- `POST /jobs`
- `GET /jobs/{id}`
- `PATCH /jobs/{id}`
- `POST /jobs/{id}/trigger-scout`
- `GET /jobs/{id}/evaluation-report` (SSE)

### 13.4 Candidates
- `GET /candidates` (search + filter)
- `GET /candidates/{id}`
- `PATCH /candidates/{id}`
- `DELETE /candidates/{id}` (GDPR erasure)
- `POST /candidates/{id}/send-outreach`

### 13.5 Applications
- `GET /applications?job_id={id}`
- `GET /applications/{id}`
- `POST /applications/{id}/trigger-test`
- `GET /test/{id}/{token}` (public)
- `POST /test/{id}/message` (public)
- `GET /actions/invite-interview/{id}/{token}` (public)

### 13.6 RAG & Widget
- `POST /rag/scrape`
- `POST /rag/documents`
- `DELETE /rag/documents/{id}`
- `GET /widget/{slug}/chat` (public, rate-limited)

### 13.7 Promo Codes & Webhooks
- `GET /promo-codes`
- `POST /promo-codes`
- `DELETE /promo-codes/{id}`
- `POST /promo-codes/validate` (public)
- `POST /webhooks/stripe` (public, signature verified)
- `POST /webhooks/email-received` (HMAC verified)

### 13.8 Audit Trail
- `GET /jobs/{id}/audit-stream` (SSE — real-time events)
- `GET /jobs/{id}/audit-events` (paginated history + export)
- `GET /super-admin/audit` (super_admin only)

### 13.9 Marketing (19 routes)
- `POST /marketing/accounts/linkedin/connect`
- `GET /marketing/accounts/linkedin/callback`
- `GET /marketing/accounts/linkedin/select-page/pages`
- `POST /marketing/accounts/linkedin/select-page`
- `GET /marketing/accounts`
- `DELETE /marketing/accounts/{id}`
- `GET /marketing/posts` (paginated)
- `POST /marketing/posts`
- `PATCH /marketing/posts/{id}`
- `POST /marketing/posts/{id}/approve`
- `POST /marketing/posts/{id}/reject`
- `DELETE /marketing/posts/{id}`
- `POST /marketing/posts/generate`
- `GET /marketing/settings`
- `PATCH /marketing/settings`
- `POST /marketing/toggle`
- `GET /marketing/analytics`
- `GET /marketing/analytics/summary`
- `GET /marketing/engagement`
