"""Add interview duration and total questions columns to jobs table.

Revision ID: m62
Revises: m61
Create Date: 2026-08-20
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "m62"
down_revision: Union[str, None] = "m61"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name
    inspector = sa.inspect(bind)
    cols = {c["name"] for c in inspector.get_columns("jobs")}

    if dialect == "sqlite":
        with op.batch_alter_table("jobs") as batch_op:
            if "total_questions" not in cols:
                batch_op.add_column(sa.Column("total_questions", sa.Integer(), nullable=True))
            if "time_limit_seconds" not in cols:
                batch_op.add_column(sa.Column("time_limit_seconds", sa.Integer(), nullable=True))
            if "duration_minutes" not in cols:
                batch_op.add_column(sa.Column("duration_minutes", sa.Integer(), nullable=True))
    else:
        if "total_questions" not in cols:
            op.add_column("jobs", sa.Column("total_questions", sa.Integer(), nullable=True))
        if "time_limit_seconds" not in cols:
            op.add_column("jobs", sa.Column("time_limit_seconds", sa.Integer(), nullable=True))
        if "duration_minutes" not in cols:
            op.add_column("jobs", sa.Column("duration_minutes", sa.Integer(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name
    inspector = sa.inspect(bind)
    cols = {c["name"] for c in inspector.get_columns("jobs")}

    if dialect == "sqlite":
        with op.batch_alter_table("jobs") as batch_op:
            for col in ("duration_minutes", "time_limit_seconds", "total_questions"):
                if col in cols:
                    batch_op.drop_column(col)
    else:
        for col in ("duration_minutes", "time_limit_seconds", "total_questions"):
            if col in cols:
                op.drop_column("jobs", col)
