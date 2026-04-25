"""SQLAlchemy models for the AI Marketing Module (Section 25)."""
import uuid
from datetime import datetime, timezone, time
from typing import Any, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, Time, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.services.crypto import decrypt, encrypt


class MarketingAccount(Base):
    __tablename__ = "marketing_accounts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # NULL = platform-level account; set = tenant account
    tenant_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    platform: Mapped[str] = mapped_column(String(), nullable=False)
    account_name: Mapped[str] = mapped_column(String(200), nullable=False)
    account_type: Mapped[str] = mapped_column(String(), nullable=False, default="company")
    linkedin_urn: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    # Fernet-encrypted OAuth tokens — never read raw; use helpers below
    access_token: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    refresh_token: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    token_expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Relationships
    posts: Mapped[list["MarketingPost"]] = relationship(
        "MarketingPost", back_populates="account", cascade="all, delete-orphan"
    )
    engagements: Mapped[list["MarketingEngagement"]] = relationship(
        "MarketingEngagement", back_populates="account", cascade="all, delete-orphan"
    )

    # ── Token helpers ──────────────────────────────────────────────────────────

    def set_encrypted_tokens(self, access_token: str, refresh_token: str) -> None:
        """Encrypt and store both OAuth tokens."""
        self.access_token = encrypt(access_token)
        self.refresh_token = encrypt(refresh_token)

    def get_decrypted_tokens(self) -> tuple[str, str]:
        """Return (access_token, refresh_token) in plaintext."""
        return decrypt(self.access_token), decrypt(self.refresh_token)

    # ── Computed properties ────────────────────────────────────────────────────

    @property
    def is_token_expired(self) -> bool:
        if self.token_expires_at is None:
            return True
        return datetime.now(timezone.utc) >= self.token_expires_at

    def is_token_expiring_soon(self, hours: int = 24) -> bool:
        if self.token_expires_at is None:
            return True
        from datetime import timedelta
        cutoff = datetime.now(timezone.utc) + timedelta(hours=hours)
        return self.token_expires_at <= cutoff

    @property
    def author_urn(self) -> str:
        """Return the LinkedIn URN string used when posting."""
        if self.account_type == "company":
            return f"urn:li:organization:{self.linkedin_urn}"
        return f"urn:li:person:{self.linkedin_urn}"


class MarketingSettings(Base):
    __tablename__ = "marketing_settings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # NULL = platform-level settings; set = tenant settings
    tenant_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    post_frequency: Mapped[str] = mapped_column(
        String(), nullable=False, default="twice_weekly"
    )
    post_time_utc: Mapped[time] = mapped_column(
        Time(), nullable=False, default=time(9, 0)
    )
    post_types_enabled: Mapped[list[Any]] = mapped_column(
        JSONB, nullable=False, default=lambda: ["thought_leadership", "industry_stat", "tip"]
    )
    platforms_enabled: Mapped[list[Any]] = mapped_column(
        JSONB, nullable=False, default=lambda: ["linkedin"]
    )
    target_audience: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    tone: Mapped[str] = mapped_column(String(), nullable=False, default="professional")
    topics: Mapped[list[Any]] = mapped_column(
        JSONB, nullable=False, default=list
    )
    auto_engage: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    engagement_per_day: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    requires_approval: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    include_images: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class MarketingPost(Base):
    __tablename__ = "marketing_posts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("marketing_accounts.id"), nullable=False
    )
    platform: Mapped[str] = mapped_column(String(), nullable=False)
    post_type: Mapped[str] = mapped_column(String(), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    hashtags: Mapped[list[Any]] = mapped_column(
        JSONB, nullable=False, default=list
    )
    topic: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    include_image: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    image_search_query: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    image_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # {photographer_name, photographer_url, unsplash_url} — required by Unsplash ToS
    image_attribution: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSONB, nullable=True
    )
    scheduled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    posted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    status: Mapped[str] = mapped_column(String(), nullable=False, default="draft")
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    platform_post_id: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    likes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    comments: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    impressions: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    clicks: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Relationships
    account: Mapped["MarketingAccount"] = relationship(
        "MarketingAccount",
        back_populates="posts",
        foreign_keys=[account_id],
        primaryjoin="MarketingPost.account_id == MarketingAccount.id",
    )

    @property
    def has_image(self) -> bool:
        return self.image_url is not None


class MarketingEngagement(Base):
    __tablename__ = "marketing_engagement"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("marketing_accounts.id"), nullable=False
    )
    action_type: Mapped[str] = mapped_column(String(), nullable=False)
    target_post_id: Mapped[str] = mapped_column(String(200), nullable=False)
    target_author: Mapped[str] = mapped_column(String(200), nullable=False)
    content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    performed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Relationships
    account: Mapped["MarketingAccount"] = relationship(
        "MarketingAccount",
        back_populates="engagements",
        foreign_keys=[account_id],
        primaryjoin="MarketingEngagement.account_id == MarketingAccount.id",
    )
