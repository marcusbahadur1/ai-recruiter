"""Add candidate_target column to jobs table

Revision ID: 0002
Revises: 0001
Create Date: 2026-04-08
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "jobs",
        sa.Column(
            "candidate_target",
            sa.Integer(),
            nullable=False,
            server_default="20",
        ),
    )


def downgrade() -> None:
    op.drop_column("jobs", "candidate_target")
