"""create job_wizard tables (job_skills, job_evaluation_frameworks, job_screening_questions, job_pipeline_stages, job_ai_configs, job_role_overviews, job_nice_to_haves)

Revision ID: m34
Revises: p1prod202606300
Create Date: 2026-07-05 10:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "m34"
down_revision: Union[str, Sequence[str], None] = "p1prod202606300"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── job_skills ────────────────────────────────────────────
    op.create_table(
        "job_skills",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("jobs.id"), nullable=False, index=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False, index=True),
        sa.Column("skill_name", sa.String(length=100), nullable=False),
        sa.Column("required_level", sa.String(length=20), nullable=False, server_default="intermediate"),
        sa.Column("weight", sa.Integer(), nullable=False, server_default="10"),
        sa.Column("is_mandatory", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=True, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("job_id", "skill_name", name="uq_job_skill_name"),
    )
    op.create_index("idx_job_skills_job", "job_skills", ["job_id"])
    op.create_index("idx_job_skills_company_name", "job_skills", ["company_id", "skill_name"])

    # ── job_evaluation_frameworks ─────────────────────────────
    op.create_table(
        "job_evaluation_frameworks",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("jobs.id"), nullable=False, unique=True, index=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False, index=True),
        sa.Column("categories", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=True, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_job_ef_job", "job_evaluation_frameworks", ["job_id"], unique=True)

    # ── job_screening_questions ───────────────────────────────
    op.create_table(
        "job_screening_questions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("jobs.id"), nullable=False, index=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False, index=True),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("type", sa.String(length=20), nullable=False, server_default="text"),
        sa.Column("options", sa.JSON(), nullable=True),
        sa.Column("is_required", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=True, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_jsq_job", "job_screening_questions", ["job_id"])
    op.create_index("idx_jsq_job_order", "job_screening_questions", ["job_id", "sort_order"])

    # ── job_pipeline_stages ───────────────────────────────────
    op.create_table(
        "job_pipeline_stages",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("jobs.id"), nullable=False, index=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False, index=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("slug", sa.String(length=100), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("color", sa.String(length=20), nullable=True),
        sa.Column("icon", sa.String(length=50), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("job_id", "slug", name="uq_job_pipeline_slug"),
    )
    op.create_index("idx_jps_job", "job_pipeline_stages", ["job_id"])
    op.create_index("idx_jps_job_order", "job_pipeline_stages", ["job_id", "sort_order"])

    # ── job_ai_configs ────────────────────────────────────────
    op.create_table(
        "job_ai_configs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("jobs.id"), nullable=False, unique=True, index=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False, index=True),
        sa.Column("ai_scoring_enabled", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("minimum_recommended_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("auto_shortlist_threshold", sa.Float(), nullable=True),
        sa.Column("auto_reject_threshold", sa.Float(), nullable=True),
        sa.Column("explain_ai_decisions", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("evidence_based_scoring", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("ignore_missing_cv", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("prioritize_verified_skills", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("custom_instructions", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=True, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_jac_job", "job_ai_configs", ["job_id"], unique=True)

    # ── job_role_overviews ────────────────────────────────────
    op.create_table(
        "job_role_overviews",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("jobs.id"), nullable=False, index=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False, index=True),
        sa.Column("question_key", sa.String(length=50), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("answer", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=True, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("job_id", "question_key", name="uq_job_role_q_key"),
    )
    op.create_index("idx_jro_job", "job_role_overviews", ["job_id"])

    # ── job_nice_to_haves ─────────────────────────────────────
    op.create_table(
        "job_nice_to_haves",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("jobs.id"), nullable=False, index=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False, index=True),
        sa.Column("requirement_type", sa.String(length=50), nullable=False),
        sa.Column("label", sa.String(length=255), nullable=False),
        sa.Column("is_preferred", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=True, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_jnth_job", "job_nice_to_haves", ["job_id"])
    op.create_index("idx_jnth_job_type", "job_nice_to_haves", ["job_id", "requirement_type"])


def downgrade() -> None:
    op.drop_table("job_nice_to_haves")
    op.drop_table("job_role_overviews")
    op.drop_table("job_ai_configs")
    op.drop_table("job_pipeline_stages")
    op.drop_table("job_screening_questions")
    op.drop_table("job_evaluation_frameworks")
    op.drop_table("job_skills")
