"""Add topic column to marketing_posts

Required by MarketingContentGenerator.get_next_topic() to track which
topics have been used in recent posts and avoid repetition within 14 days.

Revision ID: 0020
Revises: 0019
Create Date: 2026-04-24
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0020"
down_revision: Union[str, None] = "0019"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "marketing_posts",
        sa.Column("topic", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("marketing_posts", "topic")
