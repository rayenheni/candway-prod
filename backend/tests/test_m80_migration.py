"""Tests for alembic revision m80 (ck_eval_session_interview_state).

* Unit tests run everywhere. Data validation runs real SQL on SQLite; the
  MySQL/MariaDB server metadata (VERSION(), information_schema) and DDL go
  through a recording stand-in, so the orchestration (validate before any
  DDL, one atomic ALTER, downgrade refusal) is checked deterministically.
* TestRealServer runs the migration through Alembic against a real MySQL 8 /
  MariaDB server. It is skipped unless CANDWAY_M80_MYSQL_URL points at a
  DISPOSABLE, EMPTY database (it creates and drops ``evaluation_sessions``):

    CANDWAY_M80_MYSQL_URL=mysql+pymysql://root:pw@127.0.0.1:3306/m80_scratch \\
        python -m pytest backend/tests/test_m80_migration.py
"""

import importlib.util
import os
import pathlib
import re
import types

import pytest
import sqlalchemy as sa

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
M80_PATH = (
    REPO_ROOT / "alembic/versions/m80_widen_eval_session_interview_state_check.py"
)
P1PROD_PATH = (
    REPO_ROOT / "alembic/versions/p1prod202606111615_production_integrity_fixes.py"
)


def _load_m80():
    spec = importlib.util.spec_from_file_location("m80_under_test", M80_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


m80 = _load_m80()
ADDED_STATES = ("initializing", "evaluating", "failed", "transcription_failed")


# ---------------------------------------------------------------- helpers


@pytest.fixture
def data_conn():
    """SQLite table with the evaluation_sessions.interview_state column only
    (no CHECK), so arbitrary legacy values can be seeded."""
    engine = sa.create_engine("sqlite://")
    with engine.connect() as conn:
        conn.execute(
            sa.text(
                "CREATE TABLE evaluation_sessions "
                "(id INTEGER PRIMARY KEY, interview_state VARCHAR(20))"
            )
        )
        yield conn
    engine.dispose()


def _seed(conn, *states):
    conn.execute(
        sa.text("INSERT INTO evaluation_sessions (interview_state) VALUES (:s)"),
        [{"s": s} for s in states],
    )


def _states(conn):
    return sorted(
        r[0]
        for r in conn.execute(
            sa.text("SELECT interview_state FROM evaluation_sessions")
        )
        if r[0] is not None
    )


class _Scalar:
    def __init__(self, value):
        self._value = value

    def scalar(self):
        return self._value


class FakeServer:
    """MySQL/MariaDB stand-in. Data queries hit the real SQLite table; server
    metadata is scripted and DDL is recorded (and 'applied' to ``exists``)."""

    def __init__(
        self,
        data_conn,
        version="8.0.42",
        exists=True,
        has_check_catalog=True,
        persists_ddl=True,
    ):
        self.data_conn = data_conn
        self.version = version
        self.exists = exists
        self.has_check_catalog = has_check_catalog
        self.persists_ddl = persists_ddl
        self.ddl = []
        self.detection_sql = []
        self.dialect = types.SimpleNamespace(name="mysql")

    def execute(self, stmt, params=None):
        sql = str(stmt)
        if sql == "SELECT VERSION()":
            return _Scalar(self.version)
        if "TABLE_NAME = 'CHECK_CONSTRAINTS'" in sql:
            return _Scalar(int(self.has_check_catalog))
        if "information_schema" in sql:
            assert params == {"table": m80.TABLE, "name": m80.NAME}
            self.detection_sql.append(sql)
            return _Scalar(int(self.exists))
        if sql.startswith("ALTER TABLE"):
            self.ddl.append(sql)
            if self.persists_ddl:
                self.exists = True
            return None
        return self.data_conn.execute(stmt, params or {})


def _cond(states):
    return (
        "interview_state IS NULL OR interview_state IN ("
        + ", ".join(f"'{s}'" for s in states)
        + ")"
    )


# ------------------------------------------------------------ state lists


def test_old_states_match_the_constraint_p1prod_created():
    text = P1PROD_PATH.read_text(encoding="utf-8")
    match = re.search(
        r"\"ck_eval_session_interview_state\",\s*\"evaluation_sessions\",\s*\"([^\"]+)\"",
        text,
    )
    assert match, "p1prod create_check_constraint for interview_state not found"
    assert match.group(1) == _cond(m80.OLD_STATES)


def test_new_states_are_old_plus_the_live_additions():
    assert m80.NEW_STATES == m80.OLD_STATES + ADDED_STATES
    assert len(set(m80.NEW_STATES)) == len(m80.NEW_STATES)


# ---------------------------------------------------------- pure functions


@pytest.mark.parametrize(
    "version, expected",
    [
        ("8.0.42", ("mysql", (8, 0, 42))),
        ("8.0.36-0ubuntu0.22.04.1", ("mysql", (8, 0, 36))),
        ("8.4.2", ("mysql", (8, 4, 2))),
        ("5.5.5-10.4.32-MariaDB", ("mariadb", (10, 4, 32))),
        ("10.4.32-MariaDB-log", ("mariadb", (10, 4, 32))),
        ("10.11.6-MariaDB-0+deb12u1", ("mariadb", (10, 11, 6))),
    ],
)
def test_parse_server_version(version, expected):
    assert m80.parse_server_version(version) == expected


def test_parse_server_version_rejects_garbage():
    with pytest.raises(m80.M80MigrationError):
        m80.parse_server_version("not-a-version")


def test_mysql_replace_sql_is_one_atomic_statement():
    sql = m80.build_replace_sql(m80.MYSQL, True, m80.NEW_STATES)
    assert sql == (
        "ALTER TABLE evaluation_sessions "
        "DROP CHECK ck_eval_session_interview_state, "
        "ADD CONSTRAINT ck_eval_session_interview_state CHECK ("
        + _cond(m80.NEW_STATES)
        + ")"
    )
    assert ";" not in sql and sql.count("ALTER TABLE") == 1


def test_mariadb_replace_sql_uses_drop_constraint():
    sql = m80.build_replace_sql(m80.MARIADB, True, m80.NEW_STATES)
    assert sql.startswith(
        "ALTER TABLE evaluation_sessions "
        "DROP CONSTRAINT ck_eval_session_interview_state, "
        "ADD CONSTRAINT ck_eval_session_interview_state CHECK ("
    )
    assert "DROP CHECK" not in sql


@pytest.mark.parametrize("flavour", ["mysql", "mariadb"])
def test_replace_sql_without_existing_constraint_only_adds(flavour):
    sql = m80.build_replace_sql(flavour, False, m80.NEW_STATES)
    assert sql == (
        "ALTER TABLE evaluation_sessions ADD CONSTRAINT "
        f"ck_eval_session_interview_state CHECK ({_cond(m80.NEW_STATES)})"
    )


# ------------------------------------------------ invalid-data detection


def test_find_disallowed_states_accepts_every_allowed_state_and_null(data_conn):
    _seed(data_conn, *m80.NEW_STATES, None)
    assert m80.find_disallowed_states(data_conn, m80.NEW_STATES) == {}


def test_find_disallowed_states_reports_values_and_counts(data_conn):
    _seed(data_conn, "completed", "bogus", "bogus", "idle", None)
    assert m80.find_disallowed_states(data_conn, m80.NEW_STATES) == {
        "bogus": 2,
        "idle": 1,
    }


def test_transcription_failed_is_only_invalid_for_the_old_set(data_conn):
    _seed(data_conn, "transcription_failed")
    assert m80.find_disallowed_states(data_conn, m80.NEW_STATES) == {}
    assert m80.find_disallowed_states(data_conn, m80.OLD_STATES) == {
        "transcription_failed": 1
    }


# ------------------------------------------------------- upgrade logic


def test_upgrade_mysql_replaces_constraint_in_one_statement(data_conn):
    _seed(data_conn, *m80.OLD_STATES, "transcription_failed", None)
    server = FakeServer(data_conn, version="8.0.42", exists=True)

    m80.replace_constraint(server, m80.NEW_STATES, "upgrade")

    assert server.ddl == [m80.build_replace_sql(m80.MYSQL, True, m80.NEW_STATES)]
    assert all("TABLE_CONSTRAINTS" in s for s in server.detection_sql)
    assert all("CONSTRAINT_TYPE = 'CHECK'" in s for s in server.detection_sql)


def test_upgrade_mariadb_uses_check_constraints_catalog(data_conn):
    server = FakeServer(data_conn, version="5.5.5-10.4.32-MariaDB", exists=True)

    m80.replace_constraint(server, m80.NEW_STATES, "upgrade")

    assert server.ddl == [m80.build_replace_sql(m80.MARIADB, True, m80.NEW_STATES)]
    assert all(
        "information_schema.CHECK_CONSTRAINTS" in s and "TABLE_NAME = :table" in s
        for s in server.detection_sql
    )


def test_upgrade_adds_constraint_when_absent(data_conn):
    server = FakeServer(data_conn, exists=False)

    m80.replace_constraint(server, m80.NEW_STATES, "upgrade")

    assert server.ddl == [m80.build_replace_sql(m80.MYSQL, False, m80.NEW_STATES)]
    assert "DROP" not in server.ddl[0]


def test_upgrade_with_invalid_existing_data_fails_before_any_ddl(data_conn):
    _seed(data_conn, "completed", "bogus", "archived", "archived")
    server = FakeServer(data_conn, exists=True)

    with pytest.raises(m80.M80MigrationError) as err:
        m80.replace_constraint(server, m80.NEW_STATES, "upgrade")

    message = str(err.value)
    assert "'archived': 2 row(s)" in message and "'bogus': 1 row(s)" in message
    assert "No changes were made" in message
    assert server.ddl == []  # existing constraint never dropped
    assert server.detection_sql == []  # failed during validation
    assert _states(data_conn) == ["archived", "archived", "bogus", "completed"]


@pytest.mark.parametrize(
    "version, has_catalog",
    [
        ("8.0.15", True),  # MySQL before enforced CHECK / DROP CHECK
        ("5.7.44-log", True),
        ("5.5.5-10.1.48-MariaDB", True),
        ("8.0.42", False),  # no information_schema.CHECK_CONSTRAINTS
    ],
)
def test_unsupported_server_is_refused_before_any_ddl(data_conn, version, has_catalog):
    server = FakeServer(data_conn, version=version, has_check_catalog=has_catalog)

    with pytest.raises(m80.M80MigrationError, match="No changes were made"):
        m80.replace_constraint(server, m80.NEW_STATES, "upgrade")

    assert server.ddl == []


def test_upgrade_fails_loudly_if_constraint_missing_afterwards(data_conn):
    server = FakeServer(data_conn, exists=False, persists_ddl=False)

    with pytest.raises(m80.M80MigrationError, match="missing after ALTER TABLE"):
        m80.replace_constraint(server, m80.NEW_STATES, "upgrade")


# ----------------------------------------------------- downgrade logic


@pytest.mark.parametrize("state", ADDED_STATES)
def test_downgrade_refuses_to_destroy_new_states(data_conn, state):
    _seed(data_conn, "completed", state)
    server = FakeServer(data_conn, exists=True)

    with pytest.raises(m80.M80MigrationError) as err:
        m80.replace_constraint(server, m80.OLD_STATES, "downgrade")

    assert f"'{state}': 1 row(s)" in str(err.value)
    assert server.ddl == []
    assert _states(data_conn) == sorted(["completed", state])  # not rewritten


def test_downgrade_restores_old_constraint_when_safe(data_conn):
    _seed(data_conn, *m80.OLD_STATES, None)
    server = FakeServer(data_conn, exists=True)

    m80.replace_constraint(server, m80.OLD_STATES, "downgrade")

    assert server.ddl == [m80.build_replace_sql(m80.MYSQL, True, m80.OLD_STATES)]
    assert "'failed'" not in server.ddl[0]


def test_migration_never_issues_update_statements():
    source = M80_PATH.read_text(encoding="utf-8")
    assert not re.search(r"\bUPDATE\s+\{?TABLE|\bUPDATE\s+evaluation_sessions", source)
    assert "except Exception" not in source


# --------------------------------------------- alembic entry points


class _FakeOp:
    def __init__(self, bind, offline=False):
        self._bind = bind
        self._offline = offline

    def get_context(self):
        return types.SimpleNamespace(as_sql=self._offline)

    def get_bind(self):
        return self._bind


@pytest.mark.parametrize("entry", ["upgrade", "downgrade"])
def test_offline_mode_is_refused(monkeypatch, entry):
    monkeypatch.setattr(m80, "op", _FakeOp(None, offline=True))
    with pytest.raises(m80.M80MigrationError, match="offline"):
        getattr(m80, entry)()


@pytest.mark.parametrize("entry", ["upgrade", "downgrade"])
def test_unsupported_dialect_is_refused(monkeypatch, entry):
    bind = types.SimpleNamespace(dialect=types.SimpleNamespace(name="postgresql"))
    monkeypatch.setattr(m80, "op", _FakeOp(bind))
    with pytest.raises(m80.M80MigrationError, match="postgresql"):
        getattr(m80, entry)()


def test_entry_points_drive_the_mysql_path(monkeypatch, data_conn):
    _seed(data_conn, "evaluating")
    server = FakeServer(data_conn, exists=True)
    monkeypatch.setattr(m80, "op", _FakeOp(server))

    m80.upgrade()
    assert len(server.ddl) == 1 and "'transcription_failed'" in server.ddl[0]

    with pytest.raises(m80.M80MigrationError, match="'evaluating': 1 row"):
        m80.downgrade()
    assert len(server.ddl) == 1


@pytest.mark.parametrize("entry", ["upgrade", "downgrade"])
def test_offline_mode_is_refused_through_real_alembic(entry):
    """``alembic upgrade --sql`` builds an as_sql MigrationContext."""
    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    mod = _load_m80()
    ctx = MigrationContext.configure(dialect_name="mysql", opts={"as_sql": True})
    with Operations.context(ctx):
        with pytest.raises(mod.M80MigrationError, match="offline"):
            getattr(mod, entry)()


@pytest.mark.parametrize("entry", ["upgrade", "downgrade"])
def test_sqlite_is_a_noop_through_real_alembic(entry):
    """Runs the entry point through Alembic's real op proxy on SQLite."""
    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    mod = _load_m80()  # fresh module: real alembic `op` / `context` proxies
    engine = sa.create_engine("sqlite://")
    with engine.connect() as conn:
        conn.execute(sa.text("CREATE TABLE evaluation_sessions (interview_state TEXT)"))
        _seed(conn, "bogus")  # would fail validation if the path ran
        ctx = MigrationContext.configure(conn)
        with Operations.context(ctx):
            getattr(mod, entry)()
        assert _states(conn) == ["bogus"]
    engine.dispose()


# ----------------------------------------------- real MySQL / MariaDB

MYSQL_URL = os.environ.get("CANDWAY_M80_MYSQL_URL")


@pytest.mark.skipif(
    not MYSQL_URL,
    reason="real MySQL 8 / MariaDB migration test: set CANDWAY_M80_MYSQL_URL "
    "to a disposable, empty database",
)
class TestRealServer:
    @pytest.fixture
    def engine(self):
        engine = sa.create_engine(MYSQL_URL)
        tables = set(sa.inspect(engine).get_table_names())
        if tables - {"evaluation_sessions"}:
            pytest.fail(
                "CANDWAY_M80_MYSQL_URL must point at a disposable, empty database; "
                f"found tables {sorted(tables)}"
            )
        yield engine
        with engine.begin() as conn:
            conn.execute(sa.text("DROP TABLE IF EXISTS evaluation_sessions"))
        engine.dispose()

    @staticmethod
    def _create_table(engine, states):
        check = f", CONSTRAINT {m80.NAME} CHECK ({_cond(states)})" if states else ""
        with engine.begin() as conn:
            conn.execute(sa.text("DROP TABLE IF EXISTS evaluation_sessions"))
            conn.execute(
                sa.text(
                    "CREATE TABLE evaluation_sessions ("
                    "id INT AUTO_INCREMENT PRIMARY KEY, "
                    f"interview_state VARCHAR(20) NULL{check})"
                )
            )

    @staticmethod
    def _run(engine, entry):
        from alembic.migration import MigrationContext
        from alembic.operations import Operations

        mod = _load_m80()
        with engine.connect() as conn:
            with Operations.context(MigrationContext.configure(conn)):
                getattr(mod, entry)()
            conn.commit()

    @staticmethod
    def _insert(engine, state):
        with engine.begin() as conn:
            conn.execute(
                sa.text(
                    "INSERT INTO evaluation_sessions (interview_state) VALUES (:s)"
                ),
                {"s": state},
            )

    @staticmethod
    def _show_create(engine):
        with engine.connect() as conn:
            return conn.execute(sa.text("SHOW CREATE TABLE evaluation_sessions")).one()[
                1
            ]

    def test_upgrade_accepts_all_states_and_rejects_unknown(self, engine):
        self._create_table(engine, m80.OLD_STATES)
        with pytest.raises(sa.exc.DBAPIError):
            self._insert(engine, "transcription_failed")

        self._run(engine, "upgrade")

        for state in m80.NEW_STATES:
            self._insert(engine, state)
        with pytest.raises(sa.exc.DBAPIError):
            self._insert(engine, "bogus")
        self._run(engine, "upgrade")  # re-run is safe (constraint replaced again)
        assert "transcription_failed" in self._show_create(engine)

    def test_upgrade_adds_missing_constraint(self, engine):
        self._create_table(engine, None)
        self._run(engine, "upgrade")
        with pytest.raises(sa.exc.DBAPIError):
            self._insert(engine, "bogus")

    def test_invalid_existing_data_fails_without_changing_schema(self, engine):
        self._create_table(engine, None)
        self._insert(engine, "bogus")
        before = self._show_create(engine)

        with pytest.raises(m80.M80MigrationError, match="'bogus': 1 row"):
            self._run(engine, "upgrade")

        assert self._show_create(engine) == before

    def test_downgrade_refuses_then_restores_when_safe(self, engine):
        self._create_table(engine, m80.OLD_STATES)
        self._run(engine, "upgrade")
        self._insert(engine, "failed")

        with pytest.raises(m80.M80MigrationError, match="'failed': 1 row"):
            self._run(engine, "downgrade")
        assert "transcription_failed" in self._show_create(engine)
        with engine.connect() as conn:
            assert (
                conn.execute(
                    sa.text("SELECT interview_state FROM evaluation_sessions")
                ).scalar()
                == "failed"
            )

        with engine.begin() as conn:
            conn.execute(sa.text("DELETE FROM evaluation_sessions"))
        self._run(engine, "downgrade")
        assert "transcription_failed" not in self._show_create(engine)
        with pytest.raises(sa.exc.DBAPIError):
            self._insert(engine, "failed")
