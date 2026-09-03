"""Add structured decline columns to applications table.

Replaces the previous approach of jamming the candidate's decline
reason into ``recruiter_notes`` (Bug U-07 in the Candidate
Experience Audit). The old prefix-stripping string format
("Candidate declined invitation. Reason: ...") was impossible to
query against in SQL and showed up in the recruiter UI as
invisible blob text.

New columns:
  * ``declined_at``        — DateTime, indexed
  * ``decline_reason``     — Text, nullable
  * ``decline_initiated_by`` — 'candidate' or 'recruiter'

The status column itself continues to be the source of truth
(rejected vs not-rejected); these columns just carry the structured
metadata. Existing rows are backfilled with NULL values, which is
the right thing to do (we don't know if/when they were declined).

Revision ID: e3f4a5b6c7d8
Revises: d2e3f4a5b6c7
Create Date: 2026-06-02 16:30:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "e3f4a5b6c7d8"
down_revision: Union[str, Sequence[str], None] = "d2e3f4a5b6c7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "applications",
        sa.Column("declined_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "applications",
        sa.Column("decline_reason", sa.Text(), nullable=True),
    )
    op.add_column(
        "applications",
        sa.Column("decline_initiated_by", sa.String(length=32), nullable=True),
    )
    op.create_index(
        "idx_applications_declined_at",
        "applications",
        ["declined_at"],
    )


def downgrade() -> None:
    op.drop_index("idx_applications_declined_at", table_name="applications")
    try:
        op.drop_column("applications", "decline_initiated_by")
    except Exception:
        pass
    try:
        op.drop_column("applications", "decline_reason")
    except Exception:
        pass
    try:
        op.drop_column("applications", "declined_at")
    except Exception:
        pass