"""Remove dead deprecated fields, add rubric_seniority to application_scores

Revision ID: b9a8c7d6e5f4
Revises: a1b9c8d7e6f5
Create Date: 2026-06-08 15:00:00.000000

Drops columns from `applications` that have zero runtime readers:
  - generated_questions
  - video_transcript
  - video_analysis_json
  - calibration_score
  - calibration_verified_skills
  - final_eval_done
  - evaluation_started_at

Adds rubric_seniority to `application_scores` (needed to unblock
the deprecated column reader migration for app.rubric_seniority).
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

revision: str = "b9a8c7d6e5f4"
down_revision: Union[str, Sequence[str], None] = "a1b9c8d7e6f5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _col_exists(table: str, column: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return column in {c["name"] for c in inspector.get_columns(table)}


def _table_exists(table: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return table in inspector.get_table_names()


def upgrade():
    # Drop dead columns from applications. On a fresh DB most of these columns
    # were never created (the chain never adds them), so guard every drop.
    for col in (
        "generated_questions",
        "video_transcript",
        "video_analysis_json",
        "calibration_score",
        "calibration_verified_skills",
        "final_eval_done",
        "evaluation_started_at",
    ):
        if _col_exists("applications", col):
            op.drop_column("applications", col)

    # Add rubric_seniority to application_scores
    if _table_exists("application_scores") and not _col_exists("application_scores", "rubric_seniority"):
        op.add_column(
            "application_scores",
            sa.Column("rubric_seniority", sa.String(20), nullable=True, server_default="mid"),
        )


def downgrade():
    if _table_exists("application_scores") and _col_exists("application_scores", "rubric_seniority"):
        op.drop_column("application_scores", "rubric_seniority")
    if not _col_exists("applications", "evaluation_started_at"):
        op.add_column("applications", sa.Column("evaluation_started_at", sa.DateTime(), nullable=True))
    if not _col_exists("applications", "final_eval_done"):
        op.add_column("applications", sa.Column("final_eval_done", sa.Boolean(), server_default=sa.text("0")))
    if not _col_exists("applications", "calibration_verified_skills"):
        op.add_column("applications", sa.Column("calibration_verified_skills", sa.Text(), nullable=True))
    if not _col_exists("applications", "calibration_score"):
        op.add_column("applications", sa.Column("calibration_score", sa.Float(), nullable=True))
    if not _col_exists("applications", "video_analysis_json"):
        op.add_column("applications", sa.Column("video_analysis_json", mysql.LONGTEXT(), nullable=True))
    if not _col_exists("applications", "video_transcript"):
        op.add_column("applications", sa.Column("video_transcript", mysql.LONGTEXT(), nullable=True))
    if not _col_exists("applications", "generated_questions"):
        op.add_column("applications", sa.Column("generated_questions", sa.Text(), nullable=True))
