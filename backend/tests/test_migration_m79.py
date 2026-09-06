"""Unit test for m79 schema repair migration.

Validates that m79 idempotently adds company_id (NOT NULL, FK -> companies.id
with ON DELETE RESTRICT) and idx_evaluation_config_snapshots_company_id to
evaluation_config_snapshots, repairing the index independently of the column.

Case A: production drift — no company_id, no company_id index.
Case B: column already exists but the expected index is missing.
"""

import pytest
import sqlalchemy as sa
from sqlalchemy import inspect, create_engine
from sqlalchemy.pool import StaticPool

from alembic.migration import MigrationContext
from alembic.operations import Operations

import importlib.util
import os

_MIGRATION_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "alembic",
    "versions",
    "m79_add_company_id_to_evaluation_config_snapshots.py",
)

spec = importlib.util.spec_from_file_location("m79_migration", _MIGRATION_PATH)
m79_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m79_mod)

m79_upgrade = m79_mod.upgrade
m79_downgrade = m79_mod.downgrade

_TABLE = "evaluation_config_snapshots"
_COLUMN = "company_id"
_INDEX = "idx_evaluation_config_snapshots_company_id"

_TABLE_DDL = """
    CREATE TABLE evaluation_config_snapshots (
        id INTEGER PRIMARY KEY,
        source_type VARCHAR(50) NOT NULL,
        source_id INTEGER,
        hash VARCHAR(64) NOT NULL UNIQUE,
        rubric_id INTEGER,
        rubric_version INTEGER,
        total_questions INTEGER NOT NULL DEFAULT 15,
        time_limit_seconds INTEGER,
        passing_score FLOAT,
        max_score FLOAT NOT NULL DEFAULT 100.0,
        interview_instructions TEXT,
        language VARCHAR(10) NOT NULL DEFAULT 'en',
        question_generation_prompt TEXT,
        evaluation_criteria TEXT,
        scoring_weights TEXT,
        source_metadata TEXT,
        resolved_rubric_json TEXT,
        resolved_skills_json TEXT,
        interview_config_json TEXT,
        scoring_rules_json TEXT,
        config_json TEXT NOT NULL,
        created_at DATETIME NOT NULL
    );
"""


def _run_upgrade(conn):
    ctx = MigrationContext.configure(conn)
    op_impl = Operations(ctx)
    import alembic.op
    alembic.op._proxy = op_impl
    m79_upgrade()


def _run_downgrade(conn):
    ctx = MigrationContext.configure(conn)
    op_impl = Operations(ctx)
    import alembic.op
    alembic.op._proxy = op_impl
    m79_downgrade()


def _columns(conn):
    return {c["name"]: c for c in inspect(conn).get_columns(_TABLE)}


def _indexes(conn):
    return {idx["name"] for idx in inspect(conn).get_indexes(_TABLE)}


def _fks(conn):
    return {fk["name"]: fk for fk in inspect(conn).get_foreign_keys(_TABLE)}


@pytest.fixture
def engine_case_a():
    """Production drift: companies table + drifted snapshots table (no company_id)."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    with engine.begin() as conn:
        conn.execute(sa.text("CREATE TABLE companies (id INTEGER PRIMARY KEY);"))
        conn.execute(sa.text(_TABLE_DDL))
    return engine


@pytest.fixture
def engine_case_b():
    """column exists, index missing."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    with engine.begin() as conn:
        conn.execute(sa.text("CREATE TABLE companies (id INTEGER PRIMARY KEY);"))
        conn.execute(sa.text(_TABLE_DDL))
        conn.execute(
            sa.text(
                f"ALTER TABLE {_TABLE} ADD COLUMN {_COLUMN} INTEGER NOT NULL REFERENCES companies(id) ON DELETE RESTRICT;"
            )
        )
    return engine


def test_case_a_production_drift_repair(engine_case_a):
    """Case A: upgrade adds NOT NULL company_id + FK RESTRICT + index; idempotent; downgrade reverts."""
    with engine_case_a.begin() as conn:
        # 1. Before: column + index absent
        assert _COLUMN not in _columns(conn)
        assert _INDEX not in _indexes(conn)

        # 2. Upgrade
        _run_upgrade(conn)

        # 3. column exists, NOT NULL
        cols = _columns(conn)
        assert _COLUMN in cols
        assert cols[_COLUMN]["nullable"] is False

        # 4. FK -> companies.id with ON DELETE RESTRICT
        fks = _fks(conn)
        assert fks, "expected at least one FK on evaluation_config_snapshots"
        target_fk = None
        for fk in fks.values():
            if _COLUMN in fk.get("constrained_columns", []):
                target_fk = fk
                break
        assert target_fk is not None, "expected FK on company_id"
        assert target_fk["referred_table"] == "companies"
        assert set(target_fk["referred_columns"]) == {"id"}
        on_delete = (target_fk.get("options") or {}).get("ondelete")
        assert on_delete == "RESTRICT"

        # 5. index exists
        assert _INDEX in _indexes(conn)

        # 6. Idempotent: second upgrade is a safe no-op (column + index unchanged)
        _run_upgrade(conn)
        assert _COLUMN in _columns(conn)
        assert _INDEX in _indexes(conn)

        # 7. Downgrade removes index + column
        _run_downgrade(conn)
        assert _INDEX not in _indexes(conn)
        assert _COLUMN not in _columns(conn)


def test_case_b_column_exists_index_missing(engine_case_b):
    """Case B: company_id already present but index missing — upgrade must create the index."""
    with engine_case_b.begin() as conn:
        # 1. Before: column exists, index missing
        assert _COLUMN in _columns(conn)
        assert _INDEX not in _indexes(conn)

        # 2. Upgrade creates the index (column untouched)
        _run_upgrade(conn)
        assert _COLUMN in _columns(conn)
        cols = _columns(conn)
        assert cols[_COLUMN]["nullable"] is False
        assert _INDEX in _indexes(conn)

        # 3. Downgrade removes index + column symmetrically
        _run_downgrade(conn)
        assert _INDEX not in _indexes(conn)
        assert _COLUMN not in _columns(conn)


def test_case_b_idempotent_when_index_present(engine_case_b):
    """Case B: once the index exists, a further upgrade is a no-op."""
    with engine_case_b.begin() as conn:
        _run_upgrade(conn)
        assert _INDEX in _indexes(conn)

        # Second upgrade: column present + index present -> must not error
        _run_upgrade(conn)
        assert _INDEX in _indexes(conn)
        assert _COLUMN in _columns(conn)
