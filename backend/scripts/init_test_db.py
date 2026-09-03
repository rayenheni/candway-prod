"""Recreate the MySQL test database (candway_test) with the current metadata.

Usage:
    python backend/scripts/init_test_db.py [database_url]

Without an argument the script uses CANDWAY_TEST_DATABASE_URL or defaults to
    mysql+pymysql://root:@127.0.0.1:3306/candway_test
"""

import os
import sys

from sqlalchemy import create_engine, text

sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from backend.database import Base  # noqa: E402

_DEFAULT = "mysql+pymysql://root:@127.0.0.1:3306/candway_test"


def main() -> None:
    url = os.environ.get("CANDWAY_TEST_DATABASE_URL") or (
        sys.argv[1] if len(sys.argv) > 1 else _DEFAULT
    )
    if not url.startswith("mysql"):
        raise SystemExit(f"Expected a MySQL URL, got: {url!r}")
    engine = create_engine(url, pool_pre_ping=True)
    with engine.begin() as conn:
        conn.execute(text("SET FOREIGN_KEY_CHECKS=0"))
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(text(f"DROP TABLE IF EXISTS {table.name}"))
        conn.execute(text("SET FOREIGN_KEY_CHECKS=1"))
    Base.metadata.create_all(bind=engine)
    print(f"Recreated schema on {url}")


if __name__ == "__main__":
    main()
