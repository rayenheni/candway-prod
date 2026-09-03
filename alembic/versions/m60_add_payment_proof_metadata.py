"""Add payment proof metadata columns to transactions (S10)."""

from alembic import op
import sqlalchemy as sa
from datetime import datetime

# revision identifiers, used by Alembic.
revision = "m60"
down_revision = "m59"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing = {col["name"] for col in inspector.get_columns("transactions")}

    if "proof_status" not in existing:
        op.add_column(
            "transactions",
            sa.Column("proof_status", sa.String(50), nullable=False, server_default="uploaded"),
        )
    if "proof_verified_at" not in existing:
        op.add_column(
            "transactions",
            sa.Column("proof_verified_at", sa.DateTime(), nullable=True),
        )
    if "proof_verified_by" not in existing:
        op.add_column(
            "transactions",
            sa.Column("proof_verified_by", sa.Integer(), nullable=True),
        )
    if "proof_file_size" not in existing:
        op.add_column(
            "transactions",
            sa.Column("proof_file_size", sa.Integer(), nullable=True),
        )
    if "proof_file_type" not in existing:
        op.add_column(
            "transactions",
            sa.Column("proof_file_type", sa.String(100), nullable=True),
        )
    if "proof_review_notes" not in existing:
        op.add_column(
            "transactions",
            sa.Column("proof_review_notes", sa.Text(), nullable=True),
        )

    # Backfill proof_status for existing rows
    conn.execute(
        sa.text(
            "UPDATE transactions SET proof_status = 'uploaded' WHERE proof_status IS NULL"
        )
    )


def downgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing = {col["name"] for col in inspector.get_columns("transactions")}

    for col in [
        "proof_review_notes",
        "proof_file_type",
        "proof_file_size",
        "proof_verified_by",
        "proof_verified_at",
        "proof_status",
    ]:
        if col in existing:
            op.drop_column("transactions", col)
