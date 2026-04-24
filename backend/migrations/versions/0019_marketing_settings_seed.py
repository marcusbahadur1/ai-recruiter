"""Seed platform-level default marketing_settings row

Inserts the platform account's default settings (tenant_id IS NULL).
is_active=FALSE until the platform LinkedIn company page is connected.
ON CONFLICT DO NOTHING is safe to re-run.

Revision ID: 0019
Revises: 0018
Create Date: 2026-04-24
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0019"
down_revision: Union[str, None] = "0018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO marketing_settings (
            tenant_id,
            post_frequency,
            post_time_utc,
            post_types_enabled,
            platforms_enabled,
            target_audience,
            tone,
            topics,
            auto_engage,
            engagement_per_day,
            requires_approval,
            include_images,
            is_active
        ) VALUES (
            NULL,
            'twice_weekly',
            '09:00',
            '["thought_leadership","industry_stat","success_story","tip"]',
            '["linkedin"]',
            'Recruitment agency owners and directors',
            'professional',
            '["AI recruitment","time-to-hire","passive candidates","recruitment automation"]',
            TRUE,
            10,
            TRUE,
            TRUE,
            FALSE
        )
        ON CONFLICT DO NOTHING
        """
    )


def downgrade() -> None:
    # Remove the platform-level seed row only (tenant_id IS NULL).
    # Tenant rows are user data and must not be deleted on downgrade.
    op.execute("DELETE FROM marketing_settings WHERE tenant_id IS NULL")
