"""Extend feature_flags with S7 governance/rollout columns

Adds visibility, audiences, kill switches, dependency, plan restrictions,
company override key and temp/permanent user unlock columns to the existing
feature_flags table so features can be administered without code deploys.

Revision ID: m50
Revises: m49
Create Date: 2026-08-01
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "m50"
down_revision: Union[str, None] = "m49"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(bind, table: str, column: str) -> bool:
    inspector = sa.inspect(bind)
    if not inspector.has_table(table):
        return False
    cols = {c["name"] for c in inspector.get_columns(table)}
    return column in cols


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table("feature_flags"):
        op.create_table(
            "feature_flags",
            sa.Column("id", sa.Integer(), primary_key=True, index=True),
            sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id", ondelete="SET NULL"), nullable=True, index=True),
            sa.Column("flag_key", sa.String(100), nullable=False, unique=True),
            sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.text("0")),
            sa.Column("description", sa.String(255), nullable=True),
            sa.Column("rules_json", sa.Text(), nullable=True),
            sa.Column("visibility", sa.String(20), nullable=False, server_default="public"),
            sa.Column("audiences", sa.String(100), nullable=False, server_default="all"),
            sa.Column("maintenance_mode", sa.Boolean(), nullable=False, server_default=sa.text("0")),
            sa.Column("kill_switch", sa.Boolean(), nullable=False, server_default=sa.text("0")),
            sa.Column("depends_on", sa.String(100), nullable=True),
            sa.Column("plan_restrictions", sa.String(255), nullable=True),
            sa.Column("company_override_key", sa.String(100), nullable=True),
            sa.Column("temp_unlock_user_id", sa.Integer(), nullable=True),
            sa.Column("temp_unlock_until", sa.DateTime(), nullable=True),
            sa.Column("permanent_unlock_user_id", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
        )
    else:
        add = {
            "visibility": sa.Column(
                "visibility", sa.String(length=20), nullable=False, server_default="public"
            ),
            "audiences": sa.Column(
                "audiences", sa.String(length=100), nullable=False, server_default="all"
            ),
            "maintenance_mode": sa.Column(
                "maintenance_mode", sa.Boolean(), nullable=False, server_default=sa.text("0")
            ),
            "kill_switch": sa.Column(
                "kill_switch", sa.Boolean(), nullable=False, server_default=sa.text("0")
            ),
            "depends_on": sa.Column("depends_on", sa.String(length=100), nullable=True),
            "plan_restrictions": sa.Column(
                "plan_restrictions", sa.String(length=255), nullable=True
            ),
            "company_override_key": sa.Column(
                "company_override_key", sa.String(length=100), nullable=True
            ),
            "temp_unlock_user_id": sa.Column(
                "temp_unlock_user_id", sa.Integer(), nullable=True
            ),
            "temp_unlock_until": sa.Column("temp_unlock_until", sa.DateTime(), nullable=True),
            "permanent_unlock_user_id": sa.Column(
                "permanent_unlock_user_id", sa.Integer(), nullable=True
            ),
        }

        for col_name, col in add.items():
            if not _has_column(bind, "feature_flags", col_name):
                op.add_column("feature_flags", col)

    if inspector.has_table("feature_flags"):
        indexes = {idx["name"] for idx in inspector.get_indexes("feature_flags")}
        if "idx_feature_flags_key_audiences" not in indexes:
            try:
                op.create_index(
                    "idx_feature_flags_key_audiences", "feature_flags", ["flag_key", "audiences"]
                )
            except Exception:
                pass
        if "idx_feature_flags_temp_unlock" not in indexes:
            try:
                op.create_index(
                    "idx_feature_flags_temp_unlock", "feature_flags", ["temp_unlock_user_id"]
                )
            except Exception:
                pass
        if "idx_feature_flags_perm_unlock" not in indexes:
            try:
                op.create_index(
                    "idx_feature_flags_perm_unlock", "feature_flags", ["permanent_unlock_user_id"]
                )
            except Exception:
                pass


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("feature_flags"):
        return

    drop = [
        "visibility",
        "audiences",
        "maintenance_mode",
        "kill_switch",
        "depends_on",
        "plan_restrictions",
        "company_override_key",
        "temp_unlock_user_id",
        "temp_unlock_until",
        "permanent_unlock_user_id",
    ]
    for col_name in drop:
        if _has_column(bind, "feature_flags", col_name):
            op.drop_column("feature_flags", col_name)

    try:
        op.drop_index("idx_feature_flags_key_audiences", table_name="feature_flags")
        op.drop_index("idx_feature_flags_temp_unlock", table_name="feature_flags")
        op.drop_index("idx_feature_flags_perm_unlock", table_name="feature_flags")
    except Exception:
        pass
