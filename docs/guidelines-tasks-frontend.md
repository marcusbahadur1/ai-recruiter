# AI Recruiter — Project Guidelines (Rules 7–15)
**READ THIS FILE BEFORE EVERY TASK. THESE RULES ARE NON-NEGOTIABLE.**

*Rules 1–6 are in [guidelines-tenancy-ai.md](guidelines-tenancy-ai.md)*

---

## 7. GDPR — Non-Negotiable Rules

- Every outreach email MUST include an unsubscribe link
- If `candidate.opted_out = True`, never send another email — check before every send
- `DELETE /candidates/{id}` must call `services/gdpr.py:anonymise_candidate()` — not a raw DB delete
- `anonymise_candidate()` must: replace all PII fields with '[REDACTED]', set `brightdata_profile = {}`, delete `resume_embedding`, redact PII in `job_audit_events.detail` JSONB
- Never delete `job_audit_events` rows — only redact PII within them
- Resume files in Supabase Storage must be deleted when the Application record is erased

---

## 8. Celery Tasks — Structure And Error Handling

- Every Celery task must have `max_retries=3` and exponential backoff
- Use `self.retry(exc=e, countdown=2 ** self.request.retries * 30)` pattern
- After 3 failures: emit `system.task_failed_permanent` audit event and stop
- Tasks must be idempotent — safe to run twice (check status before acting)
- Always emit audit events even on failure — that's how recruiters see what went wrong

```python
@celery_app.task(bind=True, max_retries=3)
def enrich_profile(self, candidate_id: str, tenant_id: str):
    try:
        # ... do work
    except Exception as e:
        if self.request.retries >= self.max_retries:
            emit_audit_event(event_type='system.task_failed_permanent', ...)
            return
        raise self.retry(exc=e, countdown=2 ** self.request.retries * 30)
```

---

## 9. FastAPI Routes — Standard Patterns

- All routes return Pydantic v2 response models — never return raw dicts
- Always extract `tenant_id` from the JWT via a dependency — never trust `tenant_id` from the request body
- Use `Depends(get_current_tenant)` on every protected route
- Route files contain only route definitions — business logic lives in `services/`
- Paginate all list endpoints with `limit` (max 100) and `offset` params

```python
# CORRECT — tenant from JWT, not from body
@router.get("/candidates", response_model=PaginatedCandidates)
async def list_candidates(
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
    job_id: Optional[UUID] = None,
    limit: int = Query(50, le=100),
    offset: int = 0
):
    return await candidate_service.list(db, tenant.id, job_id, limit, offset)
```

---

## 10. SSE (Server-Sent Events) — Postgres LISTEN/NOTIFY

- The SSE endpoint uses `asyncpg` directly (not SQLAlchemy) for `LISTEN`
- Channel name format: `audit_{job_id}` (replace hyphens with underscores)
- Always verify the JWT and tenant scope before starting the SSE loop
- Handle client disconnect gracefully — release the LISTEN connection
- The Postgres trigger is defined in an Alembic migration — not application code

---

## 11. Testing — Every Service Gets Tests

- Every new service method must have at least one unit test
- Every new route must have at least one integration test using `httpx.AsyncClient`
- External API calls must be mocked using `respx` — never make real API calls in tests
- Test file names mirror source files: `services/apollo.py` → `tests/unit/test_apollo.py`
- Use `pytest.mark.asyncio` for all async tests
- Fixtures in `conftest.py` only — no fixture duplication across test files

---

## 12. Pydantic v2 — Strict Usage

- All request/response models use Pydantic v2 (`from pydantic import BaseModel`)
- Use `model_config = ConfigDict(from_attributes=True)` on all DB-backed schemas
- Never use `orm_mode = True` (Pydantic v1 syntax)
- Validate all enums as `Literal` types or Python `Enum` classes

---

## 13. Frontend (Next.js) — Key Rules

- Use App Router only — never Pages Router
- All API calls go through a typed `api/` client layer — never `fetch()` directly in components
- i18n: all user-facing strings must use `next-intl` — no hardcoded English strings in components
- Chat session state is fetched from server on load — never stored in `localStorage` or `sessionStorage`
- SSE connection established via `EventSource` API in a React `useEffect` with cleanup
- All forms use `react-hook-form` with Zod validation

---

## 14. Code Style

- Python: `black` formatting, `ruff` linting, `mypy` type checking
- All Python functions must have type hints
- No `Any` types except where genuinely unavoidable (document why)
- Max function length: 50 lines. If longer, extract helper functions.
- Docstrings on all public service methods
- TypeScript: strict mode enabled, no `any` types

---

## 15. What To Do If You Are Unsure

1. Re-read the relevant section of `SPEC.md`
2. Check this `guidelines.md` for the rule
3. If still unclear: implement the most conservative/secure option and add a `# TODO: confirm with spec` comment
4. Never silently skip a requirement — leave a visible marker if something is deferred

---

*Last updated: April 2026 — AI Recruiter v3.0*
