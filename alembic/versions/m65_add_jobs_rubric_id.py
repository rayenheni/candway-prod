"""m65: Add rubric_id to jobs.

Revision ID: m65
Revises: m64
"""

from alembic import op
import sqlalchemy as sa


revision = "m65"
down_revision = "m64"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "jobs",
        sa.Column("rubric_id", sa.Integer(), nullable=True),
    )

    op.create_index(
        "idx_jobs_rubric",
        "jobs",
        ["rubric_id"],
    )

    op.create_foreign_key(
        "fk_jobs_rubric_id",
        "jobs",
        "rubrics",
        ["rubric_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade():
    op.drop_constraint(
        "fk_jobs_rubric_id",
        "jobs",
        type_="foreignkey",
    )

    op.drop_index(
        "idx_jobs_rubric",
        table_name="jobs",
    )

    op.drop_column("jobs", "rubric_id")
