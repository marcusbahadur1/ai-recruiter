from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.tenant import Tenant
from app.routers.auth import get_current_tenant
from app.schemas.tenant import TenantResponse, TenantUpdate
from app.services.crypto import encrypt

router = APIRouter(prefix="/tenants", tags=["tenants"])

_ENCRYPTED_FIELDS = {
    "ai_api_key",
    "scrapingdog_api_key",
    "brightdata_api_key",
    "apollo_api_key",
    "hunter_api_key",
    "snov_api_key",
    "sendgrid_api_key",
    "email_inbox_password",
}


@router.get("/me", response_model=TenantResponse)
async def get_me(
    tenant: Tenant = Depends(get_current_tenant),
) -> TenantResponse:
    """Return the authenticated tenant's profile."""
    return TenantResponse.from_orm_with_flags(tenant)


@router.patch("/me", response_model=TenantResponse)
async def update_me(
    body: TenantUpdate,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
) -> TenantResponse:
    """Update the authenticated tenant's profile.

    Sensitive fields (API keys, passwords) are encrypted with Fernet before storage.
    """
    update_data = body.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        if field in _ENCRYPTED_FIELDS and value:
            setattr(tenant, field, encrypt(value))
        else:
            setattr(tenant, field, value)

    await db.commit()

    return TenantResponse.from_orm_with_flags(tenant)
