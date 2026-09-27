"""m80: Widen ck_eval_session_interview_state to every state production writes

p1prod202606111615 created ck_eval_session_interview_state allowing only
('not_started', 'in_progress', 'completed', 'expired', 'flagged', 'paused').
Production code also persists these values to
evaluation_sessions.interview_state (directly, via
entity_writer.sync_ai_interview_session, or via the Application.interview_state
setter, which forwards to the latest EvaluationSession):

  * evaluating           routers/ai_interview/session.py (explicit interview
                         end) and routers/ai_interview/chat.py (engine
                         transition when the last question is answered)
  * transcription_failed routers/ai_interview/media.py (video transcription
                         background task)
  * failed, initializing canonical InterviewState targets of the engine's
                         state machine (ai/engine.py transition_to() persists
                         to_state.value; force_fail() targets FAILED)

On servers that enforce CHECK constraints those writes raise IntegrityError.
States that are *not* persisted and therefore deliberately excluded:
'idle' (read-only legacy alias, normalised on read) and the display-only
'pending' / 'in-progress' locals in routers/recruiter_candidates/scoring.py.

Supported databases
-------------------
* MySQL >= 8.0.16 (production target; first release that enforces CHECK and
  supports ``DROP CHECK``).
* MariaDB >= 10.2 with information_schema.CHECK_CONSTRAINTS (the documented
  live database is MariaDB 10.4).
* SQLite: no-op. SQLite cannot alter CHECK constraints and this repository's
  SQLite test databases are built from the models (Base.metadata.create_all),
  whose CheckConstraint carries the same state list.
* Anything else, or offline (``--sql``) mode: the migration refuses to run,
  because it must inspect live data before changing the constraint.

Upgrade procedure
-----------------
1. Detect the server flavour and version and refuse unsupported servers.
2. Validate existing data: count interview_state values outside the target
   set. If any exist, raise M80MigrationError *before any DDL*, so the
   existing constraint is left untouched. Nothing is rewritten automatically.
3. Detect the existing constraint explicitly through information_schema.
4. Replace it in ONE statement, so it is dropped and recreated atomically.
   If the statement fails, the table keeps its previous constraint:
     MySQL:   ALTER TABLE evaluation_sessions
                DROP CHECK ck_..., ADD CONSTRAINT ck_... CHECK (...)
     MariaDB: ALTER TABLE evaluation_sessions
                DROP CONSTRAINT ck_..., ADD CONSTRAINT ck_... CHECK (...)
   (If the constraint is absent, e.g. a database where p1prod's constraint
   never landed, only the ADD clause is issued.)
5. Re-read information_schema and fail loudly if the constraint is missing.

Adding a CHECK constraint makes the server validate every existing row, which
can rebuild evaluation_sessions. Run it during low traffic on large tables.

Downgrade behaviour
-------------------
The downgrade restores the original six-state constraint using the same
validate-then-single-ALTER procedure. It NEVER rewrites interview_state:
mapping e.g. 'failed' to 'completed' would silently corrupt interview
history. If any row holds 'initializing', 'evaluating', 'failed' or
'transcription_failed', the downgrade raises M80MigrationError listing the
offending values and counts, and changes nothing. An operator must decide
what those rows should become, update them explicitly, then re-run the
downgrade.

Revision ID: m80
Revises: m79
Create Date: 2026-09-26
"""

import re
from typing import Dict, Iterable, Sequence, Tuple, Union

import sqlalchemy as sa

from alembic import op

revision: str = "m80"
down_revision: Union[str, None] = "m79"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE = "evaluation_sessions"
COLUMN = "interview_state"
NAME = "ck_eval_session_interview_state"

OLD_STATES: Tuple[str, ...] = (
    "not_started",
    "in_progress",
    "completed",
    "expired",
    "flagged",
    "paused",
)
NEW_STATES: Tuple[str, ...] = OLD_STATES + (
    "initializing",
    "evaluating",
    "failed",
    "transcription_failed",
)

MYSQL = "mysql"
MARIADB = "mariadb"
MIN_MYSQL_VERSION = (8, 0, 16)
MIN_MARIADB_VERSION = (10, 2, 0)


class M80MigrationError(RuntimeError):
    """Raised when m80 cannot run safely. No schema change has been made."""


def check_condition(states: Iterable[str]) -> str:
    values = ", ".join(f"'{s}'" for s in states)
    return f"{COLUMN} IS NULL OR {COLUMN} IN ({values})"


def parse_server_version(version: str) -> Tuple[str, Tuple[int, ...]]:
    """Parse ``SELECT VERSION()`` into (flavour, (major, minor, patch)).

    MariaDB may report a ``5.5.5-`` replication-compatibility prefix, e.g.
    ``5.5.5-10.4.32-MariaDB``.
    """
    flavour = MARIADB if "mariadb" in version.lower() else MYSQL
    text = re.sub(r"^5\.5\.5-", "", version.strip()) if flavour == MARIADB else version
    match = re.match(r"\s*(\d+)\.(\d+)\.(\d+)", text)
    if not match:
        raise M80MigrationError(f"m80: cannot parse server version {version!r}")
    return flavour, tuple(int(part) for part in match.groups())


def server_flavour(conn) -> str:
    """Return MYSQL or MARIADB, refusing servers that cannot enforce the CHECK."""
    version = str(conn.execute(sa.text("SELECT VERSION()")).scalar())
    flavour, numbers = parse_server_version(version)
    minimum = MIN_MARIADB_VERSION if flavour == MARIADB else MIN_MYSQL_VERSION
    if numbers < minimum:
        raise M80MigrationError(
            f"m80: {flavour} {version} cannot enforce named CHECK constraints; "
            f"{'.'.join(map(str, minimum))}+ is required. No changes were made."
        )
    has_check_catalog = conn.execute(
        sa.text(
            "SELECT COUNT(*) FROM information_schema.TABLES "
            "WHERE TABLE_SCHEMA = 'information_schema' "
            "AND TABLE_NAME = 'CHECK_CONSTRAINTS'"
        )
    ).scalar()
    if not has_check_catalog:
        raise M80MigrationError(
            f"m80: {flavour} {version} has no information_schema.CHECK_CONSTRAINTS, "
            "so the existing constraint cannot be detected safely. "
            "No changes were made."
        )
    return flavour


def constraint_exists(conn, flavour: str) -> bool:
    """Detect ck_eval_session_interview_state on evaluation_sessions."""
    if flavour == MARIADB:
        # MariaDB 10.2/10.3 do not list CHECK constraints in TABLE_CONSTRAINTS;
        # CHECK_CONSTRAINTS carries TABLE_NAME on every supported version.
        sql = (
            "SELECT COUNT(*) FROM information_schema.CHECK_CONSTRAINTS "
            "WHERE CONSTRAINT_SCHEMA = DATABASE() "
            "AND TABLE_NAME = :table AND CONSTRAINT_NAME = :name"
        )
    else:
        # MySQL's CHECK_CONSTRAINTS has no TABLE_NAME; TABLE_CONSTRAINTS lists
        # CHECK constraints (with their table) from 8.0.16.
        sql = (
            "SELECT COUNT(*) FROM information_schema.TABLE_CONSTRAINTS "
            "WHERE CONSTRAINT_SCHEMA = DATABASE() "
            "AND TABLE_NAME = :table AND CONSTRAINT_NAME = :name "
            "AND CONSTRAINT_TYPE = 'CHECK'"
        )
    count = conn.execute(sa.text(sql), {"table": TABLE, "name": NAME}).scalar()
    return bool(count)


def find_disallowed_states(conn, allowed: Iterable[str]) -> Dict[str, int]:
    """Return {value: row_count} for interview_state values outside ``allowed``.

    The comparison runs in the database, so it uses the column collation:
    exactly what the server applies when it validates the new CHECK.
    """
    stmt = sa.text(
        f"SELECT {COLUMN}, COUNT(*) FROM {TABLE} "
        f"WHERE {COLUMN} IS NOT NULL AND {COLUMN} NOT IN :allowed "
        f"GROUP BY {COLUMN} ORDER BY {COLUMN}"
    ).bindparams(sa.bindparam("allowed", expanding=True))
    rows = conn.execute(stmt, {"allowed": list(allowed)})
    return {str(value): int(count) for value, count in rows}


def build_replace_sql(flavour: str, exists: bool, states: Iterable[str]) -> str:
    """One ALTER TABLE that (drops and) adds the constraint atomically."""
    add = f"ADD CONSTRAINT {NAME} CHECK ({check_condition(states)})"
    if not exists:
        return f"ALTER TABLE {TABLE} {add}"
    drop = f"DROP CONSTRAINT {NAME}" if flavour == MARIADB else f"DROP CHECK {NAME}"
    return f"ALTER TABLE {TABLE} {drop}, {add}"


def replace_constraint(conn, states: Sequence[str], action: str) -> None:
    flavour = server_flavour(conn)

    disallowed = find_disallowed_states(conn, states)
    if disallowed:
        found = ", ".join(f"{v!r}: {n} row(s)" for v, n in disallowed.items())
        raise M80MigrationError(
            f"m80 {action}: {TABLE}.{COLUMN} contains values outside the target "
            f"state set ({found}). No changes were made; the existing constraint "
            "is untouched. m80 never rewrites interview_state automatically: "
            "decide what these rows should become, update them explicitly, "
            "then re-run the migration."
        )

    exists = constraint_exists(conn, flavour)
    conn.execute(sa.text(build_replace_sql(flavour, exists, states)))

    if not constraint_exists(conn, flavour):
        raise M80MigrationError(
            f"m80 {action}: {NAME} is missing after ALTER TABLE; "
            "the server did not persist the CHECK constraint."
        )


def _online_bind():
    # MigrationContext.as_sql is True in offline (--sql) mode.
    if op.get_context().as_sql:
        raise M80MigrationError(
            "m80 cannot run in offline (--sql) mode: it must validate existing "
            f"{TABLE}.{COLUMN} data before changing the constraint."
        )
    conn = op.get_bind()
    dialect = conn.dialect.name
    if dialect == "sqlite":
        return None
    if dialect != "mysql":
        raise M80MigrationError(
            f"m80 supports MySQL/MariaDB (and SQLite as a no-op), not {dialect!r}."
        )
    return conn


def upgrade() -> None:
    conn = _online_bind()
    if conn is None:
        # SQLite: CHECK constraints cannot be altered; test DBs come from models.
        return
    replace_constraint(conn, NEW_STATES, "upgrade")


def downgrade() -> None:
    conn = _online_bind()
    if conn is None:
        return
    # Refuses (without changing anything) while any row uses a state that the
    # old constraint cannot represent. See "Downgrade behaviour" above.
    replace_constraint(conn, OLD_STATES, "downgrade")
