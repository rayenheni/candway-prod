"""Add offer_declined (and other enum statuses) to applications.ck_application_status.

Application status is stored as a free string but constrained by a CHECK
constraint. recruiter_offers.py writes ``app.status = "offer_declined"`` when a
candidate declines an offer, but the constraint never listed that value — so on
databases where the constraint is enforced (MySQL/MariaDB 8.0.16+ / 10.2+,
and any fresh schema built from the model) the decline silently failed with a
constraint violation.

This migration rebuilds the constraint to also accept ``offer_declined`` plus
the remaining official ApplicationStatus enum values that were missing
(``withdrawn``, ``imported``, ``reviewed``, ``shortlisted``) so the DB contract
matches backend/enums.py.

Revision ID: m58
Revises: m57
Create Date: 2026-08-09
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision: str = "m58"
down_revision: Union[str, None] = "m57"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_CONSTRAINT = "ck_application_status"
_TABLE = "applications"

_NEW_CHECK = (
    "status IS NULL OR status IN ("
    "'pending', 'screening', 'interviewing', 'offer', 'rejected', "
    "'analyzed', 'failed', 'applied', 'invited', 'active', 'analyzing', "
    "'analysis_failed', 'hired', 'offer_declined', 'withdrawn', 'imported', "
    "'reviewed', 'shortlisted'"
    ")"
)


def _has_check(conn, table: str, name: str) -> bool:
    return any(c.get("name") == name for c in inspect(conn).get_check_constraints(table))


def _drop_check(conn, table: str, name: str) -> None:
    """Drop a named CHECK constraint across MySQL/MariaDB dialects.

    MySQL 8.0.16+ uses ``DROP CHECK``; MariaDB uses ``DROP CONSTRAINT``.
    ``DROP CONSTRAINT`` works on both, but we try the dialect-canonical form
    first and fall back to the generic one. Fails safely if already absent.
    """
    if not _has_check(conn, table, name):
        return
    dialect = conn.dialect.name
    if dialect == "mysql":
        # Try MariaDB-style first (MariaDB reports dialect name "mysql" too).
        try:
            conn.execute(sa.text(f"ALTER TABLE {table} DROP CONSTRAINT {name}"))
            return
        except Exception:
            pass
        conn.execute(sa.text(f"ALTER TABLE {table} DROP CHECK {name}"))
        return
    conn.execute(sa.text(f"ALTER TABLE {table} DROP CHECK {name}"))


def upgrade() -> None:
    conn = op.get_bind()
    _drop_check(conn, _TABLE, _CONSTRAINT)
    op.create_check_constraint(_CONSTRAINT, _TABLE, _NEW_CHECK)


def downgrade() -> None:
    conn = op.get_bind()
    _drop_check(conn, _TABLE, _CONSTRAINT)
    # Restore the original pre-m58 value set (missing offer_declined etc.).
    op.create_check_constraint(
        _CONSTRAINT,
        _TABLE,
        "status IS NULL OR status IN ('pending', 'screening', 'interviewing', "
        "'offer', 'rejected', 'analyzed', 'failed', 'applied', 'invited', "
        "'active', 'analyzing', 'analysis_failed', 'hired')",
    )
