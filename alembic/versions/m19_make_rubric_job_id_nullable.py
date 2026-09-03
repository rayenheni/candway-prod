"""Make rubrics.job_id nullable, add rubric_id to batch_jobs

Standalone skill trees are not tied to a specific job, so job_id
must be nullable. Also add rubric_id to batch_jobs so campaigns
can link directly to a skill tree.

Revision ID: m19_make_rubric_job_id_nullable
Revises: m18_add_rubric_snapshot_table
Create Date: 2026-06-27
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "m19_make_rubric_job_id_nullable"
down_revision: Union[str, None] = "m18_add_rubric_snapshot_table"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(conn, table_name: str, column_name: str) -> bool:
    insp = sa.inspect(conn)
    columns = [c["name"] for c in insp.get_columns(table_name)]
    return column_name in columns


def upgrade() -> None:
    conn = op.get_bind()

    # ── 1. Make rubrics.job_id nullable ───────────────────────────────
    op.drop_constraint("fk_rubric_job", "rubrics", type_="foreignkey")
    op.alter_column("rubrics", "job_id", existing_type=sa.Integer(), nullable=True)
    op.create_foreign_key(
        "fk_rubric_job",
        "rubrics", "jobs",
        ["job_id"], ["id"],
    )

    # ── 2. Add rubric_id to batch_jobs ────────────────────────────────
    if not _has_column(conn, "batch_jobs", "rubric_id"):
        op.add_column(
            "batch_jobs",
            sa.Column("rubric_id", sa.Integer(), sa.ForeignKey("rubrics.id"), nullable=True, index=True),
        )


def downgrade() -> None:
    conn = op.get_bind()

    # Drop rubric_id from batch_jobs
    if _has_column(conn, "batch_jobs", "rubric_id"):
        op.drop_constraint("batch_jobs_ibfk_3", "batch_jobs", type_="foreignkey")
        op.drop_column("batch_jobs", "rubric_id")

    # Revert rubrics.job_id to NOT NULL
    op.drop_constraint("rubrics_ibfk_1", "rubrics", type_="foreignkey")
    op.execute("UPDATE rubrics SET job_id = 0 WHERE job_id IS NULL")
    op.alter_column("rubrics", "job_id", existing_type=sa.Integer(), nullable=False)
    op.create_foreign_key(
        "rubrics_ibfk_1",
        "rubrics", "jobs",
        ["job_id"], ["id"],
    )
