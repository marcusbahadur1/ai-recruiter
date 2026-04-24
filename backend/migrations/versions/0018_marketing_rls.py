"""Enable Row-Level Security on all marketing tables

Follows the same pattern as migration 0013 (RLS on all application tables).
The backend exclusively uses the Supabase service_role key which has BYPASSRLS
and is completely unaffected. No permissive policies are added — implicit
deny-all applies to anon/authenticated roles via PostgREST.

Revision ID: 0018
Revises: 0017
Create Date: 2026-04-24
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0018"
down_revision: Union[str, None] = "0017"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLES = [
    "marketing_accounts",
    "marketing_settings",
    "marketing_posts",
    "marketing_engagement",
]


def upgrade() -> None:
    for table in _TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")


def downgrade() -> None:
    for table in reversed(_TABLES):
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
