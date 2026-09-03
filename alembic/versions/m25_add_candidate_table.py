"""m25: Create candidates table + add candidate_id to applications

Creates the ``candidates`` table (one row per unique person within a
company) and adds ``candidate_id`` to ``applications``.

This is the foundation for distinguishing "X candidates (unique people)"
from "Y applications (submissions)" throughout the system.

Revision ID: m25
Revises: m24
Create Date: 2026-07-02
"""
from alembic import op
import sqlalchemy as sa


revision = "m25"
down_revision = "m24"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── 1. Create candidates table ─────────────────────────────────
    op.create_table(
        "candidates",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False, index=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=True),
        sa.Column("phone", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(), nullable=True, index=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "email", name="uq_candidates_company_email"),
    )
    op.create_index("idx_candidates_email", "candidates", ["email"])
    op.create_index("idx_candidates_company_email", "candidates", ["company_id", "email"])

    # ── 2. Add candidate_id to applications ─────────────────────────
    op.add_column(
        "applications",
        sa.Column("candidate_id", sa.Integer(), sa.ForeignKey("candidates.id"), nullable=True, index=True),
    )
    op.create_index("idx_applications_candidate_id", "applications", ["candidate_id"])


def downgrade() -> None:
    op.drop_index("idx_applications_candidate_id", table_name="applications")
    try:
        op.drop_column("applications", "candidate_id")
    except Exception:
        pass
    op.drop_index("idx_candidates_company_email", table_name="candidates")
    op.drop_index("idx_candidates_email", table_name="candidates")
    op.drop_constraint("uq_candidates_company_email", "candidates", type_="unique")
    op.drop_table("candidates")
