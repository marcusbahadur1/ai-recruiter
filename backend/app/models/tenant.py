import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    phone: Mapped[str | None] = mapped_column(String(50))
    address: Mapped[str | None] = mapped_column(String(500))
    main_contact_name: Mapped[str | None] = mapped_column(String(300))
    main_contact_email: Mapped[str | None] = mapped_column(String(255))

    # Platform-assigned inbox (jobs-{slug}@airecruiterz.com)
    email_inbox: Mapped[str | None] = mapped_column(String(255))

    # Optional custom IMAP credentials (passwords stored Fernet-encrypted)
    email_inbox_host: Mapped[str | None] = mapped_column(String(255))
    email_inbox_port: Mapped[int | None] = mapped_column(Integer)
    email_inbox_user: Mapped[str | None] = mapped_column(String(255))
    email_inbox_password: Mapped[str | None] = mapped_column(String(1000))  # encrypted

    website_url: Mapped[str | None] = mapped_column(String(500))

    # ── Stripe ────────────────────────────────────────────────────────────────
    stripe_customer_id: Mapped[str | None] = mapped_column(String(255))
    stripe_subscription_id: Mapped[str | None] = mapped_column(String(255))
    plan: Mapped[str] = mapped_column(
        Enum(
            "free", "casual", "individual", "small_firm", "mid_firm", "enterprise",
            name="plan_enum",
        ),
        nullable=False,
        default="free",
    )
    credits_remaining: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # ── AI provider (encrypted keys override platform keys when set) ───────────
    ai_provider: Mapped[str] = mapped_column(
        Enum("anthropic", "openai", name="ai_provider_enum"),
        nullable=False,
        default="anthropic",
    )
    ai_api_key: Mapped[str | None] = mapped_column(String(1000))  # encrypted

    # ── Candidate search ──────────────────────────────────────────────────────
    search_provider: Mapped[str] = mapped_column(
        Enum("scrapingdog", "brightdata", "both", name="search_provider_enum"),
        nullable=False,
        default="brightdata",
    )
    scrapingdog_api_key: Mapped[str | None] = mapped_column(String(1000))  # encrypted
    brightdata_api_key: Mapped[str | None] = mapped_column(String(1000))   # encrypted

    # ── Email discovery ───────────────────────────────────────────────────────
    email_discovery_provider: Mapped[str] = mapped_column(
        Enum("apollo", "hunter", "snov", "domain_deduction", name="email_discovery_provider_enum"),
        nullable=False,
        default="domain_deduction",
    )
    apollo_api_key: Mapped[str | None] = mapped_column(String(1000))   # encrypted
    hunter_api_key: Mapped[str | None] = mapped_column(String(1000))   # encrypted
    snov_api_key: Mapped[str | None] = mapped_column(String(1000))     # encrypted
    sendgrid_api_key: Mapped[str | None] = mapped_column(String(1000)) # encrypted

    # ── GDPR ──────────────────────────────────────────────────────────────────
    gdpr_dpa_signed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # ── Meta ──────────────────────────────────────────────────────────────────
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
