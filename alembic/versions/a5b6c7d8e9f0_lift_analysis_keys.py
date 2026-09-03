"""Lift top-level analysis keys out of analysis_json (Bug B-31).

Adds four dedicated columns to applications:
  * analysis_strengths       JSON list of strings
  * analysis_weaknesses      JSON list of strings
  * analysis_score_breakdown JSON dict (cv/interview/per_turn)
  * analysis_score           float, indexed

A backfill script (``backend/migrations/analysis_columns_backfill.py``)
copies the values from the analysis_json bag into the new columns
on existing rows. New writes go to both — see
``backend/analysis_columns.py`` for the helper.

Revision ID: a5b6c7d8e9f0
Revises: f4a5b6c7d8e9
Create Date: 2026-06-02 17:30:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a5b6c7d8e9f0"
down_revision: Union[str, Sequence[str], None] = "f4a5b6c7d8e9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "applications",
        sa.Column("analysis_strengths", sa.JSON(), nullable=True),
    )
    op.add_column(
        "applications",
        sa.Column("analysis_weaknesses", sa.JSON(), nullable=True),
    )
    op.add_column(
        "applications",
        sa.Column("analysis_score_breakdown", sa.JSON(), nullable=True),
    )
    op.add_column(
        "applications",
        sa.Column("analysis_score", sa.Float(), nullable=True),
    )
    op.create_index(
        "idx_applications_analysis_score",
        "applications",
        ["analysis_score"],
    )


def downgrade() -> None:
    op.drop_index("idx_applications_analysis_score", table_name="applications")
    try:
        op.drop_column("applications", "analysis_score")
    except Exception:
        pass
    try:
        op.drop_column("applications", "analysis_score_breakdown")
    except Exception:
        pass
    try:
        op.drop_column("applications", "analysis_weaknesses")
    except Exception:
        pass
    try:
        op.drop_column("applications", "analysis_strengths")
    except Exception:
        pass