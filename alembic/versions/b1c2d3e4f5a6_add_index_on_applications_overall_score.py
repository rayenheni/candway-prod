"""Add index on applications.overall_score for ranking performance.

Ranking endpoint sorts by overall_score DESC — without an index this
causes full table scan + filesort at scale.

Revision ID: b1c2d3e4f5a6
Revises: fe66b0844afb
Create Date: 2026-06-08 03:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b1c2d3e4f5a6"
down_revision: Union[str, Sequence[str], None] = "fe66b0844afb"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    conn = op.get_bind()
    result = conn.execute(
        sa.text(
            "SELECT COUNT(*) FROM information_schema.statistics "
            "WHERE table_schema = DATABASE() "
            "AND table_name = 'applications' "
            "AND index_name = 'ix_applications_overall_score'"
        )
    ).scalar()
    if result == 0:
        op.create_index("ix_applications_overall_score", "applications", ["overall_score"])


def downgrade():
    op.drop_index("ix_applications_overall_score", table_name="applications")
