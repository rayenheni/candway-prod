"""Add qualifications table.

Replaces the previous ``analysis_json["qualifications"]`` JSON bag
on ``Application`` (Bug B-30 in the Candidate Experience Audit).
The bag was a 20-purpose dictionary that made Application rows
balloon to > 100 KB after a dozen uploads, slowed every read, and
offered no way to query, index, or cascade-delete.

The new table is the source of truth going forward; existing
in-bag entries are backfilled by ``backend/migrations/
qualifications_backfill.py``.

Revision ID: d2e3f4a5b6c7
Revises: c1d2e3f4a5b6
Create Date: 2026-06-02 16:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d2e3f4a5b6c7"
down_revision: Union[str, Sequence[str], None] = "c1d2e3f4a5b6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the qualifications table."""
    op.create_table(
        "qualifications",
        sa.Column("id", sa.String(length=16), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column(
            "application_id",
            sa.Integer(),
            sa.ForeignKey("applications.id"),
            nullable=True,
        ),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("file_url", sa.String(length=500), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "mime_type",
            sa.String(length=64),
            nullable=False,
            server_default="application/octet-stream",
        ),
        sa.Column("verified", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("uploaded_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("user_id", "title", "category", name="uq_qual_user_title_cat"),
    )
    op.create_index("idx_qualifications_user", "qualifications", ["user_id"])
    op.create_index("idx_qualifications_app", "qualifications", ["application_id"])


def downgrade() -> None:
    """Drop the qualifications table."""
    op.drop_index("idx_qualifications_app", table_name="qualifications")
    op.drop_index("idx_qualifications_user", table_name="qualifications")
    op.drop_table("qualifications")
