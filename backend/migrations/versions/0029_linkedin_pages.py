"""Add linkedin_pages table + needs_reconnect, target_pages, publish_results columns

Supports showcase page posting via LinkedIn's native Posts API (LinkedIn-Version 202502).

New table:
  linkedin_pages — stores all discovered pages per tenant (personal, company, showcase)

New columns:
  marketing_accounts.needs_reconnect (bool)
  marketing_posts.target_pages       (jsonb — array of page URNs)
  marketing_posts.publish_results    (jsonb — per-URN publish status dict)

Revision ID: 0029
Revises: 0028
Create Date: 2026-05-20
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0029"
down_revision: Union[str, None] = "0028"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── linkedin_pages ────────────────────────────────────────────────────────
    op.create_table(
        "linkedin_pages",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "linkedin_account_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("page_type", sa.String(20), nullable=False),       # personal | company | showcase
        sa.Column("page_name", sa.String(200), nullable=False),
        sa.Column("page_urn", sa.String(200), nullable=False),        # urn:li:person:xxx or urn:li:organization:xxx
        sa.Column("page_id", sa.String(100), nullable=False),         # numeric ID extracted from URN
        sa.Column("vanity_name", sa.String(200), nullable=True),
        sa.Column("logo_url", sa.Text(), nullable=True),
        sa.Column("follower_count", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["linkedin_account_id"],
            ["marketing_accounts.id"],
            ondelete="CASCADE",
        ),
    )
    # Index for fast per-tenant lookups
    op.create_index("ix_linkedin_pages_tenant_id", "linkedin_pages", ["tenant_id"])
    # Unique index: one row per (tenant, page_urn) — upsert safe
    op.create_index(
        "uq_linkedin_pages_tenant_urn",
        "linkedin_pages",
        ["tenant_id", "page_urn"],
        unique=True,
    )

    # ── marketing_accounts — needs_reconnect ──────────────────────────────────
    op.add_column(
        "marketing_accounts",
        sa.Column("needs_reconnect", sa.Boolean(), nullable=False, server_default="false"),
    )

    # ── marketing_posts — showcase page columns ───────────────────────────────
    op.add_column(
        "marketing_posts",
        sa.Column("target_pages", postgresql.JSONB(), nullable=True),
    )
    op.add_column(
        "marketing_posts",
        sa.Column("publish_results", postgresql.JSONB(), nullable=True),
    )

    # ── RLS on linkedin_pages ─────────────────────────────────────────────────
    op.execute("ALTER TABLE linkedin_pages ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE linkedin_pages FORCE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.drop_column("marketing_posts", "publish_results")
    op.drop_column("marketing_posts", "target_pages")
    op.drop_column("marketing_accounts", "needs_reconnect")
    op.drop_index("uq_linkedin_pages_tenant_urn", table_name="linkedin_pages")
    op.drop_index("ix_linkedin_pages_tenant_id", table_name="linkedin_pages")
    op.drop_table("linkedin_pages")
