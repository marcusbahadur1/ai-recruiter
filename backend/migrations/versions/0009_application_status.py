"""Add unified status and resume_filename to applications

Revision ID: 0009
Revises: 0008
Create Date: 2026-04-11
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: Union[str, None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Unified pipeline status for the full screener flow
    op.add_column(
        "applications",
        sa.Column(
            "status",
            sa.String(50),
            nullable=False,
            server_default="received",
        ),
    )
    op.add_column(
        "applications",
        sa.Column("resume_filename", sa.String(500), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("applications", "resume_filename")
    op.drop_column("applications", "status")
