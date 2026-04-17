"""Global search router — cross-entity search across candidates and jobs.

Routes:
  GET /search?q={query}  — search candidates and jobs for the current tenant
"""

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.candidate import Candidate
from app.models.job import Job
from app.models.tenant import Tenant
from app.routers.auth import get_current_tenant

router = APIRouter(prefix="/search", tags=["search"])


# ── Response schemas ──────────────────────────────────────────────────────────


class CandidateResult(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    title: str | None
    company: str | None
    status: str
    type: Literal["candidate"] = "candidate"


class JobResult(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    job_ref: str
    status: str
    type: Literal["job"] = "job"


class SearchResponse(BaseModel):
    candidates: list[CandidateResult]
    jobs: list[JobResult]
    query: str


# ── Route ─────────────────────────────────────────────────────────────────────


@router.get("", response_model=SearchResponse)
async def search(
    q: str = Query(
        ..., min_length=3, description="Search query (minimum 3 characters)"
    ),
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(5, le=20),
) -> SearchResponse:
    """Search candidates and jobs for the current tenant.

    Candidates are matched against name, title, and company.
    Jobs are matched against title, job_ref, and location.
    Results are capped at `limit` per entity type (default 5).
    """
    term = f"%{q}%"

    candidate_result = await db.execute(
        select(Candidate)
        .where(
            Candidate.tenant_id == tenant.id,
            or_(
                Candidate.name.ilike(term),
                Candidate.title.ilike(term),
                Candidate.company.ilike(term),
            ),
        )
        .order_by(Candidate.created_at.desc())
        .limit(limit)
    )
    candidates = candidate_result.scalars().all()

    job_result = await db.execute(
        select(Job)
        .where(
            Job.tenant_id == tenant.id,
            or_(
                Job.title.ilike(term),
                Job.job_ref.ilike(term),
                Job.location.ilike(term),
            ),
        )
        .order_by(Job.created_at.desc())
        .limit(limit)
    )
    jobs = job_result.scalars().all()

    return SearchResponse(
        candidates=[CandidateResult.model_validate(c) for c in candidates],
        jobs=[JobResult.model_validate(j) for j in jobs],
        query=q,
    )
