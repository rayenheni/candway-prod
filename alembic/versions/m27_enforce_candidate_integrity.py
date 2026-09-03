"""m27: Enforce candidate integrity at the database level.

1. Convert empty phone strings to NULL on candidates (prevents
   UNIQUE constraint collisions)
2. Add UNIQUE(company_id, phone) on candidates
3. Backfill remaining NULL candidate_id on applications
4. Make candidate_id NOT NULL on applications  
5. Explicit ON DELETE RESTRICT on candidate_id FK

Revision ID: m27
Revises: m26
Create Date: 2026-07-02
"""
from alembic import op
import sqlalchemy as sa


revision = "m27"
down_revision = "m26"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()

    # 1. Normalize empty phone strings to NULL
    conn.execute(
        sa.text("UPDATE candidates SET phone = NULL WHERE phone = ''")
    )

    # 2. Add UNIQUE(company_id, phone) — MySQL allows multiple NULLs
    op.create_unique_constraint(
        "uq_candidates_company_phone",
        "candidates",
        ["company_id", "phone"],
    )

    # 3. Backfill any remaining NULL candidate_id on applications
    conn.execute(
        sa.text(
            "UPDATE applications a "
            "SET a.candidate_id = ("
            "  SELECT c.id FROM candidates c "
            "  WHERE c.company_id = a.company_id AND c.email = a.email "
            "  AND c.deleted_at IS NULL"
            ") "
            "WHERE a.candidate_id IS NULL "
            "AND a.email IS NOT NULL AND a.email != ''"
        )
    )

    # 4. Make candidate_id NOT NULL
    op.alter_column(
        "applications",
        "candidate_id",
        existing_type=sa.Integer(),
        nullable=False,
        existing_server_default=None,
    )

    # 5. Drop old FK and re-create with explicit ON DELETE RESTRICT
    op.drop_constraint(
        "applications_ibfk_1", "applications", type_="foreignkey"
    )
    op.create_foreign_key(
        "fk_applications_candidate_id",
        "applications",
        "candidates",
        ["candidate_id"],
        ["id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_applications_candidate_id", "applications", type_="foreignkey"
    )
    op.create_foreign_key(
        "applications_ibfk_1", "applications", "candidates",
        ["candidate_id"], ["id"],
    )
    op.alter_column(
        "applications",
        "candidate_id",
        existing_type=sa.Integer(),
        nullable=True,
    )
    op.drop_constraint(
        "uq_candidates_company_phone", "candidates", type_="unique"
    )
