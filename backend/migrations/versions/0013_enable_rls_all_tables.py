"""Enable Row-Level Security on all application tables

Resolves Supabase security warnings:
  - rls_disabled_in_public   (tables publicly readable/writable via PostgREST)
  - sensitive_columns_exposed (API keys, emails, passwords accessible via anon key)

All application tables now have RLS enabled.  No PERMISSIVE policies are added,
which means the implicit Postgres rule applies: deny all access to non-superuser
roles (anon, authenticated).

The backend exclusively uses the Supabase service_role key, which has BYPASSRLS
and is therefore completely unaffected by these changes.

Revision ID: 0013
Revises: 0012
Create Date: 2026-04-24
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0013"
down_revision: Union[str, None] = "0012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Every table managed by this application.
_TABLES = [
    "tenants",
    "jobs",
    "candidates",
    "applications",
    "promo_codes",
    "chat_sessions",
    "rag_documents",
    "job_audit_events",
    "team_members",
    "test_sessions",
]


def upgrade() -> None:
    for table in _TABLES:
        # Enable RLS — blocks anon/authenticated roles from accessing the table
        # via Supabase PostgREST.  service_role (used by the FastAPI backend)
        # has BYPASSRLS and is unaffected.
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")

        # FORCE RLS ensures that even table owners (postgres role) are subject
        # to policies.  This prevents accidental exposure if the role used by
        # a future integration does not have BYPASSRLS.
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")


def downgrade() -> None:
    for table in reversed(_TABLES):
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
