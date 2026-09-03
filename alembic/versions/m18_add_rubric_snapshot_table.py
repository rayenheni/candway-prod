"""Add rubric_snapshots table + FK columns to evaluation_sessions and evaluation_results

Migration ID: m18_add_rubric_snapshot_table
Revises: m17_add_missing_application_columns
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = "m18_add_rubric_snapshot_table"
down_revision: Union[str, None] = "m17_add_missing_application_columns"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(name: str) -> bool:
    bind = op.get_bind()
    return bind.dialect.has_table(bind, name)


def _has_column(conn, table_name: str, column_name: str) -> bool:
    insp = sa.inspect(conn)
    columns = [c["name"] for c in insp.get_columns(table_name)]
    return column_name in columns


def upgrade() -> None:
    conn = op.get_bind()

    # ── 1. Create rubric_snapshots table ────────────────────────────
    if not _has_table("rubric_snapshots"):
        op.create_table(
            "rubric_snapshots",
            sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
            sa.Column("original_rubric_id", sa.Integer, sa.ForeignKey("rubrics.id"), nullable=True, index=True),
            sa.Column("job_id", sa.Integer, sa.ForeignKey("jobs.id"), nullable=True, index=True),
            sa.Column("version", sa.Integer, nullable=False, server_default=sa.text("1")),
            sa.Column("criteria_json", sa.JSON, nullable=True),
            sa.Column("skill_weights_json", sa.JSON, nullable=True),
            sa.Column("scoring_rules_json", sa.JSON, nullable=True),
            sa.Column("rubric_title", sa.String(255), nullable=True),
            sa.Column("passing_score", sa.Float, nullable=True),
            sa.Column("max_score", sa.Float, nullable=True),
            sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        )
        op.create_index(
            "idx_rubric_snapshot_original",
            "rubric_snapshots",
            ["original_rubric_id"],
        )
        op.create_index(
            "idx_rubric_snapshot_job",
            "rubric_snapshots",
            ["job_id"],
        )

    # ── 2. Add rubric_snapshot_id to evaluation_sessions ────────────
    if not _has_column(conn, "evaluation_sessions", "rubric_snapshot_id"):
        op.add_column(
            "evaluation_sessions",
            sa.Column("rubric_snapshot_id", sa.Integer, sa.ForeignKey("rubric_snapshots.id"), nullable=True, index=True),
        )

    # ── 3. Add rubric_snapshot_id to evaluation_results ─────────────
    if not _has_column(conn, "evaluation_results", "rubric_snapshot_id"):
        op.add_column(
            "evaluation_results",
            sa.Column("rubric_snapshot_id", sa.Integer, sa.ForeignKey("rubric_snapshots.id"), nullable=True, index=True),
        )


def downgrade() -> None:
    conn = op.get_bind()

    if _has_column(conn, "evaluation_results", "rubric_snapshot_id"):
        op.drop_column("evaluation_results", "rubric_snapshot_id")

    if _has_column(conn, "evaluation_sessions", "rubric_snapshot_id"):
        op.drop_column("evaluation_sessions", "rubric_snapshot_id")

    if _has_table("rubric_snapshots"):
        op.drop_table("rubric_snapshots")
