"""Add strengths and gaps columns to candidates table

Revision ID: 0004
Revises: 0003
Create Date: 2026-04-09
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("candidates", sa.Column("strengths", JSONB, nullable=True))
    op.add_column("candidates", sa.Column("gaps", JSONB, nullable=True))


def downgrade() -> None:
    op.drop_column("candidates", "gaps")
    op.drop_column("candidates", "strengths")
