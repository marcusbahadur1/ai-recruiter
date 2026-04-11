"""Add screener mode, application screening columns, and test_sessions table

Revision ID: 0008
Revises: fd821988c15c
Create Date: 2026-04-10
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0008"
down_revision: Union[str, None] = "fd821988c15c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── jobs: add mode column ─────────────────────────────────────────────────
    op.add_column(
        "jobs",
        sa.Column(
            "mode",
            sa.String(50),
            nullable=False,
            server_default="talent_scout",
        ),
    )

    # ── applications: add new screening / test / interview columns ────────────
    op.add_column("applications", sa.Column("resume_score", sa.Integer(), nullable=True))
    op.add_column("applications", sa.Column("resume_reasoning", sa.Text(), nullable=True))
    op.add_column("applications", sa.Column("resume_strengths", postgresql.JSONB(), nullable=True))
    op.add_column("applications", sa.Column("resume_gaps", postgresql.JSONB(), nullable=True))
    op.add_column("applications", sa.Column("test_evaluation", postgresql.JSONB(), nullable=True))
    op.add_column("applications", sa.Column("test_completed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("applications", sa.Column("interview_invite_token", sa.String(255), nullable=True))
    op.add_column("applications", sa.Column("interview_invite_expires_at", sa.DateTime(timezone=True), nullable=True))

    # ── test_sessions table ───────────────────────────────────────────────────
    op.create_table(
        "test_sessions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("application_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token", sa.String(255), nullable=False, unique=True),
        sa.Column("token_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("token_used", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("questions", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("answers", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("status", sa.String(50), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["application_id"], ["applications.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_test_sessions_application_id", "test_sessions", ["application_id"])
    op.create_index("ix_test_sessions_token", "test_sessions", ["token"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_test_sessions_token", table_name="test_sessions")
    op.drop_index("ix_test_sessions_application_id", table_name="test_sessions")
    op.drop_table("test_sessions")

    op.drop_column("applications", "interview_invite_expires_at")
    op.drop_column("applications", "interview_invite_token")
    op.drop_column("applications", "test_completed_at")
    op.drop_column("applications", "test_evaluation")
    op.drop_column("applications", "resume_gaps")
    op.drop_column("applications", "resume_strengths")
    op.drop_column("applications", "resume_reasoning")
    op.drop_column("applications", "resume_score")

    op.drop_column("jobs", "mode")
