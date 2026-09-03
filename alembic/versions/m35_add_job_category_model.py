"""add job_category model (job_categories table) + job_category_id on jobs

Revision ID: m35
Revises: m34
Create Date: 2026-07-05 14:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "m35"
down_revision: Union[str, Sequence[str], None] = "m34"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── job_categories ────────────────────────────────────────────
    op.create_table(
        "job_categories",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False, index=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "name", name="uq_job_category_company_name"),
    )
    op.create_index("idx_job_categories_company", "job_categories", ["company_id"])

    # ── job_category_id on jobs ───────────────────────────────────
    op.add_column("jobs",
        sa.Column("job_category_id", sa.Integer(), sa.ForeignKey("job_categories.id"), nullable=True)
    )
    op.create_index("idx_jobs_job_category", "jobs", ["job_category_id"])


def downgrade() -> None:
    op.drop_index("idx_jobs_job_category", table_name="jobs")
    try:
        op.drop_column("jobs", "job_category_id")
    except Exception:
        pass
    op.drop_index("idx_job_categories_company", table_name="job_categories")
    op.drop_constraint("uq_job_category_company_name", "job_categories", type_="unique")
    op.drop_table("job_categories")
