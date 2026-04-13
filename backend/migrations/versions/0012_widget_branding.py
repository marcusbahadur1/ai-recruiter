"""Add widget_primary_color and widget_bot_name to tenants

Revision ID: 0012
Revises: 0011
Create Date: 2026-04-13
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0012"
down_revision: Union[str, None] = "0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("tenants", sa.Column("widget_primary_color", sa.String(20), nullable=True))
    op.add_column("tenants", sa.Column("widget_bot_name", sa.String(100), nullable=True))


def downgrade() -> None:
    op.drop_column("tenants", "widget_bot_name")
    op.drop_column("tenants", "widget_primary_color")
