"""Marketing posts router — CRUD + approval workflow + AI generation.

Routes (all under /api/v1/marketing):
  GET    /posts                   — paginated list with filters
  POST   /posts                   — create draft post
  PATCH  /posts/{post_id}         — edit draft or scheduled post
  POST   /posts/{post_id}/approve — draft → scheduled
  POST   /posts/{post_id}/reject  — scheduled/draft → draft (clears scheduled_at)
  DELETE /posts/{post_id}         — delete non-posted post
  POST   /posts/generate          — AI-generate a new draft post immediately
"""
import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_marketing_limits
from app.database import get_db
from app.models.marketing import MarketingAccount, MarketingPost, MarketingSettings
from app.models.tenant import Tenant
from app.routers.auth import get_current_tenant
from app.schemas.common import PaginatedResponse
from app.schemas.marketing import (
    MarketingPostCreate,
    MarketingPostRead,
    MarketingPostUpdate,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/marketing", tags=["marketing-posts"])

_EDITABLE_STATUSES = {"draft", "scheduled"}


# ── Request schemas ────────────────────────────────────────────────────────────


class GeneratePostRequest(BaseModel):
    post_type: str | None = None
    topic: str | None = None


# ── Helpers ───────────────────────────────────────────────────────────────────


def _check_plan(tenant: Tenant) -> None:
    limits = get_marketing_limits(tenant.plan)
    if not limits["marketing_visible"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Marketing module requires Agency Small plan or above (current: {tenant.plan})",
        )


async def _get_post_or_404(
    post_id: uuid.UUID,
    tenant_id: uuid.UUID,
    db: AsyncSession,
) -> MarketingPost:
    result = await db.execute(
        select(MarketingPost).where(
            MarketingPost.id == post_id,
            MarketingPost.tenant_id == tenant_id,
        )
    )
    post = result.scalar_one_or_none()
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")
    return post


async def _get_active_account(
    tenant_id: uuid.UUID,
    platform: str,
    db: AsyncSession,
) -> MarketingAccount:
    """Return the first active account for the given platform, or 422."""
    result = await db.execute(
        select(MarketingAccount).where(
            MarketingAccount.tenant_id == tenant_id,
            MarketingAccount.platform == platform,
            MarketingAccount.is_active.is_(True),
        )
    )
    account = result.scalars().first()
    if not account:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"No active {platform} account connected — connect one first",
        )
    return account


async def _get_or_default_settings(
    tenant_id: uuid.UUID,
    db: AsyncSession,
) -> MarketingSettings:
    """Return tenant marketing settings, falling back to platform defaults."""
    result = await db.execute(
        select(MarketingSettings).where(MarketingSettings.tenant_id == tenant_id)
    )
    s = result.scalar_one_or_none()
    if s:
        return s
    # Fall back to platform-level defaults row (tenant_id IS NULL)
    result = await db.execute(
        select(MarketingSettings).where(MarketingSettings.tenant_id.is_(None))
    )
    s = result.scalar_one_or_none()
    if not s:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Marketing settings not configured — visit Settings first",
        )
    return s


# ── Routes ─────────────────────────────────────────────────────────────────────


@router.get("/posts", response_model=PaginatedResponse[MarketingPostRead])
async def list_posts(
    post_status: str | None = Query(None, alias="status"),
    platform: str | None = Query(None),
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[MarketingPostRead]:
    _check_plan(tenant)

    q = select(MarketingPost).where(MarketingPost.tenant_id == tenant.id)
    if post_status:
        q = q.where(MarketingPost.status == post_status)
    if platform:
        q = q.where(MarketingPost.platform == platform)
    if date_from:
        q = q.where(MarketingPost.scheduled_at >= date_from)
    if date_to:
        q = q.where(MarketingPost.scheduled_at <= date_to)

    total_result = await db.execute(select(func.count()).select_from(q.subquery()))
    total: int = total_result.scalar_one()

    offset = (page - 1) * page_size
    q = q.order_by(MarketingPost.scheduled_at.asc()).offset(offset).limit(page_size)
    rows = (await db.execute(q)).scalars().all()

    return PaginatedResponse(
        items=[MarketingPostRead.model_validate(r) for r in rows],
        total=total,
        limit=page_size,
        offset=offset,
    )


@router.post("/posts", response_model=MarketingPostRead, status_code=status.HTTP_201_CREATED)
async def create_post(
    body: MarketingPostCreate,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
) -> MarketingPostRead:
    _check_plan(tenant)
    account = await _get_active_account(tenant.id, body.platform, db)
    mkt_settings = await _get_or_default_settings(tenant.id, db)

    initial_status = "draft" if mkt_settings.requires_approval else "scheduled"

    post = MarketingPost(
        tenant_id=tenant.id,
        account_id=account.id,
        platform=body.platform,
        post_type=body.post_type,
        content=body.content,
        hashtags=body.hashtags,
        scheduled_at=body.scheduled_at,
        include_image=body.include_image,
        status=initial_status,
    )
    db.add(post)
    await db.commit()
    await db.refresh(post)
    logger.info("Marketing post created id=%s tenant=%s status=%s", post.id, tenant.id, initial_status)
    return MarketingPostRead.model_validate(post)


@router.patch("/posts/{post_id}", response_model=MarketingPostRead)
async def update_post(
    post_id: uuid.UUID,
    body: MarketingPostUpdate,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
) -> MarketingPostRead:
    _check_plan(tenant)
    post = await _get_post_or_404(post_id, tenant.id, db)

    if post.status not in _EDITABLE_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Cannot edit a post with status '{post.status}'",
        )

    if body.content is not None:
        post.content = body.content
    if body.hashtags is not None:
        post.hashtags = body.hashtags
    if body.scheduled_at is not None:
        post.scheduled_at = body.scheduled_at
    if body.include_image is not None:
        post.include_image = body.include_image

    await db.commit()
    await db.refresh(post)
    return MarketingPostRead.model_validate(post)


@router.post("/posts/{post_id}/approve", response_model=MarketingPostRead)
async def approve_post(
    post_id: uuid.UUID,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
) -> MarketingPostRead:
    _check_plan(tenant)
    post = await _get_post_or_404(post_id, tenant.id, db)

    if post.status != "draft":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Only draft posts can be approved (current status: {post.status})",
        )

    post.status = "scheduled"
    await db.commit()
    await db.refresh(post)
    logger.info("Marketing post approved id=%s tenant=%s", post.id, tenant.id)
    return MarketingPostRead.model_validate(post)


@router.post("/posts/{post_id}/reject", response_model=MarketingPostRead)
async def reject_post(
    post_id: uuid.UUID,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
) -> MarketingPostRead:
    _check_plan(tenant)
    post = await _get_post_or_404(post_id, tenant.id, db)

    if post.status not in ("draft", "scheduled"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Cannot reject a post with status '{post.status}'",
        )

    post.status = "draft"
    post.scheduled_at = datetime.now(timezone.utc).replace(hour=9, minute=0, second=0, microsecond=0)
    await db.commit()
    await db.refresh(post)
    logger.info("Marketing post rejected/returned to draft id=%s tenant=%s", post.id, tenant.id)
    return MarketingPostRead.model_validate(post)


@router.delete("/posts/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_post(
    post_id: uuid.UUID,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
) -> None:
    _check_plan(tenant)
    post = await _get_post_or_404(post_id, tenant.id, db)

    if post.status == "posted":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Cannot delete a post that has already been published",
        )

    await db.delete(post)
    await db.commit()
    logger.info("Marketing post deleted id=%s tenant=%s", post_id, tenant.id)


@router.post("/posts/generate", response_model=MarketingPostRead, status_code=status.HTTP_201_CREATED)
async def generate_post(
    body: GeneratePostRequest,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
) -> MarketingPostRead:
    """Trigger the AI content generator immediately and return a new draft post."""
    _check_plan(tenant)

    mkt_settings = await _get_or_default_settings(tenant.id, db)

    # Require at least one active account
    result = await db.execute(
        select(MarketingAccount).where(
            MarketingAccount.tenant_id == tenant.id,
            MarketingAccount.is_active.is_(True),
        )
    )
    account = result.scalars().first()
    if not account:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No active LinkedIn account connected — connect one first",
        )

    # Load recent posts for rotation helpers
    recent_result = await db.execute(
        select(MarketingPost)
        .where(
            MarketingPost.tenant_id == tenant.id,
            MarketingPost.account_id == account.id,
        )
        .order_by(MarketingPost.created_at.desc())
        .limit(30)
    )
    recent_posts = list(recent_result.scalars().all())

    from app.services.marketing.content_generator import (
        ContentGenerationError,
        MarketingContentGenerator,
    )

    generator = MarketingContentGenerator(tenant)

    post_type = body.post_type or generator.get_next_post_type(mkt_settings, recent_posts)
    topic = body.topic or generator.get_next_topic(mkt_settings, recent_posts)

    try:
        result_data = await generator.generate_post(mkt_settings, account, post_type, topic)
    except ContentGenerationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Content generation failed: {exc.detail}",
        )

    # Schedule for tomorrow at the configured posting time
    from datetime import timedelta

    tomorrow = datetime.now(timezone.utc).date() + timedelta(days=1)
    scheduled_at = datetime.combine(tomorrow, mkt_settings.post_time_utc).replace(
        tzinfo=timezone.utc
    )

    post = MarketingPost(
        tenant_id=tenant.id,
        account_id=account.id,
        platform=account.platform,
        post_type=post_type,
        content=result_data["content"],
        hashtags=result_data["hashtags"],
        topic=result_data["topic"],
        image_search_query=result_data.get("image_search_query"),
        image_url=result_data.get("image_url"),
        image_attribution=result_data.get("image_attribution"),
        include_image=mkt_settings.include_images,
        scheduled_at=scheduled_at,
        status="draft",  # always draft for manual generation — requires explicit approval
    )
    db.add(post)
    await db.commit()
    await db.refresh(post)
    logger.info(
        "Marketing post AI-generated id=%s type=%s topic=%r tenant=%s",
        post.id,
        post_type,
        topic,
        tenant.id,
    )
    return MarketingPostRead.model_validate(post)
