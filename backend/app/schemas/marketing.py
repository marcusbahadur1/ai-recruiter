"""Pydantic v2 schemas for the AI Marketing Module (Section 25)."""
import uuid
from datetime import datetime, time
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, field_validator


# ── Supporting schemas ─────────────────────────────────────────────────────────

class ImageAttributionSchema(BaseModel):
    """Required by Unsplash ToS — must be displayed wherever the photo appears."""
    photographer_name: str
    photographer_url: str
    unsplash_url: str


# ── MarketingAccount ───────────────────────────────────────────────────────────

class MarketingAccountRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: Optional[uuid.UUID]
    platform: Literal["linkedin", "twitter", "facebook"]
    account_name: str
    account_type: Literal["personal", "company"]
    linkedin_urn: Optional[str]
    token_expires_at: Optional[datetime]
    is_active: bool
    created_at: datetime
    # Computed from model methods/properties
    is_token_expiring_soon: bool
    author_urn: str
    account_type_label: str

    @classmethod
    def from_orm(cls, account: Any) -> "MarketingAccountRead":
        return cls(
            id=account.id,
            tenant_id=account.tenant_id,
            platform=account.platform,
            account_name=account.account_name,
            account_type=account.account_type,
            linkedin_urn=account.linkedin_urn,
            token_expires_at=account.token_expires_at,
            is_active=account.is_active,
            created_at=account.created_at,
            is_token_expiring_soon=account.is_token_expiring_soon(),
            author_urn=account.author_urn,
            account_type_label=(
                "Company Page" if account.account_type == "company" else "Personal Profile"
            ),
        )


# ── MarketingSettings ──────────────────────────────────────────────────────────

class MarketingSettingsRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: Optional[uuid.UUID]
    post_frequency: Literal["daily", "twice_weekly", "weekly"]
    post_time_utc: time
    post_types_enabled: list[str]
    platforms_enabled: list[str]
    target_audience: Optional[str]
    tone: Literal["professional", "conversational", "bold", "educational"]
    topics: list[str]
    auto_engage: bool
    engagement_per_day: int
    requires_approval: bool
    include_images: bool
    is_active: bool
    created_at: datetime


class MarketingSettingsUpdate(BaseModel):
    post_frequency: Literal["daily", "twice_weekly", "weekly"] | None = None
    post_time_utc: time | None = None
    post_types_enabled: list[str] | None = None
    platforms_enabled: list[str] | None = None
    target_audience: str | None = None
    tone: Literal["professional", "conversational", "bold", "educational"] | None = None
    topics: list[str] | None = None
    auto_engage: bool | None = None
    engagement_per_day: int | None = None
    requires_approval: bool | None = None
    include_images: bool | None = None
    is_active: bool | None = None

    @field_validator("engagement_per_day")
    @classmethod
    def cap_engagement(cls, v: int | None) -> int | None:
        if v is not None and v > 20:
            raise ValueError("engagement_per_day cannot exceed 20")
        return v

    @field_validator("post_types_enabled")
    @classmethod
    def post_types_non_empty(cls, v: list[str] | None) -> list[str] | None:
        if v is not None and len(v) == 0:
            raise ValueError("post_types_enabled must contain at least one type")
        return v

    @field_validator("topics")
    @classmethod
    def topics_non_empty(cls, v: list[str] | None) -> list[str] | None:
        if v is not None and len(v) == 0:
            raise ValueError("topics must contain at least one topic")
        return v


# ── MarketingPost ──────────────────────────────────────────────────────────────

class MarketingPostRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: Optional[uuid.UUID]
    account_id: uuid.UUID
    platform: Literal["linkedin", "twitter", "facebook"]
    post_type: Literal["thought_leadership", "industry_stat", "success_story", "tip", "poll", "carousel"]
    content: str
    hashtags: list[str]
    include_image: bool
    image_search_query: Optional[str]
    image_url: Optional[str]
    image_attribution: Optional[ImageAttributionSchema]
    scheduled_at: datetime
    posted_at: Optional[datetime]
    status: Literal["draft", "scheduled", "posted", "failed"]
    retry_count: int
    platform_post_id: Optional[str]
    likes: int
    comments: int
    impressions: int
    clicks: int
    created_at: datetime


class MarketingPostCreate(BaseModel):
    platform: Literal["linkedin", "twitter", "facebook"]
    post_type: Literal["thought_leadership", "industry_stat", "success_story", "tip", "poll", "carousel"]
    content: str
    hashtags: list[str] = []
    scheduled_at: datetime
    include_image: bool = True

    @field_validator("hashtags")
    @classmethod
    def hashtags_format(cls, v: list[str]) -> list[str]:
        for tag in v:
            if not tag.startswith("#"):
                raise ValueError(f"Hashtag '{tag}' must start with '#'")
        return v


class MarketingPostUpdate(BaseModel):
    content: str | None = None
    hashtags: list[str] | None = None
    scheduled_at: datetime | None = None
    include_image: bool | None = None

    @field_validator("hashtags")
    @classmethod
    def hashtags_format(cls, v: list[str] | None) -> list[str] | None:
        if v is not None:
            for tag in v:
                if not tag.startswith("#"):
                    raise ValueError(f"Hashtag '{tag}' must start with '#'")
        return v


# ── MarketingEngagement ────────────────────────────────────────────────────────

class MarketingEngagementRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    account_id: uuid.UUID
    action_type: Literal["like", "comment", "follow", "group_post"]
    target_post_id: str
    target_author: str
    content: Optional[str]
    performed_at: datetime
    created_at: datetime


# ── Analytics ─────────────────────────────────────────────────────────────────

class MarketingAnalyticsSummary(BaseModel):
    total_posts: int
    total_impressions: int
    avg_engagement_rate: float
    top_post: Optional[MarketingPostRead]
