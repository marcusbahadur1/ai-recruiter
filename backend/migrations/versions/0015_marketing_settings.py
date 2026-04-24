"""Add marketing_settings table

Revision ID: 0015
Revises: 0014
Create Date: 2026-04-24
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0015"
down_revision: Union[str, None] = "0014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "marketing_settings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True),
        sa.Column("post_frequency", sa.String(), nullable=False, server_default="twice_weekly"),
        sa.Column("post_time_utc", sa.Time(), nullable=False, server_default="09:00"),
        sa.Column(
            "post_types_enabled",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[\"thought_leadership\",\"industry_stat\",\"tip\"]'::jsonb"),
        ),
        sa.Column(
            "platforms_enabled",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[\"linkedin\"]'::jsonb"),
        ),
        sa.Column("target_audience", sa.Text(), nullable=True),
        sa.Column("tone", sa.String(), nullable=False, server_default="professional"),
        sa.Column("topics", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("auto_engage", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("engagement_per_day", sa.Integer(), nullable=False, server_default="10"),
        sa.Column("requires_approval", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("include_images", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint(
            "post_frequency IN ('daily', 'twice_weekly', 'weekly')",
            name="ck_marketing_settings_post_frequency",
        ),
        sa.CheckConstraint(
            "tone IN ('professional', 'conversational', 'bold', 'educational')",
            name="ck_marketing_settings_tone",
        ),
    )

    # NULLS NOT DISTINCT: only one settings row per tenant, and only one platform-level
    # row (tenant_id IS NULL). Standard UNIQUE would allow many NULL rows.
    op.execute(
        """
        CREATE UNIQUE INDEX uq_marketing_settings_tenant_id
        ON marketing_settings (tenant_id)
        NULLS NOT DISTINCT
        """
    )


def downgrade() -> None:
    op.drop_index("uq_marketing_settings_tenant_id", table_name="marketing_settings")
    op.drop_table("marketing_settings")
