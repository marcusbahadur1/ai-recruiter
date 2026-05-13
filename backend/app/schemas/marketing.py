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
    # Client Pipeline config columns (migration 0024)
    icp_config: Optional[dict[str, Any]] = None
    channel_config: Optional[dict[str, Any]] = None
    signal_config: Optional[dict[str, Any]] = None
    outreach_limits: Optional[dict[str, Any]] = None
    tenant_mode_enabled: bool = False
    tenant_mode_config: Optional[dict[str, Any]] = None


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
    # Client Pipeline config columns (migration 0024)
    icp_config: dict[str, Any] | None = None
    channel_config: dict[str, Any] | None = None
    signal_config: dict[str, Any] | None = None
    outreach_limits: dict[str, Any] | None = None
    tenant_mode_enabled: bool | None = None
    tenant_mode_config: dict[str, Any] | None = None

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
    topic: Optional[str]
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


# ── Client Pipeline: Prospects ─────────────────────────────────────────────────

ProspectStage = Literal[
    "identified", "connected", "messaged", "replied",
    "demo_booked", "trial", "paid"
]
ProspectSource = Literal["brightdata", "hunter", "manual"]


class OutreachLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    prospect_id: uuid.UUID
    step_id: Optional[uuid.UUID]
    channel: Literal["linkedin", "email"]
    sent_at: Optional[datetime]
    opened_at: Optional[datetime]
    replied_at: Optional[datetime]


class ProspectRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    name: Optional[str]
    company: Optional[str]
    title: Optional[str]
    location: Optional[str]
    company_size: Optional[int]
    company_type: Optional[str]
    linkedin_url: Optional[str]
    email: Optional[str]
    icp_score: Optional[int]
    score_breakdown: Optional[dict[str, Any]]
    source: ProspectSource
    stage: ProspectStage
    notes: Optional[str]
    last_linkedin_post_at: Optional[datetime]
    created_at: datetime
    last_activity_at: Optional[datetime]
    outreach_log: list[OutreachLogRead] = []


class ProspectCreate(BaseModel):
    name: Optional[str] = None
    company: Optional[str] = None
    title: Optional[str] = None
    location: Optional[str] = None
    company_size: Optional[int] = None
    company_type: Optional[str] = None
    linkedin_url: Optional[str] = None
    email: Optional[str] = None
    source: ProspectSource = "manual"
    stage: ProspectStage = "identified"
    notes: Optional[str] = None
    icp_score: Optional[int] = None
    score_breakdown: Optional[dict[str, Any]] = None
    last_linkedin_post_at: Optional[datetime] = None


class ProspectUpdate(BaseModel):
    stage: Optional[ProspectStage] = None
    email: Optional[str] = None
    notes: Optional[str] = None
    name: Optional[str] = None
    company: Optional[str] = None
    title: Optional[str] = None
    location: Optional[str] = None
    company_size: Optional[int] = None
    company_type: Optional[str] = None
    linkedin_url: Optional[str] = None


class ScrapeRequest(BaseModel):
    titles: list[str] = []
    locations: list[str] = []
    company_types: list[str] = []
    company_size_min: Optional[int] = None
    company_size_max: Optional[int] = None
    max_prospects: Literal[50, 100, 250, 500] = 100


class ScrapeResponse(BaseModel):
    inserted: int
    message: str


class ProspectListResponse(BaseModel):
    items: list[ProspectRead]
    total: int
    page: int
    page_size: int


# ── Client Pipeline: Signals ──────────────────────────────────────────────────

class SignalRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    type: str
    company: Optional[str]
    person_name: Optional[str]
    linkedin_url: Optional[str]
    summary: Optional[str]
    urgency: str
    detected_at: datetime
    actioned: bool
    dismissed: bool
    location: Optional[str] = None
    company_type: Optional[str] = None
    job_count: Optional[int] = None


class SignalActionRequest(BaseModel):
    action_type: str  # outreach_now | add_to_prospects | comment_connect | comment_dm


class SignalRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    started_at: datetime
    completed_at: Optional[datetime]
    signals_found: int


class SignalListResponse(BaseModel):
    items: list[SignalRead]
    total: int
    last_run: Optional[SignalRunRead] = None
    scrape_frequency_hours: int = 6


# ── Client Pipeline: Sequences ────────────────────────────────────────────────

class SequenceSummary(BaseModel):
    id: uuid.UUID
    name: str
    status: str
    enrolled_count: int
    reply_rate: float  # 0.0–1.0


# ── Client Pipeline: Sequence Steps ──────────────────────────────────────────

SequenceStepType = Literal["linkedin_connect", "linkedin_dm", "email", "wait"]
SequenceStatus = Literal["live", "paused", "draft"]
SequenceAngle = Literal["pain-led", "ROI-led", "curiosity/question", "social proof"]


class SequenceStepRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    sequence_id: uuid.UUID
    step_type: SequenceStepType
    step_name: Optional[str]
    day_offset: int
    message_template: Optional[str]
    condition: Optional[str]
    sort_order: int
    # Computed stats (populated by router from outreach_log)
    sent_count: int = 0
    accept_open_rate: float = 0.0  # accepts/opens / sent
    reply_rate: float = 0.0        # replies / sent
    has_been_sent: bool = False    # True if any outreach_log entries for this step


class SequenceStepCreate(BaseModel):
    step_type: SequenceStepType = "linkedin_dm"
    step_name: Optional[str] = None
    day_offset: int = 0
    message_template: Optional[str] = None
    condition: Optional[str] = None
    sort_order: int = 0


class SequenceStepUpdate(BaseModel):
    step_type: Optional[SequenceStepType] = None
    step_name: Optional[str] = None
    day_offset: Optional[int] = None
    message_template: Optional[str] = None
    condition: Optional[str] = None
    sort_order: Optional[int] = None


# ── Client Pipeline: Sequences ────────────────────────────────────────────────

class SequenceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    name: str
    status: SequenceStatus
    persona_target: Optional[str]
    angle: Optional[str]
    enrolled_count: int
    steps: list[SequenceStepRead] = []
    # Channel tags: unique step types used (for the list panel pill badges)
    channel_tags: list[str] = []


class SequenceCreate(BaseModel):
    name: str
    persona_target: Optional[str] = None
    angle: Optional[SequenceAngle] = None


class SequenceUpdate(BaseModel):
    name: Optional[str] = None
    status: Optional[SequenceStatus] = None
    persona_target: Optional[str] = None
    angle: Optional[SequenceAngle] = None


class SequenceStats(BaseModel):
    sent: int
    accept_open_rate: float   # 0.0–1.0
    reply_rate: float         # 0.0–1.0
    demos_booked: int


# ── Client Pipeline: Sequence AI generation ──────────────────────────────────

class GenerateSequenceRequest(BaseModel):
    name: str
    persona: str
    angle: SequenceAngle


class GeneratedStepTemplate(BaseModel):
    step_type: SequenceStepType
    day_offset: int
    message_template: Optional[str]
    condition: Optional[str]


class GenerateSequenceResponse(BaseModel):
    steps: list[GeneratedStepTemplate]


# ── Client Pipeline: Enrollment ───────────────────────────────────────────────

class EnrollProspectsRequest(BaseModel):
    prospect_ids: list[uuid.UUID]


class EnrollProspectsResponse(BaseModel):
    enrolled: int
    already_enrolled: int


# ── Client Pipeline: Pipeline summary ────────────────────────────────────────

class FunnelRow(BaseModel):
    stage: str
    label: str
    count: int
    percentage: float


class MetricCard(BaseModel):
    value: int
    delta: int
    pct_label: Optional[str] = None


class PipelineSummaryResponse(BaseModel):
    prospects_found: MetricCard
    connected: MetricCard
    replied: MetricCard
    demos_booked: MetricCard
    trials_started: MetricCard
    funnel: list[FunnelRow]
    signals: list[SignalRead]
    recent_prospects: list[ProspectRead]
    sequences: list[SequenceSummary]


# ── Client Pipeline: Tenant mode status ──────────────────────────────────────

class TenantStatusResponse(BaseModel):
    """Returned by GET /marketing/tenant-status for sidebar gating + onboarding."""
    is_super_admin: bool
    # Access gating
    has_pipeline_access: bool
    access_denied_reason: Optional[str] = None   # "tenant_mode_disabled" | "plan_too_low"
    min_plan: Optional[str] = None               # minimum plan required (e.g. "agency_small")
    # Integrations
    has_linkedin: bool
    has_hunter: bool
    # Usage vs limits (None = no limit)
    this_month_prospects: int
    prospect_month_limit: Optional[int] = None
    sequences_used: int
    sequence_limit: Optional[int] = None
    # Onboarding state
    is_new_user: bool  # True if no prospects, no sequences, no ICP configured


class TenantUsageRow(BaseModel):
    """One row in the super admin's tenant usage table."""
    tenant_id: str
    tenant_name: str
    plan: str
    prospects_this_month: int
    sequences_count: int
    has_linkedin: bool
    last_active: Optional[str] = None


class AdminTenantUsageResponse(BaseModel):
    rows: list[TenantUsageRow]
