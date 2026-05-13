"""Add Client Pipeline tables and extend marketing_settings with ICP/outreach config

Creates 7 new tables for the Client Pipeline module:
  marketing_prospects, marketing_signals, marketing_sequences,
  marketing_sequence_steps, marketing_enrollments, marketing_outreach_log,
  marketing_content

Extends existing marketing_settings with pipeline-specific JSONB config columns:
  icp_config, channel_config, signal_config, outreach_limits,
  tenant_mode_enabled, tenant_mode_config

Seeds the platform-level settings row (tenant_id IS NULL) with safe defaults.

Revision ID: 0024
Revises: 0023
Create Date: 2026-05-13
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0024"
down_revision: Union[str, None] = "0023"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_NEW_TABLES = [
    "marketing_prospects",
    "marketing_signals",
    "marketing_sequences",
    "marketing_sequence_steps",
    "marketing_enrollments",
    "marketing_outreach_log",
    "marketing_content",
]


def upgrade() -> None:
    # ── 1. marketing_prospects ────────────────────────────────────────────────
    op.create_table(
        "marketing_prospects",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.Text(), nullable=True),
        sa.Column("company", sa.Text(), nullable=True),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("linkedin_url", sa.Text(), nullable=True),
        sa.Column("email", sa.Text(), nullable=True),
        sa.Column("icp_score", sa.Integer(), nullable=True),
        sa.Column("source", sa.String(), nullable=False, server_default="manual"),
        sa.Column("stage", sa.String(), nullable=False, server_default="identified"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("last_activity_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "icp_score IS NULL OR (icp_score >= 1 AND icp_score <= 10)",
            name="ck_prospects_icp_score",
        ),
        sa.CheckConstraint(
            "source IN ('brightdata', 'hunter', 'manual')",
            name="ck_prospects_source",
        ),
        sa.CheckConstraint(
            "stage IN ('identified', 'connected', 'messaged', 'replied', "
            "'demo_booked', 'trial', 'paid')",
            name="ck_prospects_stage",
        ),
    )

    # ── 2. marketing_signals ─────────────────────────────────────────────────
    op.create_table(
        "marketing_signals",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("type", sa.String(), nullable=False),
        sa.Column("company", sa.Text(), nullable=True),
        sa.Column("person_name", sa.Text(), nullable=True),
        sa.Column("linkedin_url", sa.Text(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("urgency", sa.String(), nullable=False, server_default="medium"),
        sa.Column(
            "detected_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("actioned", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("dismissed", sa.Boolean(), nullable=False, server_default="false"),
        sa.CheckConstraint(
            "type IN ('hiring_spike', 'pain_post', 'growth_signal')",
            name="ck_signals_type",
        ),
        sa.CheckConstraint(
            "urgency IN ('high', 'medium')",
            name="ck_signals_urgency",
        ),
    )

    # ── 3. marketing_sequences ───────────────────────────────────────────────
    op.create_table(
        "marketing_sequences",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="draft"),
        sa.Column("persona_target", sa.Text(), nullable=True),
        sa.Column("angle", sa.Text(), nullable=True),
        sa.Column("enrolled_count", sa.Integer(), nullable=False, server_default="0"),
        sa.CheckConstraint(
            "status IN ('live', 'paused', 'draft')",
            name="ck_sequences_status",
        ),
    )

    # ── 4. marketing_sequence_steps ──────────────────────────────────────────
    op.create_table(
        "marketing_sequence_steps",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "sequence_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("marketing_sequences.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("step_type", sa.String(), nullable=False),
        sa.Column("day_offset", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("message_template", sa.Text(), nullable=True),
        sa.Column("condition", sa.Text(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.CheckConstraint(
            "step_type IN ('linkedin_connect', 'linkedin_dm', 'email', 'wait')",
            name="ck_sequence_steps_type",
        ),
    )

    # ── 5. marketing_enrollments ─────────────────────────────────────────────
    op.create_table(
        "marketing_enrollments",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "prospect_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("marketing_prospects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "sequence_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("marketing_sequences.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("current_step", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "enrolled_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("status", sa.String(), nullable=False, server_default="active"),
        sa.CheckConstraint(
            "status IN ('active', 'replied', 'completed', 'skipped')",
            name="ck_enrollments_status",
        ),
    )

    # ── 6. marketing_outreach_log ────────────────────────────────────────────
    op.create_table(
        "marketing_outreach_log",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "prospect_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("marketing_prospects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "step_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("marketing_sequence_steps.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("channel", sa.String(), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("replied_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "channel IN ('linkedin', 'email')",
            name="ck_outreach_log_channel",
        ),
    )

    # ── 7. marketing_content ─────────────────────────────────────────────────
    op.create_table(
        "marketing_content",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("post_type", sa.String(), nullable=False),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("channel", sa.String(), nullable=False, server_default="linkedin"),
        sa.Column("status", sa.String(), nullable=False, server_default="draft"),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("views", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("likes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("comments", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "connections_attributed",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "demos_attributed", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.CheckConstraint(
            "post_type IN ('roi', 'pain', 'proof', 'tip')",
            name="ck_content_post_type",
        ),
        sa.CheckConstraint(
            "channel IN ('linkedin')",
            name="ck_content_channel",
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'scheduled', 'posted', 'failed')",
            name="ck_content_status",
        ),
    )

    # ── 8. Extend existing marketing_settings with pipeline config columns ───
    for col_name, col_def in [
        ("icp_config", sa.Column("icp_config", postgresql.JSONB(), nullable=True)),
        (
            "channel_config",
            sa.Column("channel_config", postgresql.JSONB(), nullable=True),
        ),
        (
            "signal_config",
            sa.Column("signal_config", postgresql.JSONB(), nullable=True),
        ),
        (
            "outreach_limits",
            sa.Column("outreach_limits", postgresql.JSONB(), nullable=True),
        ),
        (
            "tenant_mode_enabled",
            sa.Column(
                "tenant_mode_enabled",
                sa.Boolean(),
                nullable=False,
                server_default="false",
            ),
        ),
        (
            "tenant_mode_config",
            sa.Column("tenant_mode_config", postgresql.JSONB(), nullable=True),
        ),
    ]:
        op.add_column("marketing_settings", col_def)

    # ── 9. Enable RLS on all new tables ──────────────────────────────────────
    for table in _NEW_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")

    # ── 10. Seed platform-level settings row with pipeline defaults ───────────
    op.execute(
        """
        UPDATE marketing_settings
        SET
            icp_config = '{
                "target_titles": [],
                "company_types": [],
                "size_min": 5,
                "size_max": 200,
                "locations": [],
                "min_score": 7
            }'::jsonb,
            channel_config = '{}'::jsonb,
            signal_config = '{
                "hiring_spike_threshold": 3,
                "scrape_frequency_hours": 6,
                "monitor_pain_posts": true,
                "monitor_growth_signals": true,
                "auto_enroll": false,
                "require_approval": true
            }'::jsonb,
            outreach_limits = '{
                "linkedin_connects_per_day": 20,
                "linkedin_dms_per_day": 30,
                "emails_per_day": 50,
                "window_start_utc": "08:00",
                "window_end_utc": "17:00",
                "skip_weekends": true
            }'::jsonb,
            tenant_mode_enabled = FALSE
        WHERE tenant_id IS NULL
        """
    )


def downgrade() -> None:
    # Remove pipeline config columns from marketing_settings
    for col in [
        "tenant_mode_config",
        "tenant_mode_enabled",
        "outreach_limits",
        "signal_config",
        "channel_config",
        "icp_config",
    ]:
        op.drop_column("marketing_settings", col)

    # Drop new tables (reverse FK order)
    for table in reversed(_NEW_TABLES):
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
        op.drop_table(table)
