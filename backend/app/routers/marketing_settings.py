"""Marketing settings router.

Routes (all under /api/v1/marketing):
  GET   /settings — get (or auto-create) marketing settings for the current tenant
  PATCH /settings — update marketing settings with plan-limit validation
  POST  /toggle   — flip settings.is_active for the current tenant
"""
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_marketing_limits, settings as app_settings
from app.database import get_db
from app.models.marketing import MarketingSettings
from app.models.tenant import Tenant
from app.routers.auth import get_current_tenant
from app.schemas.marketing import MarketingSettingsRead, MarketingSettingsUpdate

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/marketing", tags=["marketing-settings"])


# ── Request schemas ────────────────────────────────────────────────────────────


class ToggleRequest(BaseModel):
    is_active: bool


# ── Helpers ───────────────────────────────────────────────────────────────────


def _check_plan(tenant: Tenant) -> None:
    limits = get_marketing_limits(tenant.plan)
    if not limits["marketing_visible"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Marketing module requires Agency Small plan or above (current: {tenant.plan})",
        )


async def _get_or_create_settings(
    tenant_id: uuid.UUID,
    db: AsyncSession,
) -> MarketingSettings:
    """Return the tenant's marketing settings row, creating one from platform defaults if absent."""
    result = await db.execute(
        select(MarketingSettings).where(MarketingSettings.tenant_id == tenant_id)
    )
    s = result.scalar_one_or_none()
    if s:
        return s

    # Copy platform defaults (tenant_id IS NULL row), but disable until account connected
    defaults_result = await db.execute(
        select(MarketingSettings).where(MarketingSettings.tenant_id.is_(None))
    )
    defaults = defaults_result.scalar_one_or_none()

    s = MarketingSettings(
        tenant_id=tenant_id,
        post_frequency=defaults.post_frequency if defaults else "twice_weekly",
        post_time_utc=defaults.post_time_utc if defaults else None,
        post_types_enabled=(
            list(defaults.post_types_enabled)
            if defaults
            else ["thought_leadership", "industry_stat", "tip"]
        ),
        platforms_enabled=list(defaults.platforms_enabled) if defaults else ["linkedin"],
        target_audience=defaults.target_audience if defaults else None,
        tone=defaults.tone if defaults else "professional",
        topics=list(defaults.topics) if defaults else [],
        auto_engage=defaults.auto_engage if defaults else False,
        engagement_per_day=defaults.engagement_per_day if defaults else 10,
        requires_approval=defaults.requires_approval if defaults else True,
        include_images=defaults.include_images if defaults else True,
        is_active=False,  # disabled until the tenant connects a LinkedIn account
    )
    db.add(s)
    await db.commit()
    await db.refresh(s)
    logger.info("Marketing settings auto-created for tenant %s", tenant_id)
    return s


# ── Routes ─────────────────────────────────────────────────────────────────────


@router.get("/settings", response_model=MarketingSettingsRead)
async def get_settings(
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
) -> MarketingSettingsRead:
    _check_plan(tenant)
    s = await _get_or_create_settings(tenant.id, db)
    return MarketingSettingsRead.model_validate(s)


@router.patch("/settings", response_model=MarketingSettingsRead)
async def update_settings(
    body: MarketingSettingsUpdate,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
) -> MarketingSettingsRead:
    _check_plan(tenant)
    limits = get_marketing_limits(tenant.plan)
    s = await _get_or_create_settings(tenant.id, db)

    # Plan-gate: auto_engage requires Agency Medium+
    if body.auto_engage is True and not limits["auto_engage"]:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="auto_engage requires Agency Medium plan or above",
        )

    # Apply all provided fields
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(s, field, value)

    await db.commit()
    await db.refresh(s)
    logger.info("Marketing settings updated for tenant %s", tenant.id)
    return MarketingSettingsRead.model_validate(s)


@router.post("/toggle", response_model=MarketingSettingsRead)
async def toggle_marketing(
    body: ToggleRequest,
    tenant_id_override: uuid.UUID | None = Query(None, alias="tenant_id"),
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
) -> MarketingSettingsRead:
    """Flip settings.is_active.

    Super admin can pass ?tenant_id= to toggle any tenant or the platform
    account (pass tenant_id=null-equivalent by omitting the param with
    tenant_id=00000000-0000-0000-0000-000000000000 as a sentinel, or leave
    it absent to toggle the platform row when called from super admin context).
    """
    is_super = getattr(tenant, "_is_super_admin", False)

    if tenant_id_override is not None and not is_super:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Super admin access required to toggle another tenant's marketing",
        )

    # Determine which settings row to toggle
    if is_super and tenant_id_override is not None:
        result = await db.execute(
            select(MarketingSettings).where(
                MarketingSettings.tenant_id == tenant_id_override
            )
        )
        s = result.scalar_one_or_none()
        if not s:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Settings not found")
    elif is_super and tenant_id_override is None:
        # Super admin toggling the platform-level row
        result = await db.execute(
            select(MarketingSettings).where(MarketingSettings.tenant_id.is_(None))
        )
        s = result.scalar_one_or_none()
        if not s:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Platform marketing settings not found",
            )
    else:
        _check_plan(tenant)
        s = await _get_or_create_settings(tenant.id, db)

    s.is_active = body.is_active
    await db.commit()
    await db.refresh(s)
    logger.info(
        "Marketing toggled is_active=%s tenant_id=%s by=%s",
        body.is_active,
        s.tenant_id,
        tenant.id,
    )
    return MarketingSettingsRead.model_validate(s)
