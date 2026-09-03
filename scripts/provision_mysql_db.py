#!/usr/bin/env python3
"""Provision a fresh MySQL database for Candway.

Usage:
  CANDWAY_DATABASE_URL=mysql+pymysql://user:pass@host/dbname python scripts/provision_mysql_db.py

Creates all tables from the current ORM models (Base.metadata.create_all) and
stamps alembic at head so subsequent incremental migrations work correctly.

This is the recommended approach for fresh MySQL provisioning because the
alembic migration chain (m01–m52) was originally authored assuming a
create_all'd schema exists. Backfill migrations (b2c3d4e5f6a8, etc.) read
columns that only exist on the legacy dev SQLite database, so running
`alembic upgrade head` from an empty DB is not supported.

Design:
  1. Create all tables from ORM models (current final schema).
  2. Stamp alembic at m52 (head) so incremental migrations work.
  3. Optionally run a validation pass (schema + charset + FK checks).
"""

import os
import sys
import argparse
import pymysql
import sqlalchemy as sa
from sqlalchemy import inspect, text

# Ensure the project root is on sys.path
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def get_engine(url: str) -> sa.Engine:
    return sa.create_engine(url)


def ensure_database_exists(db_url: str, db_name: str) -> None:
    """Create the database if it does not already exist."""
    parts = db_url.split("@")[-1].split("/")
    host_port = parts[0]
    c = pymysql.connect(host=host_port.split(":")[0],
                        port=int(host_port.split(":")[1]) if ":" in host_port else 3306,
                        user=db_url.split("://")[1].split(":")[0],
                        password=db_url.split("://")[1].split(":")[1].split("@")[0])
    cur = c.cursor()
    cur.execute(f"CREATE DATABASE IF NOT EXISTS `{db_name}` "
                "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
    c.commit()
    c.close()


def provision(url: str, skip_validation: bool = False) -> bool:
    """Run create_all + stamp head. Returns True on success."""
    engine = get_engine(url)
    from backend.models.base import Base
    import backend.models  # noqa: F401 — ensure all models registered

    print("[1/3] Running Base.metadata.create_all ...")
    Base.metadata.create_all(engine)
    print(f"  Created {len(Base.metadata.tables)} tables.")

    # Stamp alembic at head
    print("[2/3] Stamping alembic at head (m52) ...")
    env = dict(os.environ)
    env["DATABASE_URL"] = url
    from subprocess import run
    r = run([sys.executable, "-m", "alembic", "stamp", "head"],
            env=env, capture_output=True, text=True, cwd=ROOT)
    if r.returncode != 0:
        print(f"  ERROR: alembic stamp failed\n{r.stderr[-1000:]}")
        return False
    print("  Stamped at m52 (head).")

    if skip_validation:
        engine.dispose()
        return True

    print("[3/3] Validating schema ...")
    ins = inspect(engine)
    checks = []
    def chk(cond, msg):
        checks.append((bool(cond), msg))

    def cols(t):
        return {c['name'] for c in ins.get_columns(t)}

    chk('companies' in ins.get_table_names(), "companies table")
    chk('plan_id' in cols('companies'), "companies.plan_id")
    chk('kyb_documents' in cols('companies'), "companies.kyb_documents")
    chk('subscriptions' in ins.get_table_names(), "subscriptions table")
    chk('credit_wallets' in ins.get_table_names(), "credit_wallets table")
    chk('credit_transactions' in ins.get_table_names(), "credit_transactions table")
    chk('usage_events' in ins.get_table_names(), "usage_events table")
    chk('feature_flags' in ins.get_table_names(), "feature_flags table")
    ff = cols('feature_flags')
    for cname in ['visibility', 'audiences', 'maintenance_mode', 'kill_switch',
                  'depends_on', 'plan_restrictions', 'company_override_key']:
        chk(cname in ff, f"feature_flags.{cname}")
    chk('plan_versions' in ins.get_table_names(), "plan_versions table")
    chk('credits_monthly' in cols('subscription_plans'), "subscription_plans.credits_monthly")
    chk('candidate_profiles' in ins.get_table_names(), "candidate_profiles table")
    chk('recruiter_profiles' in ins.get_table_names(), "recruiter_profiles table")
    chk('candidates' in ins.get_table_names(), "candidates table")
    chk('candidate_id' in cols('applications'), "applications.candidate_id")

    with engine.begin() as conn:
        db_cs = conn.execute(text(
            "SELECT DEFAULT_CHARACTER_SET_NAME FROM information_schema.SCHEMATA "
            "WHERE SCHEMA_NAME=:d"
        ), {'d': url.split("/")[-1].split("?")[0]}).scalar()
    chk(db_cs == 'utf8mb4', f"charset utf8mb4 (got {db_cs})")

    passed = sum(1 for c, _ in checks if c)
    failed = [m for c, m in checks if not c]
    print(f"  {passed}/{len(checks)} checks passed")
    if failed:
        for m in failed:
            print(f"  FAIL: {m}")
    engine.dispose()
    return len(failed) == 0


def main():
    parser = argparse.ArgumentParser(description="Provision fresh MySQL database")
    parser.add_argument("--url", default=os.getenv("CANDWAY_DATABASE_URL"),
                        help="MySQL connection URL (or set CANDWAY_DATABASE_URL)")
    parser.add_argument("--skip-validation", action="store_true",
                        help="Skip schema validation checks")
    args = parser.parse_args()

    if not args.url:
        print("ERROR: --url or CANDWAY_DATABASE_URL required")
        sys.exit(1)

    db_name = args.url.split("/")[-1].split("?")[0]
    print(f"Provisioning MySQL database: {db_name}")

    ok = provision(args.url, skip_validation=args.skip_validation)
    print("\nRESULT:", "SUCCESS" if ok else "PARTIAL (schema check failures)")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
