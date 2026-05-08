# Database Domain

NullPool, two engines, tenant scoping, pgvector, encrypted fields, migrations.

---

## Two Engines (Critical)

```
AsyncSessionLocal      → port 6543 (transaction pooler) → API requests
AsyncTaskSessionLocal  → port 5432 (session pooler)     → Celery tasks
```

Both use `NullPool`. See DECISIONS D1, D2 for full explanation.

## Session Factory Usage

```python
# FastAPI route (via get_db dependency)
async with AsyncSessionLocal() as session: yield session

# Celery task
async with AsyncTaskSessionLocal() as db: await db.commit()

# After streaming (chat_sessions.py) — NOT request-scoped db
async with AsyncSessionLocal() as fresh_db:
    await fresh_db.execute(update(ChatSession).where(...).values(...))
    await fresh_db.commit()
```

`_build_task_db_url()`: auto-replaces `:6543` → `:5432` in the connection URL. `DB_PASSWORD` env var handles special chars.

## Multi-Tenancy

No Supabase RLS at query level. Application-enforced:
- **Every query must include `WHERE tenant_id = :tenant_id`**
- Celery tasks receive `tenant_id` as a parameter (no JWT)
- Violating this leaks data across tenants

## pgvector

- Column type: `Vector(1536)` (OpenAI text-embedding-3-small)
- Operator: `<=>` cosine distance (lower = more similar)
- Tables: `rag_documents`, `candidates`, `applications` (all embedding columns)

## Encrypted Fields (Fernet, `crypto.py`)

All tenant API keys, IMAP password, LinkedIn OAuth tokens encrypted at rest. Key: `ENCRYPTION_KEY` env var.

## Key Tables

| Table | Scoped by |
|-------|-----------|
| tenants | user_id |
| jobs, candidates, applications, chat_sessions, rag_documents, job_audit_events | tenant_id |
| test_sessions | application_id |
| marketing_accounts/posts/settings | tenant_id (nullable) |
| promo_codes | platform-level |

## Migrations

Tool: Alembic. Files: `backend/migrations/versions/`. Run `alembic upgrade head`. Never modify existing migrations — always create new.
