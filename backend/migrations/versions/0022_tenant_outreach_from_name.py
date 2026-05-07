"""Add outreach_from_name column to tenants

Allows each tenant to set a display name for outbound emails.
All mail still routes through the platform's verified SendGrid sender address
(outreach@airecruiterz.com); only the From display name changes per-tenant.

Example: "Marcus Bahadur, Acme Corp <outreach@airecruiterz.com>"

Revision ID: 0022
Revises: 0021
Create Date: 2026-05-07
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0022"
down_revision: Union[str, None] = "0021"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "tenants",
        sa.Column("outreach_from_name", sa.String(300), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("tenants", "outreach_from_name")
