"""Add unified status and resume_filename to applications
Revision ID: 0009
Revises: 0008
Create Date: 2026-04-11
"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: Union[str, None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.execute("ALTER TABLE applications ADD COLUMN IF NOT EXISTS status VARCHAR(50) NOT NULL DEFAULT 'received'")
    op.execute("ALTER TABLE applications ADD COLUMN IF NOT EXISTS resume_filename VARCHAR(500)")

def downgrade() -> None:
    op.drop_column("applications", "resume_filename")
    op.drop_column("applications", "status")
