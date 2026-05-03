"""Jobs router — CRUD + Talent Scout trigger.

Routes (all under /api/v1/jobs):
  GET    /jobs
  POST   /jobs
  GET    /jobs/{id}
  PATCH  /jobs/{id}
  POST   /jobs/{id}/trigger-scout
  GET    /jobs/{id}/evaluation-report  → delegated to audit router
"""

import random
import string
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.job import Job
from app.models.tenant import Tenant
from app.routers.auth import get_current_tenant
from app.schemas.common import PaginatedResponse
from app.schemas.job import JobCreate, JobResponse, JobUpdate
from app.services.audit_trail import AuditTrailService

router = APIRouter(prefix="/jobs", tags=["jobs"])


# ── Helpers ───────────────────────────────────────────────────────────────────


def _generate_job_ref() -> str:
    """Generate a unique 8-character alphanumeric job reference (e.g. MI0T4AM3)."""
    chars = string.ascii_uppercase + string.digits
    return "".join(random.choices(chars, k=8))


async def _get_job_or_404(
    job_id: uuid.UUID,
    tenant_id: uuid.UUID,
    db: AsyncSession,
) -> Job:
    result = await db.execute(
        select(Job).where(Job.id == job_id, Job.tenant_id == tenant_id)
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Job not found"
        )
    return job


# ── Routes ────────────────────────────────────────────────────────────────────


@router.get("", response_model=PaginatedResponse[JobResponse])
async def list_jobs(
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
    job_status: str | None = Query(None, alias="status"),
    limit: int = Query(50, le=100),
    offset: int = Query(0, ge=0),
) -> PaginatedResponse[JobResponse]:
    """List all jobs for the current tenant with optional status filter."""
    conditions = [Job.tenant_id == tenant.id]
    if job_status:
        conditions.append(Job.status == job_status)

    result = await db.execute(
        select(Job).where(*conditions).order_by(Job.created_at.desc())
    )
    all_jobs = result.scalars().all()
    total = len(all_jobs)
    page = all_jobs[offset : offset + limit]
    return PaginatedResponse(
        items=[JobResponse.model_validate(j) for j in page],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
async def create_job(
    body: JobCreate,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
) -> JobResponse:
    """Create a new job for the current tenant."""
    job = Job(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        job_ref=_generate_job_ref(),
        title=body.title,
        title_variations=body.title_variations,
        job_type=body.job_type,
        description=body.description,
        required_skills=body.required_skills,
        experience_years=body.experience_years,
        salary_min=body.salary_min,
        salary_max=body.salary_max,
        location=body.location,
        location_variations=body.location_variations,
        work_type=body.work_type,
        tech_stack=body.tech_stack,
        team_size=body.team_size,
        minimum_score=body.minimum_score,
        hiring_manager_email=body.hiring_manager_email,
        hiring_manager_name=body.hiring_manager_name,
        evaluation_prompt=body.evaluation_prompt,
        outreach_email_prompt=body.outreach_email_prompt,
        interview_questions_count=body.interview_questions_count,
        custom_interview_questions=body.custom_interview_questions,
        ai_recruiter_config=body.ai_recruiter_config,
    )
    db.add(job)
    await db.commit()
    return JobResponse.model_validate(job)


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: uuid.UUID,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
) -> JobResponse:
    """Retrieve a single job by ID."""
    job = await _get_job_or_404(job_id, tenant.id, db)
    return JobResponse.model_validate(job)


@router.patch("/{job_id}", response_model=JobResponse)
async def update_job(
    job_id: uuid.UUID,
    body: JobUpdate,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
) -> JobResponse:
    """Partially update a job (only supplied fields are changed)."""
    job = await _get_job_or_404(job_id, tenant.id, db)
    updates = body.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(job, field, value)
    await db.commit()
    return JobResponse.model_validate(job)


@router.post("/{job_id}/trigger-scout", status_code=status.HTTP_202_ACCEPTED)
async def trigger_scout(
    job_id: uuid.UUID,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Trigger the Talent Scout pipeline for a job.

    Validates that the tenant has credits, deducts one credit, sets job status
    to 'active', emits the scout.job_started audit event, and queues the
    Celery discover_candidates task.
    """
    job = await _get_job_or_404(job_id, tenant.id, db)

    if tenant.credits_remaining < 1:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Insufficient credits. Please top up your account.",
        )

    job.status = "active"
    tenant.credits_remaining = tenant.credits_remaining - 1
    await db.commit()

    audit = AuditTrailService(db, tenant.id)
    await audit.emit(
        job_id=job_id,
        event_type="scout.job_started",
        event_category="talent_scout",
        severity="info",
        actor="recruiter",
        summary=f"Talent Scout started for job '{job.title}'",
        detail={"job_ref": job.job_ref, "job_title": job.title},
    )
    await audit.emit(
        job_id=job_id,
        event_type="payment.credit_charged",
        event_category="payment",
        severity="info",
        actor="system",
        summary="1 credit deducted for Talent Scout search",
        detail={"credits_remaining": tenant.credits_remaining},
    )

    from app.tasks.talent_scout_tasks import discover_candidates
    discover_candidates.delay(str(job_id), str(tenant.id))

    return {
        "status": "accepted",
        "job_id": str(job_id),
        "message": "Talent Scout pipeline queued",
    }
