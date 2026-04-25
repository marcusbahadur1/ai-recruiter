"""Marketing analytics router.

Routes (all under /api/v1/marketing):
  GET /analytics          — daily impression/engagement series (date-range filtered)
  GET /analytics/summary  — aggregate summary + top post
  GET /engagement         — paginated engagement action log
"""
import logging
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_marketing_limits
from app.database import get_db
from app.models.marketing import MarketingAccount, MarketingEngagement, MarketingPost
from app.models.tenant import Tenant
from app.routers.auth import get_current_tenant
from app.schemas.common import PaginatedResponse
from app.schemas.marketing import MarketingAnalyticsSummary, MarketingEngagementRead, MarketingPostRead

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/marketing", tags=["marketing-analytics"])


# ── Response schemas ───────────────────────────────────────────────────────────


class DailyAnalytics(BaseModel):
    date: str            # ISO date string e.g. "2026-04-24"
    impressions: int
    likes: int
    comments: int
    posts_count: int


# ── Helpers ───────────────────────────────────────────────────────────────────


def _check_plan(tenant: Tenant) -> None:
    limits = get_marketing_limits(tenant.plan)
    if not limits["marketing_visible"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Marketing module requires Agency Small plan or above (current: {tenant.plan})",
        )


def _apply_retention_clip(
    tenant: Tenant,
    date_from: datetime | None,
    date_to: datetime | None,
) -> tuple[datetime, datetime]:
    """Clip the requested date range to the plan's retention window."""
    limits = get_marketing_limits(tenant.plan)
    retention_days: int = limits["analytics_retention_days"]  # type: ignore[assignment]

    now = datetime.now(timezone.utc)
    max_from = now - timedelta(days=retention_days)

    effective_to = date_to or now
    effective_from = date_from or max_from

    # Enforce retention cap — move from forward if it exceeds the allowed window
    if effective_from < max_from:
        effective_from = max_from

    return effective_from, effective_to


# ── Routes ─────────────────────────────────────────────────────────────────────


@router.get("/analytics", response_model=list[DailyAnalytics])
async def get_daily_analytics(
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
) -> list[DailyAnalytics]:
    _check_plan(tenant)
    effective_from, effective_to = _apply_retention_clip(tenant, date_from, date_to)

    # Group posted posts by UTC date
    date_col = func.date(MarketingPost.posted_at).label("day")
    q = (
        select(
            date_col,
            func.sum(MarketingPost.impressions).label("impressions"),
            func.sum(MarketingPost.likes).label("likes"),
            func.sum(MarketingPost.comments).label("comments"),
            func.count(MarketingPost.id).label("posts_count"),
        )
        .where(
            MarketingPost.tenant_id == tenant.id,
            MarketingPost.status == "posted",
            MarketingPost.posted_at >= effective_from,
            MarketingPost.posted_at <= effective_to,
        )
        .group_by(date_col)
        .order_by(date_col.asc())
    )

    rows = (await db.execute(q)).all()
    return [
        DailyAnalytics(
            date=str(row.day),
            impressions=int(row.impressions or 0),
            likes=int(row.likes or 0),
            comments=int(row.comments or 0),
            posts_count=int(row.posts_count or 0),
        )
        for row in rows
    ]


@router.get("/analytics/summary", response_model=MarketingAnalyticsSummary)
async def get_analytics_summary(
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
) -> MarketingAnalyticsSummary:
    _check_plan(tenant)
    limits = get_marketing_limits(tenant.plan)
    retention_days: int = limits["analytics_retention_days"]  # type: ignore[assignment]

    since = datetime.now(timezone.utc) - timedelta(days=retention_days)

    base_filter = [
        MarketingPost.tenant_id == tenant.id,
        MarketingPost.status == "posted",
        MarketingPost.posted_at >= since,
    ]

    # Aggregate totals
    agg = (
        await db.execute(
            select(
                func.count(MarketingPost.id).label("total_posts"),
                func.coalesce(func.sum(MarketingPost.impressions), 0).label("total_impressions"),
                func.coalesce(func.sum(MarketingPost.likes), 0).label("total_likes"),
                func.coalesce(func.sum(MarketingPost.comments), 0).label("total_comments"),
            ).where(*base_filter)
        )
    ).one()

    total_posts: int = int(agg.total_posts)
    total_impressions: int = int(agg.total_impressions)
    total_engagements: int = int(agg.total_likes) + int(agg.total_comments)
    avg_engagement_rate: float = (
        round(total_engagements / total_impressions * 100, 2)
        if total_impressions > 0
        else 0.0
    )

    # Top post by impressions
    top_post_row = (
        await db.execute(
            select(MarketingPost)
            .where(*base_filter)
            .order_by(MarketingPost.impressions.desc())
            .limit(1)
        )
    ).scalar_one_or_none()

    return MarketingAnalyticsSummary(
        total_posts=total_posts,
        total_impressions=total_impressions,
        avg_engagement_rate=avg_engagement_rate,
        top_post=MarketingPostRead.model_validate(top_post_row) if top_post_row else None,
    )


@router.get("/engagement", response_model=PaginatedResponse[MarketingEngagementRead])
async def list_engagement(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[MarketingEngagementRead]:
    _check_plan(tenant)

    # Join through account to scope to tenant
    base_q = (
        select(MarketingEngagement)
        .join(MarketingAccount, MarketingEngagement.account_id == MarketingAccount.id)
        .where(MarketingAccount.tenant_id == tenant.id)
    )

    total_result = await db.execute(select(func.count()).select_from(base_q.subquery()))
    total: int = total_result.scalar_one()

    offset = (page - 1) * page_size
    rows = (
        await db.execute(
            base_q.order_by(MarketingEngagement.performed_at.desc())
            .offset(offset)
            .limit(page_size)
        )
    ).scalars().all()

    return PaginatedResponse(
        items=[MarketingEngagementRead.model_validate(r) for r in rows],
        total=total,
        limit=page_size,
        offset=offset,
    )
