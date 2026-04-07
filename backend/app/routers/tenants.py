from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.tenant import Tenant
from app.routers.auth import get_current_tenant
from app.schemas.tenant import TenantResponse, TenantUpdate

router = APIRouter(prefix="/tenants", tags=["tenants"])


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

    Encrypted API key fields are accepted as plaintext here and must be
    encrypted before storage in the service layer.
    # TODO: move encryption into a services/tenant.py service method
    """
    update_data = body.model_dump(exclude_unset=True)

    # Encrypted fields — store raw value for now; encryption added in service layer
    # TODO: encrypt api key fields via services/encryption.py before assigning
    for field, value in update_data.items():
        setattr(tenant, field, value)

    await db.commit()

    return TenantResponse.from_orm_with_flags(tenant)
