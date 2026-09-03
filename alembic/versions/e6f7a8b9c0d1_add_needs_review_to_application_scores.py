"""Add needs_review + needs_review_reason columns to application_scores

Revision ID: e6f7a8b9c0d1
Revises: a2b3c4d5e6f7
Create Date: 2026-06-10 10:00:00.000000

Phase 5: AI output schema validation — when AI returns malformed output,
the ApplicationScore row is flagged so recruiters know to manually review.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e6f7a8b9c0d1"
down_revision: Union[str, Sequence[str], None] = "a2b3c4d5e6f7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.add_column(
        "application_scores",
        sa.Column("needs_review", sa.Boolean(), server_default=sa.text("0"), nullable=False),
    )
    op.add_column(
        "application_scores",
        sa.Column("needs_review_reason", sa.String(500), nullable=True),
    )
    op.create_index(
        "idx_app_score_needs_review",
        "application_scores",
        ["needs_review"],
    )


def downgrade():
    op.drop_index("idx_app_score_needs_review", table_name="application_scores")
    op.drop_column("application_scores", "needs_review_reason")
    op.drop_column("application_scores", "needs_review")
