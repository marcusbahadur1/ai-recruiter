# Spec §23–24: Deployment Checklist & Resolved Items

*Full spec index: see [spec.md](spec.md)*

---

## 23. Deployment Checklist (Fly.io)

**Prerequisites:** `fly auth login` — install CLI: `curl -L https://fly.io/install.sh | sh`

### One-time setup

1. **Supabase** — Create project (Sydney ap-southeast-2). Run `alembic upgrade head`. Enable pgvector. Use **transaction pooler** URL (port 6543); set `DB_PASSWORD` as plain-text var.

2. **Redis** — `fly redis create --name airecruiterz-redis --region syd --plan free`. Copy `redis://` URL → set as `REDIS_URL` on both API and worker apps.

3. **Create apps**:
   ```bash
   fly apps create airecruiterz-api
   fly apps create airecruiterz-worker
   fly apps create airecruiterz-app
   ```

4. **Set secrets** on both api and worker (see §20.1 for full variable list):
   ```bash
   fly secrets set --app airecruiterz-api SQLALCHEMY_DATABASE_URL="..." DB_PASSWORD="..." ...
   fly secrets set --app airecruiterz-worker <same key=value pairs>
   ```

5. **Deploy** (from `backend/`):
   ```bash
   fly deploy --config fly.toml --app airecruiterz-api
   fly deploy --config fly.worker.toml --app airecruiterz-worker
   ```

6. **Deploy Frontend** (from `frontend/`):
   ```bash
   fly deploy --config fly.toml --app airecruiterz-app \
     --build-arg NEXT_PUBLIC_SUPABASE_URL=https://vigtvsdwbkspkqohvjna.supabase.co \
     --build-arg NEXT_PUBLIC_SUPABASE_ANON_KEY=<anon-key>
   ```

7. **Custom domain**: `fly certs add app.airecruiterz.com --app airecruiterz-app`. DNS: CNAME `app` → `airecruiterz-app.fly.dev`.

8. **Stripe webhook** — update endpoint to `https://airecruiterz-api.fly.dev/api/v1/webhooks/stripe`.

9. **Verify**: `curl https://airecruiterz-api.fly.dev/health` → `{"status":"ok","db":"ok"}`

10. **Smoke test** — sign up → post job via AI chat → verify full pipeline.

### Subsequent deploys

```bash
# Backend:
fly deploy --config fly.toml --app airecruiterz-api
fly deploy --config fly.worker.toml --app airecruiterz-worker

# Frontend (omit --build-arg if Supabase vars unchanged):
fly deploy --config fly.toml --app airecruiterz-app
```

---

## 24. Resolved Items from v1 & v2

| Item | Resolution |
|---|---|
| BrightData product | LinkedIn People Profiles — collect by LinkedIn URL |
| Email infrastructure | Platform-managed shared server by default; larger firms can override with own IMAP |
| Apollo.io | Optional, tenant-selectable. Hunter.io and Snov.io also integrated. Domain deduction always available. |
| Stripe pricing | Trial (free 14-day) / Recruiter $499 / Agency Small $999 / Agency Medium $2,999 / Enterprise custom AUD/mo |
| Frontend framework | Next.js 16 App Router — i18n via `proxy.ts` (not `middleware.ts`) |
| Chat history | Server-side in chat_sessions table — not browser state |
| AI provider | Anthropic (default) + OpenAI (optional) — switchable at tenant level |
| SERP provider | ScrapingDog + BrightData SERP — both integrated, tenant-selectable |
| RAG / chat widget | §9. Website scraping + document upload + embeddable widget. Agency Small plan+. |
| GDPR | Full §16. Lawful basis, data rights, retention, DPA, technical measures. |
| Audit trail | §15. 45 typed events, real-time SSE via Postgres LISTEN/NOTIFY, tabbed UI on job detail page |
