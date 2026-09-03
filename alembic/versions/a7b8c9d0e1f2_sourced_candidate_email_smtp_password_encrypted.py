"""add email to sourced_candidates; encrypt smtp_password

Revision ID: a7b8c9d0e1f2
Revises: f5e4d3c2b1a0
Create Date: 2026-06-06

Changes
-------
1. sourced_candidates.email  — new nullable VARCHAR(255) so invite
   emails have a destination (B1 fix).
2. users.smtp_password       — widen from VARCHAR(255) to VARCHAR(2040)
   so the Fernet ciphertext fits.  The column already stores plain
   passwords; existing rows remain readable (decrypt_text passes
   plaintext through untouched) while new writes are encrypted.
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "a7b8c9d0e1f2"
down_revision = "f5e4d3c2b1a0"
branch_labels = None
depends_on = None


def _table_exists(table: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return table in inspector.get_table_names()


def upgrade() -> None:
    # 1. Add email column to sourced_candidates.
    #    The table only exists on legacy deployments; the SourcedCandidate model
    #    is dead code and no migration creates it, so a fresh DB must skip this.
    if _table_exists("sourced_candidates"):
        with op.batch_alter_table("sourced_candidates", schema=None) as batch_op:
            batch_op.add_column(
                sa.Column("email", sa.String(255), nullable=True)
            )
            batch_op.create_index("idx_sc_email", ["email"])

    # 2. Widen smtp_password to hold Fernet ciphertext
    #    Fernet adds ~100 bytes of overhead; 512 chars is safe.
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.alter_column(
            "smtp_password",
            existing_type=sa.String(255),
            type_=sa.String(2040),   # EncryptedText(512) → 512*4 = 2048 max
            existing_nullable=True,
        )


def downgrade() -> None:
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.alter_column(
            "smtp_password",
            existing_type=sa.String(2040),
            type_=sa.String(255),
            existing_nullable=True,
        )

    if _table_exists("sourced_candidates"):
        with op.batch_alter_table("sourced_candidates", schema=None) as batch_op:
            batch_op.drop_index("idx_sc_email")
            batch_op.drop_column("email")
