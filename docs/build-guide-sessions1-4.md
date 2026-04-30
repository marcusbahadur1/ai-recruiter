> **Historical document** — used to bootstrap code generation in sessions 1–10. Not needed for active development.

# Build Guide Part 2: Sessions 1–4 (Backend Foundation)

*Full index: see [build-guide.md](build-guide.md)*

---

## SESSION 1 — Backend project structure + database models

Paste this prompt into Claude Code:
```
Read SPEC.md and guidelines.md carefully.

Your task: Set up the Python backend project structure and generate all SQLAlchemy 2.x async database models.

1. Create folder structure as defined in SPEC.md Section 19:
   backend/app/main.py, config.py, database.py
   backend/app/models/ (one file per model)
   backend/requirements.txt, backend/Dockerfile

2. requirements.txt must include: fastapi, uvicorn[standard], sqlalchemy[asyncio], asyncpg, alembic,
   pydantic[email], pydantic-settings, celery[redis], redis, httpx, anthropic, openai,
   cryptography, stripe, sendgrid, pdfplumber, python-docx, crawl4ai, pgvector,
   python-jose[cryptography], passlib[bcrypt], python-multipart, jinja2, pytest, pytest-asyncio,
   httpx, respx, playwright

3. Generate all SQLAlchemy models exactly as defined in SPEC.md Section 5:
   Tenant (Section 2.1), Job (5.1), Candidate (5.2), Application (5.3),
   PromoCode (5.4), ChatSession (5.5), RagDocument (5.6), JobAuditEvent (5.7)

4. Generate database.py with async SQLAlchemy session factory using asyncpg

5. Create Alembic migration including pgvector extension, all tables, the Postgres trigger
   on job_audit_events that fires NOTIFY audit_{job_id} after INSERT, and all indexes.

Do NOT generate routes or services yet — models only.
```

After: review models in PyCharm, run `cd backend && pip install -r requirements.txt && alembic upgrade head`, commit: `"Session 1: database models and migrations"`.

---

## SESSION 2 — Pydantic schemas + FastAPI app factory + auth

```
Read SPEC.md and guidelines.md.

1. Generate backend/app/schemas/ — Base/Create/Update/Response schemas for each model,
   model_config = ConfigDict(from_attributes=True) on all response schemas, PaginatedResponse generic

2. Generate backend/app/main.py: FastAPI app with /api/v1 prefix, CORS middleware, include all routers

3. Generate backend/app/routers/auth.py:
   - POST /api/v1/auth/signup — create user in Supabase Auth + create Tenant record
   - POST /api/v1/auth/login — return Supabase JWT
   - get_current_tenant dependency validates JWT and returns Tenant from DB

4. Generate backend/app/routers/tenants.py — GET/PATCH /api/v1/tenants/me

5. All routes: tenant_id from JWT only, never from body.
```

After: test `curl http://localhost:8000/docs` → Swagger UI, commit: `"Session 2: schemas, app factory, auth"`.

---

## SESSION 3 — AI provider facade + core services

```
Read SPEC.md and guidelines.md.

1. backend/app/services/claude_ai.py — async Anthropic SDK wrapper: complete(), complete_json()
2. backend/app/services/openai_ai.py — same interface as claude_ai.py
3. backend/app/services/ai_provider.py — facade routing by tenant.ai_provider (NEVER call SDKs directly)
4. backend/app/services/embeddings.py — generate_embedding(text) -> list[float] (1536 dims)
5. backend/app/services/scrapingdog.py — search_linkedin(query, start, api_key) -> list[dict]
6. backend/app/services/brightdata.py — get_linkedin_profile(linkedin_url, api_key) -> dict
7. backend/app/services/apollo.py — find_email(name, company, api_key) -> Optional[str]
8. backend/app/services/hunter.py — find_email(first_name, last_name, domain, api_key); confidence > 70%
9. backend/app/services/snov.py — find_email(first_name, last_name, domain, api_key)
10. backend/app/services/email_deduction.py — full EmailDeductionService per SPEC.md Section 7.4.4
11. backend/app/services/sendgrid_email.py — send_email(to, subject, html_body, tenant)
12. Write unit tests in backend/tests/unit/ — mock all external HTTP calls using respx
```

After: run `pytest backend/tests/unit/ -v`, commit: `"Session 3: AI facade and integration services"`.

---

## SESSION 4 — Audit trail service + Jobs/Candidates/Applications routes

```
Read SPEC.md and guidelines.md.

1. backend/app/services/audit_trail.py — AuditTrailService with emit() method.
   Use all event_type strings exactly as defined in SPEC.md Sections 15.2-15.4.
   Postgres NOTIFY handled by DB trigger — do NOT call NOTIFY from Python.

2. backend/app/routers/audit.py:
   - GET /jobs/{id}/audit-stream (SSE, asyncpg LISTEN, handle client disconnect cleanly)
   - GET /jobs/{id}/audit-events (paginated, filter by category/severity)
   - GET /super-admin/audit (super_admin only)

3. backend/app/routers/jobs.py — full CRUD + trigger-scout + SSE evaluation report

4. backend/app/routers/candidates.py — full implementation.
   DELETE must call gdpr.anonymise_candidate(), not raw delete.

5. backend/app/services/gdpr.py — anonymise_candidate(): replaces PII with '[REDACTED]',
   clears brightdata_profile, deletes resume_embedding, redacts job_audit_events.detail JSONB,
   deletes resume files from Supabase Storage. Does NOT delete rows.

6. backend/app/routers/applications.py — full implementation

7. Write integration tests for all new routes.
```

After: run `pytest backend/tests/ -v`, commit: `"Session 4: audit trail, CRUD routes"`.
