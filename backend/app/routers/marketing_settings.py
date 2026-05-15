"""Marketing settings router.

Routes (all under /api/v1/marketing):
  GET   /settings           — get (or auto-create) marketing settings for the current tenant
  PATCH /settings           — update marketing settings with plan-limit validation
  POST  /toggle             — flip settings.is_active for the current tenant
  GET   /tenant-status      — pipeline access status + usage stats (sidebar gating + onboarding)
  GET   /admin/tenant-usage — super admin only: per-tenant usage table
"""
import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import and_, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_marketing_limits, settings as app_settings
from app.database import get_db
from app.models.marketing import MarketingAccount, MarketingProspect, MarketingSequence, MarketingSettings
from app.models.tenant import Tenant
from app.routers.auth import get_current_tenant
from app.schemas.marketing import (
    AdminTenantUsageResponse,
    MarketingSettingsRead,
    MarketingSettingsUpdate,
    TenantStatusResponse,
    TenantUsageRow,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/marketing", tags=["marketing-settings"])


# ── Request schemas ────────────────────────────────────────────────────────────


class ToggleRequest(BaseModel):
    is_active: bool


# ── Helpers ───────────────────────────────────────────────────────────────────


def _check_plan(tenant: Tenant) -> None:
    is_super = getattr(tenant, "_is_super_admin", False) or tenant.slug == "super-admin"
    if is_super:
        return
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
        # Client pipeline defaults for tenants
        icp_config={},
        signal_config=defaults.signal_config if defaults and defaults.signal_config else {},
        outreach_limits=defaults.outreach_limits if defaults and defaults.outreach_limits else {},
        tenant_mode_enabled=False,  # tenants cannot enable sub-tenant mode
        tenant_mode_config=None,
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

    # Super admin: propagate tenant_mode_enabled / tenant_mode_config to the
    # platform NULL row so that get_tenant_status sees the updated value.
    # Create the platform row if it doesn't exist yet.
    is_super = _is_super_admin_tenant(tenant)
    if is_super and (body.tenant_mode_enabled is not None or body.tenant_mode_config is not None):
        platform_result = await db.execute(
            select(MarketingSettings).where(MarketingSettings.tenant_id.is_(None))
        )
        platform_row = platform_result.scalar_one_or_none()
        if platform_row is None:
            platform_row = MarketingSettings(
                tenant_id=None,
                post_frequency="twice_weekly",
                platforms_enabled=["linkedin"],
                post_types_enabled=["thought_leadership", "industry_stat", "tip"],
                tone="professional",
                topics=[],
                auto_engage=False,
                engagement_per_day=10,
                requires_approval=True,
                include_images=True,
                is_active=False,
                tenant_mode_enabled=False,
                tenant_mode_config=None,
            )
            db.add(platform_row)
        if body.tenant_mode_enabled is not None:
            platform_row.tenant_mode_enabled = body.tenant_mode_enabled
        if body.tenant_mode_config is not None:
            platform_row.tenant_mode_config = body.tenant_mode_config
        await db.commit()

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


# ── Plan ordering helper ──────────────────────────────────────────────────────

_PLAN_ORDER = ["trial", "trial_expired", "recruiter", "agency_small", "agency_medium", "enterprise"]


def _plan_gte(plan: str, min_plan: str) -> bool:
    """Return True if plan >= min_plan in hierarchy."""
    try:
        return _PLAN_ORDER.index(plan) >= _PLAN_ORDER.index(min_plan)
    except ValueError:
        return False


def _is_super_admin_tenant(tenant: Tenant) -> bool:
    return getattr(tenant, "_is_super_admin", False) or tenant.slug == "super-admin"


# ── GET /tenant-status ────────────────────────────────────────────────────────


@router.get("/tenant-status", response_model=TenantStatusResponse)
async def get_tenant_status(
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
) -> TenantStatusResponse:
    """Return the current user's pipeline access status and usage counts.

    Used by the frontend sidebar for gating and by the page for onboarding.
    Works for both super admin and regular tenants.
    """
    is_super = _is_super_admin_tenant(tenant)

    # ── Fetch platform-level settings (tenant_id IS NULL) ──────────────────
    platform_result = await db.execute(
        select(MarketingSettings).where(MarketingSettings.tenant_id.is_(None))
    )
    platform_settings = platform_result.scalar_one_or_none()
    platform_tenant_mode_enabled: bool = (
        bool(platform_settings.tenant_mode_enabled) if platform_settings else False
    )
    tenant_mode_config: dict = (
        platform_settings.tenant_mode_config or {} if platform_settings else {}
    )
    min_plan: str = tenant_mode_config.get("min_plan", "agency_small")

    # ── Super admin always has access ──────────────────────────────────────
    if is_super:
        this_month_start = datetime.now(timezone.utc).replace(
            day=1, hour=0, minute=0, second=0, microsecond=0
        )
        prospect_count_result = await db.execute(
            select(func.count()).where(
                and_(
                    MarketingProspect.tenant_id == tenant.id,
                    MarketingProspect.created_at >= this_month_start,
                )
            )
        )
        seq_count_result = await db.execute(
            select(func.count()).where(MarketingSequence.tenant_id == tenant.id)
        )
        has_li_result = await db.execute(
            select(MarketingAccount).where(
                and_(
                    MarketingAccount.tenant_id == tenant.id,
                    MarketingAccount.platform == "linkedin",
                    MarketingAccount.is_active.is_(True),
                )
            )
        )
        return TenantStatusResponse(
            is_super_admin=True,
            has_pipeline_access=True,
            has_linkedin=has_li_result.scalar_one_or_none() is not None,
            has_hunter=False,
            this_month_prospects=prospect_count_result.scalar_one() or 0,
            sequences_used=seq_count_result.scalar_one() or 0,
            is_new_user=False,
        )

    # ── Regular tenant — check access ──────────────────────────────────────
    if not platform_tenant_mode_enabled:
        return TenantStatusResponse(
            is_super_admin=False,
            has_pipeline_access=False,
            access_denied_reason="tenant_mode_disabled",
            min_plan=min_plan,
            has_linkedin=False,
            has_hunter=False,
            this_month_prospects=0,
            sequences_used=0,
            is_new_user=True,
        )

    if not _plan_gte(tenant.plan, min_plan):
        return TenantStatusResponse(
            is_super_admin=False,
            has_pipeline_access=False,
            access_denied_reason="plan_too_low",
            min_plan=min_plan,
            has_linkedin=False,
            has_hunter=False,
            this_month_prospects=0,
            sequences_used=0,
            is_new_user=True,
        )

    # Tenant has access — collect usage stats
    this_month_start = datetime.now(timezone.utc).replace(
        day=1, hour=0, minute=0, second=0, microsecond=0
    )
    prospect_count_result = await db.execute(
        select(func.count()).where(
            and_(
                MarketingProspect.tenant_id == tenant.id,
                MarketingProspect.created_at >= this_month_start,
            )
        )
    )
    seq_count_result = await db.execute(
        select(func.count()).where(MarketingSequence.tenant_id == tenant.id)
    )
    this_month_prospects = prospect_count_result.scalar_one() or 0
    sequences_used = seq_count_result.scalar_one() or 0

    li_result = await db.execute(
        select(MarketingAccount).where(
            and_(
                MarketingAccount.tenant_id == tenant.id,
                MarketingAccount.platform == "linkedin",
                MarketingAccount.is_active.is_(True),
            )
        )
    )
    has_linkedin = li_result.scalar_one_or_none() is not None

    tenant_settings_result = await db.execute(
        select(MarketingSettings).where(MarketingSettings.tenant_id == tenant.id)
    )
    tenant_settings = tenant_settings_result.scalar_one_or_none()
    has_hunter = bool(
        tenant_settings
        and tenant_settings.channel_config
        and tenant_settings.channel_config.get("hunter_api_key")
    )
    icp_set = bool(
        tenant_settings
        and tenant_settings.icp_config
        and (
            tenant_settings.icp_config.get("target_titles")
            or tenant_settings.icp_config.get("company_types")
            or tenant_settings.icp_config.get("locations")
        )
    )

    return TenantStatusResponse(
        is_super_admin=False,
        has_pipeline_access=True,
        min_plan=min_plan,
        has_linkedin=has_linkedin,
        has_hunter=has_hunter,
        this_month_prospects=this_month_prospects,
        prospect_month_limit=tenant_mode_config.get("max_prospects_per_month"),
        sequences_used=sequences_used,
        sequence_limit=tenant_mode_config.get("max_sequences"),
        is_new_user=(this_month_prospects == 0 and sequences_used == 0 and not icp_set),
    )


# ── GET /admin/tenant-usage ───────────────────────────────────────────────────


@router.get("/admin/tenant-usage", response_model=AdminTenantUsageResponse)
async def get_admin_tenant_usage(
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
) -> AdminTenantUsageResponse:
    """Super admin only — return per-tenant pipeline usage stats."""
    if not _is_super_admin_tenant(tenant):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Super admin only")

    this_month_start = datetime.now(timezone.utc).replace(
        day=1, hour=0, minute=0, second=0, microsecond=0
    )

    rows_result = await db.execute(
        text(
            """
            SELECT
                t.id                                                        AS tenant_id,
                t.name                                                      AS tenant_name,
                t.plan,
                COUNT(DISTINCT p.id) FILTER (
                    WHERE p.created_at >= :month_start
                )                                                           AS prospects_this_month,
                COUNT(DISTINCT s.id)                                        AS sequences_count,
                BOOL_OR(ma.id IS NOT NULL AND ma.is_active)                 AS has_linkedin,
                MAX(p.last_activity_at)                                     AS last_active
            FROM tenants t
            LEFT JOIN marketing_prospects p  ON p.tenant_id = t.id
            LEFT JOIN marketing_sequences s  ON s.tenant_id = t.id
            LEFT JOIN marketing_accounts ma  ON ma.tenant_id = t.id AND ma.platform = 'linkedin'
            WHERE t.is_active = true
              AND t.slug != 'super-admin'
            GROUP BY t.id, t.name, t.plan
            ORDER BY prospects_this_month DESC, t.name
            """
        ),
        {"month_start": this_month_start},
    )

    result_rows: list[TenantUsageRow] = []
    for row in rows_result.fetchall():
        last_active: str | None = None
        if row.last_active:
            ts = row.last_active
            last_active = ts.isoformat() if hasattr(ts, "isoformat") else str(ts)
        result_rows.append(
            TenantUsageRow(
                tenant_id=str(row.tenant_id),
                tenant_name=row.tenant_name,
                plan=row.plan,
                prospects_this_month=int(row.prospects_this_month or 0),
                sequences_count=int(row.sequences_count or 0),
                has_linkedin=bool(row.has_linkedin),
                last_active=last_active,
            )
        )

    return AdminTenantUsageResponse(rows=result_rows)
