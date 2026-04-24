"""Add marketing_engagement table

Revision ID: 0017
Revises: 0016
Create Date: 2026-04-24
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0017"
down_revision: Union[str, None] = "0016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "marketing_engagement",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("marketing_accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("action_type", sa.String(), nullable=False),
        sa.Column("target_post_id", sa.String(200), nullable=False),
        sa.Column("target_author", sa.String(200), nullable=False),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("performed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint(
            "action_type IN ('like', 'comment', 'follow', 'group_post')",
            name="ck_marketing_engagement_action_type",
        ),
        sa.UniqueConstraint("account_id", "target_post_id", "action_type", name="uq_marketing_engagement_account_post_action"),
    )

    op.create_index(
        "idx_marketing_engagement_account_performed",
        "marketing_engagement",
        ["account_id", "performed_at"],
    )


def downgrade() -> None:
    op.drop_index("idx_marketing_engagement_account_performed", table_name="marketing_engagement")
    op.drop_table("marketing_engagement")
