"""Merge migration heads m33 and m38

Resolves the divergence between:
  - m33_normalize_batch_job_counters (tenant/candidate branch)
  - m38_add_subscription_columns_to_profiles (job-wizard branch)

Both converge at p1prod202606300. This merge makes them linear.

Revision ID: m_merge_m33_m38
Revises: m33, m38
Create Date: 2026-07-06
"""
from alembic import op
import sqlalchemy as sa


revision = "m_merge_m33_m38"
down_revision = ("m33", "m38")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
