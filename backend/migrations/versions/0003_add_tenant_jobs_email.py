"""Add jobs_email column to tenants table

Revision ID: 0003
Revises: 0002
Create Date: 2026-04-09
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "tenants",
        sa.Column("jobs_email", sa.String(255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("tenants", "jobs_email")
