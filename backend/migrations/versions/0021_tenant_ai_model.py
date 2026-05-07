"""Add anthropic_model and openai_model columns to tenants

Revision ID: 0021
Revises: 0020
Create Date: 2026-05-05
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0021"
down_revision: Union[str, None] = "0020"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "tenants",
        sa.Column(
            "anthropic_model",
            sa.String(100),
            nullable=False,
            server_default="claude-haiku-4-5-20251001",
        ),
    )
    op.add_column(
        "tenants",
        sa.Column(
            "openai_model",
            sa.String(100),
            nullable=False,
            server_default="gpt-4o-mini",
        ),
    )


def downgrade() -> None:
    op.drop_column("tenants", "openai_model")
    op.drop_column("tenants", "anthropic_model")
