"""GDPR erasure service.

anonymise_candidate() implements the right-to-erasure workflow described in
SPEC.md §16.2.  It NEVER deletes candidate or audit event rows — it only
redacts PII in-place.
"""

import logging
import uuid
from typing import Any

import httpx
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.application import Application
from app.models.candidate import Candidate
from app.models.job_audit_event import JobAuditEvent
from app.services.audit_trail import AuditTrailService

logger = logging.getLogger(__name__)

_REDACTED = "[REDACTED]"

# PII fields on the Candidate row that must be replaced
_CANDIDATE_PII_FIELDS: list[str] = [
    "name",
    "title",
    "snippet",
    "linkedin_url",
    "email",
    "company",
    "location",
    "outreach_email_content",
]

# JSONB detail keys that may contain PII — redact their values
_DETAIL_PII_KEYS: list[str] = [
    "name",
    "email",
    "linkedin_url",
    "company",
    "location",
    "title",
    "snippet",
    "applicant_name",
    "applicant_email",
]


async def anonymise_candidate(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    candidate_id: uuid.UUID,
) -> None:
    """Anonymise all PII for a candidate (GDPR right to erasure).

    Steps performed (in order):
    1. Verify the candidate exists and belongs to the tenant.
    2. Replace all PII columns with '[REDACTED]'.
    3. Clear ``brightdata_profile`` (set to empty dict).
    4. Delete ``resume_embedding`` (set to NULL).
    5. Redact PII keys within ``job_audit_events.detail`` JSONB.
    6. Delete resume files from Supabase Storage for all linked applications.
    7. Emit a ``system.gdpr_erasure`` audit event.

    Raises:
        ValueError: If the candidate is not found or belongs to another tenant.
    """
    # 1. Load candidate — enforce tenant scope
    result = await db.execute(
        select(Candidate).where(
            Candidate.id == candidate_id,
            Candidate.tenant_id == tenant_id,
        )
    )
    candidate = result.scalar_one_or_none()
    if not candidate:
        raise ValueError(f"Candidate {candidate_id} not found for tenant {tenant_id}")

    job_id = candidate.job_id

    async with db.begin():
        # 2 & 3 & 4. Redact PII columns, clear profile, null embedding
        pii_updates: dict[str, Any] = {field: _REDACTED for field in _CANDIDATE_PII_FIELDS}
        pii_updates["brightdata_profile"] = {}
        pii_updates["resume_embedding"] = None
        await db.execute(
            update(Candidate)
            .where(Candidate.id == candidate_id, Candidate.tenant_id == tenant_id)
            .values(**pii_updates)
        )

        # 5. Redact PII in audit event detail JSONB for this candidate
        await _redact_audit_detail(db, tenant_id, candidate_id)

        # 6. Delete resume files from Supabase Storage
        app_result = await db.execute(
            select(Application).where(
                Application.candidate_id == candidate_id,
                Application.tenant_id == tenant_id,
            )
        )
        applications = app_result.scalars().all()
        for application in applications:
            if application.resume_storage_path:
                await _delete_supabase_file(application.resume_storage_path)

    # 7. Emit audit event (own transaction)
    audit = AuditTrailService(db, tenant_id)
    await audit.emit(
        job_id=job_id,
        candidate_id=candidate_id,
        event_type="system.gdpr_erasure",
        event_category="system",
        severity="info",
        actor="recruiter",
        summary="Candidate PII anonymised (GDPR erasure)",
        detail={"candidate_id": str(candidate_id)},
    )


async def _redact_audit_detail(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    candidate_id: uuid.UUID,
) -> None:
    """Replace known PII keys inside job_audit_events.detail for this candidate."""
    result = await db.execute(
        select(JobAuditEvent).where(
            JobAuditEvent.candidate_id == candidate_id,
            JobAuditEvent.tenant_id == tenant_id,
        )
    )
    events = result.scalars().all()
    for event in events:
        if not event.detail:
            continue
        redacted = _redact_dict(event.detail)
        # Use raw UPDATE to avoid triggering the NOTIFY trigger again
        await db.execute(
            update(JobAuditEvent)
            .where(JobAuditEvent.id == event.id)
            .values(detail=redacted)
        )


def _redact_dict(d: dict[str, Any]) -> dict[str, Any]:
    """Recursively replace known PII keys with '[REDACTED]'."""
    result: dict[str, Any] = {}
    for k, v in d.items():
        if k in _DETAIL_PII_KEYS:
            result[k] = _REDACTED
        elif isinstance(v, dict):
            result[k] = _redact_dict(v)
        else:
            result[k] = v
    return result


async def _delete_supabase_file(storage_path: str) -> None:
    """Delete a file from Supabase Storage via the REST API.

    Failures are logged but do not raise — erasure continues even if
    the file has already been removed.
    """
    bucket = "resumes"
    url = f"{settings.supabase_url}/storage/v1/object/{bucket}/{storage_path}"
    headers = {
        "Authorization": f"Bearer {settings.supabase_service_key}",
        "apikey": settings.supabase_service_key,
    }
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.delete(url, headers=headers)
        if resp.status_code not in (200, 204, 404):
            logger.warning(
                "Supabase Storage delete returned %s for path %r",
                resp.status_code,
                storage_path,
            )
    except Exception as exc:
        logger.error("Failed to delete Supabase Storage file %r: %s", storage_path, exc)
