"""Repair profile company_id schema drift.

m43 made profile company_id nullable, but only modified the column when it
already existed. On databases where the column was absent, candidate_profiles
and admin_profiles remained out of sync with the SQLAlchemy models.

This migration repairs:
- candidate_profiles.company_id: add nullable FK -> companies.id
- admin_profiles.company_id: add nullable FK -> companies.id
- recruiter_profiles.company_id: enforce ON DELETE SET NULL

Revision ID: m66
Revises: m65
Create Date: 2026-08-23
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "m66"
down_revision: Union[str, None] = "m65"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(bind, table: str, column: str) -> bool:
    inspector = sa.inspect(bind)
    if not inspector.has_table(table):
        return False
    return column in {c["name"] for c in inspector.get_columns(table)}


def _has_index(bind, table: str, index_name: str) -> bool:
    inspector = sa.inspect(bind)
    if not inspector.has_table(table):
        return False
    return any(
        idx.get("name") == index_name
        for idx in inspector.get_indexes(table)
    )


def _find_fk(bind, table: str, column: str) -> str | None:
    dialect = bind.dialect.name

    if dialect == "mysql":
        result = bind.execute(
            sa.text(
                """
                SELECT CONSTRAINT_NAME
                FROM information_schema.KEY_COLUMN_USAGE
                WHERE TABLE_SCHEMA = DATABASE()
                  AND TABLE_NAME = :table_name
                  AND COLUMN_NAME = :column_name
                  AND REFERENCED_TABLE_NAME IS NOT NULL
                LIMIT 1
                """
            ),
            {"table_name": table, "column_name": column},
        )
        row = result.fetchone()
        return row[0] if row else None

    if dialect == "postgresql":
        result = bind.execute(
            sa.text(
                """
                SELECT tc.constraint_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                  ON tc.constraint_name = kcu.constraint_name
                 AND tc.table_schema = kcu.table_schema
                WHERE tc.constraint_type = 'FOREIGN KEY'
                  AND tc.table_name = :table_name
                  AND kcu.column_name = :column_name
                  AND tc.table_schema = 'public'
                LIMIT 1
                """
            ),
            {"table_name": table, "column_name": column},
        )
        row = result.fetchone()
        return row[0] if row else None

    return None


def _mysql_fk_delete_rule(bind, table: str, constraint_name: str) -> str | None:
    result = bind.execute(
        sa.text(
            """
            SELECT DELETE_RULE
            FROM information_schema.REFERENTIAL_CONSTRAINTS
            WHERE CONSTRAINT_SCHEMA = DATABASE()
              AND CONSTRAINT_NAME = :constraint_name
              AND TABLE_NAME = :table_name
            LIMIT 1
            """
        ),
        {
            "constraint_name": constraint_name,
            "table_name": table,
        },
    )
    row = result.fetchone()
    return row[0] if row else None


def _add_mysql_company_fk(
    bind,
    table: str,
    constraint_name: str,
) -> None:
    op.execute(
        f"""
        ALTER TABLE {table}
        ADD CONSTRAINT {constraint_name}
        FOREIGN KEY (company_id)
        REFERENCES companies(id)
        ON DELETE SET NULL
        """
    )


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == "mysql":
        # ---------------------------------------------------------------
        # candidate_profiles
        # ---------------------------------------------------------------
        if not _has_column(bind, "candidate_profiles", "company_id"):
            op.execute(
                """
                ALTER TABLE candidate_profiles
                ADD COLUMN company_id INT NULL
                """
            )

        if not _has_index(
            bind,
            "candidate_profiles",
            "idx_candidate_profiles_company_id",
        ):
            op.execute(
                """
                CREATE INDEX idx_candidate_profiles_company_id
                ON candidate_profiles(company_id)
                """
            )

        if _find_fk(bind, "candidate_profiles", "company_id") is None:
            _add_mysql_company_fk(
                bind,
                "candidate_profiles",
                "fk_candidate_profiles_company_id",
            )

        # ---------------------------------------------------------------
        # admin_profiles
        # ---------------------------------------------------------------
        if not _has_column(bind, "admin_profiles", "company_id"):
            op.execute(
                """
                ALTER TABLE admin_profiles
                ADD COLUMN company_id INT NULL
                """
            )

        if not _has_index(
            bind,
            "admin_profiles",
            "idx_admin_profiles_company_id",
        ):
            op.execute(
                """
                CREATE INDEX idx_admin_profiles_company_id
                ON admin_profiles(company_id)
                """
            )

        if _find_fk(bind, "admin_profiles", "company_id") is None:
            _add_mysql_company_fk(
                bind,
                "admin_profiles",
                "fk_admin_profiles_company_id",
            )

        # ---------------------------------------------------------------
        # recruiter_profiles
        # Model says:
        # ForeignKey("companies.id", ondelete="SET NULL")
        # ---------------------------------------------------------------
        existing_fk = _find_fk(
            bind,
            "recruiter_profiles",
            "company_id",
        )

        if existing_fk:
            delete_rule = _mysql_fk_delete_rule(
                bind,
                "recruiter_profiles",
                existing_fk,
            )

            if delete_rule != "SET NULL":
                op.execute(
                    f"""
                    ALTER TABLE recruiter_profiles
                    DROP FOREIGN KEY {existing_fk}
                    """
                )
                _add_mysql_company_fk(
                    bind,
                    "recruiter_profiles",
                    "fk_recruiter_profiles_company_id",
                )

    elif dialect == "postgresql":
        for table in ("candidate_profiles", "admin_profiles"):
            if not _has_column(bind, table, "company_id"):
                op.add_column(
                    table,
                    sa.Column(
                        "company_id",
                        sa.Integer(),
                        nullable=True,
                    ),
                )

            index_name = f"idx_{table}_company_id"
            if not _has_index(bind, table, index_name):
                op.create_index(
                    index_name,
                    table,
                    ["company_id"],
                )

            if _find_fk(bind, table, "company_id") is None:
                op.create_foreign_key(
                    f"fk_{table}_company_id",
                    table,
                    "companies",
                    ["company_id"],
                    ["id"],
                    ondelete="SET NULL",
                )

        existing_fk = _find_fk(
            bind,
            "recruiter_profiles",
            "company_id",
        )

        if existing_fk:
            op.drop_constraint(
                existing_fk,
                "recruiter_profiles",
                type_="foreignkey",
            )

        op.create_foreign_key(
            "fk_recruiter_profiles_company_id",
            "recruiter_profiles",
            "companies",
            ["company_id"],
            ["id"],
            ondelete="SET NULL",
        )

    elif dialect == "sqlite":
        # SQLite migrations cannot safely ALTER existing tables to add/drop
        # foreign-key constraints without table recreation. The test harness
        # does not need this production MySQL repair.
        pass


def downgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == "mysql":
        for table in (
            "candidate_profiles",
            "admin_profiles",
            "recruiter_profiles",
        ):
            fk = _find_fk(bind, table, "company_id")
            if fk:
                op.execute(
                    f"ALTER TABLE {table} DROP FOREIGN KEY {fk}"
                )

        for table, index_name in (
            ("candidate_profiles", "idx_candidate_profiles_company_id"),
            ("admin_profiles", "idx_admin_profiles_company_id"),
        ):
            if _has_index(bind, table, index_name):
                op.execute(
                    f"DROP INDEX {index_name} ON {table}"
                )

        for table in ("candidate_profiles", "admin_profiles"):
            if _has_column(bind, table, "company_id"):
                op.execute(
                    f"""
                    ALTER TABLE {table}
                    DROP COLUMN company_id
                    """
                )

    elif dialect == "postgresql":
        for table in (
            "candidate_profiles",
            "admin_profiles",
            "recruiter_profiles",
        ):
            fk = _find_fk(bind, table, "company_id")
            if fk:
                op.drop_constraint(
                    fk,
                    table,
                    type_="foreignkey",
                )

        for table, index_name in (
            ("candidate_profiles", "idx_candidate_profiles_company_id"),
            ("admin_profiles", "idx_admin_profiles_company_id"),
        ):
            if _has_index(bind, table, index_name):
                op.drop_index(index_name, table_name=table)

        for table in ("candidate_profiles", "admin_profiles"):
            if _has_column(bind, table, "company_id"):
                op.drop_column(table, "company_id")
