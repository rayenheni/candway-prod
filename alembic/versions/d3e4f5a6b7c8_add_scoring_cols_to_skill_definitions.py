"""Add scoring columns (keywords, levels, is_required) to skill_definitions.

Makes SkillDefinition the source of truth for scoring data by adding
the fields that were previously only stored in rubric_json.

Revision ID: d3e4f5a6b7c8
Revises: c2d3e4f5a6b7
Create Date: 2026-06-08 04:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

revision: str = "d3e4f5a6b7c8"
down_revision: Union[str, Sequence[str], None] = "c2d3e4f5a6b7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    conn = op.get_bind()
    # The skill_definitions table is not created by any migration in the chain
    # (it existed only on the legacy DB). On a fresh deployment it is created
    # later by the m53 schema-sync migration with all columns already present.
    table_exists = conn.execute(
        sa.text(
            "SELECT COUNT(*) FROM information_schema.tables "
            "WHERE table_schema = DATABASE() AND table_name = 'skill_definitions'"
        )
    ).scalar()
    if not table_exists:
        return
    for col in ("keywords", "levels", "is_required"):
        exists = conn.execute(
            sa.text(
                "SELECT COUNT(*) FROM information_schema.columns "
                "WHERE table_schema = DATABASE() "
                "AND table_name = 'skill_definitions' "
                "AND column_name = :c"
            ).bindparams(c=col)
        ).scalar()
        if not exists:
            if col == "is_required":
                op.add_column("skill_definitions", sa.Column("is_required", sa.Boolean(), default=False))
            elif col == "keywords":
                op.add_column("skill_definitions", sa.Column("keywords", mysql.JSON(), nullable=True))
            elif col == "levels":
                op.add_column("skill_definitions", sa.Column("levels", mysql.JSON(), nullable=True))


def downgrade():
    for col in ("keywords", "levels", "is_required"):
        try:
            op.drop_column("skill_definitions", col)
        except Exception:
            pass
