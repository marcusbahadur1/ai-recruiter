from typing import Literal

from pydantic import Field, model_validator
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
    # Optional here so the validator below can fall back to DATABASE_URL when
    # the cross-service reference variable (${{ api.SQLALCHEMY_DATABASE_URL }})
    # fails to resolve in the worker service.
    sqlalchemy_database_url: str | None = Field(
        None, description="asyncpg PostgreSQL URL (postgresql+asyncpg://...)"
    )
    # Fallback: Railway injects DATABASE_URL from Postgres / Supabase add-ons.
    database_url: str | None = Field(None, description="Fallback DATABASE_URL")
    test_database_url: str | None = Field(None, description="Separate DB for tests")

    @model_validator(mode="after")
    def resolve_database_url(self) -> "Settings":
        """Ensure sqlalchemy_database_url is always populated.

        Resolution order:
        1. SQLALCHEMY_DATABASE_URL (explicit, preferred)
        2. DATABASE_URL (Railway Postgres / Supabase add-on injection)

        Raises ValueError if neither is set so the error is clear.
        """
        if not self.sqlalchemy_database_url:
            if self.database_url:
                self.sqlalchemy_database_url = self.database_url
            else:
                raise ValueError(
                    "Neither SQLALCHEMY_DATABASE_URL nor DATABASE_URL is set. "
                    "Set one of these environment variables on the worker service."
                )
        return self

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

settings = Settings()
