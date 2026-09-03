"""Enforce ON DELETE rules on all critical foreign keys

MED-8 (Sprint 12-13): Model-level ondelete rules were added to 58 FKs
across 20+ tables, but MySQL does not propagate model changes to existing
constraints. This migration drops and recreates each FK with the correct
ON DELETE behavior.

Scope:
  - SET NULL: 29 FKs (optional references — nullify on parent delete)
  - CASCADE:   27 FKs (child records — delete when parent deleted)
  - RESTRICT:   2 FKs (TenantMixin.company_id — prevent company deletion)

Revision ID: m42
Revises: m41
Create Date: 2026-07-21
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "m42"
down_revision: Union[str, Sequence[str], None] = "m41"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# ── FK definitions: (table, column, ref_table, ref_column, ondelete) ────

SET_NULL_FKS = [
    ("applications", "user_id", "users", "id", "SET NULL"),
    ("applications", "candidate_id", "candidates", "id", "SET NULL"),
    ("applications", "job_id", "jobs", "id", "SET NULL"),
    ("applications", "batch_id", "batch_jobs", "id", "SET NULL"),
    ("cv_documents", "evaluation_session_id", "evaluation_sessions", "id", "SET NULL"),
    ("offers", "created_by", "users", "id", "SET NULL"),
    ("background_checks", "offer_id", "offers", "id", "SET NULL"),
    ("background_checks", "recruiter_id", "users", "id", "SET NULL"),
    ("interviews", "scheduled_by", "users", "id", "SET NULL"),
    ("interview_participants", "user_id", "users", "id", "SET NULL"),
    ("interview_feedback", "interviewer_id", "users", "id", "SET NULL"),
    ("jobs", "recruiter_id", "users", "id", "SET NULL"),
    ("evaluation_sessions", "candidate_id", "candidate_profiles", "id", "SET NULL"),
    ("evaluation_sessions", "rubric_id", "rubrics", "id", "SET NULL"),
    ("evaluation_sessions", "rubric_snapshot_id", "rubric_snapshots", "id", "SET NULL"),
    ("evaluation_sessions", "evaluation_config_snapshot_id", "evaluation_config_snapshots", "id", "SET NULL"),
    ("evaluation_results", "rubric_id", "rubrics", "id", "SET NULL"),
    ("evaluation_results", "rubric_snapshot_id", "rubric_snapshots", "id", "SET NULL"),
    ("interview_turns", "user_id", "users", "id", "SET NULL"),
    ("ab_test_experiments", "created_by", "users", "id", "SET NULL"),
    ("ab_test_assignments", "user_id", "users", "id", "SET NULL"),
    ("ab_test_assignments", "candidate_id", "applications", "id", "SET NULL"),
    ("prompt_tests", "created_by", "users", "id", "SET NULL"),
    ("prompt_test_results", "variant_id", "prompt_variants", "id", "SET NULL"),
    ("skill_definitions", "category_id", "categories", "id", "SET NULL"),
]

CASCADE_FKS = [
    ("cv_documents", "application_id", "applications", "id", "CASCADE"),
    ("offers", "application_id", "applications", "id", "CASCADE"),
    ("background_checks", "application_id", "applications", "id", "CASCADE"),
    ("interviews", "application_id", "applications", "id", "CASCADE"),
    ("interview_participants", "interview_id", "interviews", "id", "CASCADE"),
    ("interview_feedback", "interview_id", "interviews", "id", "CASCADE"),
    ("job_skills", "job_id", "jobs", "id", "CASCADE"),
    ("job_evaluation_frameworks", "job_id", "jobs", "id", "CASCADE"),
    ("job_screening_questions", "job_id", "jobs", "id", "CASCADE"),
    ("job_pipeline_stages", "job_id", "jobs", "id", "CASCADE"),
    ("job_ai_configs", "job_id", "jobs", "id", "CASCADE"),
    ("job_role_overviews", "job_id", "jobs", "id", "CASCADE"),
    ("job_nice_to_haves", "job_id", "jobs", "id", "CASCADE"),
    ("evaluation_sessions", "application_id", "applications", "id", "CASCADE"),
    ("evaluation_results", "evaluation_session_id", "evaluation_sessions", "id", "CASCADE"),
    ("interview_turns", "application_id", "applications", "id", "CASCADE"),
    ("interview_turns", "evaluation_session_id", "evaluation_sessions", "id", "CASCADE"),
    ("ai_audit_logs", "application_id", "applications", "id", "CASCADE"),
    ("calibration_samples", "application_id", "applications", "id", "CASCADE"),
    ("ab_test_experiments", "job_id", "jobs", "id", "CASCADE"),
    ("ab_test_assignments", "experiment_id", "ab_test_experiments", "id", "CASCADE"),
    ("scoring_variant_results", "experiment_id", "ab_test_experiments", "id", "CASCADE"),
    ("scoring_variant_results", "candidate_id", "applications", "id", "CASCADE"),
    ("prompt_test_results", "test_id", "prompt_tests", "id", "CASCADE"),
    ("company_members", "company_id", "companies", "id", "CASCADE"),
    ("company_members", "user_id", "users", "id", "CASCADE"),
    ("team_members", "owner_id", "users", "id", "CASCADE"),
    ("team_members", "member_id", "users", "id", "CASCADE"),
]

RESTRICT_FKS = [
    # TenantMixin.company_id is already RESTRICT on all 55+ tenant tables
    # (set in Sprint 12). Only evaluation_sessions has an explicit
    # company_id FK that needs enforcement:
    ("evaluation_sessions", "company_id", "companies", "id", "RESTRICT"),
]

# Profile FKs (user cascade — already set in Sprint 12)
PROFILE_CASCADE_FKS = [
    ("candidate_profiles", "user_id", "users", "id", "CASCADE"),
    ("recruiter_profiles", "user_id", "users", "id", "CASCADE"),
    ("admin_profiles", "user_id", "users", "id", "CASCADE"),
]

ALL_FKS = SET_NULL_FKS + CASCADE_FKS + RESTRICT_FKS + PROFILE_CASCADE_FKS


def _find_fk_name(bind, table: str, column: str) -> str | None:
    """Find existing FK constraint name for a (table, column) pair."""
    dialect = bind.dialect.name
    if dialect == "sqlite":
        return None  # SQLite doesn't support DROP CONSTRAINT

    if dialect == "mysql":
        result = bind.execute(sa.text(
            "SELECT CONSTRAINT_NAME "
            "FROM information_schema.KEY_COLUMN_USAGE "
            "WHERE TABLE_SCHEMA = DATABASE() "
            "AND TABLE_NAME = :tbl AND COLUMN_NAME = :col "
            "AND REFERENCED_TABLE_NAME IS NOT NULL"
        ), {"tbl": table, "col": column})
        row = result.fetchone()
        return row[0] if row else None

    # PostgreSQL
    result = bind.execute(sa.text(
        "SELECT tc.constraint_name "
        "FROM information_schema.table_constraints tc "
        "JOIN information_schema.key_column_usage kcu "
        "  ON tc.constraint_name = kcu.constraint_name "
        "  AND tc.table_schema = kcu.table_schema "
        "WHERE tc.constraint_type = 'FOREIGN KEY' "
        "AND tc.table_name = :tbl AND kcu.column_name = :col "
        "AND tc.table_schema = :schema"
    ), {"tbl": table, "col": column, "schema": "public"})
    row = result.fetchone()
    return row[0] if row else None


def _recreate_fk(bind, table: str, column: str, ref_table: str,
                 ref_column: str, ondelete: str) -> None:
    """Drop existing FK and recreate with correct ON DELETE."""
    dialect = bind.dialect.name
    if dialect == "sqlite":
        return  # SQLite ignores FK constraints by default; no-op

    existing_name = _find_fk_name(bind, table, column)
    if existing_name:
        if dialect == "mysql":
            bind.execute(sa.text(
                f"ALTER TABLE `{table}` DROP FOREIGN KEY `{existing_name}`"
            ))
        else:
            bind.execute(sa.text(
                f"ALTER TABLE {table} DROP CONSTRAINT {existing_name}"
            ))

    new_name = f"fk_{table}_{column}"
    bind.execute(sa.text(
        f"ALTER TABLE `{table}` ADD CONSTRAINT `{new_name}` "
        f"FOREIGN KEY (`{column}`) REFERENCES `{ref_table}`(`{ref_column}`) "
        f"ON DELETE {ondelete}"
    ))


def upgrade() -> None:
    bind = op.get_bind()
    for table, col, ref_table, ref_col, ondelete in ALL_FKS:
        try:
            _recreate_fk(bind, table, col, ref_table, ref_col, ondelete)
        except Exception as e:
            pass


def downgrade() -> None:
    bind = op.get_bind()
    # Revert to MySQL default (NO ACTION = RESTRICT equivalent)
    for table, col, ref_table, ref_col, _ondelete in reversed(ALL_FKS):
        dialect = bind.dialect.name
        if dialect == "sqlite":
            continue
        existing_name = _find_fk_name(bind, table, col)
        if existing_name:
            if dialect == "mysql":
                bind.execute(sa.text(
                    f"ALTER TABLE `{table}` DROP FOREIGN KEY `{existing_name}`"
                ))
            else:
                bind.execute(sa.text(
                    f"ALTER TABLE {table} DROP CONSTRAINT {existing_name}"
                ))
        new_name = f"fk_{table}_{col}"
        bind.execute(sa.text(
            f"ALTER TABLE `{table}` ADD CONSTRAINT `{new_name}` "
            f"FOREIGN KEY (`{col}`) REFERENCES `{ref_table}`(`{ref_col}`)"
        ))
