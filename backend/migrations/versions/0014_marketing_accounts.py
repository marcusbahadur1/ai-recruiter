"""Add marketing_accounts table

Revision ID: 0014
Revises: 0013
Create Date: 2026-04-24
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0014"
down_revision: Union[str, None] = "0013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "marketing_accounts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True),
        sa.Column("platform", sa.String(), nullable=False),
        sa.Column("account_name", sa.String(200), nullable=False),
        sa.Column("account_type", sa.String(), nullable=False, server_default="company"),
        sa.Column("linkedin_urn", sa.String(200), nullable=True),
        sa.Column("access_token", sa.Text(), nullable=True),
        sa.Column("refresh_token", sa.Text(), nullable=True),
        sa.Column("token_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("platform IN ('linkedin', 'twitter', 'facebook')", name="ck_marketing_accounts_platform"),
        sa.CheckConstraint("account_type IN ('personal', 'company')", name="ck_marketing_accounts_account_type"),
    )

    op.create_index("idx_marketing_accounts_tenant_id", "marketing_accounts", ["tenant_id"])

    # NULLS NOT DISTINCT: allow one personal + one company per tenant per platform,
    # AND one platform-level account (tenant_id IS NULL) per platform + account_type.
    # Standard UNIQUE treats NULLs as distinct, so multiple NULL rows would be allowed.
    # PostgreSQL 15+ NULLS NOT DISTINCT makes NULL == NULL for uniqueness purposes.
    op.execute(
        """
        CREATE UNIQUE INDEX uq_marketing_accounts_tenant_platform_type
        ON marketing_accounts (tenant_id, platform, account_type)
        NULLS NOT DISTINCT
        """
    )


def downgrade() -> None:
    op.drop_index("uq_marketing_accounts_tenant_platform_type", table_name="marketing_accounts")
    op.drop_index("idx_marketing_accounts_tenant_id", table_name="marketing_accounts")
    op.drop_table("marketing_accounts")
