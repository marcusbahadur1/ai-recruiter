"""Add connections_attributed and demos_attributed to marketing_posts

Revision ID: 0028
Revises: 0027
Create Date: 2026-05-13
"""
from alembic import op
import sqlalchemy as sa

revision = "0028"
down_revision = "0027"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "marketing_posts",
        sa.Column("connections_attributed", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "marketing_posts",
        sa.Column("demos_attributed", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("marketing_posts", "demos_attributed")
    op.drop_column("marketing_posts", "connections_attributed")
