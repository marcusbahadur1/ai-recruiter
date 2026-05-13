"""Marketing Content router — Client Pipeline content tab.

Manages ROI / Pain / Proof / Tip LinkedIn posts for the content pipeline.

Routes (all under /api/v1/marketing/content):
  GET    /                 — list posts (excludes discarded), status filter
  POST   /generate         — AI-generate a draft (ROI/Pain/Proof/Tip prompt)
  PATCH  /{post_id}        — update body, status, scheduled_at
  DELETE /{post_id}        — soft-delete (status → discarded)
  GET    /stats            — content performance metrics + mix + upcoming
"""
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.marketing import MarketingAccount, MarketingPost, MarketingSettings
from app.models.tenant import Tenant
from app.routers.auth import get_current_tenant
from app.config import get_marketing_limits

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/marketing/content", tags=["marketing-content"])

CONTENT_POST_TYPES = {"roi_post", "pain_post", "proof_post", "tip_post"}

POST_TYPE_LABEL: dict[str, str] = {
    "roi_post":   "ROI post",
    "pain_post":  "Pain post",
    "proof_post": "Proof post",
    "tip_post":   "Tip",
}

# Target mix: ROI 40%, Pain 30%, Proof 20%, Tip 10%
TARGET_MIX: dict[str, float] = {
    "roi_post":   0.40,
    "pain_post":  0.30,
    "proof_post": 0.20,
    "tip_post":   0.10,
}


# ── Pydantic schemas ───────────────────────────────────────────────────────────

class ContentPostRead(BaseModel):
    id: uuid.UUID
    post_type: str
    content: str
    hashtags: list[str]
    status: str
    scheduled_at: Optional[datetime]
    posted_at: Optional[datetime]
    impressions: int
    likes: int
    comments: int
    connections_attributed: int
    demos_attributed: int
    platform_post_id: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class GenerateContentRequest(BaseModel):
    post_type: Optional[str] = None   # roi_post | pain_post | proof_post | tip_post
    topic_hint: Optional[str] = None


class UpdateContentRequest(BaseModel):
    content: Optional[str] = None
    status: Optional[str] = None        # draft | scheduled | discarded
    scheduled_at: Optional[datetime] = None


class ContentStatsResponse(BaseModel):
    avg_views: float
    avg_connections: float
    post_demo_rate: float          # SUM(demos_attributed) / COUNT(posted)
    best_post_type: Optional[str]
    mix: dict[str, float]          # {roi_post: 0.45, ...}
    upcoming: list[ContentPostRead]


# ── Helpers ────────────────────────────────────────────────────────────────────

def _is_super_admin_tenant(tenant: Tenant) -> bool:
    return getattr(tenant, "_is_super_admin", False) or tenant.slug == "super-admin"


def _check_plan(tenant: Tenant) -> None:
    if _is_super_admin_tenant(tenant):
        return
    limits = get_marketing_limits(tenant.plan)
    if not limits["marketing_visible"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Marketing module requires Agency Small plan or above (current: {tenant.plan})",
        )


async def _get_content_post(
    post_id: uuid.UUID,
    tenant_id: uuid.UUID,
    db: AsyncSession,
) -> MarketingPost:
    result = await db.execute(
        select(MarketingPost).where(
            MarketingPost.id == post_id,
            MarketingPost.tenant_id == tenant_id,
            MarketingPost.post_type.in_(CONTENT_POST_TYPES),
        )
    )
    post = result.scalar_one_or_none()
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Content post not found")
    return post


async def _get_or_create_settings(
    tenant_id: uuid.UUID,
    db: AsyncSession,
) -> MarketingSettings:
    result = await db.execute(
        select(MarketingSettings).where(MarketingSettings.tenant_id == tenant_id)
    )
    s = result.scalar_one_or_none()
    if s:
        return s
    result = await db.execute(
        select(MarketingSettings).where(MarketingSettings.tenant_id.is_(None))
    )
    s = result.scalar_one_or_none()
    if not s:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Marketing settings not configured",
        )
    return s


def _pick_underrepresented_type(recent_posts: list[MarketingPost]) -> str:
    """Return the post type furthest below its target mix."""
    counts: dict[str, int] = {t: 0 for t in CONTENT_POST_TYPES}
    for p in recent_posts:
        if p.post_type in CONTENT_POST_TYPES:
            counts[p.post_type] = counts.get(p.post_type, 0) + 1
    total = sum(counts.values()) or 1
    actuals = {t: counts[t] / total for t in CONTENT_POST_TYPES}
    return min(CONTENT_POST_TYPES, key=lambda t: actuals[t] - TARGET_MIX[t])


_SYSTEM_PROMPTS: dict[str, str] = {
    "roi_post": (
        "You are a LinkedIn content writer for AIRecruiterz, an AI recruitment "
        "automation platform. Target audience: recruitment agency owners and HR directors. "
        "Write a ROI LinkedIn post. Lead with a striking number or cost saving. "
        "Show the tangible business value of AI-powered recruitment. "
        "Tone: direct, confident, no buzzwords, no hashtag spam (max 3 hashtags). "
        "Max 1200 characters. End with a soft CTA (DM me / comment below / link in bio). "
        "Return only the post text, no preamble."
    ),
    "pain_post": (
        "You are a LinkedIn content writer for AIRecruiterz, an AI recruitment "
        "automation platform. Target audience: recruitment agency owners and HR directors. "
        "Write a Pain LinkedIn post. Articulate a specific pain the audience feels daily — "
        "CV overload, ghost candidates, slow time-to-hire, misaligned briefs. "
        "Be empathetic and specific. "
        "Tone: direct, confident, no buzzwords, no hashtag spam (max 3 hashtags). "
        "Max 1200 characters. End with a soft CTA. "
        "Return only the post text, no preamble."
    ),
    "proof_post": (
        "You are a LinkedIn content writer for AIRecruiterz, an AI recruitment "
        "automation platform. Target audience: recruitment agency owners and HR directors. "
        "Write a Proof/Success Story LinkedIn post. Describe a concrete outcome — "
        "e.g. 400 CVs screened in a weekend, 3x faster time-to-shortlist, "
        "hired in 6 days not 6 weeks. Use plausible, specific numbers. "
        "Tone: direct, confident, no buzzwords, no hashtag spam (max 3 hashtags). "
        "Max 1200 characters. End with a soft CTA. "
        "Return only the post text, no preamble."
    ),
    "tip_post": (
        "You are a LinkedIn content writer for AIRecruiterz, an AI recruitment "
        "automation platform. Target audience: recruitment agency owners and HR directors. "
        "Write a Tip LinkedIn post. Give one actionable insight that recruitment agency "
        "owners can use today — interview structure, job description writing, sourcing trick. "
        "Tone: direct, confident, no buzzwords, no hashtag spam (max 3 hashtags). "
        "Max 1200 characters. End with a soft CTA. "
        "Return only the post text, no preamble."
    ),
}


# ── Routes ─────────────────────────────────────────────────────────────────────

@router.get("", response_model=list[ContentPostRead])
async def list_content(
    post_status: Optional[str] = Query(None, alias="status"),
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
) -> list[ContentPostRead]:
    _check_plan(tenant)

    q = select(MarketingPost).where(
        MarketingPost.tenant_id == tenant.id,
        MarketingPost.post_type.in_(CONTENT_POST_TYPES),
        MarketingPost.status != "discarded",
    )
    if post_status:
        q = q.where(MarketingPost.status == post_status)
    q = q.order_by(MarketingPost.created_at.desc())

    rows = (await db.execute(q)).scalars().all()
    return [ContentPostRead.model_validate(r) for r in rows]


@router.post("/generate", response_model=ContentPostRead, status_code=status.HTTP_201_CREATED)
async def generate_content(
    body: GenerateContentRequest,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
) -> ContentPostRead:
    _check_plan(tenant)

    # Require a connected LinkedIn account
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

    mkt_settings = await _get_or_create_settings(tenant.id, db)

    # Determine post type
    if body.post_type and body.post_type in CONTENT_POST_TYPES:
        post_type = body.post_type
    else:
        recent_result = await db.execute(
            select(MarketingPost)
            .where(
                MarketingPost.tenant_id == tenant.id,
                MarketingPost.post_type.in_(CONTENT_POST_TYPES),
                MarketingPost.status != "discarded",
            )
            .order_by(MarketingPost.created_at.desc())
            .limit(30)
        )
        recent = list(recent_result.scalars().all())
        post_type = _pick_underrepresented_type(recent)

    system_prompt = _SYSTEM_PROMPTS[post_type]
    if body.topic_hint:
        system_prompt += f" Focus on: {body.topic_hint}."

    from app.services.ai_provider import AIProvider
    provider = AIProvider(tenant)
    try:
        generated_text = await provider.complete(
            prompt="Write the post now.",
            system=system_prompt,
            max_tokens=600,
        )
    except Exception as exc:
        logger.error("Content generation failed tenant=%s: %s", tenant.id, exc)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"AI generation failed: {exc}",
        )

    # Extract hashtags from generated text (lines starting with #)
    hashtags = [w for w in generated_text.split() if w.startswith("#")]
    # Schedule for tomorrow at 9 AM UTC
    tomorrow = datetime.now(timezone.utc).date() + timedelta(days=1)
    post_time = getattr(mkt_settings, "post_time_utc", None)
    if post_time:
        scheduled_at = datetime.combine(tomorrow, post_time).replace(tzinfo=timezone.utc)
    else:
        scheduled_at = datetime.combine(tomorrow, datetime.min.time()).replace(
            hour=9, tzinfo=timezone.utc
        )

    post = MarketingPost(
        tenant_id=tenant.id,
        account_id=account.id,
        platform=account.platform,
        post_type=post_type,
        content=generated_text,
        hashtags=hashtags,
        scheduled_at=scheduled_at,
        status="draft",
        include_image=False,
    )
    db.add(post)
    await db.commit()
    await db.refresh(post)
    logger.info(
        "Content post generated id=%s type=%s tenant=%s",
        post.id, post_type, tenant.id,
    )
    return ContentPostRead.model_validate(post)


@router.get("/stats", response_model=ContentStatsResponse)
async def content_stats(
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
) -> ContentStatsResponse:
    _check_plan(tenant)

    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)

    # Posted posts in last 30 days
    posted_result = await db.execute(
        select(MarketingPost).where(
            MarketingPost.tenant_id == tenant.id,
            MarketingPost.post_type.in_(CONTENT_POST_TYPES),
            MarketingPost.status == "posted",
            MarketingPost.posted_at >= thirty_days_ago,
        )
    )
    posted_posts = list(posted_result.scalars().all())

    # Metrics
    if posted_posts:
        avg_views = sum(p.impressions for p in posted_posts) / len(posted_posts)
        avg_connections = sum(p.connections_attributed for p in posted_posts) / len(posted_posts)
        total_demos = sum(p.demos_attributed for p in posted_posts)
        post_demo_rate = total_demos / len(posted_posts)

        # Best post type by avg impressions
        type_impressions: dict[str, list[int]] = {}
        for p in posted_posts:
            type_impressions.setdefault(p.post_type, []).append(p.impressions)
        best_post_type = max(
            type_impressions,
            key=lambda t: sum(type_impressions[t]) / len(type_impressions[t]),
        )
    else:
        avg_views = avg_connections = post_demo_rate = 0.0
        best_post_type = None

    # Content mix (last 30 days, all non-discarded)
    all_recent_result = await db.execute(
        select(MarketingPost).where(
            MarketingPost.tenant_id == tenant.id,
            MarketingPost.post_type.in_(CONTENT_POST_TYPES),
            MarketingPost.status != "discarded",
            MarketingPost.created_at >= thirty_days_ago,
        )
    )
    all_recent = list(all_recent_result.scalars().all())
    mix: dict[str, float] = {t: 0.0 for t in CONTENT_POST_TYPES}
    if all_recent:
        counts: dict[str, int] = {t: 0 for t in CONTENT_POST_TYPES}
        for p in all_recent:
            if p.post_type in counts:
                counts[p.post_type] += 1
        total = len(all_recent)
        mix = {t: round(counts[t] / total, 3) for t in CONTENT_POST_TYPES}

    # Upcoming: next 4 scheduled posts
    upcoming_result = await db.execute(
        select(MarketingPost)
        .where(
            MarketingPost.tenant_id == tenant.id,
            MarketingPost.post_type.in_(CONTENT_POST_TYPES),
            MarketingPost.status == "scheduled",
            MarketingPost.scheduled_at >= datetime.now(timezone.utc),
        )
        .order_by(MarketingPost.scheduled_at.asc())
        .limit(4)
    )
    upcoming = list(upcoming_result.scalars().all())

    return ContentStatsResponse(
        avg_views=round(avg_views, 1),
        avg_connections=round(avg_connections, 2),
        post_demo_rate=round(post_demo_rate, 3),
        best_post_type=best_post_type,
        mix=mix,
        upcoming=[ContentPostRead.model_validate(p) for p in upcoming],
    )


@router.patch("/{post_id}", response_model=ContentPostRead)
async def update_content(
    post_id: uuid.UUID,
    body: UpdateContentRequest,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
) -> ContentPostRead:
    _check_plan(tenant)
    post = await _get_content_post(post_id, tenant.id, db)

    if post.status == "posted" and body.content is not None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Cannot edit a post that has already been published",
        )

    if body.content is not None:
        post.content = body.content
        # Re-extract hashtags
        post.hashtags = [w for w in body.content.split() if w.startswith("#")]
        # Editing a scheduled post returns it to draft
        if post.status == "scheduled":
            post.status = "draft"
    if body.status is not None:
        allowed = {"draft", "scheduled", "discarded"}
        if body.status not in allowed:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Status must be one of {allowed}",
            )
        post.status = body.status
    if body.scheduled_at is not None:
        post.scheduled_at = body.scheduled_at

    await db.commit()
    await db.refresh(post)
    return ContentPostRead.model_validate(post)


@router.delete("/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
async def discard_content(
    post_id: uuid.UUID,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
) -> None:
    _check_plan(tenant)
    post = await _get_content_post(post_id, tenant.id, db)
    post.status = "discarded"
    await db.commit()
    logger.info("Content post discarded id=%s tenant=%s", post_id, tenant.id)
