"""Financial dashboard service (Monetization S8).

Computes all revenue / customer / credit / AI-cost / forecast KPIs for the
admin Finance dashboard. Mirrors the ``AdminAnalyticsService`` pattern but
reads from the monetization tables: ``transactions`` (succeeded), ``invoices``,
``subscriptions``, ``subscription_history``, ``credit_transactions``,
``usage_events`` and ``users``. No new infrastructure.
"""

import logging
from datetime import UTC, datetime, timedelta
from typing import Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.database import (
    CreditTransaction,
    Subscription,
    SubscriptionHistory,
    Transaction,
    UsageEvent,
    User,
)

logger = logging.getLogger(__name__)

_SUCCEEDED = "succeeded"


def _now():
    return datetime.now(UTC).replace(tzinfo=None)


def _month_key(dt: Optional[datetime]) -> str:
    if not dt:
        return "unknown"
    return dt.strftime("%Y-%m")


def _fmt_month(dt: datetime) -> str:
    return dt.strftime("%b %Y")


class AdminFinancialService:
    """Financial KPIs for the admin Finance dashboard (Part 5)."""

    # ── Revenue ──────────────────────────────────────────────────────────

    @staticmethod
    def get_revenue(db: Session, months: int = 6) -> Dict:
        """Today / month / annual revenue, MRR/ARR, MoM growth, by-plan and
        by-month breakdowns."""
        now = _now()
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        year_start = now.replace(
            month=1, day=1, hour=0, minute=0, second=0, microsecond=0
        )
        day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        prev_month_start = (month_start - timedelta(days=1)).replace(
            day=1, hour=0, minute=0, second=0, microsecond=0
        )

        succeeded = [Transaction.status == _SUCCEEDED]

        today = (
            db.query(func.coalesce(func.sum(Transaction.amount_ttc), 0.0))
            .filter(*succeeded, Transaction.created_at >= day_start)
            .scalar()
            or 0.0
        )
        this_month = (
            db.query(func.coalesce(func.sum(Transaction.amount_ttc), 0.0))
            .filter(*succeeded, Transaction.created_at >= month_start)
            .scalar()
            or 0.0
        )
        this_year = (
            db.query(func.coalesce(func.sum(Transaction.amount_ttc), 0.0))
            .filter(*succeeded, Transaction.created_at >= year_start)
            .scalar()
            or 0.0
        )
        total = (
            db.query(func.coalesce(func.sum(Transaction.amount_ttc), 0.0))
            .filter(*succeeded)
            .scalar()
            or 0.0
        )
        prev_month = (
            db.query(func.coalesce(func.sum(Transaction.amount_ttc), 0.0))
            .filter(
                *succeeded,
                Transaction.created_at >= prev_month_start,
                Transaction.created_at < month_start,
            )
            .scalar()
            or 0.0
        )

        # MRR / ARR from active subscriptions (plan price × billing cycle)
        mrr = 0.0
        active_subs = (
            db.query(Subscription)
            .filter(Subscription.status.in_(["active", "trialing"]))
            .all()
        )
        for sub in active_subs:
            price = getattr(sub.plan, "price_monthly", 0) or 0
            mrr += price
        arr = mrr * 12

        # Revenue by plan — Transaction has no plan_id column; the plan name
        # is embedded in the description ("Manual Upgrade to <plan name>",
        # "Credit top-up: N credits", ...). Group by matched plan name where
        # possible, else bucket as "Other".
        by_plan = []
        raw_plan_rows = (
            db.query(
                Transaction.description,
                func.coalesce(func.sum(Transaction.amount_ttc), 0.0),
                func.count(Transaction.id),
            )
            .filter(*succeeded)
            .group_by(Transaction.description)
            .order_by(func.sum(Transaction.amount_ttc).desc())
            .all()
        )
        plan_buckets: Dict[str, List] = {}
        for desc, rev, cnt in raw_plan_rows:
            plan_name = None
            d = desc or ""
            if "Credit top-up" in d:
                plan_name = "Credit Top-up"
            else:
                low = d.lower()
                for keyword in (
                    "upgrade to",
                    "purchase of",
                    "subscription to",
                    "pro ",
                    "premium",
                    "enterprise",
                    "starter",
                ):
                    if keyword in low:
                        # extract trailing plan name from the description
                        idx = d.lower().find(keyword)
                        tail = d[idx + len(keyword) :].strip()
                        plan_name = tail.split(".")[0].strip() or "Subscription"
                        break
                if plan_name is None:
                    plan_name = "Other"
            bucket = plan_buckets.setdefault(plan_name, {"revenue": 0.0, "count": 0})
            bucket["revenue"] += float(rev)
            bucket["count"] += int(cnt)
        by_plan = [
            {"plan": name, "revenue": round(v["revenue"], 2), "count": v["count"]}
            for name, v in sorted(
                plan_buckets.items(), key=lambda kv: kv[1]["revenue"], reverse=True
            )
        ]

        # Revenue by month
        monthly = []
        current = now
        for i in range(months):
            ym_start = current.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            ym_end = (ym_start + timedelta(days=32)).replace(
                day=1, hour=0, minute=0, second=0, microsecond=0
            )
            rev = (
                db.query(func.coalesce(func.sum(Transaction.amount_ttc), 0.0))
                .filter(
                    *succeeded,
                    Transaction.created_at >= ym_start,
                    Transaction.created_at < ym_end,
                )
                .scalar()
                or 0.0
            )
            monthly.append(
                {"month": _fmt_month(ym_start), "revenue": round(float(rev), 2)}
            )
            current = (ym_start - timedelta(days=1)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
        monthly.reverse()

        return {
            "today": round(float(today), 2),
            "this_month": round(float(this_month), 2),
            "this_year": round(float(this_year), 2),
            "total": round(float(total), 2),
            "prev_month": round(float(prev_month), 2),
            "month_over_month_growth": round(
                ((this_month - prev_month) / prev_month) * 100, 1
            )
            if prev_month > 0
            else 0.0,
            "mrr": round(mrr, 2),
            "arr": round(arr, 2),
            "by_plan": by_plan,
            "by_month": monthly,
        }

    # ── Customers ────────────────────────────────────────────────────────

    @staticmethod
    def get_customers(db: Session) -> Dict:
        """Customer counts, ARPU/ARPCompany, churn, LTV, top payers."""
        now = _now()
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        last_month_end = month_start - timedelta(seconds=1)
        last_month_start = last_month_end.replace(
            day=1, hour=0, minute=0, second=0, microsecond=0
        )

        total_users = db.query(User).count()
        recruiters = db.query(User).filter(User.role == "recruiter").count()
        candidates = db.query(User).filter(User.role == "candidate").count()
        admins = db.query(User).filter(User.role == "admin").count()

        active_subs = (
            db.query(Subscription)
            .filter(Subscription.status.in_(["active", "trialing"]))
            .count()
        )
        expired_subs = (
            db.query(Subscription).filter(Subscription.status == "expired").count()
        )
        canceled_subs = (
            db.query(Subscription).filter(Subscription.status == "canceled").count()
        )
        past_due_subs = (
            db.query(Subscription).filter(Subscription.status == "past_due").count()
        )

        pending_payments = (
            db.query(Transaction).filter(Transaction.status == "pending").count()
        )
        approved_payments = (
            db.query(Transaction).filter(Transaction.status == _SUCCEEDED).count()
        )
        rejected_payments = (
            db.query(Transaction).filter(Transaction.status == "Failed").count()
        )

        # Monthly churn: (expired+canceled during period) / active at period end
        churned_this_month = (
            db.query(Subscription)
            .filter(
                Subscription.status.in_(["expired", "canceled"]),
                Subscription.updated_at >= last_month_start,
                Subscription.updated_at <= last_month_end,
            )
            .count()
        )
        monthly_churn = (
            round((churned_this_month / active_subs) * 100, 2)
            if active_subs > 0
            else 0.0
        )

        # ARPU / ARPCompany
        revenue = AdminFinancialService.get_revenue(db, months=1)
        this_month_rev = revenue.get("this_month", 0)
        arpu = round(this_month_rev / total_users, 2) if total_users > 0 else 0.0
        arpcompany = round(this_month_rev / active_subs, 2) if active_subs > 0 else 0.0
        ltv = (
            round(arpu * (1 / monthly_churn), 2)
            if monthly_churn > 0
            else round(arpu, 2)
        )

        # Top paying companies/recruiters (succeeded transactions → users)
        top_payers = (
            db.query(
                User.id,
                User.email,
                func.coalesce(func.sum(Transaction.amount_ttc), 0.0),
                func.count(Transaction.id),
            )
            .join(Transaction, Transaction.user_id == User.id)
            .filter(Transaction.status == _SUCCEEDED)
            .group_by(User.id, User.email)
            .order_by(func.sum(Transaction.amount_ttc).desc())
            .limit(10)
            .all()
        )

        # Renewal / upgrade / downgrade rates from history
        renewal_count = (
            db.query(func.count(SubscriptionHistory.id))
            .filter(SubscriptionHistory.action == "renewed")
            .scalar()
            or 0
        )
        upgrade_count = (
            db.query(func.count(SubscriptionHistory.id))
            .filter(SubscriptionHistory.action == "upgraded")
            .scalar()
            or 0
        )
        downgrade_count = (
            db.query(func.count(SubscriptionHistory.id))
            .filter(SubscriptionHistory.action == "downgraded")
            .scalar()
            or 0
        )
        total_hist = db.query(func.count(SubscriptionHistory.id)).scalar() or 1

        return {
            "total_users": total_users,
            "recruiters": recruiters,
            "candidates": candidates,
            "admins": admins,
            "subscriptions": {
                "active": active_subs,
                "trialing": (
                    db.query(Subscription)
                    .filter(Subscription.status == "trialing")
                    .count()
                ),
                "pending": (
                    db.query(Subscription)
                    .filter(Subscription.status == "pending")
                    .count()
                ),
                "past_due": past_due_subs,
                "expired": expired_subs,
                "canceled": canceled_subs,
            },
            "payments": {
                "pending": pending_payments,
                "approved": approved_payments,
                "rejected": rejected_payments,
            },
            "monthly_churn": monthly_churn,
            "arpu": arpu,
            "arpcompany": arpcompany,
            "ltv": ltv,
            "lifecycle": {
                "renewal_count": renewal_count,
                "upgrade_count": upgrade_count,
                "downgrade_count": downgrade_count,
                "renewal_rate": round((renewal_count / total_hist) * 100, 1),
                "upgrade_rate": round((upgrade_count / total_hist) * 100, 1),
                "downgrade_rate": round((downgrade_count / total_hist) * 100, 1),
            },
            "top_payers": [
                {
                    "user_id": uid,
                    "email": email,
                    "revenue": round(float(rev), 2),
                    "transactions": cnt,
                }
                for uid, email, rev, cnt in top_payers
            ],
        }

    # ── Credits ──────────────────────────────────────────────────────────

    @staticmethod
    def get_credits(db: Session) -> Dict:
        """Credits granted/sold/consumed, balances, AI cost + gross margin."""
        granted = (
            db.query(func.coalesce(func.sum(CreditTransaction.amount), 0.0))
            .filter(
                CreditTransaction.type.in_(["grant", "purchase", "topup", "promo"]),
                CreditTransaction.status == _SUCCEEDED,
            )
            .scalar()
            or 0.0
        )
        consumed = (
            db.query(func.coalesce(func.sum(-CreditTransaction.amount), 0.0))
            .filter(
                CreditTransaction.type == "consume",
                CreditTransaction.status == _SUCCEEDED,
            )
            .scalar()
            or 0.0
        )
        total_wallets = db.query(CreditTransaction.wallet_id).distinct().count()
        active_balance = (
            db.query(func.coalesce(func.sum(CreditTransaction.amount), 0.0))
            .filter(CreditTransaction.status == _SUCCEEDED)
            .scalar()
            or 0.0
        )

        # AI cost from usage_events
        ai_cost = (
            db.query(func.coalesce(func.sum(UsageEvent.cost_usd), 0.0)).scalar() or 0.0
        )
        revenue = AdminFinancialService.get_revenue(db, months=1)
        this_month_rev = revenue.get("this_month", 0)
        ai_cost_float = float(ai_cost)
        gross_margin = (
            round((1 - (ai_cost_float / this_month_rev)) * 100, 1)
            if this_month_rev > 0
            else 0.0
        )
        ai_profit = round(this_month_rev - ai_cost_float, 2)

        # Most used / expensive / profitable features from usage_events
        feature_usage = (
            db.query(
                UsageEvent.resource,
                func.count(UsageEvent.id),
                func.coalesce(func.sum(UsageEvent.credits), 0),
                func.coalesce(func.sum(UsageEvent.cost_usd), 0.0),
            )
            .group_by(UsageEvent.resource)
            .order_by(func.count(UsageEvent.id).desc())
            .limit(15)
            .all()
        )

        # Credits consumed by resource (for the chart)
        by_resource = (
            db.query(
                CreditTransaction.resource,
                func.coalesce(func.sum(-CreditTransaction.amount), 0.0),
            )
            .filter(
                CreditTransaction.type == "consume",
                CreditTransaction.status == _SUCCEEDED,
                CreditTransaction.resource.isnot(None),
            )
            .group_by(CreditTransaction.resource)
            .order_by(func.sum(-CreditTransaction.amount).desc())
            .all()
        )

        return {
            "credits_granted": round(float(granted), 0),
            "credits_consumed": round(float(consumed), 0),
            "active_balance": round(float(active_balance), 0),
            "wallets": total_wallets,
            "ai_cost_usd": round(float(ai_cost), 4),
            "gross_margin_pct": gross_margin,
            "ai_profit_usd": round(ai_profit, 2),
            "features": [
                {
                    "resource": r,
                    "count": c,
                    "credits": cr,
                    "cost_usd": round(float(cost), 4),
                }
                for r, c, cr, cost in feature_usage
            ],
            "by_resource": [
                {"resource": r, "credits": round(float(cr), 0)} for r, cr in by_resource
            ],
        }

    # ── Forecast ─────────────────────────────────────────────────────────

    @staticmethod
    def get_forecast(db: Session, months: int = 3) -> Dict:
        """Simple linear projection of monthly revenue from the last 6 months."""
        now = _now()
        history = AdminFinancialService.get_revenue(db, months=6)
        series = history.get("by_month", [])
        values = [m["revenue"] for m in series]
        n = len(values)

        forecast = []
        if n >= 2 and max(values) > 0:
            x_mean = (n - 1) / 2
            y_mean = sum(values) / n
            num = sum((i - x_mean) * (v - y_mean) for i, v in enumerate(values))
            den = sum((i - x_mean) ** 2 for i in range(n))
            slope = num / den if den else 0.0
            intercept = y_mean - slope * x_mean

            base = datetime(now.year, now.month, 1)
            for i in range(1, months + 1):
                next_month = (base.month - 1 + i) % 12 + 1
                next_year = base.year + (base.month - 1 + i) // 12
                x = n - 1 + i
                projected = max(0.0, intercept + slope * x)
                forecast.append(
                    {
                        "month": _fmt_month(datetime(next_year, next_month, 1)),
                        "projected_revenue": round(float(projected), 2),
                    }
                )
        else:
            for i in range(1, months + 1):
                next_month = (now.month - 1 + i) % 12 + 1
                next_year = now.year + (now.month - 1 + i) // 12
                forecast.append(
                    {
                        "month": _fmt_month(datetime(next_year, next_month, 1)),
                        "projected_revenue": 0.0,
                    }
                )

        return {
            "based_on": history.get("by_month", [])[-6:],
            "projected": forecast,
            "next_12m_arr": round(
                sum(f["projected_revenue"] for f in forecast) * 12, 2
            ),
        }

    # ── Overview (single snapshot) ───────────────────────────────────────

    @staticmethod
    def get_overview(db: Session) -> Dict:
        """Composite overview: 4 stat cards + chart datasets for the dashboard."""
        revenue = AdminFinancialService.get_revenue(db, months=6)
        customers = AdminFinancialService.get_customers(db)
        credits = AdminFinancialService.get_credits(db)
        return {
            "revenue": revenue,
            "customers": customers,
            "credits": credits,
        }

    # ── Export ───────────────────────────────────────────────────────────

    @staticmethod
    def export_csv(db: Session, section: str = "revenue") -> bytes:
        """Build a UTF-8 CSV export for the requested section."""
        import csv
        import io

        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(["Candway Financial Export", section, _now().isoformat()])

        if section == "revenue":
            revenue = AdminFinancialService.get_revenue(db, months=12)
            writer.writerow([])
            writer.writerow(["Metric", "Value"])
            for k, v in revenue.items():
                if k not in ("by_plan", "by_month"):
                    writer.writerow([k, v])
            writer.writerow([])
            writer.writerow(["Month", "Revenue"])
            for m in revenue.get("by_month", []):
                writer.writerow([m["month"], m["revenue"]])
            writer.writerow([])
            writer.writerow(["Plan", "Revenue", "Transactions"])
            for p in revenue.get("by_plan", []):
                writer.writerow([p["plan"], p["revenue"], p["count"]])
        elif section == "customers":
            customers = AdminFinancialService.get_customers(db)
            writer.writerow([])
            writer.writerow(["Metric", "Value"])
            for k, v in customers.items():
                if k in ("subscriptions", "payments", "lifecycle", "top_payers"):
                    continue
                writer.writerow([k, v])
            writer.writerow([])
            writer.writerow(["Top Payer Email", "Revenue", "Transactions"])
            for p in customers.get("top_payers", []):
                writer.writerow([p["email"], p["revenue"], p["transactions"]])
        elif section == "credits":
            credits = AdminFinancialService.get_credits(db)
            writer.writerow([])
            writer.writerow(["Metric", "Value"])
            for k, v in credits.items():
                if k in ("features", "by_resource"):
                    continue
                writer.writerow([k, v])
            writer.writerow([])
            writer.writerow(["Feature", "Calls", "Credits", "Cost USD"])
            for f in credits.get("features", []):
                writer.writerow(
                    [f["resource"], f["count"], f["credits"], f["cost_usd"]]
                )
        else:
            writer.writerow(["No export available for section", section])

        return buf.getvalue().encode("utf-8-sig")

    @staticmethod
    def export_pdf(db: Session, section: str = "overview") -> bytes:
        """Render a PDF summary via the existing FPDF report helper."""
        try:
            from fpdf import FPDF
        except Exception as e:  # noqa: BLE001
            logger.error(f"fpdf unavailable: {e}")
            return b""

        overview = AdminFinancialService.get_overview(db)
        revenue = overview.get("revenue", {})
        customers = overview.get("customers", {})

        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Helvetica", "B", 16)
        pdf.cell(0, 10, "Candway Financial Summary", ln=True, align="C")
        pdf.ln(4)
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(0, 8, f"Generated: {_now().strftime('%Y-%m-%d %H:%M')}", ln=True)
        pdf.ln(4)

        pdf.set_font("Helvetica", "B", 13)
        pdf.cell(0, 10, "Revenue", ln=True)
        pdf.set_font("Helvetica", "", 11)
        for label, key in [
            ("Today", "today"),
            ("This Month", "this_month"),
            ("This Year", "this_year"),
            ("Total", "total"),
            ("MRR", "mrr"),
            ("ARR", "arr"),
        ]:
            pdf.cell(0, 8, f"{label}: {revenue.get(key, 0)} TND", ln=True)
        pdf.ln(4)

        pdf.set_font("Helvetica", "B", 13)
        pdf.cell(0, 10, "Customers", ln=True)
        pdf.set_font("Helvetica", "", 11)
        for label, key in [
            ("Total Users", "total_users"),
            ("Recruiters", "recruiters"),
            ("Candidates", "candidates"),
            ("Active Subs", "subscriptions"),
            ("Monthly Churn", "monthly_churn"),
            ("ARPU", "arpu"),
        ]:
            val = customers.get(key, 0)
            if key == "subscriptions":
                val = customers.get("subscriptions", {}).get("active", 0)
            pdf.cell(0, 8, f"{label}: {val}", ln=True)

        return bytes(pdf.output(dest="S"), "latin-1")
