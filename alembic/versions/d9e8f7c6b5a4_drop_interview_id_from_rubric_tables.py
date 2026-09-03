"""Drop interview_id from 3 rubric tables (dual-column phase completed).

interview_id columns on RubricScoringResult, InterviewRubricSummary,
and ExtractedSkill were kept during the migration for zero-downtime.
All reads have been switched to application_id; dual-writes have
been in place. Safe to drop now.

Revision ID: d9e8f7c6b5a4
Revises: c4d5e6f7a8b9
Create Date: 2026-06-08 12:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

revision: str = "d9e8f7c6b5a4"
down_revision: Union[str, Sequence[str], None] = "c4d5e6f7a8b9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _col_exists(table, column):
    conn = op.get_bind()
    return conn.execute(
        sa.text(f"SHOW COLUMNS FROM `{table}` LIKE :col"),
        {"col": column},
    ).fetchone() is not None


def _idx_exists(table, index_name):
    conn = op.get_bind()
    return conn.execute(
        sa.text("SHOW INDEX FROM `" + table + "` WHERE Key_name = :idx"),
        {"idx": index_name},
    ).fetchone() is not None


def _fks_referencing(table, column):
    """Names of every FK constraint that uses ``column`` on ``table``."""
    conn = op.get_bind()
    rows = conn.execute(
        sa.text(
            "SELECT CONSTRAINT_NAME FROM information_schema.KEY_COLUMN_USAGE "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = :t "
            "AND COLUMN_NAME = :c AND REFERENCED_TABLE_NAME IS NOT NULL"
        ),
        {"t": table, "c": column},
    ).fetchall()
    return [r[0] for r in rows]


def upgrade():
    conn = op.get_bind()
    # (table, indexes to drop on interview_id)
    tables_config = [
        ("rubric_scoring_results", ["idx_rubric_score_interview"]),
        ("interview_rubric_summaries", ["idx_rubric_summary_interview"]),
        ("extracted_skills", ["idx_extracted_skills_interview"]),
    ]
    for table, idx_names in tables_config:
        # MySQL refuses to drop an index still backing a foreign key, so drop
        # every FK that references interview_id FIRST (names were never stable
        # across the legacy chain — fk_rs_app/fk_irs_app/fk_es_app today).
        for fk in _fks_referencing(table, "interview_id"):
            conn.execute(sa.text(f"ALTER TABLE `{table}` DROP FOREIGN KEY `{fk}`"))
        for idx in idx_names:
            if _idx_exists(table, idx):
                conn.execute(sa.text(f"ALTER TABLE `{table}` DROP INDEX `{idx}`"))
        if _col_exists(table, "interview_id"):
            conn.execute(sa.text(f"ALTER TABLE `{table}` DROP COLUMN `interview_id`"))


def downgrade():
    conn = op.get_bind()
    # Restore the FK names actually used by the current schema.
    tables_config = [
        ("rubric_scoring_results", "fk_rs_app", ["idx_rubric_score_interview"]),
        ("interview_rubric_summaries", "fk_irs_app", ["interview_id", "idx_rubric_summary_interview"]),
        ("extracted_skills", "fk_es_app", ["idx_extracted_skills_interview"]),
    ]
    for table, fk_name, idx_names in tables_config:
        if not _col_exists(table, "interview_id"):
            op.add_column(
                table,
                sa.Column("interview_id", mysql.INTEGER(display_width=11), autoincrement=False, nullable=True),
            )
        for idx in idx_names:
            if not _idx_exists(table, idx):
                op.create_index(idx, table, ["interview_id"])
        existing = _fks_referencing(table, "interview_id")
        if fk_name not in existing:
            op.create_foreign_key(
                fk_name, table, "applications",
                ["interview_id"], ["id"],
            )
