"""Phase 1 — Entity Ownership: add name/phone/email to profiles

Adds name, phone, email columns to candidate_profiles and
recruiter_profiles, then backfills from the users table.

Migration ID: m13_phase1_entity_ownership
Revises: m12_add_missing_timestamps
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = "m13_phase1_entity_ownership"
down_revision: Union[str, None] = "m12_add_missing_timestamps"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── candidate_profiles ──────────────────────────────────────────
    op.add_column("candidate_profiles", sa.Column("name", sa.String(255), nullable=True))
    op.add_column("candidate_profiles", sa.Column("phone", sa.String(255), nullable=True))
    op.add_column("candidate_profiles", sa.Column("email", sa.String(255), nullable=True))

    # Backfill candidate_profiles from users
    op.execute("""
        UPDATE candidate_profiles cp
        JOIN users u ON cp.user_id = u.id
        SET
            cp.name = u.name,
            cp.phone = u.phone,
            cp.email = u.email
        WHERE cp.name IS NULL
    """)

    # ── recruiter_profiles ──────────────────────────────────────────
    op.add_column("recruiter_profiles", sa.Column("name", sa.String(255), nullable=True))
    op.add_column("recruiter_profiles", sa.Column("phone", sa.String(255), nullable=True))
    op.add_column("recruiter_profiles", sa.Column("email", sa.String(255), nullable=True))

    # Backfill recruiter_profiles from users
    op.execute("""
        UPDATE recruiter_profiles rp
        JOIN users u ON rp.user_id = u.id
        SET
            rp.name = u.name,
            rp.phone = u.phone,
            rp.email = u.email
        WHERE rp.name IS NULL
    """)


def downgrade() -> None:
    op.drop_column("recruiter_profiles", "email")
    op.drop_column("recruiter_profiles", "phone")
    op.drop_column("recruiter_profiles", "name")
    op.drop_column("candidate_profiles", "email")
    op.drop_column("candidate_profiles", "phone")
    op.drop_column("candidate_profiles", "name")
