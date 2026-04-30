# Spec §19–20: Project Structure & Environment Variables

*Full spec index: see [spec.md](spec.md)*

---

## 19. Project Structure

```
ai-recruiter/
├── backend/
│   ├── app/
│   │   ├── main.py            # FastAPI app factory
│   │   ├── config.py          # Settings (pydantic-settings)
│   │   ├── database.py        # Supabase/asyncpg session
│   │   ├── models/            # tenant, job, candidate, application,
│   │   │                      #   chat_session, rag_document,
│   │   │                      #   job_audit_event, promo_code, marketing*
│   │   ├── schemas/           # Pydantic v2 schemas
│   │   ├── routers/           # auth, chat_sessions, jobs, candidates,
│   │   │                      #   applications, audit, rag, widget,
│   │   │                      #   promo_codes, super_admin, webhooks,
│   │   │                      #   marketing_oauth, marketing_posts,
│   │   │                      #   marketing_settings, marketing_analytics
│   │   ├── services/          # talent_scout, resume_screener,
│   │   │                      #   email_deduction, apollo, hunter, snov,
│   │   │                      #   brightdata, scrapingdog, claude_ai,
│   │   │                      #   openai_ai, ai_provider (facade),
│   │   │                      #   embeddings, rag_pipeline, audit_trail,
│   │   │                      #   gdpr, platform_settings, sendgrid_email,
│   │   │                      #   marketing/ (linkedin_client, unsplash_client,
│   │   │                      #              content_generator, image_query)
│   │   ├── tasks/             # celery_app, talent_scout_tasks,
│   │   │                      #   screener_tasks, scheduled_tasks,
│   │   │                      #   marketing_tasks
│   │   └── templates/         # Jinja2 email templates (12)
│   ├── tests/                 # conftest, unit/, integration/, e2e/
│   ├── migrations/            # Alembic versions (0001–0020)
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/                  # Next.js 16 App Router
│   ├── app/[locale]/          # i18n routing (en/de/es/fr)
│   ├── components/
│   ├── lib/api/               # client.ts, index.ts, types.ts
│   ├── messages/              # en, de, es, fr JSON
│   └── public/widget/         # Embeddable widget JS
└── e2e/                       # Playwright tests (smoke + production)
```

---

## 20. Environment Variables

### 20.1 Platform-Level (Fly.io secrets)

| Variable | Description |
|---|---|
| ANTHROPIC_API_KEY | Default Claude Sonnet API key |
| OPENAI_API_KEY | Default OpenAI API key |
| SUPABASE_URL | Supabase project URL |
| SUPABASE_SERVICE_KEY | Service role key (server-side only) |
| SUPABASE_ANON_KEY | Anon key (frontend) |
| REDIS_URL | Redis connection string |
| STRIPE_SECRET_KEY | Stripe secret key |
| STRIPE_WEBHOOK_SECRET | Stripe webhook signing secret |
| SENDGRID_API_KEY | Platform SendGrid key |
| IMAP_HOST / IMAP_PORT / IMAP_MASTER_PASSWORD | Shared mail server |
| SCRAPINGDOG_API_KEY / BRIGHTDATA_API_KEY | SERP + LinkedIn enrichment |
| ENCRYPTION_KEY | Fernet key for tenant API key encryption |
| FRONTEND_URL | https://app.airecruiterz.com |
| ENVIRONMENT | development \| staging \| production |
| SQLALCHEMY_DATABASE_URL | asyncpg URL using Supabase **transaction pooler** (port 6543) |
| DB_PASSWORD | DB password as plain text (injected at runtime to avoid URL-encoding issues) |
| LINKEDIN_CLIENT_ID / LINKEDIN_CLIENT_SECRET / LINKEDIN_REDIRECT_URI | Marketing OAuth |
| UNSPLASH_ACCESS_KEY | Unsplash image search |

> **asyncpg + pgbouncer**: set `statement_cache_size=0` and `prepared_statement_cache_size=0` in `connect_args`. Do NOT use `pool_pre_ping=True`.

### 20.2 Tenant-Overridable

`ai_provider`, `ai_api_key`, `search_provider`, `scrapingdog_api_key`, `brightdata_api_key`, `email_discovery_provider`, `apollo_api_key`, `hunter_api_key`, `snov_api_key`, `sendgrid_api_key`, `email_inbox_host/port/user/password`.

### 20.3 Local Environment Convention

`backend/.env` is the active file. Switch: `cp backend/.env-staging backend/.env` or `cp backend/.env-production backend/.env`. Both gitignored. Reference: `backend/.env.example`.
