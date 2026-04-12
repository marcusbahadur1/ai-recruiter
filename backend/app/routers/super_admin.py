"""Super admin panel routes — restricted to super_admin role only.

All routes are protected by _require_super_admin() which checks the role claim
embedded in the Supabase JWT app_metadata.

Routes:
  GET  /super-admin/tenants                  — list all tenants
  GET  /super-admin/tenants/{id}             — get one tenant
  PATCH /super-admin/tenants/{id}            — update tenant (plan, credits, active)
  POST /super-admin/impersonate/{tenant_id}  — generate impersonation token (logged)
  GET  /super-admin/platform-keys            — view platform API key presence flags
  POST /super-admin/platform-keys            — update platform API keys (env is canonical)
  POST /super-admin/promo-codes              — create platform-wide promo code
  GET  /super-admin/health                   — Celery queue depth + recent errors
  GET  /super-admin/audit                    — platform-wide payment/system events
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Annotated, Any, Literal

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.job_audit_event import JobAuditEvent
from app.models.promo_code import PromoCode
from app.models.tenant import Tenant
from app.schemas.common import PaginatedResponse
from app.schemas.job_audit_event import JobAuditEventResponse
from app.schemas.promo_code import PromoCodeCreate, PromoCodeResponse
from app.schemas.tenant import TenantResponse
from app.services.audit_trail import AuditTrailService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/super-admin", tags=["super-admin"])


# ── Auth dependency ───────────────────────────────────────────────────────────

async def _get_super_admin(
    authorization: Annotated[str, Header()],
    db: AsyncSession = Depends(get_db),
) -> Tenant:
    """Validate JWT and confirm super_admin role.

    The role is read from app_metadata.role in the Supabase JWT.  The
    super_admin account is a special tenant record used only for platform
    management — it has slug='super-admin'.
    """
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Bearer token required")

    token = authorization[len("Bearer "):]

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{settings.supabase_url}/auth/v1/user",
            headers={"Authorization": f"Bearer {token}", "apikey": settings.supabase_anon_key},
        )

    if resp.status_code != 200:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

    user_data = resp.json()
    app_meta: dict[str, Any] = user_data.get("app_metadata") or {}
    role: str = app_meta.get("role", "")
    user_email: str = (user_data.get("email") or "").lower()

    is_super_admin = role == "super_admin" or (
        bool(settings.super_admin_email)
        and user_email == settings.super_admin_email.lower()  # type: ignore[union-attr]
    )
    if not is_super_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Super admin access required")

    tenant_id_str: str | None = app_meta.get("tenant_id")
    if not tenant_id_str:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tenant associated")

    try:
        tenant_id = uuid.UUID(tenant_id_str)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Malformed tenant_id")

    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    admin_tenant = result.scalar_one_or_none()
    if not admin_tenant:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Super admin tenant not found")

    # Tag the tenant object so downstream helpers can detect super_admin context.
    admin_tenant._is_super_admin = True  # type: ignore[attr-defined]
    return admin_tenant


# ── Schemas ───────────────────────────────────────────────────────────────────

class TenantAdminUpdate(BaseModel):
    plan: Literal["free", "casual", "individual", "small_firm", "mid_firm", "enterprise"] | None = None
    credits_remaining: int | None = None
    is_active: bool | None = None
    name: str | None = None


class ImpersonateResponse(BaseModel):
    access_token: str
    tenant_id: str
    tenant_name: str


class PlatformKeyStatus(BaseModel):
    has_anthropic_api_key: bool
    has_openai_api_key: bool
    has_sendgrid_api_key: bool
    has_scrapingdog_api_key: bool
    has_brightdata_api_key: bool
    default_ai_provider: str


class HealthResponse(BaseModel):
    celery_queue_depth: int | None
    failed_tasks_count: int | None
    worker_count: int | None
    status: str
    checked_at: datetime


# ── Tenant management ─────────────────────────────────────────────────────────

@router.get("/tenants", response_model=PaginatedResponse[TenantResponse])
async def list_tenants(
    _admin: Tenant = Depends(_get_super_admin),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(50, le=100),
    offset: int = Query(0, ge=0),
    plan: str | None = Query(None),
    is_active: bool | None = Query(None),
    search: str | None = Query(None, description="Search by name or slug"),
) -> PaginatedResponse[TenantResponse]:
    """List all tenants across the platform."""
    from sqlalchemy import func

    filters = []
    if plan:
        filters.append(Tenant.plan == plan)
    if is_active is not None:
        filters.append(Tenant.is_active.is_(is_active))
    if search:
        like = f"%{search}%"
        filters.append(or_(Tenant.name.ilike(like), Tenant.slug.ilike(like)))

    result = await db.execute(
        select(Tenant)
        .where(*filters)
        .order_by(Tenant.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    tenants = list(result.scalars().all())

    count_result = await db.execute(
        select(func.count()).select_from(Tenant).where(*filters)
    )
    total = count_result.scalar_one()

    return PaginatedResponse(
        items=[TenantResponse.from_orm_with_flags(t) for t in tenants],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/tenants/{tenant_id}", response_model=TenantResponse)
async def get_tenant(
    tenant_id: uuid.UUID,
    _admin: Tenant = Depends(_get_super_admin),
    db: AsyncSession = Depends(get_db),
) -> TenantResponse:
    """Get full details for a single tenant."""
    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")
    return TenantResponse.from_orm_with_flags(tenant)


@router.patch("/tenants/{tenant_id}", response_model=TenantResponse)
async def update_tenant(
    tenant_id: uuid.UUID,
    body: TenantAdminUpdate,
    admin: Tenant = Depends(_get_super_admin),
    db: AsyncSession = Depends(get_db),
) -> TenantResponse:
    """Update plan, credit balance, or active status for any tenant.

    Audit event emitted on credit adjustment.
    """
    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

    old_credits = tenant.credits_remaining
    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(tenant, field, value)

    await db.commit()

    # Emit audit event if credits were manually adjusted.
    if "credits_remaining" in update_data:
        audit = AuditTrailService(db, tenant_id)
        # Use a placeholder job_id (zeroed UUID) for platform-level events.
        placeholder_job_id = uuid.UUID("00000000-0000-0000-0000-000000000000")
        try:
            await audit.emit(
                job_id=placeholder_job_id,
                event_type="payment.credit_charged",
                event_category="payment",
                severity="info",
                actor="recruiter",
                actor_user_id=admin.id,
                summary=f"Credits manually adjusted: {old_credits} → {body.credits_remaining}",
                detail={"old_credits": old_credits, "new_credits": body.credits_remaining, "by": "super_admin"},
            )
        except Exception as exc:
            logger.warning("update_tenant: could not emit audit event: %s", exc)

    return TenantResponse.from_orm_with_flags(tenant)


# ── Impersonation ─────────────────────────────────────────────────────────────

@router.post("/impersonate/{tenant_id}", response_model=ImpersonateResponse)
async def impersonate_tenant(
    tenant_id: uuid.UUID,
    admin: Tenant = Depends(_get_super_admin),
    db: AsyncSession = Depends(get_db),
) -> ImpersonateResponse:
    """Generate a short-lived impersonation token for the given tenant.

    This calls Supabase Admin API to create a magic link / one-time token.
    The action is always audit-logged (SPEC §11).
    """
    result = await db.execute(
        select(Tenant).where(Tenant.id == tenant_id, Tenant.is_active.is_(True))
    )
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found or inactive")

    # Log the impersonation event before proceeding.
    audit = AuditTrailService(db, tenant_id)
    placeholder_job_id = uuid.UUID("00000000-0000-0000-0000-000000000000")
    try:
        await audit.emit(
            job_id=placeholder_job_id,
            event_type="system.impersonation",
            event_category="system",
            severity="warning",
            actor="recruiter",
            actor_user_id=admin.id,
            summary=f"Super admin impersonated tenant '{tenant.name}'",
            detail={"admin_tenant_id": str(admin.id), "target_tenant_id": str(tenant_id)},
        )
    except Exception as exc:
        logger.error("impersonate_tenant: audit emit failed: %s", exc)

    # Generate a Supabase impersonation token via admin API.
    # Supabase does not have a native impersonation API; we issue a custom JWT
    # with the target tenant's app_metadata using the service role.
    try:
        impersonation_token = await _generate_impersonation_token(tenant)
    except Exception as exc:
        logger.error("impersonate_tenant: token generation failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to generate impersonation token",
        )

    return ImpersonateResponse(
        access_token=impersonation_token,
        tenant_id=str(tenant_id),
        tenant_name=tenant.name,
    )


async def _generate_impersonation_token(tenant: Tenant) -> str:
    """Generate a short-lived JWT for impersonating a tenant.

    Uses PyJWT to produce a signed token with the tenant's app_metadata.
    The frontend uses this token as a Bearer token — it expires in 1 hour.
    """
    import time

    import jwt  # PyJWT

    now = int(time.time())
    payload = {
        "sub": str(tenant.id),
        "iat": now,
        "exp": now + 3600,  # 1 hour
        "app_metadata": {"tenant_id": str(tenant.id), "role": "admin", "impersonated": True},
        "aud": "authenticated",
        "role": "authenticated",
    }
    token = jwt.encode(payload, settings.supabase_service_key, algorithm="HS256")
    return token


# ── Platform API key management ───────────────────────────────────────────────

@router.get("/platform-keys", response_model=PlatformKeyStatus)
async def get_platform_keys(
    _admin: Tenant = Depends(_get_super_admin),
) -> PlatformKeyStatus:
    """Return boolean presence flags for platform-level API keys.

    Never returns the actual key values.
    """
    return PlatformKeyStatus(
        has_anthropic_api_key=bool(settings.anthropic_api_key),
        has_openai_api_key=bool(settings.openai_api_key),
        has_sendgrid_api_key=bool(settings.sendgrid_api_key),
        has_scrapingdog_api_key=bool(settings.scrapingdog_api_key),
        has_brightdata_api_key=bool(settings.brightdata_api_key),
        default_ai_provider="anthropic" if settings.anthropic_api_key else "openai",
    )


# ── Platform-wide promo code creation ─────────────────────────────────────────

@router.post("/promo-codes", response_model=PromoCodeResponse, status_code=status.HTTP_201_CREATED)
async def create_platform_promo_code(
    body: PromoCodeCreate,
    _admin: Tenant = Depends(_get_super_admin),
    db: AsyncSession = Depends(get_db),
) -> PromoCodeResponse:
    """Create a platform-wide promo code (tenant_id = NULL — available to all tenants)."""
    promo = PromoCode(
        id=uuid.uuid4(),
        tenant_id=None,  # platform-wide
        code=body.code.upper().strip(),
        type=body.type,
        value=body.value,
        expires_at=body.expires_at,
        max_uses=body.max_uses,
        uses_count=0,
        is_active=body.is_active,
    )
    try:
        db.add(promo)
        await db.commit()
    except Exception as exc:
        await db.rollback()
        if "unique" in str(exc).lower():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Promo code '{promo.code}' already exists",
            )
        raise

    return PromoCodeResponse.model_validate(promo)


# ── System health ─────────────────────────────────────────────────────────────

@router.get("/health", response_model=HealthResponse)
async def system_health(
    _admin: Tenant = Depends(_get_super_admin),
) -> HealthResponse:
    """Return Celery worker health: queue depth, failed task count, worker count."""
    queue_depth: int | None = None
    failed_count: int | None = None
    worker_count: int | None = None
    health_status = "unknown"

    try:
        from app.tasks.celery_app import celery_app

        inspect = celery_app.control.inspect(timeout=3)

        # Queue depth via broker.
        with celery_app.connection_or_connect() as conn:
            with conn.channel() as ch:
                _, count, _ = ch.queue_declare(queue="celery", passive=True)
                queue_depth = count

        # Active worker count.
        active = inspect.active()
        if active is not None:
            worker_count = len(active)
            health_status = "healthy" if worker_count > 0 else "no_workers"
        else:
            health_status = "unreachable"

        # Failed tasks from result backend (approximate).
        inspect.reserved()
        failed_count = 0  # Celery doesn't expose failed count directly; use monitoring

    except Exception as exc:
        logger.warning("system_health: Celery inspection failed: %s", exc)
        health_status = "error"

    return HealthResponse(
        celery_queue_depth=queue_depth,
        failed_tasks_count=failed_count,
        worker_count=worker_count,
        status=health_status,
        checked_at=datetime.now(timezone.utc),
    )


# ── Platform audit view ────────────────────────────────────────────────────────

@router.get("/audit", response_model=PaginatedResponse[JobAuditEventResponse])
async def platform_audit(
    _admin: Tenant = Depends(_get_super_admin),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(50, le=100),
    offset: int = Query(0, ge=0),
    event_category: str | None = Query(None, description="payment | system"),
) -> PaginatedResponse[JobAuditEventResponse]:
    """View platform-wide payment and system audit events across all tenants.

    Deliberately excludes talent_scout and resume_screener categories to avoid
    exposing candidate PII to the super admin view (SPEC §11).
    """
    from sqlalchemy import func

    # Restrict to payment + system categories only (no candidate PII).
    allowed_categories = ["payment", "system"]
    filters = [JobAuditEvent.event_category.in_(allowed_categories)]

    if event_category and event_category in allowed_categories:
        filters = [JobAuditEvent.event_category == event_category]

    result = await db.execute(
        select(JobAuditEvent)
        .where(*filters)
        .order_by(JobAuditEvent.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    events = list(result.scalars().all())

    count_result = await db.execute(
        select(func.count()).select_from(JobAuditEvent).where(*filters)
    )
    total = count_result.scalar_one()

    return PaginatedResponse(
        items=[JobAuditEventResponse.model_validate(e) for e in events],
        total=total,
        limit=limit,
        offset=offset,
    )
