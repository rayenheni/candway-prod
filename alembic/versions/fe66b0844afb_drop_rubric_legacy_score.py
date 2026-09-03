"""Drop rubric_legacy_score from applications (DEAD column).

Confirmed DEAD — zero production readers or writers remain.
Last write was removed during scoring refactor (Phase 2).

Revision ID: fe66b0844afb
Revises: d9e8f7c6b5a4
Create Date: 2026-06-08 02:30:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

revision: str = "fe66b0844afb"
down_revision: Union[str, Sequence[str], None] = "d9e8f7c6b5a4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    conn = op.get_bind()
    exists = conn.execute(
        sa.text("SHOW COLUMNS FROM `applications` LIKE 'rubric_legacy_score'")
    ).fetchone() is not None
    if exists:
        op.drop_column("applications", "rubric_legacy_score")


def downgrade():
    op.add_column(
        "applications",
        sa.Column("rubric_legacy_score", mysql.FLOAT(), nullable=True),
    )
