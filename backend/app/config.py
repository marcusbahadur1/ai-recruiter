from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Database ──────────────────────────────────────────────────────────────
    # Named SQLALCHEMY_DATABASE_URL to avoid collision with Railway's
    # Supabase integration which injects DATABASE_URL automatically.
    sqlalchemy_database_url: str = Field(
        ..., description="asyncpg PostgreSQL URL (postgresql+asyncpg://...)"
    )
    test_database_url: str | None = Field(None, description="Separate DB for tests")
    # Optional override — when set, replaces the password in sqlalchemy_database_url.
    # Avoids URL-encoding issues with special characters in passwords.
    db_password: str | None = Field(None, description="DB password override (plain text)")

    # ── Supabase ──────────────────────────────────────────────────────────────
    supabase_url: str
    supabase_service_key: str = Field(
        ..., description="Service role key — server-side only, never expose"
    )
    supabase_anon_key: str = Field(..., description="Anon key for frontend / RLS auth")

    # ── AI providers ──────────────────────────────────────────────────────────
    anthropic_api_key: str = Field(..., description="Platform-level Claude Sonnet key")
    openai_api_key: str | None = Field(
        None, description="Platform-level OpenAI key (optional)"
    )

    # ── Redis / Celery ────────────────────────────────────────────────────────
    redis_url: str = Field(
        ..., description="Redis connection string for Celery broker + result backend"
    )

    # ── Stripe ────────────────────────────────────────────────────────────────
    stripe_secret_key: str = ""
    stripe_publishable_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_price_recruiter: str = ""
    stripe_price_agency_small: str = ""
    stripe_price_agency_medium: str = ""

    # ── Email ─────────────────────────────────────────────────────────────────
    sendgrid_api_key: str = Field(
        ..., description="Platform SendGrid key — overridable per tenant"
    )
    sendgrid_from_email: str = "marcus.bahadur@aiworkerz.com"
    platform_jobs_email: str = "jobs@airecruiterz.com"
    imap_host: str
    imap_port: int = 993
    imap_master_password: str

    # ── Candidate search ──────────────────────────────────────────────────────
    scrapingdog_api_key: str | None = None
    brightdata_api_key: str | None = None

    # ── Security ──────────────────────────────────────────────────────────────
    encryption_key: str = Field(
        ...,
        description="Fernet key (32 url-safe base64 bytes) for encrypting tenant API keys in DB",
    )

    # ── Email test mode ───────────────────────────────────────────────────────
    email_test_mode: bool = Field(
        False,
        description="When true, all outreach emails are redirected to email_test_recipient",
    )
    email_test_recipient: str | None = Field(
        None, description="Override recipient for outreach emails in test mode"
    )

    # ── Super admin ───────────────────────────────────────────────────────────
    super_admin_email: str | None = Field(
        None,
        description="Email that bypasses role check for super admin access (bootstrap)",
    )

    # ── App ───────────────────────────────────────────────────────────────────
    frontend_url: str = "https://app.airecruiterz.com"
    backend_url: str = "http://localhost:8000"
    environment: Literal["development", "staging", "production"] = "development"

    # ── Plan limits ───────────────────────────────────────────────────────────
    @property
    def plan_limits(self) -> dict[str, dict[str, int]]:
        return PLAN_LIMITS


PLAN_LIMITS: dict[str, dict[str, int]] = {
    "trial": {"jobs": 3, "candidates": 10, "resumes": 50},
    "trial_expired": {"jobs": 0, "candidates": 0, "resumes": 0},
    "recruiter": {"jobs": 5, "candidates": 20, "resumes": 50},
    "agency_small": {"jobs": 20, "candidates": 40, "resumes": 75},
    "agency_medium": {"jobs": 75, "candidates": 60, "resumes": 100},
    "enterprise": {"jobs": 999999, "candidates": 999999, "resumes": 999999},
}

# ── Marketing module plan features ────────────────────────────────────────────
# marketing_visible:        plans that can access the marketing module at all
# linkedin_connect:         plans allowed to connect a LinkedIn account
# posts_per_week:           max posts per week (None = unlimited)
# auto_engage:              plans allowed to enable auto-engagement
# group_posting:            plans allowed to post to LinkedIn groups
# analytics_retention_days: days of post analytics history retained
MARKETING_PLAN_FEATURES: dict[str, object] = {
    "marketing_visible":        ["agency_small", "agency_medium", "enterprise"],
    "linkedin_connect":         ["agency_small", "agency_medium", "enterprise"],
    "posts_per_week":           {"trial": 0, "trial_expired": 0, "recruiter": 0,
                                 "agency_small": 2, "agency_medium": 5, "enterprise": None},
    "auto_engage":              ["agency_medium", "enterprise"],
    "group_posting":            ["agency_medium", "enterprise"],
    "analytics_retention_days": {"trial": 0, "trial_expired": 0, "recruiter": 0,
                                 "agency_small": 30, "agency_medium": 90, "enterprise": 365},
}


def get_marketing_limits(tenant_plan: str) -> dict[str, object]:
    """Return the applicable marketing feature set for the given plan string."""
    return {
        "marketing_visible": tenant_plan in MARKETING_PLAN_FEATURES["marketing_visible"],
        "linkedin_connect": tenant_plan in MARKETING_PLAN_FEATURES["linkedin_connect"],
        "posts_per_week": MARKETING_PLAN_FEATURES["posts_per_week"].get(tenant_plan, 0),
        "auto_engage": tenant_plan in MARKETING_PLAN_FEATURES["auto_engage"],
        "group_posting": tenant_plan in MARKETING_PLAN_FEATURES["group_posting"],
        "analytics_retention_days": MARKETING_PLAN_FEATURES["analytics_retention_days"].get(tenant_plan, 0),
    }


settings = Settings()
