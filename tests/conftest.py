"""
Root-level conftest for tests/ directory.
Sets up the test environment before any backend imports.

By default the suite uses an in-memory SQLite database so it
runs anywhere with no MySQL dependency. To exercise the real
MySQL schema, set ``CANDWAY_TEST_DATABASE_URL`` to a MySQL
``DATABASE_URL`` (must be a disposable test DB — the suite
will ``DROP``/``CREATE`` tables). Example:

    CANDWAY_TEST_DATABASE_URL=mysql+pymysql://root:@localhost/candway_test \\
        python -m pytest tests/

The production code path (``database.py``) is MySQL-first; the
SQLite default is purely a test convenience.
"""
import os
import sys
from pathlib import Path

# Ensure the repository root is importable when pytest loads this
# conftest from the tests/ directory.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from cryptography.fernet import Fernet

# Set TESTING=true before any backend imports to disable rate limiting
os.environ["TESTING"] = "true"
# Honour an explicit override (e.g. CI runs against MySQL); fall
# back to a shared in-memory SQLite so every connection in the
# pool sees the same tables. ``sqlite:///:memory:`` would create
# a fresh DB per connection and break the admin API tests.
os.environ.setdefault(
    "DATABASE_URL",
    "sqlite:///file:test_db?mode=memory&cache=shared&uri=true",
)
os.environ.setdefault("SECRET_KEY", "test_secret_key_for_jwt_encoding_12345")
os.environ.setdefault("ALGORITHM", "HS256")
os.environ.setdefault("ACCESS_TOKEN_EXPIRE_MINUTES", "30")
os.environ.setdefault("DEBUG", "false")
os.environ.setdefault("ENVIRONMENT", "test")
# P0-02 FIX: encryption key is mandatory in production. Tests get a
# freshly-generated Fernet key per pytest run so a leaked test key
# cannot decrypt real data.
os.environ.setdefault(
    "CANDWAY_FIELD_ENCRYPTION_KEY", Fernet.generate_key().decode("ascii")
)


import pytest


@pytest.fixture(scope="session", autouse=True)
def _create_test_schema():
    """Create the SQLAlchemy schema on the test database exactly
    once per pytest run. Without this, every test that hits an
    admin route gets ``no such table: users`` because the test
    DB was never populated.

    This fixture also seeds a single super-admin user so the
    admin-route surface tests have a stable target to query
    against. The seed is intentionally minimal — these tests
    are RBAC / route-surface checks, not end-to-end flows.
    """
    from backend.database import Base, engine, User

    # SQLite shared in-memory DB: force schema creation on the exact
    # engine/connection used by the test suite and keep it alive for
    # the entire pytest session.
    connection = engine.connect()
    Base.metadata.create_all(bind=connection)

    from sqlalchemy.orm import Session

    with Session(bind=connection) as s:
        if not s.query(User).filter(User.email == "admin@test.local").first():
            s.add(
                User(
                    email="admin@test.local",
                    name="Test Admin",
                    role="admin",
                    is_super_admin=True,
                )
            )
            s.commit()
    yield

    connection.close()


@pytest.fixture(autouse=True)
def _silence_scheduler_lifecycle(monkeypatch):
    """Suppress the ``Failed to start scheduler: Event loop is
    closed`` warning that fires when the test process tears down
    the FastAPI app before the background scheduler can stop.

    The scheduler is started on the ``startup`` event and
    stopped on ``shutdown``. TestClient tears down between
    tests, but the scheduler's event loop is the process-level
    one — the loop is already closed by the time the next test
    starts, so the start call fails harmlessly. We short-circuit
    the scheduler lifecycle to a no-op in tests.
    """
    import backend.scheduler as scheduler_module

    monkeypatch.setattr(
        scheduler_module, "start_scheduler", lambda: None, raising=False
    )
    monkeypatch.setattr(
        scheduler_module, "stop_scheduler", lambda: None, raising=False
    )
    yield

