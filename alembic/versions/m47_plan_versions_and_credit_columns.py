"""Add plan_versions + credit columns to subscription_plans

Monetization S1: adds credits_monthly/plan_group to subscription_plans,
creates the plan_versions table for grandfathering, and seeds the 6 paid
plans from pricing.html (candidate Pro/Premium, recruiter
Starter/Professional/Enterprise). Free plans stay lazy-created by services.

Revision ID: m47
Revises: m46
Create Date: 2026-08-01
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "m47"
down_revision: Union[str, None] = "m46"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


PAID_PLANS = [
    # ── Candidate plans ──────────────────────────────────────────────
    {
        "name": "Candidate Pro",
        "slug": "candidate-pro",
        "target_audience": "candidate",
        "price_monthly": 29.0,
        "price_yearly": 278.0,
        "features": (
            '["10 CV uploads/month", "10 AI analyses/month", '
            '"Unlimited job matching", "5 PDF downloads/month", '
            '"Enhanced profile badge", "3 courses", "AI career roadmap", '
            '"Priority support"]'
        ),
        "candidate_cv_uploads_limit": 10,
        "candidate_ai_analyses_limit": 10,
        "candidate_pdf_downloads_limit": 5,
        "candidate_job_matches_limit": -1,
        "credits_monthly": 30,
        "plan_group": "standard",
        "is_featured": True,
    },
    {
        "name": "Candidate Premium",
        "slug": "candidate-premium",
        "target_audience": "candidate",
        "price_monthly": 49.0,
        "price_yearly": 470.0,
        "features": (
            '["Unlimited CV uploads", "Unlimited AI analyses", '
            '"Unlimited job matching", "Premium profile badge", '
            '"All courses", "1-on-1 mentorship", "AI career roadmap", '
            '"Priority support"]'
        ),
        "candidate_cv_uploads_limit": -1,
        "candidate_ai_analyses_limit": -1,
        "candidate_pdf_downloads_limit": -1,
        "candidate_job_matches_limit": -1,
        "credits_monthly": 100,
        "plan_group": "standard",
        "is_featured": False,
    },
    # ── Recruiter plans ──────────────────────────────────────────────
    {
        "name": "Recruiter Starter",
        "slug": "recruiter-starter",
        "target_audience": "recruiter",
        "price_monthly": 49.0,
        "price_yearly": 470.0,
        "features": (
            '["5 active jobs", "50 CV reviews/month", '
            '"10 AI interviews/month", "1 team seat", '
            '"Candidate database access", "Email invitations"]'
        ),
        "job_limit": 5,
        "cv_limit": 50,
        "ai_interview_limit": 10,
        "team_seat_limit": 1,
        "credits_monthly": 60,
        "plan_group": "standard",
        "is_featured": False,
    },
    {
        "name": "Recruiter Professional",
        "slug": "recruiter-professional",
        "target_audience": "recruiter",
        "price_monthly": 149.0,
        "price_yearly": 1430.0,
        "features": (
            '["25 active jobs", "200 CV reviews/month", '
            '"50 AI interviews/month", "5 team seats", '
            '"AI Talent Scout", "Ghost Formatter", '
            '"Bulk campaign management", "Analytics dashboard", '
            '"Priority support"]'
        ),
        "job_limit": 25,
        "cv_limit": 200,
        "ai_interview_limit": 50,
        "team_seat_limit": 5,
        "credits_monthly": 250,
        "plan_group": "standard",
        "is_featured": True,
    },
    {
        "name": "Recruiter Enterprise",
        "slug": "recruiter-enterprise",
        "target_audience": "recruiter",
        "price_monthly": 499.0,
        "price_yearly": 4790.0,
        "features": (
            '["Unlimited jobs", "Unlimited CV reviews", '
            '"Unlimited AI interviews", "Unlimited team seats", '
            '"Custom SMTP integration", "White-label branding", '
            '"Dedicated account manager", "SLA guarantee"]'
        ),
        "job_limit": -1,
        "cv_limit": -1,
        "ai_interview_limit": -1,
        "team_seat_limit": -1,
        "credits_monthly": 1000,
        "plan_group": "enterprise",
        "is_featured": False,
    },
]


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    cols = {c["name"] for c in inspector.get_columns("subscription_plans")}
    if "credits_monthly" not in cols:
        op.add_column(
            "subscription_plans",
            sa.Column("credits_monthly", sa.Integer(), nullable=False, server_default="0"),
        )
    if "plan_group" not in cols:
        op.add_column(
            "subscription_plans",
            sa.Column("plan_group", sa.String(length=20), nullable=False, server_default="standard"),
        )

    if not inspector.has_table("plan_versions"):
        op.create_table(
            "plan_versions",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("plan_id", sa.Integer(), nullable=False),
            sa.Column("version", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(length=255), nullable=False),
            sa.Column("slug", sa.String(length=255), nullable=False),
            sa.Column("price_monthly", sa.Float(), nullable=True),
            sa.Column("price_yearly", sa.Float(), nullable=True),
            sa.Column("currency", sa.String(length=10), nullable=True),
            sa.Column("job_limit", sa.Integer(), nullable=True),
            sa.Column("cv_limit", sa.Integer(), nullable=True),
            sa.Column("ai_interview_limit", sa.Integer(), nullable=True),
            sa.Column("team_seat_limit", sa.Integer(), nullable=True),
            sa.Column("credits_monthly", sa.Integer(), nullable=True),
            sa.Column("candidate_cv_uploads_limit", sa.Integer(), nullable=True),
            sa.Column("candidate_ai_analyses_limit", sa.Integer(), nullable=True),
            sa.Column("candidate_pdf_downloads_limit", sa.Integer(), nullable=True),
            sa.Column("candidate_job_matches_limit", sa.Integer(), nullable=True),
            sa.Column("features", sa.Text(), nullable=True),
            sa.Column("permissions_json", sa.Text(), nullable=True),
            sa.Column("valid_from", sa.DateTime(), nullable=True),
            sa.Column("valid_to", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["plan_id"], ["subscription_plans.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("idx_plan_versions_plan", "plan_versions", ["plan_id"])
        op.create_index(
            "idx_plan_versions_valid", "plan_versions", ["plan_id", "valid_from"]
        )

    table = sa.table(
        "subscription_plans",
        sa.column("id", sa.Integer()),
        sa.column("name", sa.String()),
        sa.column("slug", sa.String()),
        sa.column("target_audience", sa.String()),
        sa.column("price_monthly", sa.Float()),
        sa.column("price_yearly", sa.Float()),
        sa.column("currency", sa.String()),
        sa.column("features", sa.Text()),
        sa.column("permissions_json", sa.Text()),
        sa.column("is_active", sa.Boolean()),
        sa.column("is_featured", sa.Boolean()),
        sa.column("job_limit", sa.Integer()),
        sa.column("cv_limit", sa.Integer()),
        sa.column("ai_interview_limit", sa.Integer()),
        sa.column("team_seat_limit", sa.Integer()),
        sa.column("candidate_cv_uploads_limit", sa.Integer()),
        sa.column("candidate_ai_analyses_limit", sa.Integer()),
        sa.column("candidate_pdf_downloads_limit", sa.Integer()),
        sa.column("candidate_job_matches_limit", sa.Integer()),
        sa.column("credits_monthly", sa.Integer()),
        sa.column("plan_group", sa.String()),
    )

    conn = op.get_bind()
    for plan in PAID_PLANS:
        existing = conn.execute(
            sa.select(table.c.id).where(table.c.slug == plan["slug"])
        ).fetchone()
        if existing:
            continue
        conn.execute(
            table.insert().values(
                name=plan["name"],
                slug=plan["slug"],
                target_audience=plan["target_audience"],
                price_monthly=plan.get("price_monthly", 0),
                price_yearly=plan.get("price_yearly", 0),
                currency="TND",
                features=plan.get("features"),
                permissions_json="{}",
                is_active=True,
                is_featured=plan.get("is_featured", False),
                job_limit=plan.get("job_limit", 5),
                cv_limit=plan.get("cv_limit", 50),
                ai_interview_limit=plan.get("ai_interview_limit", 10),
                team_seat_limit=plan.get("team_seat_limit", 1),
                candidate_cv_uploads_limit=plan.get("candidate_cv_uploads_limit", 2),
                candidate_ai_analyses_limit=plan.get("candidate_ai_analyses_limit", 1),
                candidate_pdf_downloads_limit=plan.get("candidate_pdf_downloads_limit", 0),
                candidate_job_matches_limit=plan.get("candidate_job_matches_limit", 5),
                credits_monthly=plan.get("credits_monthly", 0),
                plan_group=plan.get("plan_group", "standard"),
            )
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if inspector.has_table("plan_versions"):
        pv_idxs = {idx["name"] for idx in inspector.get_indexes("plan_versions")}
        if "idx_plan_versions_valid" in pv_idxs:
            op.drop_index("idx_plan_versions_valid", table_name="plan_versions")
        if "idx_plan_versions_plan" in pv_idxs:
            op.drop_index("idx_plan_versions_plan", table_name="plan_versions")
        op.drop_table("plan_versions")

    cols = {c["name"] for c in inspector.get_columns("subscription_plans")}
    for col in ("plan_group", "credits_monthly"):
        if col in cols:
            op.drop_column("subscription_plans", col)
