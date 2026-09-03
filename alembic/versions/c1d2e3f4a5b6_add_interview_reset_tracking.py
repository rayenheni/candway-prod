"""Add interview reset tracking columns to applications table.

Lifts ``_reset_count`` and ``_last_reset`` out of the analysis_json
JSON-bag (Bug B-09 in the Candidate Experience Audit). The previous
design stored these in analysis_json, which is overwritten on every
CV reanalysis — silently resetting the per-application reset quota
and letting candidates burn through unlimited interview retries.

Revision ID: c1d2e3f4a5b6
Revises: d8fefe0773fd
Create Date: 2026-06-02 12:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c1d2e3f4a5b6"
down_revision: Union[str, Sequence[str], None] = "d8fefe0773fd"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add durable reset-tracking columns."""
    op.add_column(
        "applications",
        sa.Column(
            "interview_reset_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "applications",
        sa.Column("interview_last_reset_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    """Remove reset-tracking columns."""
    try:
        op.drop_column("applications", "interview_last_reset_at")
    except Exception:
        pass
    try:
        op.drop_column("applications", "interview_reset_count")
    except Exception:
        pass