"""Add missing Application columns

Migration ID: m17_add_missing_application_columns
Revises: m16_drop_deprecated_interview_state_columns
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "m17_add_missing_application_columns"
down_revision: Union[str, None] = "m16_drop_deprecated_interview_state_columns"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add missing columns to applications table
    missing_cols = [
        sa.Column("declared_role", sa.String(255), nullable=True),
        sa.Column("detected_role", sa.String(255), nullable=True),
        sa.Column("cv_text_anonymized", sa.Text, nullable=True),
        sa.Column("cv_file_path", sa.String(512), nullable=True),
        sa.Column("analysis_json", sa.Text, nullable=True),
        sa.Column("cv_embedding", sa.LargeBinary, nullable=True),
        sa.Column("interview_log", sa.JSON, nullable=True),
        sa.Column("interview_questions", sa.JSON, nullable=True),
        sa.Column("video_file_path", sa.String(512), nullable=True),
        sa.Column("roadmap_json", sa.Text, nullable=True),
        sa.Column("cv_review_json", sa.Text, nullable=True),
        sa.Column("final_eval_timestamp", sa.DateTime, nullable=True),
        sa.Column("evaluation_completed_at", sa.DateTime, nullable=True),
        sa.Column("evaluation_source", sa.String(50), nullable=True),
        sa.Column("source", sa.String(50), nullable=True),
        sa.Column("recruiter_notes", sa.Text, nullable=True),
        sa.Column("rubric_id", sa.Integer, nullable=True),
        sa.Column("analysis_strengths", sa.Text, nullable=True),
        sa.Column("analysis_weaknesses", sa.Text, nullable=True),
        sa.Column("analysis_score_breakdown", sa.Text, nullable=True),
        sa.Column("analysis_score", sa.Float, nullable=True),
        sa.Column("assigned_to", sa.Integer, nullable=True),
        sa.Column("assigned_at", sa.DateTime, nullable=True),
    ]
    
    for col in missing_cols:
        try:
            op.add_column("applications", col)
        except Exception:
            pass

    # The model marks ``source`` and ``analysis_score`` as indexed; the legacy
    # migration 4e4f4b511b0e could not create ix_applications_source (column was
    # added here). Recreate the model index once the column exists.
    inspector = sa.inspect(op.get_bind())
    app_cols = {c["name"] for c in inspector.get_columns("applications")}
    existing_indexes = {i["name"] for i in inspector.get_indexes("applications")}
    if "source" in app_cols and "ix_applications_source" not in existing_indexes:
        try:
            op.create_index("ix_applications_source", "applications", ["source"], unique=False)
        except Exception:
            pass


def downgrade() -> None:
    cols_to_drop = [
        "declared_role", "detected_role", "cv_text_anonymized", "cv_file_path",
        "analysis_json", "cv_embedding", "interview_log", "interview_questions",
        "video_file_path", "roadmap_json", "cv_review_json", "final_eval_timestamp",
        "evaluation_completed_at", "evaluation_source", "source", "recruiter_notes",
        "rubric_id", "analysis_strengths", "analysis_weaknesses", "analysis_score_breakdown",
        "analysis_score", "assigned_to", "assigned_at",
    ]
    for col in cols_to_drop:
        try:
            op.drop_column("applications", col)
        except Exception:
            pass