import json
import logging
from datetime import UTC, datetime, timedelta
from typing import Dict

from sqlalchemy import extract, func, or_
from sqlalchemy.orm import Session

from backend.database import (
    Application,
    AuditLog,
    DailyPlatformReport,
    Interview,
    Job,
    SalesCampaign,
    SalesLead,
    Transaction,
    User,
)

logger = logging.getLogger(__name__)


class AdminAnalyticsService:
    """Advanced analytics and business intelligence for platform admins"""

    @staticmethod
    def get_overview_stats(db: Session) -> Dict:
        """Get high-level platform status and growth metrics"""
        try:
            # Use naive UTC for DB comparison to match created_at column
            now = datetime.now(UTC).replace(tzinfo=None)
            last_30d = now - timedelta(days=30)

            # User Growth
            total_users = db.query(User).count()
            new_users_30d = db.query(User).filter(User.created_at >= last_30d).count()

            # Split by role
            recruiters = db.query(User).filter(User.role == "recruiter").count()
            candidates = db.query(User).filter(User.role == "candidate").count()

            # Platform Activity
            total_jobs = db.query(Job).count()
            total_apps = db.query(Application).count()
            total_interviews = db.query(Interview).count()

            # Sales Autopilot Stats
            total_leads = db.query(SalesLead).count()
            active_campaigns = (
                db.query(SalesCampaign)
                .filter(SalesCampaign.status == "running")
                .count()
            )

            return {
                "users": {
                    "total": total_users,
                    "new_30d": new_users_30d,
                    "growth_rate": round(
                        (new_users_30d / (total_users - new_users_30d) * 100), 1
                    )
                    if (total_users - new_users_30d) > 0
                    else 100,
                    "by_role": {"recruiters": recruiters, "candidates": candidates},
                },
                "activity": {
                    "jobs": total_jobs,
                    "applications": total_apps,
                    "interviews": total_interviews,
                    "funnel_conversion": round((total_interviews / total_apps * 100), 1)
                    if total_apps > 0
                    else 0,
                },
                "sales_autopilot": {
                    "leads_found": total_leads,
                    "active_missions": active_campaigns,
                },
            }
        except Exception as e:
            logger.error(f"Overview stats error: {e}")
            return {}

    @staticmethod
    def get_revenue_analytics(db: Session, months: int = 6) -> Dict:
        """Analyze revenue and transaction health"""
        try:
            # Total Revenue (Paid Transactions)
            total_revenue = (
                db.query(func.sum(Transaction.amount))
                .filter(Transaction.status.in_(["paid", "Succeeded"]))
                .scalar()
                or 0.0
            )

            # Monthly Trend - Use actual calendar months to avoid duplicates or gaps
            trend = []
            current_date = datetime.now(UTC).replace(tzinfo=None)
            for i in range(months):
                # Calculate first day of the target month
                # Subtracting i months
                target_month = (current_date.month - 1 - i) % 12 + 1
                target_year = current_date.year + (current_date.month - 1 - i) // 12

                date_for_label = datetime(target_year, target_month, 1)

                monthly_rev = (
                    db.query(func.sum(Transaction.amount))
                    .filter(
                        Transaction.status.in_(["paid", "Succeeded"]),
                        extract("month", Transaction.created_at) == target_month,
                        extract("year", Transaction.created_at) == target_year,
                    )
                    .scalar()
                    or 0.0
                )

                trend.append(
                    {
                        "month": date_for_label.strftime("%b %Y"),
                        "revenue": float(monthly_rev),
                    }
                )

            # Transaction Status Breakdown
            statuses = (
                db.query(Transaction.status, func.count(Transaction.id))
                .group_by(Transaction.status)
                .all()
            )

            return {
                "total_revenue": round(total_revenue, 2),
                "monthly_trend": trend[::-1],  # Chronological
                "status_breakdown": {s: c for s, c in statuses},
            }
        except Exception as e:
            logger.error(f"Revenue analytics error: {e}")
            return {}

    @staticmethod
    def get_ai_performance(db: Session) -> Dict:
        """Get insights into AI engine performance and efficiency"""
        try:
            # We use AuditLogs to track AI activity
            ai_logs = (
                db.query(AuditLog)
                .filter(
                    or_(
                        AuditLog.action.like("%AI%"),
                        AuditLog.action.like("%ai_inference%"),
                    )
                )
                .order_by(AuditLog.timestamp.desc())
                .limit(200)
                .all()
            )

            # Analytics Data
            total_executions = 0
            total_tokens = 0
            total_cost = 0.0
            model_usage = {}

            import json

            # COST ESTIMATION (Per 1M Tokens)
            # Llama-3-70b: ~$0.70 (Groq/Blended)
            # Llama-3-8b: ~$0.10
            # Mixtral: ~$0.27
            COST_MAP = {
                "llama-3.3-70b-versatile": 0.70,
                "llama-3.1-8b-instant": 0.10,
                "mixtral-8x7b-32768": 0.27,
                "groq/compound": 0.70,
                "groq/compound-mini": 0.10,
                "openai/gpt-oss-20b": 0.10,
                "openai/gpt-oss-120b": 0.70,
                "default": 0.50,
            }

            for log in ai_logs:
                total_executions += 1
                try:
                    # Trakin logs are JSON in 'details'
                    if log.details and "{" in log.details:
                        data = json.loads(log.details)

                        # Tokens
                        tokens = data.get("tokens", {}).get("total", 0)
                        total_tokens += tokens

                        # Model
                        model = data.get("model", "unknown")
                        model_usage[model] = model_usage.get(model, 0) + 1

                        # Cost
                        rate = COST_MAP.get(model, COST_MAP["default"])
                        cost = (tokens / 1_000_000) * rate
                        total_cost += cost
                except Exception:
                    # Fallback for old logs or plain text details
                    pass

            return {
                "total_executions": total_executions,
                "total_tokens": total_tokens,
                "estimated_cost_usd": round(total_cost, 4),
                "model_usage": model_usage,
                "latest_events": [
                    {
                        "action": log.action,
                        "target": log.target_id,
                        "time": log.timestamp.strftime("%H:%M:%S"),
                        "status": "Success",  # Simplified for UI
                    }
                    for log in ai_logs[-5:]
                ],
            }
        except Exception as e:
            logger.error(f"AI performance error: {e}")
            return {}

    @staticmethod
    def get_growth_data(db: Session, days: int = 30) -> Dict:
        """Get time-series data for user and job growth"""
        try:
            data = []
            for i in range(days):
                date = datetime.now(UTC) - timedelta(days=days - 1 - i)
                date_str = date.strftime("%Y-%m-%d")

                user_count = (
                    db.query(User)
                    .filter(func.date(User.created_at) == date.date())
                    .count()
                )
                job_count = (
                    db.query(Job)
                    .filter(func.date(Job.created_at) == date.date())
                    .count()
                )

                data.append(
                    {"date": date_str, "new_users": user_count, "new_jobs": job_count}
                )
            return data
        except Exception as e:
            logger.error(f"Growth data error: {e}")
            return []

    @staticmethod
    async def generate_ai_daily_report(db: Session) -> Dict:
        """Generate and archive a strategic AI platform report"""
        try:
            from backend.ai.llm import call_groq_cascade
            from backend.ai.prompts import get_admin_platform_report_prompt

            # 1. Gather Snapshot Data
            overview = AdminAnalyticsService.get_overview_stats(db)
            revenue = AdminAnalyticsService.get_revenue_analytics(db, months=1)
            ai_perf = AdminAnalyticsService.get_ai_performance(db)

            snapshot = {
                "overview": overview,
                "revenue_30d": revenue.get("total_revenue", 0),
                "ai_executions": ai_perf.get("total_executions", 0),
                "ai_cost_est": ai_perf.get("estimated_cost_usd", 0),
            }

            # 2. Call AI
            prompt = get_admin_platform_report_prompt(json.dumps(snapshot))
            report_data = await call_groq_cascade(
                [{"role": "system", "content": prompt}], temperature=0.4
            )

            if not report_data:
                return {}

            # 3. Archive to DB
            today = datetime.now(UTC).date()
            existing = (
                db.query(DailyPlatformReport)
                .filter(DailyPlatformReport.date == today)
                .first()
            )
            if existing:
                existing.report_json = json.dumps(report_data)
            else:
                new_report = DailyPlatformReport(
                    date=today, report_json=json.dumps(report_data)
                )
                db.add(new_report)

            db.commit()
            return report_data
        except Exception as e:
            logger.error(f"Daily report generation failed: {e}")
            return {}

    @staticmethod
    def get_platform_efficiency(db: Session) -> Dict:
        """Calculate AI ROI and efficiency metrics"""
        try:
            ai_perf = AdminAnalyticsService.get_ai_performance(db)
            revenue = AdminAnalyticsService.get_revenue_analytics(db, months=1)

            total_rev = revenue.get("total_revenue", 0)
            ai_cost = ai_perf.get("estimated_cost_usd", 0)

            efficiency_ratio = 0
            if ai_cost > 0:
                efficiency_ratio = round(total_rev / ai_cost, 2)

            return {
                "ai_cost_usd": ai_cost,
                "revenue_tnd": total_rev,
                "roi_multiplier": efficiency_ratio,
                "token_usage": ai_perf.get("total_tokens", 0),
                "avg_cost_per_execution": round(
                    ai_cost / ai_perf.get("total_executions", 1), 4
                )
                if ai_perf.get("total_executions", 0) > 0
                else 0,
            }
        except Exception as e:
            logger.error(f"Efficiency metrics error: {e}")
            return {}
