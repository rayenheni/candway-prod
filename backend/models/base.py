"""Database engine, session, base class, and TenantMixin.

Every company-owned resource MUST inherit from TenantMixin to enforce
multi-tenant isolation at the model layer.

Extracted from database.py to reduce monolithic file size.
All model classes remain in database.py with backward-compatible imports.
"""

import os
from datetime import UTC, datetime

from dotenv import load_dotenv as _load_dotenv_early

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
for _env_file in (
    os.path.join(_BASE_DIR, ".env"),
    os.path.join(_BASE_DIR, "backend", ".env"),
):
    if os.path.exists(_env_file):
        _load_dotenv_early(_env_file, override=False)

import threading  # noqa: E402

from sqlalchemy import Column, ForeignKey, Integer, create_engine, event  # noqa: E402
from sqlalchemy.ext.compiler import compiles  # noqa: E402
from sqlalchemy.orm import (  # noqa: E402
    declarative_base,
    declared_attr,
    relationship,
    sessionmaker,
)
from sqlalchemy.sql.functions import Function  # noqa: E402

from backend.logger import logger  # noqa: E402


@compiles(Function, "sqlite")
def _compile_sqlite_function(element, compiler, **kw):
    """Provide a SQLite implementation of MySQL's DATEDIFF().

    Registered globally so ``func.datediff(...)`` (used across
    MetricsRepository / analytics_service) also runs on the SQLite test
    harness without changing any production queries. On MySQL the native
    ``DATEDIFF()`` is used unchanged.
    """
    if element.name.lower() == "datediff":
        a, b = list(element.clauses)
        return "CAST(julianday(%s) - julianday(%s) AS INTEGER)" % (
            compiler.process(a),
            compiler.process(b),
        )
    return compiler.visit_function(element, **kw)


DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    logger.error("DATABASE_URL not found in .env. SQLite fallback is disabled.")
    raise ValueError("DATABASE_URL is not set. Please configure .env for MySQL.")

safe_db_url = DATABASE_URL
if "@" in safe_db_url:
    import re

    safe_db_url = re.sub(r":([^:@]+)@", ":****@", safe_db_url)
logger.info(f"DATABASE_URL loaded: {safe_db_url}")

if "sqlite" in DATABASE_URL:
    # Tests use a shared in-memory SQLite database. StaticPool keeps
    # one connection alive so every thread sees the same database/schema.
    # check_same_thread=False allows FastAPI/TestClient to use it across
    # worker threads. Production MySQL configuration is unchanged.
    from sqlalchemy.pool import StaticPool

    engine_args = {
        "connect_args": {"check_same_thread": False},
        "poolclass": StaticPool,
    }
else:
    pool_size = int(os.getenv("DB_POOL_SIZE", "10"))
    max_overflow = int(os.getenv("DB_MAX_OVERFLOW", "20"))
    pool_timeout = int(os.getenv("DB_POOL_TIMEOUT", "10"))
    pool_recycle = int(os.getenv("DB_POOL_RECYCLE", "1800"))
    mysql_connect_args = {
        "connect_timeout": 10,
        "read_timeout": 30,
        "write_timeout": 30,
    }
    # utf8mb4: full Unicode (4-byte) including emoji + all CJK. Apply at the
    # client layer so every table created by Alembic inherits it, unless the
    # URL already pins a charset (e.g. docker-compose sets ?charset=utf8mb4).
    if "charset" not in DATABASE_URL.lower():
        mysql_connect_args["charset"] = "utf8mb4"
    engine_args = {
        "pool_size": pool_size,
        "max_overflow": max_overflow,
        "pool_recycle": pool_recycle,
        "pool_pre_ping": True,
        "pool_timeout": pool_timeout,
        "connect_args": mysql_connect_args,
    }
    logger.info(
        f"DB Pool configured: size={pool_size}, overflow={max_overflow}, timeout={pool_timeout}s"
    )

engine = create_engine(DATABASE_URL, **engine_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# ---------------------------------------------------------------------------
# Task 1: DB statement timeout — 30s for MySQL, silently ignored on SQLite
# ---------------------------------------------------------------------------
@event.listens_for(engine, "connect")
def set_statement_timeout(dbapi_connection, connection_record):
    try:
        cursor = dbapi_connection.cursor()
        cursor.execute("SET SESSION max_execution_time = 30000")
        cursor.close()
    except Exception:
        pass  # SQLite doesn't support this


# ---------------------------------------------------------------------------
# Task 2: Connection leak detection
# ---------------------------------------------------------------------------
_checked_out = {}
_lock = threading.Lock()


@event.listens_for(engine, "checkout")
def receive_checkout(dbapi_connection, connection_record, connection_proxy):
    with _lock:
        thread_id = threading.get_ident()
        _checked_out[thread_id] = _checked_out.get(thread_id, 0) + 1
        current = _checked_out[thread_id]
        if current > 5:
            logger.warning(
                f"Thread {thread_id} has {current} active connections (potential leak)"
            )


@event.listens_for(engine, "checkin")
def receive_checkin(dbapi_connection, connection_record):
    with _lock:
        thread_id = threading.get_ident()
        _checked_out[thread_id] = max(0, _checked_out.get(thread_id, 0) - 1)


@event.listens_for(engine, "connect")
def receive_connect(dbapi_connection, connection_record):
    logger.debug(f"New DB connection established (pool status: {engine.pool.status()})")


class TenantMixin:
    """Mixin that adds company_id to any SQLAlchemy model.

    All company-owned resources MUST inherit from TenantMixin to enforce
    multi-tenant isolation at the model layer.

    Usage::

        class MyModel(Base, TenantMixin):
            __tablename__ = "my_models"
            ...

    The mixin adds:
    * ``company_id`` — FK to ``companies.id``, NOT NULL, indexed
    * ``company`` — SQLAlchemy relationship back to ``Company``
    """

    company_id = Column(
        Integer,
        ForeignKey("companies.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    @declared_attr
    def company(cls):
        return relationship("Company", foreign_keys=[cls.company_id])


def utcnow():
    return datetime.now(UTC).replace(tzinfo=None)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
