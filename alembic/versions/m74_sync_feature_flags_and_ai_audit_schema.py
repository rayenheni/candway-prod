"""Sync feature flags and AI audit schema with SQLAlchemy models.

Revision ID: m74
Revises: m73
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "m74"
down_revision: Union[str, None] = "m73"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(bind, table: str) -> bool:
    return sa.inspect(bind).has_table(table)


def _columns(bind, table: str) -> set[str]:
    inspector = sa.inspect(bind)
    if not inspector.has_table(table):
        return set()
    return {c["name"] for c in inspector.get_columns(table)}


def _indexes(bind, table: str) -> set[str]:
    inspector = sa.inspect(bind)
    if not inspector.has_table(table):
        return set()
    return {i["name"] for i in inspector.get_indexes(table)}


def upgrade() -> None:
    bind = op.get_bind()

    # ===============================================================
    # 1. AI AUDIT LOGS
    # ===============================================================
    if _has_table(bind, "ai_audit_logs"):
        cols = _columns(bind, "ai_audit_logs")

        if "prompt_version" not in cols:
            op.add_column(
                "ai_audit_logs",
                sa.Column("prompt_version", sa.String(20), nullable=True),
            )

        if "prompt_injection_blocked" not in cols:
            op.add_column(
                "ai_audit_logs",
                sa.Column(
                    "prompt_injection_blocked",
                    sa.Boolean(),
                    nullable=True,
                    server_default=sa.text("0"),
                ),
            )

        if "previous_hash" not in cols:
            op.add_column(
                "ai_audit_logs",
                sa.Column(
                    "previous_hash",
                    sa.String(64),
                    nullable=True,
                ),
            )

        if "record_hash" not in cols:
            op.add_column(
                "ai_audit_logs",
                sa.Column(
                    "record_hash",
                    sa.String(64),
                    nullable=True,
                ),
            )

        indexes = _indexes(bind, "ai_audit_logs")

        if "ix_ai_audit_logs_previous_hash" not in indexes:
            op.create_index(
                "ix_ai_audit_logs_previous_hash",
                "ai_audit_logs",
                ["previous_hash"],
            )

        if "ix_ai_audit_logs_record_hash" not in indexes:
            op.create_index(
                "ix_ai_audit_logs_record_hash",
                "ai_audit_logs",
                ["record_hash"],
            )

    # ===============================================================
    # 2. FEATURE FLAGS
    # ===============================================================
    if _has_table(bind, "feature_flags"):
        cols = _columns(bind, "feature_flags")

        # -----------------------------------------------------------
        # user_id
        # -----------------------------------------------------------
        if "user_id" not in cols:
            op.add_column(
                "feature_flags",
                sa.Column(
                    "user_id",
                    sa.Integer(),
                    nullable=True,
                ),
            )

            op.create_foreign_key(
                "fk_feature_flags_user",
                "feature_flags",
                "users",
                ["user_id"],
                ["id"],
                ondelete="CASCADE",
            )

        # -----------------------------------------------------------
        # enabled
        #
        # Existing schema uses is_enabled.
        # Preserve the data and migrate the column name.
        # -----------------------------------------------------------
        if "enabled" not in cols:
            if "is_enabled" in cols:
                op.alter_column(
                    "feature_flags",
                    "is_enabled",
                    new_column_name="enabled",
                    existing_type=sa.Boolean(),
                    existing_nullable=False,
                    existing_server_default=sa.text("0"),
                )
            else:
                op.add_column(
                    "feature_flags",
                    sa.Column(
                        "enabled",
                        sa.Boolean(),
                        nullable=False,
                        server_default=sa.text("0"),
                    ),
                )

        # -----------------------------------------------------------
        # rollout_percentage
        # -----------------------------------------------------------
        if "rollout_percentage" not in cols:
            op.add_column(
                "feature_flags",
                sa.Column(
                    "rollout_percentage",
                    sa.Integer(),
                    nullable=False,
                    server_default="0",
                ),
            )

        # -----------------------------------------------------------
        # Indexes expected by the model
        # -----------------------------------------------------------
        indexes = _indexes(bind, "feature_flags")

        if "idx_feature_flags_user" not in indexes:
            op.create_index(
                "idx_feature_flags_user",
                "feature_flags",
                ["user_id"],
            )


def downgrade() -> None:
    bind = op.get_bind()

    # ===============================================================
    # FEATURE FLAGS
    # ===============================================================
    if _has_table(bind, "feature_flags"):
        indexes = _indexes(bind, "feature_flags")

        if "idx_feature_flags_user" in indexes:
            op.drop_index(
                "idx_feature_flags_user",
                table_name="feature_flags",
            )

        inspector = sa.inspect(bind)
        fks = {
            fk["name"]
            for fk in inspector.get_foreign_keys("feature_flags")
            if fk.get("name")
        }

        if "fk_feature_flags_user" in fks:
            op.drop_constraint(
                "fk_feature_flags_user",
                "feature_flags",
                type_="foreignkey",
            )

        cols = _columns(bind, "feature_flags")

        if "rollout_percentage" in cols:
            op.drop_column(
                "feature_flags",
                "rollout_percentage",
            )

        if "enabled" in cols:
            op.alter_column(
                "feature_flags",
                "enabled",
                new_column_name="is_enabled",
            )

        cols = _columns(bind, "feature_flags")

        if "user_id" in cols:
            op.drop_column(
                "feature_flags",
                "user_id",
            )

    # ===============================================================
    # AI AUDIT LOGS
    # ===============================================================
    if _has_table(bind, "ai_audit_logs"):
        indexes = _indexes(bind, "ai_audit_logs")

        if "ix_ai_audit_logs_previous_hash" in indexes:
            op.drop_index(
                "ix_ai_audit_logs_previous_hash",
                table_name="ai_audit_logs",
            )

        if "ix_ai_audit_logs_record_hash" in indexes:
            op.drop_index(
                "ix_ai_audit_logs_record_hash",
                table_name="ai_audit_logs",
            )

        cols = _columns(bind, "ai_audit_logs")

        for column in (
            "record_hash",
            "previous_hash",
            "prompt_injection_blocked",
            "prompt_version",
        ):
            if column in cols:
                op.drop_column(
                    "ai_audit_logs",
                    column,
                )
