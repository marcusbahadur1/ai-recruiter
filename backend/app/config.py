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
    database_url: str = Field(..., description="asyncpg PostgreSQL URL (postgresql+asyncpg://...)")
    test_database_url: str | None = Field(None, description="Separate DB for tests")

    # ── Supabase ──────────────────────────────────────────────────────────────
    supabase_url: str
    supabase_service_key: str = Field(..., description="Service role key — server-side only, never expose")
    supabase_anon_key: str = Field(..., description="Anon key for frontend / RLS auth")

    # ── AI providers ──────────────────────────────────────────────────────────
    anthropic_api_key: str = Field(..., description="Platform-level Claude Sonnet key")
    openai_api_key: str | None = Field(None, description="Platform-level OpenAI key (optional)")

    # ── Redis / Celery ────────────────────────────────────────────────────────
    redis_url: str = Field(..., description="Redis connection string for Celery broker + result backend")

    # ── Stripe ────────────────────────────────────────────────────────────────
    stripe_secret_key: str
    stripe_webhook_secret: str

    # ── Email ─────────────────────────────────────────────────────────────────
    sendgrid_api_key: str = Field(..., description="Platform SendGrid key — overridable per tenant")
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
    email_test_mode: bool = Field(False, description="When true, all outreach emails are redirected to email_test_recipient")
    email_test_recipient: str | None = Field(None, description="Override recipient for outreach emails in test mode")

    # ── App ───────────────────────────────────────────────────────────────────
    frontend_url: str = "https://app.airecruiterz.com"
    environment: Literal["development", "staging", "production"] = "development"


settings = Settings()
