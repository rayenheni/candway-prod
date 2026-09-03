"""Create prompt management tables

Revision ID: m72
Revises: 2e0181531b7a
Create Date: 2026-08-24
"""

from alembic import op
import sqlalchemy as sa


revision = "m72"
down_revision = "2e0181531b7a"
branch_labels = None
depends_on = None


def upgrade():
    # ---------------------------------------------------------
    # prompt_tests
    # ---------------------------------------------------------
    op.create_table(
        "prompt_tests",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("prompt_type", sa.String(length=100), nullable=True),
        sa.Column("version", sa.String(length=20), nullable=True),
        sa.Column("variant", sa.String(length=20), nullable=True),
        sa.Column("test_name", sa.String(length=255), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("prompt_content", sa.Text(), nullable=True),
        sa.Column("expected_output", sa.Text(), nullable=True),

        sa.Column("test_cases_count", sa.Integer(), nullable=True),
        sa.Column("total_runs", sa.Integer(), nullable=True),
        sa.Column("successful_runs", sa.Integer(), nullable=True),
        sa.Column("avg_latency_ms", sa.Float(), nullable=True),
        sa.Column("avg_score", sa.Float(), nullable=True),

        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=True),

        sa.Column("company_id", sa.Integer(), nullable=False),

        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name="fk_prompt_tests_created_by_users",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            name="fk_prompt_tests_company",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "ix_prompt_tests_id",
        "prompt_tests",
        ["id"],
        unique=False,
    )
    op.create_index(
        "ix_prompt_tests_prompt_type",
        "prompt_tests",
        ["prompt_type"],
        unique=False,
    )
    op.create_index(
        "ix_prompt_tests_company_id",
        "prompt_tests",
        ["company_id"],
        unique=False,
    )
    op.create_index(
        "idx_prompt_tests_created_by",
        "prompt_tests",
        ["created_by"],
        unique=False,
    )

    # ---------------------------------------------------------
    # prompt_variants
    # ---------------------------------------------------------
    op.create_table(
        "prompt_variants",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("prompt_type", sa.String(length=100), nullable=True),
        sa.Column("version", sa.String(length=20), nullable=True),
        sa.Column("variant_name", sa.String(length=100), nullable=True),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),

        sa.Column("times_used", sa.Integer(), nullable=True),
        sa.Column("success_rate", sa.Float(), nullable=True),
        sa.Column("avg_latency", sa.Float(), nullable=True),

        sa.Column("is_enabled", sa.Boolean(), nullable=True),
        sa.Column("traffic_percentage", sa.Float(), nullable=True),

        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),

        sa.Column("company_id", sa.Integer(), nullable=False),

        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            name="fk_prompt_variants_company",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "ix_prompt_variants_id",
        "prompt_variants",
        ["id"],
        unique=False,
    )
    op.create_index(
        "ix_prompt_variants_prompt_type",
        "prompt_variants",
        ["prompt_type"],
        unique=False,
    )
    op.create_index(
        "ix_prompt_variants_company_id",
        "prompt_variants",
        ["company_id"],
        unique=False,
    )

    # ---------------------------------------------------------
    # prompt_test_results
    # ---------------------------------------------------------
    op.create_table(
        "prompt_test_results",
        sa.Column("id", sa.Integer(), nullable=False),

        sa.Column("test_id", sa.Integer(), nullable=True),
        sa.Column("variant_id", sa.Integer(), nullable=True),

        sa.Column("version", sa.String(length=20), nullable=True),
        sa.Column("variant", sa.String(length=20), nullable=True),

        sa.Column("status", sa.String(length=50), nullable=True),
        sa.Column("response_time_ms", sa.Float(), nullable=True),

        sa.Column("output_score", sa.Float(), nullable=True),
        sa.Column("quality_metrics", sa.Text(), nullable=True),

        sa.Column("actual_output", sa.Text(), nullable=True),
        sa.Column("similarity_score", sa.Float(), nullable=True),

        sa.Column("executed_at", sa.DateTime(), nullable=True),

        sa.Column("company_id", sa.Integer(), nullable=False),

        sa.ForeignKeyConstraint(
            ["test_id"],
            ["prompt_tests.id"],
            name="fk_prompt_test_results_test",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["variant_id"],
            ["prompt_variants.id"],
            name="fk_prompt_test_results_variant",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            name="fk_prompt_test_results_company",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "ix_prompt_test_results_id",
        "prompt_test_results",
        ["id"],
        unique=False,
    )
    op.create_index(
        "idx_prompt_test_results_test",
        "prompt_test_results",
        ["test_id"],
        unique=False,
    )
    op.create_index(
        "idx_prompt_test_results_variant",
        "prompt_test_results",
        ["variant_id"],
        unique=False,
    )
    op.create_index(
        "ix_prompt_test_results_company_id",
        "prompt_test_results",
        ["company_id"],
        unique=False,
    )


def downgrade():
    op.drop_table("prompt_test_results")
    op.drop_table("prompt_variants")
    op.drop_table("prompt_tests")
