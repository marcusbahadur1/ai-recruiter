"""LinkedIn Pages router — discover and manage connected pages per tenant.

Routes (all under /api/v1/marketing/linkedin):
  GET  /pages          — list all linkedin_pages for current tenant
  POST /pages/sync     — trigger syncLinkedInPages (refresh from LinkedIn API)
  PATCH /pages/{id}    — update is_active toggle for a page
"""
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.marketing import LinkedInPage, MarketingAccount
from app.models.tenant import Tenant
from app.routers.auth import get_current_tenant
from app.services.marketing.publish_service import sync_linkedin_pages

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/marketing/linkedin", tags=["marketing-linkedin-pages"])


# ── Schemas ────────────────────────────────────────────────────────────────────

class LinkedInPageRead(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    linkedin_account_id: uuid.UUID
    page_type: str               # personal | company | showcase
    page_name: str
    page_urn: str
    page_id: str
    vanity_name: str | None
    logo_url: str | None
    follower_count: int | None
    is_active: bool
    last_synced_at: str | None
    created_at: str

    class Config:
        from_attributes = True

    @classmethod
    def from_orm(cls, p: LinkedInPage) -> "LinkedInPageRead":
        return cls(
            id=p.id,
            tenant_id=p.tenant_id,
            linkedin_account_id=p.linkedin_account_id,
            page_type=p.page_type,
            page_name=p.page_name,
            page_urn=p.page_urn,
            page_id=p.page_id,
            vanity_name=p.vanity_name,
            logo_url=p.logo_url,
            follower_count=p.follower_count,
            is_active=p.is_active,
            last_synced_at=p.last_synced_at.isoformat() if p.last_synced_at else None,
            created_at=p.created_at.isoformat(),
        )


class UpdatePageRequest(BaseModel):
    is_active: bool


class SyncResponse(BaseModel):
    pages_synced: int
    pages: list[LinkedInPageRead]


# ── Routes ─────────────────────────────────────────────────────────────────────

@router.get("/pages", response_model=list[LinkedInPageRead])
async def list_pages(
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
) -> list[LinkedInPageRead]:
    """Return all discovered LinkedIn pages for the current tenant."""
    result = await db.execute(
        select(LinkedInPage)
        .where(LinkedInPage.tenant_id == tenant.id)
        .order_by(LinkedInPage.page_type, LinkedInPage.page_name)
    )
    pages = result.scalars().all()
    return [LinkedInPageRead.from_orm(p) for p in pages]


@router.post("/pages/sync", response_model=SyncResponse)
async def sync_pages(
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
) -> SyncResponse:
    """Re-discover LinkedIn pages for this tenant's connected account.

    Calls the LinkedIn API to fetch the personal profile and all admin pages
    (company + showcase). Requires w_organization_social scope for company
    and showcase pages — if missing, only the personal profile is synced.
    """
    # Find active LinkedIn account for this tenant
    account_result = await db.execute(
        select(MarketingAccount).where(
            MarketingAccount.tenant_id == tenant.id,
            MarketingAccount.is_active.is_(True),
        )
    )
    account = account_result.scalars().first()
    if not account:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No active LinkedIn account connected — connect one first",
        )

    if account.needs_reconnect:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="LinkedIn token expired — please reconnect your LinkedIn account",
        )

    access_token, _ = account.get_decrypted_tokens()

    try:
        pages = await sync_linkedin_pages(
            tenant_id=tenant.id,
            account_id=account.id,
            access_token=access_token,
            db=db,
        )
    except Exception as exc:
        logger.error("Pages sync failed tenant=%s: %s", tenant.id, exc)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Page sync failed: {exc}",
        )

    return SyncResponse(
        pages_synced=len(pages),
        pages=[LinkedInPageRead.from_orm(p) for p in pages],
    )


@router.patch("/pages/{page_id}", response_model=LinkedInPageRead)
async def update_page(
    page_id: uuid.UUID,
    body: UpdatePageRequest,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
) -> LinkedInPageRead:
    """Toggle is_active for a LinkedIn page (hide it from post targeting)."""
    result = await db.execute(
        select(LinkedInPage).where(
            LinkedInPage.id == page_id,
            LinkedInPage.tenant_id == tenant.id,
        )
    )
    page = result.scalar_one_or_none()
    if not page:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Page not found")

    page.is_active = body.is_active
    await db.commit()
    await db.refresh(page)
    return LinkedInPageRead.from_orm(page)
