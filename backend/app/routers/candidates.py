"""Candidates router — search, CRUD, GDPR erasure, outreach.

Routes (all under /api/v1/candidates):
  GET    /candidates            — full-text search + filter
  GET    /candidates/{id}
  PATCH  /candidates/{id}
  DELETE /candidates/{id}       — GDPR erasure (calls gdpr.anonymise_candidate)
  POST   /candidates/{id}/send-outreach
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel as _BaseModel
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.candidate import Candidate
from app.models.job import Job
from app.models.tenant import Tenant
from app.routers.auth import get_current_tenant
from app.schemas.candidate import CandidateResponse, CandidateUpdate
from app.schemas.common import PaginatedResponse
from app.services.ai_provider import AIProvider
from app.services.audit_trail import AuditTrailService
from app.services.gdpr import anonymise_candidate
from app.services.sendgrid_email import send_email

router = APIRouter(prefix="/candidates", tags=["candidates"])


# ── Helpers ───────────────────────────────────────────────────────────────────


async def _get_candidate_or_404(
    candidate_id: uuid.UUID,
    tenant_id: uuid.UUID,
    db: AsyncSession,
) -> Candidate:
    result = await db.execute(
        select(Candidate).where(
            Candidate.id == candidate_id,
            Candidate.tenant_id == tenant_id,
        )
    )
    candidate = result.scalar_one_or_none()
    if not candidate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Candidate not found"
        )
    return candidate


async def _get_job_for_candidate(
    candidate: Candidate,
    tenant_id: uuid.UUID,
    db: AsyncSession,
) -> Job:
    result = await db.execute(
        select(Job).where(Job.id == candidate.job_id, Job.tenant_id == tenant_id)
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Associated job not found"
        )
    return job


# ── Routes ────────────────────────────────────────────────────────────────────


@router.get("", response_model=PaginatedResponse[CandidateResponse])
async def list_candidates(
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
    job_id: uuid.UUID | None = Query(None),
    candidate_status: str | None = Query(None, alias="status"),
    search: str | None = Query(
        None, description="Full-text search on name, title, company"
    ),
    min_score: int | None = Query(
        None, description="Minimum suitability score (inclusive)"
    ),
    max_score: int | None = Query(
        None, description="Maximum suitability score (inclusive)"
    ),
    limit: int = Query(50, le=500),
    offset: int = Query(0, ge=0),
) -> PaginatedResponse[CandidateResponse]:
    """Search and filter candidates for this tenant."""
    conditions = [Candidate.tenant_id == tenant.id]
    if job_id:
        conditions.append(Candidate.job_id == job_id)
    if candidate_status:
        conditions.append(Candidate.status == candidate_status)
    if search:
        term = f"%{search}%"
        conditions.append(
            or_(
                Candidate.name.ilike(term),
                Candidate.title.ilike(term),
                Candidate.company.ilike(term),
                Candidate.location.ilike(term),
            )
        )
    if min_score is not None:
        conditions.append(Candidate.suitability_score >= min_score)
    if max_score is not None:
        conditions.append(Candidate.suitability_score <= max_score)

    result = await db.execute(
        select(Candidate).where(*conditions).order_by(Candidate.created_at.desc())
    )
    all_candidates = result.scalars().all()
    total = len(all_candidates)
    page = all_candidates[offset : offset + limit]
    return PaginatedResponse(
        items=[CandidateResponse.model_validate(c) for c in page],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{candidate_id}", response_model=CandidateResponse)
async def get_candidate(
    candidate_id: uuid.UUID,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
) -> CandidateResponse:
    """Retrieve a single candidate by ID."""
    candidate = await _get_candidate_or_404(candidate_id, tenant.id, db)
    return CandidateResponse.model_validate(candidate)


@router.patch("/{candidate_id}", response_model=CandidateResponse)
async def update_candidate(
    candidate_id: uuid.UUID,
    body: CandidateUpdate,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
) -> CandidateResponse:
    """Partially update a candidate record."""
    candidate = await _get_candidate_or_404(candidate_id, tenant.id, db)
    updates = body.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(candidate, field, value)
    await db.commit()
    return CandidateResponse.model_validate(candidate)


@router.delete("/{candidate_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_candidate(
    candidate_id: uuid.UUID,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
) -> None:
    """GDPR erasure — anonymises all PII.  Does NOT delete the row.

    Calls gdpr.anonymise_candidate() which:
    - Replaces all PII fields with '[REDACTED]'
    - Clears brightdata_profile and resume_embedding
    - Redacts PII in linked job_audit_events.detail JSONB
    - Deletes resume files from Supabase Storage
    """
    # Verify candidate exists and belongs to tenant before erasure
    await _get_candidate_or_404(candidate_id, tenant.id, db)
    await anonymise_candidate(db, tenant.id, candidate_id)


@router.post("/{candidate_id}/send-outreach", response_model=CandidateResponse)
async def send_outreach(
    candidate_id: uuid.UUID,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
) -> CandidateResponse:
    """Generate a personalised outreach email and send it via SendGrid.

    Checks opted_out before sending.  Updates candidate status to 'emailed'.
    """
    candidate = await _get_candidate_or_404(candidate_id, tenant.id, db)
    job = await _get_job_for_candidate(candidate, tenant.id, db)
    audit = AuditTrailService(db, tenant.id)

    if candidate.opted_out:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Candidate has opted out of outreach",
        )
    if not candidate.email:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No email address for this candidate",
        )

    # Generate personalised email via AI facade
    ai = AIProvider(tenant)
    system_prompt = job.outreach_email_prompt or _default_outreach_prompt()
    profile_summary = _summarise_profile(candidate)
    user_prompt = (
        f"Candidate profile:\n{profile_summary}\n\n"
        f"Job: {job.title} ({job.job_type})\n"
        f"Job ref: {job.job_ref}\n"
        f"Apply by emailing resume to: {tenant.email_inbox} "
        f"with subject: {job.job_ref} – <your name>"
    )

    try:
        email_body = await ai.complete(
            prompt=user_prompt, system=system_prompt, max_tokens=600
        )
    except Exception as exc:
        await audit.emit(
            job_id=job.id,
            candidate_id=candidate_id,
            event_type="scout.outreach_email_failed",
            event_category="talent_scout",
            severity="error",
            actor="system",
            summary=f"Email generation failed for {candidate.name}",
            detail={"error": str(exc)},
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI email generation failed",
        )

    # Add mandatory unsubscribe link (GDPR)
    unsubscribe_url = f"https://app.airecruiterz.com/unsubscribe/{candidate_id}"
    full_body = (
        f"{email_body}\n\n---\nTo unsubscribe from future emails: {unsubscribe_url}"
    )

    sent = await send_email(
        to=candidate.email,
        subject=f"Exciting opportunity: {job.title} — {job.job_ref}",
        html_body=full_body.replace("\n", "<br>"),
        tenant=tenant,
    )

    if not sent:
        await audit.emit(
            job_id=job.id,
            candidate_id=candidate_id,
            event_type="scout.outreach_email_failed",
            event_category="talent_scout",
            severity="error",
            actor="system",
            summary=f"SendGrid delivery failed for {candidate.name}",
            detail={"email": candidate.email},
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Email delivery failed",
        )

    # Persist generated email and update status
    candidate.outreach_email_content = full_body
    candidate.status = "emailed"
    await db.commit()

    await audit.emit(
        job_id=job.id,
        candidate_id=candidate_id,
        event_type="scout.outreach_email_sent",
        event_category="talent_scout",
        severity="success",
        actor="system",
        summary=f"Outreach email sent to {candidate.name}",
        detail={"email": candidate.email, "job_ref": job.job_ref},
    )
    return CandidateResponse.model_validate(candidate)


# ── Public unsubscribe ────────────────────────────────────────────────────────


class UnsubscribeResponse(_BaseModel):
    success: bool
    already_opted_out: bool
    message: str


@router.get("/unsubscribe/{candidate_id}", response_model=UnsubscribeResponse)
async def unsubscribe_candidate(
    candidate_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> UnsubscribeResponse:
    """Public endpoint — no auth required.

    Called when a candidate clicks the unsubscribe link in an outreach email.
    Sets opted_out=True so they are never emailed again.
    """
    result = await db.execute(select(Candidate).where(Candidate.id == candidate_id))
    candidate = result.scalar_one_or_none()

    if not candidate:
        # Return success to avoid leaking whether a candidate ID exists.
        return UnsubscribeResponse(
            success=True, already_opted_out=False, message="Unsubscribed successfully."
        )

    if candidate.opted_out:
        return UnsubscribeResponse(
            success=True,
            already_opted_out=True,
            message="You have already unsubscribed.",
        )

    candidate.opted_out = True
    await db.commit()

    return UnsubscribeResponse(
        success=True, already_opted_out=False, message="Unsubscribed successfully."
    )


# ── Private helpers ────────────────────────────────────────────────────────────


def _default_outreach_prompt() -> str:
    return (
        "You are a professional recruiter writing to a passive candidate. "
        "Write a concise, friendly, and genuinely personalised email (max 200 words) "
        "that references specific details from the candidate's current role and experience. "
        "Do not sound like a mass email. Highlight why this specific opportunity is relevant "
        "to their career. Include the job reference and application instructions. "
        "Sign off with the recruiter's name."
    )


def _summarise_profile(candidate: Candidate) -> str:
    """Build a brief profile summary for the AI prompt."""
    parts = [f"Name: {candidate.name}"]
    if candidate.title:
        parts.append(f"Current title: {candidate.title}")
    if candidate.company:
        parts.append(f"Company: {candidate.company}")
    if candidate.location:
        parts.append(f"Location: {candidate.location}")
    if candidate.snippet:
        parts.append(f"Snippet: {candidate.snippet}")
    if candidate.brightdata_profile:
        summary = candidate.brightdata_profile.get("summary", "")
        if summary:
            parts.append(f"LinkedIn summary: {summary[:300]}")
    return "\n".join(parts)
