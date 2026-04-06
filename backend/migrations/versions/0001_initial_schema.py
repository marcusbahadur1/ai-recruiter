"""Initial schema — all tables, indexes, pgvector, NOTIFY trigger

Revision ID: 0001
Revises:
Create Date: 2026-04-06
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── pgvector extension ────────────────────────────────────────────────────
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # ── Enums ─────────────────────────────────────────────────────────────────
    _create_enum("plan_enum", "free", "casual", "individual", "small_firm", "mid_firm", "enterprise")
    _create_enum("ai_provider_enum", "anthropic", "openai")
    _create_enum("search_provider_enum", "scrapingdog", "brightdata", "both")
    _create_enum("email_discovery_provider_enum", "apollo", "hunter", "snov", "domain_deduction")
    _create_enum("work_type_enum", "onsite", "hybrid", "remote", "remote_global")
    _create_enum("job_status_enum", "draft", "active", "paused", "closed")
    _create_enum(
        "candidate_status_enum",
        "discovered", "profiled", "scored", "passed", "failed",
        "emailed", "applied", "tested", "interviewed", "rejected",
    )
    _create_enum("email_source_enum", "apollo", "hunter", "snov", "deduced", "manual", "unknown")
    _create_enum("screening_status_enum", "pending", "passed", "failed")
    _create_enum("test_status_enum", "not_started", "invited", "in_progress", "completed", "passed", "failed")
    _create_enum("promo_code_type_enum", "credits", "discount_pct", "full_access")
    _create_enum("chat_phase_enum", "job_collection", "payment", "recruitment", "post_recruitment")
    _create_enum("rag_source_type_enum", "website_scrape", "manual_upload")
    _create_enum("audit_event_category_enum", "talent_scout", "resume_screener", "payment", "system")
    _create_enum("audit_severity_enum", "info", "success", "warning", "error")
    _create_enum("audit_actor_enum", "system", "recruiter", "candidate", "hiring_manager")

    # ── tenants ───────────────────────────────────────────────────────────────
    op.create_table(
        "tenants",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(300), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False, unique=True),
        sa.Column("phone", sa.String(50)),
        sa.Column("address", sa.String(500)),
        sa.Column("main_contact_name", sa.String(300)),
        sa.Column("main_contact_email", sa.String(255)),
        sa.Column("email_inbox", sa.String(255)),
        sa.Column("email_inbox_host", sa.String(255)),
        sa.Column("email_inbox_port", sa.Integer()),
        sa.Column("email_inbox_user", sa.String(255)),
        sa.Column("email_inbox_password", sa.String(1000)),
        sa.Column("website_url", sa.String(500)),
        sa.Column("stripe_customer_id", sa.String(255)),
        sa.Column("stripe_subscription_id", sa.String(255)),
        sa.Column("plan", sa.Text(), nullable=False, server_default="free"),
        sa.Column("credits_remaining", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("ai_provider", sa.Text(), nullable=False, server_default="anthropic"),
        sa.Column("ai_api_key", sa.String(1000)),
        sa.Column("search_provider", sa.Text(), nullable=False, server_default="brightdata"),
        sa.Column("scrapingdog_api_key", sa.String(1000)),
        sa.Column("brightdata_api_key", sa.String(1000)),
        sa.Column("email_discovery_provider", sa.Text(), nullable=False, server_default="domain_deduction"),
        sa.Column("apollo_api_key", sa.String(1000)),
        sa.Column("hunter_api_key", sa.String(1000)),
        sa.Column("snov_api_key", sa.String(1000)),
        sa.Column("sendgrid_api_key", sa.String(1000)),
        sa.Column("gdpr_dpa_signed_at", sa.DateTime(timezone=True)),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    # Cast text columns to their enum types now that the enums exist
    op.execute("ALTER TABLE tenants ALTER COLUMN plan DROP DEFAULT")
    op.execute("ALTER TABLE tenants ALTER COLUMN plan TYPE plan_enum USING plan::plan_enum")
    op.execute("ALTER TABLE tenants ALTER COLUMN plan SET DEFAULT 'free'")
    op.execute("ALTER TABLE tenants ALTER COLUMN ai_provider DROP DEFAULT")
    op.execute("ALTER TABLE tenants ALTER COLUMN ai_provider TYPE ai_provider_enum USING ai_provider::ai_provider_enum")
    op.execute("ALTER TABLE tenants ALTER COLUMN ai_provider SET DEFAULT 'anthropic'")
    op.execute("ALTER TABLE tenants ALTER COLUMN search_provider DROP DEFAULT")
    op.execute("ALTER TABLE tenants ALTER COLUMN search_provider TYPE search_provider_enum USING search_provider::search_provider_enum")
    op.execute("ALTER TABLE tenants ALTER COLUMN search_provider SET DEFAULT 'brightdata'")
    op.execute("ALTER TABLE tenants ALTER COLUMN email_discovery_provider DROP DEFAULT")
    op.execute("ALTER TABLE tenants ALTER COLUMN email_discovery_provider TYPE email_discovery_provider_enum USING email_discovery_provider::email_discovery_provider_enum")
    op.execute("ALTER TABLE tenants ALTER COLUMN email_discovery_provider SET DEFAULT 'domain_deduction'")

    # ── jobs ──────────────────────────────────────────────────────────────────
    op.create_table(
        "jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("job_ref", sa.String(20), nullable=False, unique=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("title_variations", postgresql.JSONB()),
        sa.Column("job_type", sa.String(100)),
        sa.Column("description", sa.Text()),
        sa.Column("required_skills", postgresql.JSONB()),
        sa.Column("experience_years", sa.Integer()),
        sa.Column("salary_min", sa.Numeric()),
        sa.Column("salary_max", sa.Numeric()),
        sa.Column("location", sa.String(200)),
        sa.Column("location_variations", postgresql.JSONB()),
        sa.Column("work_type", sa.Text()),
        sa.Column("tech_stack", postgresql.JSONB()),
        sa.Column("team_size", sa.Integer()),
        sa.Column("minimum_score", sa.Integer(), nullable=False, server_default="6"),
        sa.Column("hiring_manager_email", sa.String(255)),
        sa.Column("hiring_manager_name", sa.String(200)),
        sa.Column("evaluation_prompt", sa.Text()),
        sa.Column("outreach_email_prompt", sa.Text()),
        sa.Column("interview_questions_count", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("custom_interview_questions", postgresql.JSONB()),
        sa.Column("ai_recruiter_config", postgresql.JSONB()),
        sa.Column("status", sa.Text(), nullable=False, server_default="draft"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.execute("ALTER TABLE jobs ALTER COLUMN work_type TYPE work_type_enum USING work_type::work_type_enum")
    op.execute("ALTER TABLE jobs ALTER COLUMN status DROP DEFAULT")
    op.execute("ALTER TABLE jobs ALTER COLUMN status TYPE job_status_enum USING status::job_status_enum")
    op.execute("ALTER TABLE jobs ALTER COLUMN status SET DEFAULT 'draft'")
    op.create_index("ix_jobs_tenant_id", "jobs", ["tenant_id"])

    # ── candidates ────────────────────────────────────────────────────────────
    op.create_table(
        "candidates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(300), nullable=False),
        sa.Column("title", sa.String(300)),
        sa.Column("snippet", sa.Text()),
        sa.Column("linkedin_url", sa.String(500)),
        sa.Column("email", sa.String(255)),
        sa.Column("email_source", sa.Text()),
        sa.Column("company", sa.String(300)),
        sa.Column("location", sa.String(300)),
        sa.Column("brightdata_profile", postgresql.JSONB()),
        # resume_embedding (vector) added via raw DDL below
        sa.Column("suitability_score", sa.Integer()),
        sa.Column("score_reasoning", sa.Text()),
        sa.Column("status", sa.Text(), nullable=False, server_default="discovered"),
        sa.Column("outreach_email_sent_at", sa.DateTime(timezone=True)),
        sa.Column("outreach_email_content", sa.Text()),
        sa.Column("gdpr_consent_given", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("gdpr_consent_at", sa.DateTime(timezone=True)),
        sa.Column("opted_out", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.execute("ALTER TABLE candidates ALTER COLUMN email_source TYPE email_source_enum USING email_source::email_source_enum")
    op.execute("ALTER TABLE candidates ALTER COLUMN status DROP DEFAULT")
    op.execute("ALTER TABLE candidates ALTER COLUMN status TYPE candidate_status_enum USING status::candidate_status_enum")
    op.execute("ALTER TABLE candidates ALTER COLUMN status SET DEFAULT 'discovered'")
    op.execute("ALTER TABLE candidates ADD COLUMN resume_embedding vector(1536)")
    op.create_index("ix_candidates_tenant_id", "candidates", ["tenant_id"])
    op.create_index("ix_candidates_job_id", "candidates", ["job_id"])

    # ── applications ──────────────────────────────────────────────────────────
    op.create_table(
        "applications",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("candidate_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("candidates.id", ondelete="SET NULL")),
        sa.Column("applicant_name", sa.String(300), nullable=False),
        sa.Column("applicant_email", sa.String(255), nullable=False),
        sa.Column("resume_storage_path", sa.String(500)),
        sa.Column("resume_text", sa.Text()),
        # resume_embedding (vector) added via raw DDL below
        sa.Column("screening_score", sa.Integer()),
        sa.Column("screening_reasoning", sa.Text()),
        sa.Column("screening_status", sa.Text(), nullable=False, server_default="pending"),
        sa.Column("test_status", sa.Text(), nullable=False, server_default="not_started"),
        sa.Column("test_score", sa.Integer()),
        sa.Column("test_answers", postgresql.JSONB()),
        sa.Column("interview_invited", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("interview_invited_at", sa.DateTime(timezone=True)),
        sa.Column("email_message_id", sa.String(500), unique=True),
        sa.Column("gdpr_consent_given", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("received_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.execute("ALTER TABLE applications ALTER COLUMN screening_status DROP DEFAULT")
    op.execute("ALTER TABLE applications ALTER COLUMN screening_status TYPE screening_status_enum USING screening_status::screening_status_enum")
    op.execute("ALTER TABLE applications ALTER COLUMN screening_status SET DEFAULT 'pending'")
    op.execute("ALTER TABLE applications ALTER COLUMN test_status DROP DEFAULT")
    op.execute("ALTER TABLE applications ALTER COLUMN test_status TYPE test_status_enum USING test_status::test_status_enum")
    op.execute("ALTER TABLE applications ALTER COLUMN test_status SET DEFAULT 'not_started'")
    op.execute("ALTER TABLE applications ADD COLUMN resume_embedding vector(1536)")
    op.create_index("ix_applications_tenant_id", "applications", ["tenant_id"])
    op.create_index("ix_applications_job_id", "applications", ["job_id"])

    # ── promo_codes ───────────────────────────────────────────────────────────
    op.create_table(
        "promo_codes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE")),
        sa.Column("code", sa.String(50), nullable=False, unique=True),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column("value", sa.Numeric(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("max_uses", sa.Integer()),
        sa.Column("uses_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
    )
    op.execute("ALTER TABLE promo_codes ALTER COLUMN type TYPE promo_code_type_enum USING type::promo_code_type_enum")
    op.create_index("ix_promo_codes_tenant_id", "promo_codes", ["tenant_id"])

    # ── chat_sessions ─────────────────────────────────────────────────────────
    op.create_table(
        "chat_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("jobs.id", ondelete="SET NULL")),
        sa.Column("messages", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("phase", sa.Text(), nullable=False, server_default="job_collection"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.execute("ALTER TABLE chat_sessions ALTER COLUMN phase DROP DEFAULT")
    op.execute("ALTER TABLE chat_sessions ALTER COLUMN phase TYPE chat_phase_enum USING phase::chat_phase_enum")
    op.execute("ALTER TABLE chat_sessions ALTER COLUMN phase SET DEFAULT 'job_collection'")
    op.create_index("ix_chat_sessions_tenant_id", "chat_sessions", ["tenant_id"])

    # ── rag_documents ─────────────────────────────────────────────────────────
    op.create_table(
        "rag_documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_type", sa.Text(), nullable=False),
        sa.Column("source_url", sa.String(500)),
        sa.Column("filename", sa.String(300)),
        sa.Column("content_text", sa.Text(), nullable=False),
        # embedding (vector) added via raw DDL below
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.execute("ALTER TABLE rag_documents ALTER COLUMN source_type TYPE rag_source_type_enum USING source_type::rag_source_type_enum")
    # embedding is NOT NULL; supply an empty default that migrations can set — services always write real embeddings
    op.execute("ALTER TABLE rag_documents ADD COLUMN embedding vector(1536) NOT NULL DEFAULT array_fill(0, ARRAY[1536])::vector")
    op.create_index("ix_rag_documents_tenant_id", "rag_documents", ["tenant_id"])

    # ── job_audit_events ──────────────────────────────────────────────────────
    op.create_table(
        "job_audit_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("candidate_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("candidates.id", ondelete="SET NULL")),
        sa.Column("application_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("applications.id", ondelete="SET NULL")),
        sa.Column("event_type", sa.String(80), nullable=False),
        sa.Column("event_category", sa.Text(), nullable=False),
        sa.Column("severity", sa.Text(), nullable=False, server_default="info"),
        sa.Column("actor", sa.Text(), nullable=False, server_default="system"),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True)),
        sa.Column("summary", sa.String(500), nullable=False),
        sa.Column("detail", postgresql.JSONB()),
        sa.Column("duration_ms", sa.Integer()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.execute("ALTER TABLE job_audit_events ALTER COLUMN event_category TYPE audit_event_category_enum USING event_category::audit_event_category_enum")
    op.execute("ALTER TABLE job_audit_events ALTER COLUMN severity DROP DEFAULT")
    op.execute("ALTER TABLE job_audit_events ALTER COLUMN severity TYPE audit_severity_enum USING severity::audit_severity_enum")
    op.execute("ALTER TABLE job_audit_events ALTER COLUMN severity SET DEFAULT 'info'")
    op.execute("ALTER TABLE job_audit_events ALTER COLUMN actor DROP DEFAULT")
    op.execute("ALTER TABLE job_audit_events ALTER COLUMN actor TYPE audit_actor_enum USING actor::audit_actor_enum")
    op.execute("ALTER TABLE job_audit_events ALTER COLUMN actor SET DEFAULT 'system'")
    op.create_index("ix_job_audit_events_tenant_id", "job_audit_events", ["tenant_id"])
    op.create_index("ix_job_audit_events_job_id", "job_audit_events", ["job_id"])
    op.create_index("ix_job_audit_events_created_at", "job_audit_events", ["created_at"])

    # ── Postgres trigger: NOTIFY audit_{job_id} after INSERT ──────────────────
    # Channel name replaces hyphens in the UUID with underscores (guidelines §10).
    # The full new event row is sent as the JSON payload for SSE delivery.
    op.execute("""
        CREATE OR REPLACE FUNCTION notify_audit_event()
        RETURNS trigger AS $$
        DECLARE
            channel_name TEXT;
            payload      TEXT;
        BEGIN
            channel_name := 'audit_' || replace(NEW.job_id::text, '-', '_');
            payload      := row_to_json(NEW)::text;
            PERFORM pg_notify(channel_name, payload);
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)

    op.execute("""
        CREATE TRIGGER trg_notify_audit_event
        AFTER INSERT ON job_audit_events
        FOR EACH ROW
        EXECUTE FUNCTION notify_audit_event();
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_notify_audit_event ON job_audit_events")
    op.execute("DROP FUNCTION IF EXISTS notify_audit_event()")

    op.drop_table("job_audit_events")
    op.drop_table("rag_documents")
    op.drop_table("chat_sessions")
    op.drop_table("promo_codes")
    op.drop_table("applications")
    op.drop_table("candidates")
    op.drop_table("jobs")
    op.drop_table("tenants")

    for enum_name in [
        "audit_actor_enum", "audit_severity_enum", "audit_event_category_enum",
        "rag_source_type_enum", "chat_phase_enum", "promo_code_type_enum",
        "test_status_enum", "screening_status_enum", "email_source_enum",
        "candidate_status_enum", "job_status_enum", "work_type_enum",
        "email_discovery_provider_enum", "search_provider_enum",
        "ai_provider_enum", "plan_enum",
    ]:
        op.execute(f"DROP TYPE IF EXISTS {enum_name}")

    op.execute("DROP EXTENSION IF EXISTS vector")


# ── Helper ────────────────────────────────────────────────────────────────────

def _create_enum(name: str, *values: str) -> None:
    """Create a Postgres ENUM type if it does not already exist."""
    quoted = ", ".join(f"'{v}'" for v in values)
    op.execute(f"DO $$ BEGIN CREATE TYPE {name} AS ENUM ({quoted}); EXCEPTION WHEN duplicate_object THEN null; END $$;")
