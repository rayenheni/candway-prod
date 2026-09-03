"""add missing timestamps to tables

Migration to add created_at and / or updated_at columns to tables
that are missing them for consistency.

Revision ID: m12_add_missing_timestamps
Revises: m11_drop_deprecated_app_columns
Create Date: 2026-06-25 10:30:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = "m12_add_missing_timestamps"
down_revision: Union[str, None] = "m11_drop_deprecated_app_columns"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(name: str) -> bool:
    bind = op.get_bind()
    return bind.dialect.has_table(bind, name)


def upgrade() -> None:
    # --- categories ---
    op.add_column("categories", sa.Column("created_at", sa.DateTime(), nullable=True, server_default=sa.func.now()))
    op.add_column("categories", sa.Column("updated_at", sa.DateTime(), nullable=True, onupdate=sa.func.now()))

    # --- email_verifications ---
    op.add_column("email_verifications", sa.Column("created_at", sa.DateTime(), nullable=True, server_default=sa.func.now()))
    op.add_column("email_verifications", sa.Column("updated_at", sa.DateTime(), nullable=True, onupdate=sa.func.now()))

    # --- login_attempts ---
    op.add_column("login_attempts", sa.Column("created_at", sa.DateTime(), nullable=True, server_default=sa.func.now()))
    op.add_column("login_attempts", sa.Column("updated_at", sa.DateTime(), nullable=True, onupdate=sa.func.now()))

    # --- token_blacklist ---
    op.add_column("token_blacklist", sa.Column("created_at", sa.DateTime(), nullable=True, server_default=sa.func.now()))
    op.add_column("token_blacklist", sa.Column("updated_at", sa.DateTime(), nullable=True, onupdate=sa.func.now()))

    # --- audit_logs ---
    op.add_column("audit_logs", sa.Column("created_at", sa.DateTime(), nullable=True, server_default=sa.func.now()))
    op.add_column("audit_logs", sa.Column("updated_at", sa.DateTime(), nullable=True, onupdate=sa.func.now()))

    # --- company_members ---
    op.add_column("company_members", sa.Column("updated_at", sa.DateTime(), nullable=True, onupdate=sa.func.now()))

    # --- company_verifications ---
    op.add_column("company_verifications", sa.Column("updated_at", sa.DateTime(), nullable=True, onupdate=sa.func.now()))

    # --- consent_logs ---
    op.add_column("consent_logs", sa.Column("created_at", sa.DateTime(), nullable=True, server_default=sa.func.now()))
    op.add_column("consent_logs", sa.Column("updated_at", sa.DateTime(), nullable=True, onupdate=sa.func.now()))

    # --- password_resets ---
    op.add_column("password_resets", sa.Column("updated_at", sa.DateTime(), nullable=True, onupdate=sa.func.now()))

    # --- extracted_skills ---
    op.add_column("extracted_skills", sa.Column("updated_at", sa.DateTime(), nullable=True, onupdate=sa.func.now()))

    # --- interview_questions (table may not exist on all DBs) ---
    if _table_exists("interview_questions"):
        op.add_column("interview_questions", sa.Column("updated_at", sa.DateTime(), nullable=True, onupdate=sa.func.now()))

    # --- qualifications ---
    op.add_column("qualifications", sa.Column("created_at", sa.DateTime(), nullable=True, server_default=sa.func.now()))
    op.add_column("qualifications", sa.Column("updated_at", sa.DateTime(), nullable=True, onupdate=sa.func.now()))

    # --- activity_logs ---
    op.add_column("activity_logs", sa.Column("updated_at", sa.DateTime(), nullable=True, onupdate=sa.func.now()))

    # --- candidate_interactions ---
    op.add_column("candidate_interactions", sa.Column("updated_at", sa.DateTime(), nullable=True, onupdate=sa.func.now()))

    # --- ab_test_assignments ---
    op.add_column("ab_test_assignments", sa.Column("updated_at", sa.DateTime(), nullable=True, onupdate=sa.func.now()))

    # --- scoring_variant_results ---
    op.add_column("scoring_variant_results", sa.Column("updated_at", sa.DateTime(), nullable=True, onupdate=sa.func.now()))

    # --- drift_snapshots ---
    op.add_column("drift_snapshots", sa.Column("updated_at", sa.DateTime(), nullable=True, onupdate=sa.func.now()))

    # --- calibration_samples ---
    op.add_column("calibration_samples", sa.Column("updated_at", sa.DateTime(), nullable=True, onupdate=sa.func.now()))

    # --- translation_cache ---
    op.add_column("translation_cache", sa.Column("updated_at", sa.DateTime(), nullable=True, onupdate=sa.func.now()))

    # --- transactions ---
    op.add_column("transactions", sa.Column("updated_at", sa.DateTime(), nullable=True, onupdate=sa.func.now()))


def downgrade() -> None:
    # --- transactions ---
    op.drop_column("transactions", "updated_at")

    # --- translation_cache ---
    op.drop_column("translation_cache", "updated_at")

    # --- calibration_samples ---
    op.drop_column("calibration_samples", "updated_at")

    # --- drift_snapshots ---
    op.drop_column("drift_snapshots", "updated_at")

    # --- scoring_variant_results ---
    op.drop_column("scoring_variant_results", "updated_at")

    # --- ab_test_assignments ---
    op.drop_column("ab_test_assignments", "updated_at")

    # --- candidate_interactions ---
    op.drop_column("candidate_interactions", "updated_at")

    # --- activity_logs ---
    op.drop_column("activity_logs", "updated_at")

    # --- qualifications ---
    op.drop_column("qualifications", "updated_at")
    op.drop_column("qualifications", "created_at")

    # --- interview_questions (skip if table was dropped) ---
    if _table_exists("interview_questions"):
        op.drop_column("interview_questions", "updated_at")

    # --- extracted_skills ---
    op.drop_column("extracted_skills", "updated_at")

    # --- password_resets ---
    op.drop_column("password_resets", "updated_at")

    # --- consent_logs ---
    op.drop_column("consent_logs", "updated_at")
    op.drop_column("consent_logs", "created_at")

    # --- company_verifications ---
    op.drop_column("company_verifications", "updated_at")

    # --- company_members ---
    op.drop_column("company_members", "updated_at")

    # --- audit_logs ---
    op.drop_column("audit_logs", "updated_at")
    op.drop_column("audit_logs", "created_at")

    # --- token_blacklist ---
    op.drop_column("token_blacklist", "updated_at")
    op.drop_column("token_blacklist", "created_at")

    # --- login_attempts ---
    op.drop_column("login_attempts", "updated_at")
    op.drop_column("login_attempts", "created_at")

    # --- email_verifications ---
    op.drop_column("email_verifications", "updated_at")
    op.drop_column("email_verifications", "created_at")

    # --- categories ---
    op.drop_column("categories", "updated_at")
    op.drop_column("categories", "created_at")
