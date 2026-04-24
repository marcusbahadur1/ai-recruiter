"""Add marketing_posts table

Revision ID: 0016
Revises: 0015
Create Date: 2026-04-24
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0016"
down_revision: Union[str, None] = "0015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "marketing_posts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("marketing_accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("platform", sa.String(), nullable=False),
        sa.Column("post_type", sa.String(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("hashtags", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("include_image", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("image_search_query", sa.Text(), nullable=True),
        sa.Column("image_url", sa.Text(), nullable=True),
        sa.Column("image_attribution", postgresql.JSONB(), nullable=True),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="draft"),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("platform_post_id", sa.String(200), nullable=True),
        sa.Column("likes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("comments", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("impressions", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("clicks", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint(
            "platform IN ('linkedin', 'twitter', 'facebook')",
            name="ck_marketing_posts_platform",
        ),
        sa.CheckConstraint(
            "post_type IN ('thought_leadership', 'industry_stat', 'success_story', 'tip', 'poll', 'carousel')",
            name="ck_marketing_posts_post_type",
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'scheduled', 'posted', 'failed')",
            name="ck_marketing_posts_status",
        ),
    )

    op.create_index("idx_marketing_posts_tenant_status", "marketing_posts", ["tenant_id", "status"])
    op.create_index("idx_marketing_posts_account_status", "marketing_posts", ["account_id", "status"])
    op.create_index("idx_marketing_posts_scheduled_at", "marketing_posts", ["scheduled_at"])
    op.create_index("idx_marketing_posts_posted_at", "marketing_posts", ["posted_at"])


def downgrade() -> None:
    op.drop_index("idx_marketing_posts_posted_at", table_name="marketing_posts")
    op.drop_index("idx_marketing_posts_scheduled_at", table_name="marketing_posts")
    op.drop_index("idx_marketing_posts_account_status", table_name="marketing_posts")
    op.drop_index("idx_marketing_posts_tenant_status", table_name="marketing_posts")
    op.drop_table("marketing_posts")
