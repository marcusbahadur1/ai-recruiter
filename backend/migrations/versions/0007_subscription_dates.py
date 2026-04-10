"""Add subscription_started_at and subscription_ends_at to tenants

Revision ID: 0007
Revises: 0006
Create Date: 2026-04-10
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("tenants", sa.Column("subscription_started_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("tenants", sa.Column("subscription_ends_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("tenants", "subscription_ends_at")
    op.drop_column("tenants", "subscription_started_at")
