"""Fix jobs table: rename company -> company_name + add missing nullable columns.

The initial migration (367fd943df54) created the jobs table with a
``company`` VARCHAR(255) column, but the SQLAlchemy model (job.py)
defines it as ``company_name``.  A standalone rename script existed
but was never executed against production, causing every SELECT on
the jobs table to fail with ``Unknown column 'jobs.company_name'``.

Two additional model columns (``interview_instructions``,
``custom_question_prompt``) were also never migrated — they are
nullable so the INSERT path never crashed *yet*, but setting them
via the recruiter UI would produce the same 500.

Revision ID: m64
Revises: m63
Create Date: 2026-08-22
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "m64"
down_revision: Union[str, None] = "m63"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name
    inspector = sa.inspect(bind)
    cols = {c["name"] for c in inspector.get_columns("jobs")}

    # ── 1. Rename jobs.company -> jobs.company_name (preserve data) ──
    if "company" in cols and "company_name" not in cols:
        if dialect == "sqlite":
            with op.batch_alter_table("jobs") as batch_op:
                batch_op.alter_column(
                    "company", new_column_name="company_name"
                )
        elif dialect == "mysql":
            op.execute(
                "ALTER TABLE jobs CHANGE COLUMN company company_name VARCHAR(255)"
            )
        else:
            op.execute(
                "ALTER TABLE jobs RENAME COLUMN company TO company_name"
            )

    # ── 2. Add interview_instructions (nullable Text, no data loss) ──
    if "interview_instructions" not in cols:
        op.add_column(
            "jobs",
            sa.Column("interview_instructions", sa.Text(), nullable=True),
        )

    # ── 3. Add custom_question_prompt (nullable Text, no data loss) ──
    if "custom_question_prompt" not in cols:
        op.add_column(
            "jobs",
            sa.Column("custom_question_prompt", sa.Text(), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name
    inspector = sa.inspect(bind)
    cols = {c["name"] for c in inspector.get_columns("jobs")}

    # ── Drop added columns (reverse order) ──
    if "custom_question_prompt" in cols:
        op.drop_column("jobs", "custom_question_prompt")
    if "interview_instructions" in cols:
        op.drop_column("jobs", "interview_instructions")

    # ── Reverse rename: company_name -> company ──
    if "company_name" in cols and "company" not in cols:
        if dialect == "sqlite":
            with op.batch_alter_table("jobs") as batch_op:
                batch_op.alter_column(
                    "company_name", new_column_name="company"
                )
        elif dialect == "mysql":
            op.execute(
                "ALTER TABLE jobs CHANGE COLUMN company_name company VARCHAR(255)"
            )
        else:
            op.execute(
                "ALTER TABLE jobs RENAME COLUMN company_name TO company"
            )
