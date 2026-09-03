"""Merge migration heads m25 and m_merge_m21_m22b

Resolves the divergence between:
  - m25_add_candidate_table
  - m_merge_m21_m22b

Both converge at the same base. This merge makes them linear.

Revision ID: m_merge_m25_m_merge
Revises: m25, m_merge_m21_m22b
Create Date: 2026-07-02
"""
from alembic import op
import sqlalchemy as sa


revision = "m_merge_m25_m_merge"
down_revision = ("m25", "m_merge_m21_m22b")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
