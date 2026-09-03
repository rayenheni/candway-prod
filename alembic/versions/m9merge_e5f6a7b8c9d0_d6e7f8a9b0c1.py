"""M9-MERGE: Merge M005 (drop application_scores) and M008 (scoring_status state machine).

Revision ID: m9merge_e5f6a7b8c9d0_d6e7f8a9b0c1
Revises: e5f6a7b8c9d0, d6e7f8a9b0c1
Create Date: 2026-06-12

Merge of two diverged heads:

  Head A: e5f6a7b8c9d0 — M005: Drop application_scores table.
  Head B: d6e7f8a9b0c1 — M008: Add scoring_status state machine.

These migrations touch different tables:
  - M005: only application_scores (dropped)
  - M008: only evaluation_results (adds columns, constraints)

No overlapping operations. Safe merge.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "m9merge_e5f6a7b8c9d0_d6e7f8a9b0c1"
down_revision: Union[str, Sequence[str], None] = ("e5f6a7b8c9d0", "d6e7f8a9b0c1")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
