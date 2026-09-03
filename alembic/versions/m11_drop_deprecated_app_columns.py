"""drop deprecated columns from applications

Migration to drop 11 deprecated columns from the applications table.
These columns were migrated to CvDocument and EvaluationSession tables.

Revision ID: m11_drop_deprecated_app_columns
Revises: m10_drop_recommended_verdicts
Create Date: 2026-06-25 10:15:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "m11_drop_deprecated_app_columns"
down_revision: Union[str, None] = "m10_drop_recommended_verdicts"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    try:
        op.drop_column("applications", "declared_role")
    except Exception:
        pass
    try:
        op.drop_column("applications", "detected_role")
    except Exception:
        pass
    try:
        op.drop_column("applications", "cv_text_anonymized")
    except Exception:
        pass
    try:
        op.drop_column("applications", "cv_file_path")
    except Exception:
        pass
    try:
        op.drop_column("applications", "analysis_json")
    except Exception:
        pass
    try:
        op.drop_column("applications", "cv_embedding")
    except Exception:
        pass
    try:
        op.drop_column("applications", "interview_log")
    except Exception:
        pass
    try:
        op.drop_column("applications", "interview_questions")
    except Exception:
        pass
    try:
        op.drop_column("applications", "video_file_path")
    except Exception:
        pass
    try:
        op.drop_column("applications", "roadmap_json")
    except Exception:
        pass
    try:
        op.drop_column("applications", "cv_review_json")
    except Exception:
        pass
def downgrade() -> None:
    # Cannot restore — data was migrated to CvDocument/EvaluationSession
    pass
