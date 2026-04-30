# AI Recruiter — Project Guidelines (Rules 1–6)
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

*Continued in [guidelines-tasks-frontend.md](guidelines-tasks-frontend.md) — Rules 7–15*
