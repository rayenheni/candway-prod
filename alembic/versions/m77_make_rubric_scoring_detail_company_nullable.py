"""Allow standalone rubric scoring details without company context.

Revision ID: m77
Revises: a443829e5d63
"""

from alembic import op
import sqlalchemy as sa


revision = "m77"
down_revision = "a443829e5d63"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column(
        "rubric_scoring_details",
        "company_id",
        existing_type=sa.Integer(),
        nullable=True,
    )


def downgrade():
    # Only safe if no NULL company_id rows exist.
    conn = op.get_bind()
    null_count = conn.execute(
        sa.text(
            "SELECT COUNT(*) FROM rubric_scoring_details "
            "WHERE company_id IS NULL"
        )
    ).scalar()

    if null_count:
        raise RuntimeError(
            f"Cannot downgrade: {null_count} rubric_scoring_details "
            "rows have NULL company_id"
        )

    op.alter_column(
        "rubric_scoring_details",
        "company_id",
        existing_type=sa.Integer(),
        nullable=False,
    )
