# AI Recruiter — Project Guidelines
**READ THIS FILE BEFORE EVERY TASK. THESE RULES ARE NON-NEGOTIABLE.**

---

## 1. The Spec Is The Source Of Truth

- Always read `SPEC.md` before starting any task
- If something is unclear, refer back to SPEC.md — do not invent behaviour
- If SPEC.md and this file conflict, SPEC.md wins on business logic, this file wins on technical approach
- Never simplify or skip a spec requirement to make implementation easier

---

## 2. Multi-Tenancy — Zero Tolerance For Cross-Tenant Data Leaks

- **Every single database query MUST include a `tenant_id` filter**
- Never query a table without scoping by `tenant_id`, even in background tasks
- Supabase RLS is the safety net, not the primary defence — always filter in application code too
- When writing a new service method, the first line of review is: "could this return another tenant's data?"
- Background Celery tasks receive `tenant_id` as a parameter and must pass it to every DB call

```python
# CORRECT
result = await db.execute(
    select(Candidate).where(
        Candidate.tenant_id == tenant_id,
        Candidate.job_id == job_id
    )
)

# WRONG — missing tenant_id filter
result = await db.execute(
    select(Candidate).where(Candidate.job_id == job_id)
)
```

---

## 3. Database — Always Async

- Use SQLAlchemy 2.x async with `asyncpg` driver throughout
- Always use `async with db.begin()` for transactions
- Never use synchronous SQLAlchemy sessions anywhere
- All DB operations must use `await`

```python
# CORRECT
async def get_job(db: AsyncSession, tenant_id: UUID, job_id: UUID) -> Job:
    result = await db.execute(
        select(Job).where(Job.tenant_id == tenant_id, Job.id == job_id)
    )
    return result.scalar_one_or_none()
```

---

## 4. API Keys — Never Hardcode, Never Log

- All API keys come from environment variables (`config.py` via `pydantic-settings`)
- Tenant API keys are stored Fernet-encrypted in the DB — decrypt in the service layer only, never pass raw encrypted bytes around
- **Never log API keys, tokens, passwords, or personal data**
- Never commit a `.env` file — use `.env.example` with placeholder values only

---

## 5. AI Provider — Always Use The Facade

- **Never call `anthropic` or `openai` SDKs directly from routers or Celery tasks**
- Always go through `services/ai_provider.py` (the facade)
- The facade reads `tenant.ai_provider` and routes to `claude_ai.py` or `openai_ai.py`
- This ensures tenants can switch AI providers without code changes

```python
# CORRECT
from app.services.ai_provider import AIProvider
ai = AIProvider(tenant)
response = await ai.complete(prompt=..., system=...)

# WRONG — bypasses tenant AI provider setting
from anthropic import AsyncAnthropic
client = AsyncAnthropic()
```

---

## 6. Audit Trail — Write An Event For Every Pipeline Step

- Every Talent Scout and Resume Screener step MUST emit an audit event via `services/audit_trail.py`
- Use the exact `event_type` strings defined in SPEC.md Section 15
- Write the event AFTER the operation completes (success or failure)
- Include `duration_ms` for all external API calls
- For errors: set `severity = 'error'` and include the full error message in `detail`

```python
# CORRECT — emit event after operation
start = time.time()
try:
    profile = await brightdata.get_profile(candidate.linkedin_url)
    candidate.brightdata_profile = profile
    candidate.status = 'profiled'
    await audit.emit(
        job_id=candidate.job_id,
        candidate_id=candidate.id,
        event_type='scout.profile_enrichment_success',
        event_category='talent_scout',
        severity='success',
        actor='system',
        summary=f'BrightData profile received for {candidate.name}',
        detail={'profile_roles': len(profile.get('positions', []))},
        duration_ms=int((time.time() - start) * 1000)
    )
except Exception as e:
    await audit.emit(event_type='scout.profile_enrichment_failed', severity='error',
                     summary=f'BrightData error for {candidate.name}',
                     detail={'error': str(e)}, ...)
```

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
