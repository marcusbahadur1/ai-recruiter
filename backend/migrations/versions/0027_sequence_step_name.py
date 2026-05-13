"""Add step_name column to marketing_sequence_steps

Revision ID: 0027
Revises: 0026
Create Date: 2026-05-13
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0027"
down_revision: Union[str, None] = "0026"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "marketing_sequence_steps",
        sa.Column("step_name", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("marketing_sequence_steps", "step_name")
