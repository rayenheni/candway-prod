"""Merge migration heads m21 and m22b

Resolves the divergence between:
  - m21_add_active_snapshot_id_to_batch_jobs
  - m22b_enforce_company_id_not_null → m22 → p1prod202606300 → p1prod202606111615

Both converge at p1prod202606111615. This merge makes them linear.

Revision ID: m_merge_m21_m22b
Revises: m22b, m21_add_active_snapshot_id_to_batch_jobs
Create Date: 2026-07-01
"""
from alembic import op
import sqlalchemy as sa


revision = "m_merge_m21_m22b"
down_revision = ("m22b", "m21_add_active_snapshot_id_to_batch_jobs")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
