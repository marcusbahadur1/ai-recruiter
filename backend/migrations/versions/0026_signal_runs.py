"""Add marketing_signal_runs table and extra columns to marketing_signals.

New table: marketing_signal_runs (id, tenant_id, started_at, completed_at, signals_found)

New columns on marketing_signals:
  location (Text, nullable)
  company_type (Text, nullable)
  job_count (Integer, nullable)

Revision ID: 0026
Revises: 0025
Create Date: 2026-05-13
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0026"
down_revision: Union[str, None] = "0025"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── 1. New columns on marketing_signals ─────────────────────────────────
    op.add_column("marketing_signals", sa.Column("location", sa.Text(), nullable=True))
    op.add_column("marketing_signals", sa.Column("company_type", sa.Text(), nullable=True))
    op.add_column("marketing_signals", sa.Column("job_count", sa.Integer(), nullable=True))

    # ── 2. marketing_signal_runs ─────────────────────────────────────────────
    op.create_table(
        "marketing_signal_runs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("signals_found", sa.Integer(), nullable=False, server_default="0"),
    )

    op.create_index("ix_signal_runs_tenant_started", "marketing_signal_runs", ["tenant_id", "started_at"])

    # RLS
    op.execute("ALTER TABLE marketing_signal_runs ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE marketing_signal_runs FORCE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.execute("ALTER TABLE marketing_signal_runs NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE marketing_signal_runs DISABLE ROW LEVEL SECURITY")
    op.drop_index("ix_signal_runs_tenant_started", table_name="marketing_signal_runs")
    op.drop_table("marketing_signal_runs")

    op.drop_column("marketing_signals", "job_count")
    op.drop_column("marketing_signals", "company_type")
    op.drop_column("marketing_signals", "location")
