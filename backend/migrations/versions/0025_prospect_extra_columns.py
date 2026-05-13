"""Add location, company_size, company_type, last_linkedin_post_at, score_breakdown, notes
to marketing_prospects.

Revision ID: 0025
Revises: 0024
Create Date: 2026-05-13
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0025"
down_revision: Union[str, None] = "0024"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("marketing_prospects", sa.Column("location", sa.Text(), nullable=True))
    op.add_column("marketing_prospects", sa.Column("company_size", sa.Integer(), nullable=True))
    op.add_column("marketing_prospects", sa.Column("company_type", sa.Text(), nullable=True))
    op.add_column(
        "marketing_prospects",
        sa.Column("last_linkedin_post_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "marketing_prospects",
        sa.Column("score_breakdown", postgresql.JSONB(), nullable=True),
    )
    op.add_column("marketing_prospects", sa.Column("notes", sa.Text(), nullable=True))


def downgrade() -> None:
    for col in ["notes", "score_breakdown", "last_linkedin_post_at", "company_type", "company_size", "location"]:
        op.drop_column("marketing_prospects", col)
