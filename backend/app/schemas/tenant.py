import uuid
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, EmailStr


class TenantBase(BaseModel):
    name: str
    slug: str
    phone: str | None = None
    address: str | None = None
    main_contact_name: str | None = None
    main_contact_email: EmailStr | None = None
    website_url: str | None = None
    email_inbox_host: str | None = None
    email_inbox_port: int | None = None
    email_inbox_user: str | None = None
    ai_provider: Literal["anthropic", "openai"] = "openai"
    search_provider: Literal["scrapingdog", "brightdata", "both"] = "brightdata"
    email_discovery_provider: Literal[
        "apollo", "hunter", "snov", "domain_deduction"
    ] = "domain_deduction"


class TenantCreate(TenantBase):
    pass


class TenantUpdate(BaseModel):
    name: str | None = None
    phone: str | None = None
    address: str | None = None
    main_contact_name: str | None = None
    main_contact_email: EmailStr | None = None
    website_url: str | None = None
    jobs_email: str | None = None
    email_inbox_host: str | None = None
    email_inbox_port: int | None = None
    email_inbox_user: str | None = None
    # Raw key values accepted on write — encrypted before storage in the service layer
    ai_api_key: str | None = None
    scrapingdog_api_key: str | None = None
    brightdata_api_key: str | None = None
    apollo_api_key: str | None = None
    hunter_api_key: str | None = None
    snov_api_key: str | None = None
    sendgrid_api_key: str | None = None
    email_inbox_password: str | None = None
    data_retention_months: int | None = None
    gdpr_dpa_signed_at: Optional[datetime] = None
    recruiter_system_prompt: str | None = None
    widget_primary_color: str | None = None
    widget_bot_name: str | None = None
    ai_provider: Literal["anthropic", "openai"] | None = None
    search_provider: Literal["scrapingdog", "brightdata", "both"] | None = None
    email_discovery_provider: (
        Literal["apollo", "hunter", "snov", "domain_deduction"] | None
    ) = None


class TenantResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str
    phone: str | None
    address: str | None
    main_contact_name: str | None
    main_contact_email: str | None
    email_inbox: str | None
    jobs_email: str | None
    email_inbox_host: str | None
    email_inbox_port: int | None
    email_inbox_user: str | None
    website_url: str | None
    stripe_customer_id: str | None
    stripe_subscription_id: str | None
    plan: Literal[
        "trial",
        "trial_expired",
        "recruiter",
        "agency_small",
        "agency_medium",
        "enterprise",
    ]
    credits_remaining: int
    trial_started_at: datetime | None
    trial_ends_at: datetime | None
    subscription_started_at: datetime | None
    subscription_ends_at: datetime | None
    ai_provider: Literal["anthropic", "openai"]
    search_provider: Literal["scrapingdog", "brightdata", "both"]
    email_discovery_provider: Literal["apollo", "hunter", "snov", "domain_deduction"]
    # API key presence flags — never return raw or encrypted values
    has_ai_api_key: bool = False
    has_scrapingdog_api_key: bool = False
    has_brightdata_api_key: bool = False
    has_apollo_api_key: bool = False
    has_hunter_api_key: bool = False
    has_snov_api_key: bool = False
    has_sendgrid_api_key: bool = False
    # Masked password — "••••••••" if set, "" if not
    email_inbox_password: str = ""
    gdpr_dpa_signed_at: datetime | None
    data_retention_months: int
    recruiter_system_prompt: str | None
    widget_primary_color: str | None
    widget_bot_name: str | None
    is_active: bool
    created_at: datetime

    @classmethod
    def from_orm_with_flags(cls, tenant: object) -> "TenantResponse":
        """Build response with boolean presence flags for encrypted key fields."""
        data = {
            field: getattr(tenant, field)
            for field in cls.model_fields
            if not field.startswith("has_")
            and field != "email_inbox_password"
            and hasattr(tenant, field)
        }
        data["has_ai_api_key"] = bool(getattr(tenant, "ai_api_key", None))
        data["has_scrapingdog_api_key"] = bool(
            getattr(tenant, "scrapingdog_api_key", None)
        )
        data["has_brightdata_api_key"] = bool(
            getattr(tenant, "brightdata_api_key", None)
        )
        data["has_apollo_api_key"] = bool(getattr(tenant, "apollo_api_key", None))
        data["has_hunter_api_key"] = bool(getattr(tenant, "hunter_api_key", None))
        data["has_snov_api_key"] = bool(getattr(tenant, "snov_api_key", None))
        data["has_sendgrid_api_key"] = bool(getattr(tenant, "sendgrid_api_key", None))
        data["email_inbox_password"] = (
            "••••••••" if getattr(tenant, "email_inbox_password", None) else ""
        )
        return cls(**data)
