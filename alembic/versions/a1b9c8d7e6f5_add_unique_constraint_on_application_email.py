"""Add unique constraint on Application.email

Revision ID: a1b9c8d7e6f5
Revises: f09a7b3c4d5e
Create Date: 2026-06-08 14:00:00.000000

Changes:
- Adds unique constraint on applications.email
- Deduplicates existing duplicate emails (keeps the most recent application)
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "a1b9c8d7e6f5"
down_revision: Union[str, Sequence[str], None] = "f09a7b3c4d5e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _deduplicate_emails():
    """Remove duplicate applications by email, keeping only the most recent."""
    conn = op.get_bind()
    duplicates = conn.execute(
        sa.text(
            """
            SELECT email FROM applications
            WHERE email IS NOT NULL AND email != ''
            GROUP BY email HAVING COUNT(*) > 1
            """
        )
    ).fetchall()
    for row in duplicates:
        email = row[0]
        ids_to_keep = conn.execute(
            sa.text(
                """
                SELECT id FROM applications
                WHERE email = :email
                ORDER BY created_at DESC
                LIMIT 1
                """,
            ),
            {"email": email},
        ).scalar()
        if ids_to_keep:
            conn.execute(
                sa.text(
                    "DELETE FROM applications WHERE email = :email AND id != :keep_id",
                ),
                {"email": email, "keep_id": ids_to_keep},
            )


def upgrade():
    _deduplicate_emails()
    op.create_unique_constraint("uq_applications_email", "applications", ["email"])


def downgrade():
    op.drop_constraint("uq_applications_email", "applications", type_="unique")
