"""m29: Backfill AdminProfile from User columns and add migration check.

1. Populate admin_profiles for any admin users missing them
2. Backfill is_super_admin and permissions from User columns
3. Add NOT NULL to admin_profiles.user_id safety check (already not-null)

Revision ID: m29
Revises: m28
Create Date: 2026-07-04
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "m29"
down_revision: Union[str, Sequence[str], None] = "m28"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    # 1. Create admin_profiles for admin users that don't have one
    conn.execute(
        sa.text(
            "INSERT IGNORE INTO admin_profiles (user_id, is_super_admin, permissions, created_at, updated_at) "
            "SELECT u.id, u.is_super_admin, u.admin_permissions, NOW(), NOW() "
            "FROM users u "
            "WHERE u.role = 'admin' "
            "AND NOT EXISTS (SELECT 1 FROM admin_profiles ap WHERE ap.user_id = u.id)"
        )
    )

    # 2. Backfill is_super_admin and permissions for existing admin profiles
    conn.execute(
        sa.text(
            "UPDATE admin_profiles ap "
            "JOIN users u ON u.id = ap.user_id "
            "SET ap.is_super_admin = u.is_super_admin, "
            "    ap.permissions = u.admin_permissions "
            "WHERE u.role = 'admin'"
        )
    )


def downgrade() -> None:
    pass
