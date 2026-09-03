"""fix missing columns on companies, company_members, ab_experiments, calibration_samples

Migration to add columns that exist in the Python models but are missing
from the database tables. These columns were originally added in revisions
under the a7b8c9d0e1f2 branch which was ancestrally included in M005 and
therefore skipped during the merge migration.

Revision ID: a3b4c5d6e7f8
Revises: m9merge_e5f6a7b8c9d0_d6e7f8a9b0c1
Create Date: 2026-06-13 12:48:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "a3b4c5d6e7f8"
down_revision: Union[str, None] = "m9merge_e5f6a7b8c9d0_d6e7f8a9b0c1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- company_members ---
    op.add_column("company_members", sa.Column("permissions", sa.Text(), nullable=True))
    op.add_column("company_members", sa.Column("invited_at", sa.DateTime(), nullable=True))
    op.add_column("company_members", sa.Column("joined_at", sa.DateTime(), nullable=True))

    # --- companies ---
    op.add_column("companies", sa.Column("domain", sa.String(255), nullable=True))
    op.add_column("companies", sa.Column("tier", sa.String(50), nullable=True, server_default="free"))
    op.add_column("companies", sa.Column("subscription_status", sa.String(50), nullable=True, server_default="active"))
    op.add_column("companies", sa.Column("max_users", sa.Integer(), nullable=True, server_default="10"))
    op.add_column("companies", sa.Column("max_jobs", sa.Integer(), nullable=True, server_default="50"))
    op.add_column("companies", sa.Column("max_ai_interviews", sa.Integer(), nullable=True, server_default="500"))
    op.add_column("companies", sa.Column("logo_url", sa.String(500), nullable=True))
    op.add_column("companies", sa.Column("primary_color", sa.String(7), nullable=True))
    op.add_column("companies", sa.Column("deleted_at", sa.DateTime(), nullable=True))

    # --- ab_experiments ---
    op.add_column("ab_experiments", sa.Column("experiment_id", sa.String(64), nullable=False))
    op.add_column("ab_experiments", sa.Column("variant_a_config", sa.Text(), nullable=True))
    op.add_column("ab_experiments", sa.Column("variant_b_config", sa.Text(), nullable=True))
    op.add_column("ab_experiments", sa.Column("variant_a_results", sa.Text(), nullable=True))
    op.add_column("ab_experiments", sa.Column("variant_b_results", sa.Text(), nullable=True))
    op.add_column("ab_experiments", sa.Column("winner", sa.String(8), nullable=True))
    op.add_column("ab_experiments", sa.Column("confidence_level", sa.Float(), nullable=True))
    op.add_column("ab_experiments", sa.Column("created_at", sa.DateTime(), nullable=True))

    # --- calibration_samples ---
    op.add_column("calibration_samples", sa.Column("sample_id", sa.String(64), nullable=False))
    op.add_column("calibration_samples", sa.Column("role", sa.String(128), nullable=True))
    op.add_column("calibration_samples", sa.Column("seniority", sa.String(50), nullable=True))
    op.add_column("calibration_samples", sa.Column("ai_scores", sa.Text(), nullable=False))
    op.add_column("calibration_samples", sa.Column("human_ratings", sa.Text(), nullable=True))
    op.add_column("calibration_samples", sa.Column("ai_human_correlation", sa.Float(), nullable=True))
    op.add_column("calibration_samples", sa.Column("score_delta", sa.Float(), nullable=True))
    op.add_column("calibration_samples", sa.Column("metadata_json", sa.Text(), nullable=True))


def downgrade() -> None:
    # --- calibration_samples ---
    op.drop_column("calibration_samples", "metadata_json")
    op.drop_column("calibration_samples", "score_delta")
    op.drop_column("calibration_samples", "ai_human_correlation")
    op.drop_column("calibration_samples", "human_ratings")
    op.drop_column("calibration_samples", "ai_scores")
    op.drop_column("calibration_samples", "seniority")
    op.drop_column("calibration_samples", "role")
    op.drop_column("calibration_samples", "sample_id")

    # --- ab_experiments ---
    op.drop_column("ab_experiments", "created_at")
    op.drop_column("ab_experiments", "confidence_level")
    op.drop_column("ab_experiments", "winner")
    op.drop_column("ab_experiments", "variant_b_results")
    op.drop_column("ab_experiments", "variant_a_results")
    op.drop_column("ab_experiments", "variant_b_config")
    op.drop_column("ab_experiments", "variant_a_config")
    op.drop_column("ab_experiments", "experiment_id")

    # --- companies ---
    op.drop_column("companies", "deleted_at")
    op.drop_column("companies", "primary_color")
    op.drop_column("companies", "logo_url")
    op.drop_column("companies", "max_ai_interviews")
    op.drop_column("companies", "max_jobs")
    op.drop_column("companies", "max_users")
    op.drop_column("companies", "subscription_status")
    op.drop_column("companies", "tier")
    op.drop_column("companies", "domain")

    # --- company_members ---
    op.drop_column("company_members", "joined_at")
    op.drop_column("company_members", "invited_at")
    op.drop_column("company_members", "permissions")
