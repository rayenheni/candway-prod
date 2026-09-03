"""P0-05 FIX: Idempotency columns on subscription/payment approvals.

Records who approved a Transaction or Enrollment and when, so the
admin endpoints can detect a double-approval attempt and respond
deterministically instead of silently extending the subscription
window by 2x.

This migration is forward-only safe: existing rows get NULL
``approved_at`` and ``approved_by`` which the application code
treats as "never approved", and the existing status column still
drives the business state.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "5f6a7b8c9d0e"
down_revision: Union[str, Sequence[str], None] = "a5b6c7d8e9f0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "transactions",
        sa.Column("approved_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "transactions",
        sa.Column("approved_by", sa.Integer(), nullable=True),
    )
    op.add_column(
        "transactions",
        sa.Column("rejected_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "transactions",
        sa.Column("rejected_by", sa.Integer(), nullable=True),
    )
    op.add_column(
        "transactions",
        sa.Column("idempotency_key", sa.String(length=128), nullable=True),
    )
    op.create_index(
        "idx_transactions_idempotency",
        "transactions",
        ["idempotency_key"],
        unique=False,
    )

    op.add_column(
        "enrollments",
        sa.Column("approved_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "enrollments",
        sa.Column("approved_by", sa.Integer(), nullable=True),
    )
    op.add_column(
        "enrollments",
        sa.Column("rejected_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "enrollments",
        sa.Column("rejected_by", sa.Integer(), nullable=True),
    )
    op.add_column(
        "enrollments",
        sa.Column("idempotency_key", sa.String(length=128), nullable=True),
    )
    op.create_index(
        "idx_enrollments_idempotency",
        "enrollments",
        ["idempotency_key"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_enrollments_idempotency", table_name="enrollments")
    op.drop_column("enrollments", "idempotency_key")
    op.drop_column("enrollments", "rejected_by")
    op.drop_column("enrollments", "rejected_at")
    op.drop_column("enrollments", "approved_by")
    op.drop_column("enrollments", "approved_at")

    op.drop_index("idx_transactions_idempotency", table_name="transactions")
    op.drop_column("transactions", "idempotency_key")
    op.drop_column("transactions", "rejected_by")
    op.drop_column("transactions", "rejected_at")
    op.drop_column("transactions", "approved_by")
    op.drop_column("transactions", "approved_at")
