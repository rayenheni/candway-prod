"""Allow token_blacklist.user_id to be NULL for interview nonce entries.

verify_interview_token (backend/dependencies.py) uses token_blacklist as a
database-backed single-use store for interview HMAC tokens when Redis is
unavailable. It writes a sentinel user_id (-1) because the nonce is NOT a real
user token, but the column was NOT NULL + FK'd to users.id, so the INSERT failed
on the FK and every guest-login 401'd ("Invalid interview link") while Redis was
down. Making the column nullable lets the fallback store NULL instead.

Revision ID: m59
Revises: m58
Create Date: 2026-08-10
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "m59"
down_revision: Union[str, None] = "m58"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    dialect = conn.dialect.name
    if dialect == "mysql":
        # Existing rows created with the -1 sentinel would now violate the FK,
        # so neutralise them first (they are single-use markers only).
        op.execute(
            sa.text("UPDATE token_blacklist SET user_id = NULL WHERE user_id = -1")
        )
        op.execute(sa.text("ALTER TABLE token_blacklist MODIFY user_id INT NULL"))
    else:
        op.alter_column("token_blacklist", "user_id", existing_type=sa.Integer(), nullable=True)


def downgrade() -> None:
    conn = op.get_bind()
    dialect = conn.dialect.name
    if dialect == "mysql":
        op.execute(sa.text("ALTER TABLE token_blacklist MODIFY user_id INT NOT NULL"))
    else:
        op.alter_column("token_blacklist", "user_id", existing_type=sa.Integer(), nullable=False)
