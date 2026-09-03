"""add subscription & tier columns to recruiter_profiles and candidate_profiles

Migration Phase 2: adds new columns to Profile tables for subscription/tier/plan
fields that were previously only on the User model.

Affected tables:
  - recruiter_profiles: +tier, +subscription_status, +subscription_end,
                        +current_plan_id (FK), +subscription_plan, +calendar_settings
  - candidate_profiles: +subscription_status, +subscription_plan

Revision ID: m38
Revises: m37
Create Date: 2026-07-06 10:15:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "m38"
down_revision: Union[str, Sequence[str], None] = "m37"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # ── RecruiterProfile ────────────────────────────────────────────
    r_cols = {c["name"] for c in inspector.get_columns("recruiter_profiles")}
    if "tier" not in r_cols:
        op.add_column("recruiter_profiles", sa.Column("tier", sa.String(50), nullable=True))
    if "subscription_status" not in r_cols:
        op.add_column("recruiter_profiles", sa.Column("subscription_status", sa.String(50), server_default="active", nullable=True))
    if "subscription_end" not in r_cols:
        op.add_column("recruiter_profiles", sa.Column("subscription_end", sa.DateTime(), nullable=True))
    if "current_plan_id" not in r_cols:
        op.add_column("recruiter_profiles", sa.Column("current_plan_id", sa.Integer(), sa.ForeignKey("subscription_plans.id"), nullable=True))
    if "subscription_plan" not in r_cols:
        op.add_column("recruiter_profiles", sa.Column("subscription_plan", sa.String(255), nullable=True))
    if "calendar_settings" not in r_cols:
        op.add_column("recruiter_profiles", sa.Column("calendar_settings", sa.Text(), nullable=True))

    r_idxs = {idx["name"] for idx in inspector.get_indexes("recruiter_profiles")}
    if "idx_recruiter_profiles_subscription" not in r_idxs:
        op.create_index("idx_recruiter_profiles_subscription", "recruiter_profiles", ["subscription_status"])

    # ── CandidateProfile ────────────────────────────────────────────
    c_cols = {c["name"] for c in inspector.get_columns("candidate_profiles")}
    if "subscription_status" not in c_cols:
        op.add_column("candidate_profiles", sa.Column("subscription_status", sa.String(50), server_default="active", nullable=True))
    if "subscription_plan" not in c_cols:
        op.add_column("candidate_profiles", sa.Column("subscription_plan", sa.String(255), nullable=True))

    c_idxs = {idx["name"] for idx in inspector.get_indexes("candidate_profiles")}
    if "idx_candidate_profiles_subscription" not in c_idxs:
        op.create_index("idx_candidate_profiles_subscription", "candidate_profiles", ["subscription_status"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    c_idxs = {idx["name"] for idx in inspector.get_indexes("candidate_profiles")}
    if "idx_candidate_profiles_subscription" in c_idxs:
        op.drop_index("idx_candidate_profiles_subscription", table_name="candidate_profiles")

    c_cols = {c["name"] for c in inspector.get_columns("candidate_profiles")}
    for col in ("subscription_plan", "subscription_status"):
        if col in c_cols:
            op.drop_column("candidate_profiles", col)

    r_idxs = {idx["name"] for idx in inspector.get_indexes("recruiter_profiles")}
    if "idx_recruiter_profiles_subscription" in r_idxs:
        op.drop_index("idx_recruiter_profiles_subscription", table_name="recruiter_profiles")

    r_cols = {c["name"] for c in inspector.get_columns("recruiter_profiles")}
    for col in ("calendar_settings", "subscription_plan", "current_plan_id", "subscription_end", "subscription_status", "tier"):
        if col in r_cols:
            op.drop_column("recruiter_profiles", col)
