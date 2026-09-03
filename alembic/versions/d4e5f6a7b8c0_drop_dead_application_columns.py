"""M004: Drop dead columns from applications table.

Revision ID: d4e5f6a7b8c0
Revises: c3d4e5f6a7b9
Create Date: 2026-06-11

Drops columns on the applications table that were only ever written but
never read — reads all went through EvaluationSession / EvaluationResult.

Safe to drop because:
  - proctoring_violations     → EvaluationSession.proctoring_violations
  - generated_questions       → EvaluationSession.generated_questions
  - calibration_score         → EvaluationSession.calibration_score
  - calibration_verified_skills → EvaluationSession.calibration_verified_skills
  - fraud_reported_by         → EvaluationResult.fraud_reported_by
  - fraud_reported_at         → EvaluationResult.fraud_reported_at
  - video_transcript          → EvaluationSession.video_transcript
  - video_analysis_json       → EvaluationSession.video_analysis_json
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "d4e5f6a7b8c0"
down_revision: Union[str, Sequence[str], None] = "c3d4e5f6a7b9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _col_exists(conn, column: str) -> bool:
    return (
        conn.execute(
            sa.text(
                "SELECT COLUMN_NAME FROM information_schema.COLUMNS "
                "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'applications' "
                "AND COLUMN_NAME = :col"
            ),
            {"col": column},
        ).fetchone()
        is not None
    )


DEAD_COLUMNS = [
    "proctoring_violations",
    "generated_questions",
    "calibration_score",
    "calibration_verified_skills",
    "fraud_reported_by",
    "fraud_reported_at",
    "video_transcript",
    "video_analysis_json",
]


def upgrade():
    conn = op.get_bind()
    for col in DEAD_COLUMNS:
        if _col_exists(conn, col):
            op.drop_column("applications", col)


def downgrade():
    # Columns are already empty / unused — restore as nullable
    conn = op.get_bind()
    restores = {
        "proctoring_violations": sa.Text(),
        "generated_questions": sa.Text(),
        "calibration_score": sa.Float(),
        "calibration_verified_skills": sa.Text(),
        "fraud_reported_by": sa.Integer(),
        "fraud_reported_at": sa.DateTime(),
        "video_transcript": sa.Text(),
        "video_analysis_json": sa.JSON(),
    }
    for col, col_type in restores.items():
        if not _col_exists(conn, col):
            op.add_column("applications", sa.Column(col, col_type, nullable=True))
