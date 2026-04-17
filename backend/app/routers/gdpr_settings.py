"""GDPR & Privacy settings routes.

POST /gdpr/export      — export tenant's own data as JSON
POST /gdpr/delete-all  — anonymise all candidates and delete knowledge base
"""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import delete as sa_delete, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.candidate import Candidate
from app.models.rag_document import RagDocument
from app.models.tenant import Tenant
from app.routers.auth import get_current_tenant

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/gdpr", tags=["gdpr"])

_REDACTED = "[REDACTED]"
_CANDIDATE_PII_FIELDS = [
    "name",
    "title",
    "snippet",
    "linkedin_url",
    "email",
    "company",
    "location",
    "outreach_email_content",
]


class DeleteAllRequest(BaseModel):
    confirm: bool = False


class ExportResponse(BaseModel):
    tenant_id: str
    firm_name: str
    main_contact_name: str | None
    main_contact_email: str | None
    phone: str | None
    address: str | None
    website_url: str | None
    plan: str
    created_at: str
    export_note: str


@router.post("/export", response_model=ExportResponse)
async def export_data(
    tenant: Tenant = Depends(get_current_tenant),
) -> ExportResponse:
    """Return a JSON export of the tenant's own account data (GDPR Article 20)."""
    return ExportResponse(
        tenant_id=str(tenant.id),
        firm_name=tenant.name,
        main_contact_name=tenant.main_contact_name,
        main_contact_email=tenant.main_contact_email,
        phone=tenant.phone,
        address=tenant.address,
        website_url=tenant.website_url,
        plan=tenant.plan,
        created_at=tenant.created_at.isoformat(),
        export_note=(
            "This export contains your firm's account data. "
            "Candidate data collected through Talent Scout is governed by your firm's privacy policy "
            "and can be erased per-candidate via the Candidates section."
        ),
    )


@router.post("/delete-all", status_code=status.HTTP_204_NO_CONTENT)
async def delete_all_data(
    body: DeleteAllRequest,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Anonymise all candidate PII and delete the knowledge base for this tenant.

    Requires ``{ "confirm": true }`` in the request body.
    Does NOT delete the tenant account itself — contact support to close your account.
    """
    if not body.confirm:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Set confirm=true to proceed with data deletion",
        )

    pii_updates: dict[str, Any] = {field: _REDACTED for field in _CANDIDATE_PII_FIELDS}
    pii_updates["brightdata_profile"] = {}
    pii_updates["resume_embedding"] = None

    # Batch-anonymise all candidates
    await db.execute(
        update(Candidate).where(Candidate.tenant_id == tenant.id).values(**pii_updates)
    )

    # Delete all RAG documents
    await db.execute(sa_delete(RagDocument).where(RagDocument.tenant_id == tenant.id))

    await db.commit()
    logger.info("gdpr.delete_all: tenant %s data anonymised", tenant.id)
