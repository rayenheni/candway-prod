"""Add draft fields (status, name, user_id, base_version, updated_at) to job_rubrics.

Phase C1 of the unified rubric model migration.  job_rubrics becomes the single
source of truth for both published rubrics and recruiter drafts.

Revision ID: f0b1c2d3e4f5
Revises: e6f7a8b9c0d1
Create Date: 2026-06-10 14:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f0b1c2d3e4f5"
down_revision: Union[str, Sequence[str], None] = "e6f7a8b9c0d1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    # Existing published rows get status='published' automatically
    op.add_column(
        "job_rubrics",
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default=sa.text("'published'"),
        ),
    )
    op.add_column(
        "job_rubrics",
        sa.Column("name", sa.String(255), nullable=True),
    )
    op.add_column(
        "job_rubrics",
        sa.Column("user_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "job_rubrics",
        sa.Column("base_version", sa.Integer(), nullable=True),
    )
    op.add_column(
        "job_rubrics",
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    # Index for recruiter draft queries
    op.create_index(
        "idx_job_rubrics_user_status",
        "job_rubrics",
        ["user_id", "status"],
    )
    # FK on user_id (optional — drafts owned by a recruiter)
    op.create_foreign_key(
        "fk_job_rubrics_user_id",
        "job_rubrics",
        "users",
        ["user_id"],
        ["id"],
    )


def downgrade():
    op.drop_constraint("fk_job_rubrics_user_id", "job_rubrics", type_="foreignkey")
    op.drop_index("idx_job_rubrics_user_status", table_name="job_rubrics")
    op.drop_column("job_rubrics", "updated_at")
    op.drop_column("job_rubrics", "base_version")
    op.drop_column("job_rubrics", "user_id")
    op.drop_column("job_rubrics", "name")
    op.drop_column("job_rubrics", "status")
