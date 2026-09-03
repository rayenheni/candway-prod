"""Add expires_at to evaluation_sessions for authoritative interview deadline.

Revision ID: m63
Revises: m62
Create Date: 2026-08-21
"""
from alembic import op
import sqlalchemy as sa

revision = "m63"
down_revision = "m62"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cols = {c["name"] for c in inspector.get_columns("evaluation_sessions")}
    if "expires_at" not in cols:
        op.add_column(
            "evaluation_sessions",
            sa.Column("expires_at", sa.DateTime(), nullable=True, index=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cols = {c["name"] for c in inspector.get_columns("evaluation_sessions")}
    if "expires_at" in cols:
        idxs = {idx["name"] for idx in inspector.get_indexes("evaluation_sessions")}
        if "ix_evaluation_sessions_expires_at" in idxs:
            op.drop_index("ix_evaluation_sessions_expires_at", table_name="evaluation_sessions")
        op.drop_column("evaluation_sessions", "expires_at")
