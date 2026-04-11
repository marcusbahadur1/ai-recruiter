"""Add interview_type to jobs and test_sessions

Revision ID: 0010
Revises: 0009
Create Date: 2026-04-11
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0010"
down_revision: Union[str, None] = "0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "jobs",
        sa.Column(
            "interview_type",
            sa.String(20),
            nullable=False,
            server_default="text",
        ),
    )
    op.add_column(
        "test_sessions",
        sa.Column(
            "interview_type",
            sa.String(20),
            nullable=False,
            server_default="text",
        ),
    )
    op.add_column(
        "test_sessions",
        sa.Column(
            "recording_urls",
            postgresql.JSONB,
            nullable=False,
            server_default="[]",
        ),
    )
    op.add_column(
        "test_sessions",
        sa.Column(
            "transcripts",
            postgresql.JSONB,
            nullable=False,
            server_default="[]",
        ),
    )


def downgrade() -> None:
    op.drop_column("test_sessions", "transcripts")
    op.drop_column("test_sessions", "recording_urls")
    op.drop_column("test_sessions", "interview_type")
    op.drop_column("jobs", "interview_type")
