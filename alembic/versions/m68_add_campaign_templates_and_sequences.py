"""
Add campaign templates and email sequence fields to batch_jobs.

Revision ID: m68
Revises: m67
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "m68"
down_revision: Union[str, None] = "m67"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # 1. Create campaign_templates if missing
    if not inspector.has_table("campaign_templates"):
        op.create_table(
            "campaign_templates",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("recruiter_id", sa.Integer(), nullable=True),
            sa.Column("name", sa.String(255), nullable=False),
            sa.Column("role", sa.String(255), nullable=True),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("subject_template", sa.String(500), nullable=True),
            sa.Column("body_template", sa.Text(), nullable=True),
            sa.Column("is_default", sa.Boolean(), server_default=sa.text("0")),
            sa.Column("is_active", sa.Boolean(), server_default=sa.text("1")),
            sa.Column(
                "created_at",
                sa.DateTime(),
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(),
                server_default=sa.text(
                    "CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"
                ),
            ),
            sa.ForeignKeyConstraint(
                ["recruiter_id"],
                ["users.id"],
                ondelete="SET NULL",
            ),
            sa.PrimaryKeyConstraint("id"),
        )

        op.create_index(
            "idx_recruiter_id",
            "campaign_templates",
            ["recruiter_id"],
        )
        op.create_index(
            "idx_is_default",
            "campaign_templates",
            ["is_default"],
        )

    # Refresh inspector after table creation
    inspector = sa.inspect(bind)

    # 2. Add campaign template / sequence fields to batch_jobs
    columns = {
        column["name"]
        for column in inspector.get_columns("batch_jobs")
    }

    if "template_id" not in columns:
        op.add_column(
            "batch_jobs",
            sa.Column("template_id", sa.Integer(), nullable=True),
        )

    if "email_sequence_enabled" not in columns:
        op.add_column(
            "batch_jobs",
            sa.Column(
                "email_sequence_enabled",
                sa.Boolean(),
                server_default=sa.text("0"),
                nullable=True,
            ),
        )

    if "email_sequence_days" not in columns:
        op.add_column(
            "batch_jobs",
            sa.Column("email_sequence_days", sa.Text(), nullable=True),
        )

    # 3. Add index + FK for template_id only if missing
    indexes = inspector.get_indexes("batch_jobs")
    index_names = {idx["name"] for idx in indexes}

    if "idx_batch_jobs_template" not in index_names:
        op.create_index(
            "idx_batch_jobs_template",
            "batch_jobs",
            ["template_id"],
        )

    foreign_keys = inspector.get_foreign_keys("batch_jobs")
    has_template_fk = any(
        fk.get("constrained_columns") == ["template_id"]
        and fk.get("referred_table") == "campaign_templates"
        for fk in foreign_keys
    )

    if not has_template_fk:
        op.create_foreign_key(
            "fk_batch_jobs_template_id",
            "batch_jobs",
            "campaign_templates",
            ["template_id"],
            ["id"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table("batch_jobs"):
        return

    # Remove FK if present
    foreign_keys = inspector.get_foreign_keys("batch_jobs")

    for fk in foreign_keys:
        if (
            fk.get("name") == "fk_batch_jobs_template_id"
            or (
                fk.get("constrained_columns") == ["template_id"]
                and fk.get("referred_table") == "campaign_templates"
            )
        ):
            if fk.get("name"):
                op.drop_constraint(
                    fk["name"],
                    "batch_jobs",
                    type_="foreignkey",
                )
            break

    # Remove index if present
    indexes = sa.inspect(bind).get_indexes("batch_jobs")
    if any(
        idx["name"] == "idx_batch_jobs_template"
        for idx in indexes
    ):
        op.drop_index(
            "idx_batch_jobs_template",
            table_name="batch_jobs",
        )

    columns = {
        column["name"]
        for column in sa.inspect(bind).get_columns("batch_jobs")
    }

    for column_name in (
        "email_sequence_days",
        "email_sequence_enabled",
        "template_id",
    ):
        if column_name in columns:
            op.drop_column("batch_jobs", column_name)

    # Drop template table only if it exists.
    if sa.inspect(bind).has_table("campaign_templates"):
        op.drop_index(
            "idx_is_default",
            table_name="campaign_templates",
        )
        op.drop_index(
            "idx_recruiter_id",
            table_name="campaign_templates",
        )
        op.drop_table("campaign_templates")
