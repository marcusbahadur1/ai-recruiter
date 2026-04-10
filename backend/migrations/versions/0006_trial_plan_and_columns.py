"""Replace plan_enum with trial plans and add trial columns to tenants

Revision ID: 0006
Revises: 0005
Create Date: 2026-04-10
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_OLD_VALUES = ("free", "casual", "individual", "small_firm", "mid_firm", "enterprise")
_NEW_VALUES = ("trial", "trial_expired", "recruiter", "agency_small", "agency_medium", "enterprise")


def upgrade() -> None:
    # 1. Add trial columns
    op.add_column("tenants", sa.Column("trial_started_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("tenants", sa.Column("trial_ends_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("tenants", sa.Column("trial_expiry_email_sent_at", sa.DateTime(timezone=True), nullable=True))

    # 2. Migrate the plan column away from the old enum type.
    #    PostgreSQL enums cannot be altered in place while a column uses them,
    #    so we:
    #      a. Add a temporary TEXT column
    #      b. Copy + remap values (old → new best match)
    #      c. Drop the old enum column
    #      d. Create a new enum type with the new values
    #      e. Re-add the plan column with the new enum type
    #      f. Drop the temporary column

    op.add_column("tenants", sa.Column("plan_tmp", sa.Text(), nullable=True))

    # Remap old values to new equivalents
    op.execute("""
        UPDATE tenants SET plan_tmp = CASE plan::text
            WHEN 'free'       THEN 'trial'
            WHEN 'casual'     THEN 'recruiter'
            WHEN 'individual' THEN 'recruiter'
            WHEN 'small_firm' THEN 'agency_small'
            WHEN 'mid_firm'   THEN 'agency_medium'
            WHEN 'enterprise' THEN 'enterprise'
            ELSE 'trial'
        END
    """)

    # Drop the old plan column (which uses the old enum)
    op.drop_column("tenants", "plan")

    # Drop the old enum type
    op.execute("DROP TYPE IF EXISTS plan_enum")

    # Create the new enum type
    new_plan_enum = postgresql.ENUM(*_NEW_VALUES, name="plan_enum", create_type=False)
    new_plan_enum.create(op.get_bind(), checkfirst=True)

    # Re-add plan column with new enum
    op.add_column(
        "tenants",
        sa.Column(
            "plan",
            sa.Enum(*_NEW_VALUES, name="plan_enum"),
            nullable=False,
            server_default="trial",
        ),
    )

    # Copy remapped values into the new plan column
    op.execute("UPDATE tenants SET plan = plan_tmp::plan_enum")

    # Remove server default (application manages defaults)
    op.alter_column("tenants", "plan", server_default=None)

    # Drop the temp column
    op.drop_column("tenants", "plan_tmp")


def downgrade() -> None:
    # Add tmp column for rollback remapping
    op.add_column("tenants", sa.Column("plan_tmp", sa.Text(), nullable=True))

    op.execute("""
        UPDATE tenants SET plan_tmp = CASE plan::text
            WHEN 'trial'         THEN 'free'
            WHEN 'trial_expired' THEN 'free'
            WHEN 'recruiter'     THEN 'casual'
            WHEN 'agency_small'  THEN 'small_firm'
            WHEN 'agency_medium' THEN 'mid_firm'
            WHEN 'enterprise'    THEN 'enterprise'
            ELSE 'free'
        END
    """)

    op.drop_column("tenants", "plan")
    op.execute("DROP TYPE IF EXISTS plan_enum")

    old_plan_enum = postgresql.ENUM(*_OLD_VALUES, name="plan_enum", create_type=False)
    old_plan_enum.create(op.get_bind(), checkfirst=True)

    op.add_column(
        "tenants",
        sa.Column(
            "plan",
            sa.Enum(*_OLD_VALUES, name="plan_enum"),
            nullable=False,
            server_default="free",
        ),
    )

    op.execute("UPDATE tenants SET plan = plan_tmp::plan_enum")
    op.alter_column("tenants", "plan", server_default=None)
    op.drop_column("tenants", "plan_tmp")

    # Remove trial columns
    op.drop_column("tenants", "trial_expiry_email_sent_at")
    op.drop_column("tenants", "trial_ends_at")
    op.drop_column("tenants", "trial_started_at")
