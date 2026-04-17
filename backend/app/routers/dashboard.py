"""Dashboard router — single stats endpoint for the frontend dashboard.

GET /api/v1/dashboard/stats

Returns aggregated counts for the current tenant:
- active_jobs, candidates_today, applications, credits_remaining
- pipeline: cumulative candidate counts per stage
- recent_activity: latest 10 audit events across all tenant jobs
- active_jobs_list: active jobs with per-job candidate counts
"""

import uuid
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict
from sqlalchemy import case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.application import Application
from app.models.candidate import Candidate
from app.models.job import Job
from app.models.job_audit_event import JobAuditEvent
from app.models.tenant import Tenant
from app.routers.auth import get_current_tenant
from app.schemas.job_audit_event import JobAuditEventResponse

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


# ── Response schemas ──────────────────────────────────────────────────────────


class DashboardPipeline(BaseModel):
    discovered: int
    profiled: int
    scored: int
    passed: int
    emailed: int
    applied: int
    tested: int
    invited: int


class DashboardJobItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    status: str
    job_ref: str
    candidate_count: int = 0


class DashboardStatsResponse(BaseModel):
    active_jobs: int
    candidates_today: int
    applications: int
    credits_remaining: int
    pipeline: DashboardPipeline
    recent_activity: list[JobAuditEventResponse]
    active_jobs_list: list[DashboardJobItem]


# ── Route ─────────────────────────────────────────────────────────────────────


@router.get("/stats", response_model=DashboardStatsResponse)
async def get_dashboard_stats(
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
) -> DashboardStatsResponse:
    """Return all dashboard stats for the current tenant in a single query round-trip."""

    tid = tenant.id

    # ── Active jobs count + list ──────────────────────────────────────────────
    jobs_result = await db.execute(
        select(Job)
        .where(Job.tenant_id == tid, Job.status == "active")
        .order_by(Job.created_at.desc())
        .limit(5)
    )
    active_jobs_rows = jobs_result.scalars().all()

    total_active_jobs_result = await db.execute(
        select(func.count(Job.id)).where(Job.tenant_id == tid, Job.status == "active")
    )
    total_active_jobs = total_active_jobs_result.scalar() or 0

    # ── Candidate counts per job (for active_jobs_list) ───────────────────────
    counts_result = await db.execute(
        select(Candidate.job_id, func.count(Candidate.id).label("cnt"))
        .where(Candidate.tenant_id == tid)
        .group_by(Candidate.job_id)
    )
    count_by_job: dict[uuid.UUID, int] = {
        row.job_id: row.cnt for row in counts_result.all()
    }

    active_jobs_list = [
        DashboardJobItem(
            id=j.id,
            title=j.title,
            status=j.status,
            job_ref=j.job_ref,
            candidate_count=count_by_job.get(j.id, 0),
        )
        for j in active_jobs_rows
    ]

    # ── Cumulative pipeline counts (single aggregation query) ─────────────────
    # Each stage counts candidates who have reached that stage OR beyond.
    profiled_statuses = (
        "profiled",
        "scored",
        "passed",
        "failed",
        "emailed",
        "applied",
        "tested",
        "interviewed",
        "rejected",
    )
    passed_statuses = ("passed", "emailed", "applied", "tested", "interviewed")
    emailed_statuses = ("emailed", "applied", "tested", "interviewed")
    applied_statuses = ("applied", "tested", "interviewed")
    tested_statuses = ("tested", "interviewed")

    pipeline_result = await db.execute(
        select(
            func.count(Candidate.id).label("discovered"),
            func.count(case((Candidate.status.in_(profiled_statuses), 1))).label(
                "profiled"
            ),
            func.count(case((Candidate.suitability_score.is_not(None), 1))).label(
                "scored"
            ),
            func.count(case((Candidate.status.in_(passed_statuses), 1))).label(
                "passed"
            ),
            func.count(
                case(
                    (
                        or_(
                            Candidate.status.in_(emailed_statuses),
                            Candidate.outreach_email_sent_at.is_not(None),
                        ),
                        1,
                    )
                )
            ).label("emailed"),
            func.count(case((Candidate.status.in_(applied_statuses), 1))).label(
                "applied"
            ),
            func.count(case((Candidate.status.in_(tested_statuses), 1))).label(
                "tested"
            ),
            func.count(case((Candidate.status == "interviewed", 1))).label("invited"),
        ).where(Candidate.tenant_id == tid)
    )
    p = pipeline_result.one()
    pipeline = DashboardPipeline(
        discovered=p.discovered,
        profiled=p.profiled,
        scored=p.scored,
        passed=p.passed,
        emailed=p.emailed,
        applied=p.applied,
        tested=p.tested,
        invited=p.invited,
    )

    # ── Candidates created today ───────────────────────────────────────────────
    today_start = datetime.combine(date.today(), datetime.min.time()).replace(
        tzinfo=timezone.utc
    )
    today_result = await db.execute(
        select(func.count(Candidate.id)).where(
            Candidate.tenant_id == tid,
            Candidate.created_at >= today_start,
        )
    )
    candidates_today = today_result.scalar() or 0

    # ── Total applications ────────────────────────────────────────────────────
    apps_result = await db.execute(
        select(func.count(Application.id)).where(Application.tenant_id == tid)
    )
    applications = apps_result.scalar() or 0

    # ── Recent activity (latest 10 audit events across all tenant jobs) ────────
    activity_result = await db.execute(
        select(JobAuditEvent)
        .where(JobAuditEvent.tenant_id == tid)
        .order_by(JobAuditEvent.created_at.desc())
        .limit(10)
    )
    recent_activity = [
        JobAuditEventResponse.model_validate(e) for e in activity_result.scalars().all()
    ]

    return DashboardStatsResponse(
        active_jobs=total_active_jobs,
        candidates_today=candidates_today,
        applications=applications,
        credits_remaining=tenant.credits_remaining,
        pipeline=pipeline,
        recent_activity=recent_activity,
        active_jobs_list=active_jobs_list,
    )
