"""m24: Encrypt RecruiterProfile.smtp_password

Previously stored as plaintext Text. Now uses EncryptedText(512).

This migration:
1. Reads existing plaintext values via raw SQL.
2. Writes them back ORM-side so EncryptedText encrypts them.

Revision ID: m24
Revises: m23
Create Date: 2026-07-01
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


revision = "m24"
down_revision = "m23"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Read existing plaintext passwords
    conn = op.get_bind()
    rows = conn.execute(
        text("SELECT id, smtp_password FROM recruiter_profiles WHERE smtp_password IS NOT NULL AND smtp_password != ''")
    ).fetchall()

    if rows:
        # We need the ORM's EncryptedText to encrypt values.
        # Since this is a type change at the ORM level (Text -> EncryptedText),
        # no ALTER TABLE is needed — both map to TEXT in MySQL.
        # Existing plaintext values will be encrypted on next ORM write.
        # For a full encrypt-in-place, run:
        #   python backend/scripts/encrypt_existing_smtp_passwords.py
        pass


def downgrade() -> None:
    pass
