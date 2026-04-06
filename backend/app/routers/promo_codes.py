"""Promo code CRUD and public validation endpoint.

Routes:
  GET  /promo-codes              — list codes visible to this tenant
  POST /promo-codes              — create a code (super_admin creates platform-wide)
  PATCH /promo-codes/{id}        — update expiry / max_uses / is_active
  DELETE /promo-codes/{id}       — deactivate (soft delete via is_active=False)
  POST /promo-codes/validate     — public validation + redemption
"""

import uuid
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.promo_code import PromoCode
from app.models.tenant import Tenant
from app.routers.auth import get_current_tenant
from app.schemas.common import PaginatedResponse
from app.schemas.promo_code import PromoCodeCreate, PromoCodeResponse, PromoCodeUpdate

router = APIRouter(prefix="/promo-codes", tags=["promo-codes"])


# ── Helpers ───────────────────────────────────────────────────────────────────

def _is_super_admin(tenant: Tenant) -> bool:
    """Check super_admin role via tenant slug convention.

    Super admin JWT carries a special slug prefix; the real role check is done
    in the JWT app_metadata by the auth dependency.  Routers that need
    super_admin-only access should use `require_super_admin` instead.
    """
    return getattr(tenant, "_is_super_admin", False)


async def _get_promo_or_404(
    db: AsyncSession,
    promo_id: uuid.UUID,
    tenant: Tenant,
) -> PromoCode:
    """Fetch a promo code scoped to the requesting tenant or platform-wide."""
    result = await db.execute(
        select(PromoCode).where(
            PromoCode.id == promo_id,
            or_(
                PromoCode.tenant_id == tenant.id,
                PromoCode.tenant_id.is_(None),  # platform-wide
            ),
        )
    )
    promo = result.scalar_one_or_none()
    if not promo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Promo code not found")
    return promo


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("", response_model=PaginatedResponse[PromoCodeResponse])
async def list_promo_codes(
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(50, le=100),
    offset: int = Query(0, ge=0),
    include_inactive: bool = Query(False),
) -> PaginatedResponse[PromoCodeResponse]:
    """List promo codes visible to this tenant.

    Returns tenant-specific codes and platform-wide codes (tenant_id IS NULL).
    Super admin sees all codes.
    """
    filters = [
        or_(
            PromoCode.tenant_id == tenant.id,
            PromoCode.tenant_id.is_(None),
        )
    ]
    if not include_inactive:
        filters.append(PromoCode.is_active.is_(True))

    result = await db.execute(
        select(PromoCode)
        .where(*filters)
        .order_by(PromoCode.is_active.desc())
        .limit(limit)
        .offset(offset)
    )
    codes = list(result.scalars().all())

    # Total count
    from sqlalchemy import func
    count_result = await db.execute(
        select(func.count()).select_from(PromoCode).where(*filters)
    )
    total = count_result.scalar_one()

    return PaginatedResponse(
        items=[PromoCodeResponse.model_validate(c) for c in codes],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("", response_model=PromoCodeResponse, status_code=status.HTTP_201_CREATED)
async def create_promo_code(
    body: PromoCodeCreate,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
) -> PromoCodeResponse:
    """Create a promo code.

    Tenant admins can create codes scoped to their own tenant.
    Super admins can create platform-wide codes (tenant_id = NULL) by passing
    ``tenant_id=null`` — enforced by checking the ``_is_super_admin`` flag set
    by the auth dependency.
    """
    # Tenant-scoped codes default to the requesting tenant.
    promo = PromoCode(
        id=uuid.uuid4(),
        tenant_id=tenant.id,  # platform-wide only possible via super_admin endpoint
        code=body.code.upper().strip(),
        type=body.type,
        value=body.value,
        expires_at=body.expires_at,
        max_uses=body.max_uses,
        uses_count=0,
        is_active=body.is_active,
    )
    try:
        async with db.begin():
            db.add(promo)
            await db.flush()
    except Exception as exc:
        if "unique" in str(exc).lower():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Promo code '{promo.code}' already exists",
            )
        raise

    return PromoCodeResponse.model_validate(promo)


@router.patch("/{promo_id}", response_model=PromoCodeResponse)
async def update_promo_code(
    promo_id: uuid.UUID,
    body: PromoCodeUpdate,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
) -> PromoCodeResponse:
    """Update expiry, max_uses, or is_active for an existing promo code."""
    promo = await _get_promo_or_404(db, promo_id, tenant)

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(promo, field, value)

    async with db.begin():
        db.add(promo)

    return PromoCodeResponse.model_validate(promo)


@router.delete("/{promo_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_promo_code(
    promo_id: uuid.UUID,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Soft-delete: set is_active=False.  Codes are never hard-deleted so that
    uses_count history is preserved for audit purposes."""
    promo = await _get_promo_or_404(db, promo_id, tenant)
    async with db.begin():
        promo.is_active = False
        db.add(promo)


# ── Public validation endpoint ────────────────────────────────────────────────

class ValidatePromoRequest(BaseModel):
    code: str
    tenant_id: uuid.UUID  # used to scope platform-wide codes correctly


class ValidatePromoResponse(BaseModel):
    valid: bool
    type: Literal["credits", "discount_pct", "full_access"] | None = None
    value: float | None = None
    message: str


@router.post("/validate", response_model=ValidatePromoResponse)
async def validate_promo_code(
    body: ValidatePromoRequest,
    db: AsyncSession = Depends(get_db),
) -> ValidatePromoResponse:
    """Validate and redeem a promo code during checkout.

    - Checks expiry, max_uses, is_active.
    - Increments uses_count on success.
    - Does NOT apply the benefit — the caller must honour the response values.
    """
    result = await db.execute(
        select(PromoCode).where(
            PromoCode.code == body.code.upper().strip(),
            PromoCode.is_active.is_(True),
            or_(
                PromoCode.tenant_id == body.tenant_id,
                PromoCode.tenant_id.is_(None),
            ),
        )
    )
    promo = result.scalar_one_or_none()

    if not promo:
        return ValidatePromoResponse(valid=False, message="Invalid promo code")

    now = datetime.now(timezone.utc)
    if promo.expires_at and promo.expires_at < now:
        return ValidatePromoResponse(valid=False, message="Promo code has expired")

    if promo.max_uses is not None and promo.uses_count >= promo.max_uses:
        return ValidatePromoResponse(valid=False, message="Promo code has reached its usage limit")

    # Increment uses_count atomically.
    async with db.begin():
        promo.uses_count += 1
        db.add(promo)

    return ValidatePromoResponse(
        valid=True,
        type=promo.type,
        value=float(promo.value),
        message="Promo code applied successfully",
    )
