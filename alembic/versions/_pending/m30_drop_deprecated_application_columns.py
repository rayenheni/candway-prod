"""m30: Drop 8 deprecated Application columns migrated to CvDocument.

These 8 columns (declared_role, detected_role, cv_text_anonymized,
cv_file_path, analysis_json, cv_embedding, roadmap_json, cv_review_json)
were migrated to CvDocument (cv_documents table) in Sprint 2.

Write paths were redirected to sync_cv_document() and read paths now
delegate to CvDocument via @property accessors with _deprecated_* fallback.

Run the backfill script first if needed:
    python -m backend.scripts.backfill_cv_documents

Revision ID: m30
Revises: m29
Create Date: 2026-07-04
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "m30"
down_revision: Union[str, Sequence[str], None] = "m29"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    for col in (
        "declared_role",
        "detected_role",
        "cv_text_anonymized",
        "cv_file_path",
        "analysis_json",
        "cv_embedding",
        "roadmap_json",
        "cv_review_json",
    ):
        try:
            op.drop_column("applications", col)
        except Exception:
            pass


def downgrade() -> None:
    op.add_column("applications", sa.Column("declared_role", sa.String(255), nullable=True))
    op.add_column("applications", sa.Column("detected_role", sa.String(255), nullable=True))
    op.add_column("applications", sa.Column("cv_text_anonymized", sa.Text, nullable=True))
    op.add_column("applications", sa.Column("cv_file_path", sa.String(255), nullable=True))
    op.add_column("applications", sa.Column("analysis_json", sa.Text, nullable=True))
    op.add_column("applications", sa.Column("cv_embedding", sa.Text, nullable=True))
    op.add_column("applications", sa.Column("roadmap_json", sa.Text, nullable=True))
    op.add_column("applications", sa.Column("cv_review_json", sa.Text, nullable=True))
