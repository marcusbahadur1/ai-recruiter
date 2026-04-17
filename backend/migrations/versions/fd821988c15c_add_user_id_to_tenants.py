"""add_user_id_to_tenants

Adds user_id (UUID, nullable) to the tenants table and a non-unique index on
chat_sessions.user_id.

The column carries no foreign key — Supabase auth.users lives in the separate
auth schema and is referenced by value only (see Tenant.user_id in
app/models/tenant.py).

Revision ID: fd821988c15c
Revises: 0007
Create Date: 2026-04-10 15:46:37.087612
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'fd821988c15c'
down_revision: Union[str, None] = '0007'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add user_id to tenants (no FK — auth.users is in a separate Supabase schema)
    op.add_column(
        'tenants',
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=True),
    )

    # Index on chat_sessions.user_id for efficient per-user session lookups
    op.create_index(
        op.f('ix_chat_sessions_user_id'),
        'chat_sessions',
        ['user_id'],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_chat_sessions_user_id'), table_name='chat_sessions')
    op.drop_column('tenants', 'user_id')
