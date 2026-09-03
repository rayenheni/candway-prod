"""Tests for the admin financial dashboard service (Monetization S8).

Covers: revenue aggregation (today/month/year/total/MRR), customers KPIs
(ARPU/churn/LTV/top payers), credits + AI cost, forecast projection and
CSV export shape.
"""

from datetime import UTC, datetime, timedelta

import pytest

from backend.admin_financial_service import AdminFinancialService
from backend.database import (
    CreditTransaction,
    CreditWallet,
    Subscription,
    Transaction,
    UsageEvent,
)
from backend.models.foundation.subscription import SubscriptionPlan


def _naive(dt):
    return dt.replace(tzinfo=None)


@pytest.fixture
def test_plan(db_session):
    plan = SubscriptionPlan(
        name="Pro Recruiter",
        slug="recruiter-pro",
        target_audience="recruiter",
        price_monthly=149.0,
        currency="TND",
        credits_monthly=250,
        plan_group="standard",
    )
    db_session.add(plan)
    db_session.commit()
    db_session.refresh(plan)
    return plan


@pytest.fixture
def seeded_transactions(db_session, test_recruiter, test_company, test_plan):
    now = _naive(datetime.now(UTC))
    txs = [
        Transaction(
            user_id=test_recruiter.id,
            company_id=test_company.id,
            amount=149.0,
            amount_ttc=149.0,
            status="succeeded",
            description="Manual Upgrade to Pro Recruiter",
            created_at=now,
        ),
        Transaction(
            user_id=test_recruiter.id,
            company_id=test_company.id,
            amount=149.0,
            amount_ttc=149.0,
            status="succeeded",
            description="Manual Upgrade to Pro Recruiter",
            created_at=now - timedelta(days=30),
        ),
        Transaction(
            user_id=test_recruiter.id,
            company_id=test_company.id,
            amount=50.0,
            amount_ttc=50.0,
            status="pending",
            description="Manual Upgrade to Starter",
            created_at=now,
        ),
        Transaction(
            user_id=test_recruiter.id,
            company_id=test_company.id,
            amount=149.0,
            amount_ttc=149.0,
            status="Failed",
            description="Manual Upgrade to Pro Recruiter",
            created_at=now,
        ),
    ]
    db_session.add_all(txs)
    db_session.commit()
    return txs


def test_revenue_aggregates_only_succeeded(
    db_session, test_recruiter, test_company, seeded_transactions
):
    rev = AdminFinancialService.get_revenue(db_session, months=6)
    # succeeded total = 149 + 149 = 298 (pending + Failed excluded)
    assert rev["total"] == 298.0
    assert rev["this_month"] == 149.0
    assert rev["today"] == 149.0
    assert rev["mrr"] == 0.0  # no active Subscription rows
    assert len(rev["by_month"]) == 6
    # credit top-up description not present → plans bucketed from descriptions
    assert any(p["plan"] == "Pro Recruiter" for p in rev["by_plan"])


def test_customers_kpis(db_session, test_recruiter, test_company, test_plan):
    now = _naive(datetime.now(UTC))
    sub = Subscription(
        company_id=test_company.id,
        user_id=test_recruiter.id,
        plan_id=test_plan.id,
        target_audience="recruiter",
        status="active",
        billing_cycle="monthly",
        current_period_start=now,
        current_period_end=now + timedelta(days=30),
    )
    db_session.add(sub)
    db_session.commit()

    customers = AdminFinancialService.get_customers(db_session)
    assert customers["total_users"] >= 1
    assert customers["subscriptions"]["active"] >= 1
    assert "arpu" in customers
    assert "monthly_churn" in customers
    assert "top_payers" in customers


def test_credits_and_ai_cost(db_session, test_recruiter, test_company):
    wallet = CreditWallet(
        company_id=test_company.id,
        user_id=test_recruiter.id,
        balance=0,
    )
    db_session.add(wallet)
    db_session.flush()
    db_session.add_all(
        [
            CreditTransaction(
                company_id=test_company.id,
                wallet_id=wallet.id,
                user_id=test_recruiter.id,
                amount=250,
                type="grant",
                idempotency_key=f"grant-{test_recruiter.id}",
                status="succeeded",
            ),
            CreditTransaction(
                company_id=test_company.id,
                wallet_id=wallet.id,
                user_id=test_recruiter.id,
                amount=-10,
                type="consume",
                resource="cv_analysis",
                idempotency_key=f"consume-{test_recruiter.id}",
                status="succeeded",
            ),
        ]
    )
    db_session.add(
        UsageEvent(
            company_id=test_company.id,
            user_id=test_recruiter.id,
            resource="cv_analysis",
            credits=10,
            cost_usd=0.003,
        )
    )
    db_session.commit()

    credits = AdminFinancialService.get_credits(db_session)
    assert credits["credits_granted"] == 250
    assert credits["credits_consumed"] == 10
    assert credits["ai_cost_usd"] > 0
    assert any(f["resource"] == "cv_analysis" for f in credits["features"])


def test_forecast_shape(db_session):
    forecast = AdminFinancialService.get_forecast(db_session, months=3)
    assert len(forecast["projected"]) == 3
    assert all("projected_revenue" in m for m in forecast["projected"])
    assert "next_12m_arr" in forecast


def test_csv_export_shape(db_session):
    csv_bytes = AdminFinancialService.export_csv(db_session, "revenue")
    text = csv_bytes.decode("utf-8-sig")
    assert "Candway Financial Export" in text
    assert "Metric" in text
    assert "Month" in text


def test_export_pdf_returns_bytes(db_session):
    pdf_bytes = AdminFinancialService.export_pdf(db_session, "overview")
    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 0
