"""m31: Enrich Candidate model with Sprint 3 profile fields.

Adds headline, bio, skills, location, and internal_mobility columns
to the candidates table, plus a skills index for talent search.

Revision ID: m31
Revises: m30
Create Date: 2026-07-04
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "m31"
down_revision: Union[str, Sequence[str], None] = "m29"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    cols = {c["name"] for c in inspector.get_columns("candidates")}

    if "headline" not in cols:
        op.add_column("candidates", sa.Column("headline", sa.String(255), nullable=True))
    if "bio" not in cols:
        op.add_column("candidates", sa.Column("bio", sa.Text, nullable=True))
    if "skills" not in cols:
        op.add_column("candidates", sa.Column("skills", sa.Text, nullable=True))
    if "location" not in cols:
        op.add_column("candidates", sa.Column("location", sa.String(255), nullable=True))
    if "internal_mobility" not in cols:
        op.add_column("candidates", sa.Column("internal_mobility", sa.Boolean, nullable=False, server_default=sa.text("0")))

    indexes = {idx["name"] for idx in inspector.get_indexes("candidates")}
    if "idx_candidates_skills" not in indexes:
        op.create_index(
            "idx_candidates_skills",
            "candidates",
            ["company_id", "skills"],
            mysql_length={"skills": 255},
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    indexes = {idx["name"] for idx in inspector.get_indexes("candidates")}
    if "idx_candidates_skills" in indexes:
        op.drop_index("idx_candidates_skills", table_name="candidates")

    cols = {c["name"] for c in inspector.get_columns("candidates")}
    for col in ("internal_mobility", "location", "skills", "bio", "headline"):
        if col in cols:
            op.drop_column("candidates", col)
