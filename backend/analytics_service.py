"""
Analytics Service for Candway ATS
Provides recruitment metrics, insights, and data visualization
"""

import logging
from collections import Counter
from datetime import UTC, datetime, timedelta
from typing import Dict

from sqlalchemy import and_, case, func, or_
from sqlalchemy.orm import Session, selectinload

from backend.database import (
    Application,
    BatchJob,
    CandidateRating,
    Comment,
    EvaluationResult,
    EvaluationSession,
    Interview,
    InterviewParticipant,
    Job,
    Offer,
    Rubric,
    RubricScoringDetail,
    User,
)

logger = logging.getLogger(__name__)


class AnalyticsService:
    """Recruitment analytics and metrics service"""

    @staticmethod
    def _alive(query, model):
        if hasattr(model, "deleted_at"):
            return query.filter(model.deleted_at.is_(None))
        return query

    @staticmethod
    def get_recruiter_dashboard_metrics(
        recruiter_id: int, db: Session, days: int = 30
    ) -> Dict:
        """
        Get comprehensive metrics for recruiter dashboard

        Args:
            recruiter_id: Recruiter user ID
            db: Database session
            days: Number of days to analyze (default: 30)

        Returns:
            Dictionary with all metrics
        """
        try:
            cutoff_date = datetime.now() - timedelta(days=days)

            # Get recruiter's jobs and batch jobs (owned)
            jobs = AnalyticsService._alive(
                db.query(Job).filter(Job.recruiter_id == recruiter_id), Job
            ).all()
            job_ids = [j.id for j in jobs]
            batch_jobs = AnalyticsService._alive(
                db.query(BatchJob).filter(BatchJob.recruiter_id == recruiter_id),
                BatchJob,
            ).all()
            batch_ids = [b.id for b in batch_jobs]

            # Also get applications directly assigned to recruiter
            assigned_apps = AnalyticsService._alive(
                db.query(Application)
                .options(
                    selectinload(Application.evaluation_sessions).selectinload(
                        EvaluationSession.evaluation_result
                    )
                )
                .filter(Application.assigned_to == recruiter_id),
                Application,
            ).all()
            assigned_job_ids = set(a.job_id for a in assigned_apps if a.job_id)
            assigned_batch_ids = set(a.batch_id for a in assigned_apps if a.batch_id)

            # Combine all job/batch IDs
            all_job_ids = list(set(job_ids) | assigned_job_ids)
            all_batch_ids = list(set(batch_ids) | assigned_batch_ids)

            # Build reusable filter for recruiter-scoped applications
            def _recruiter_filter():
                return AnalyticsService._alive(
                    db.query(Application.id).filter(
                        or_(
                            Application.job_id.in_(all_job_ids)
                            if all_job_ids
                            else False,
                            Application.batch_id.in_(all_batch_ids)
                            if all_batch_ids
                            else False,
                            Application.assigned_to == recruiter_id,
                        )
                    ),
                    Application,
                )

            # --- Status counts (single SQL aggregation) ---
            status_rows = (
                _recruiter_filter()
                .with_entities(Application.status, func.count(Application.id))
                .group_by(Application.status)
                .all()
            )
            status_map = dict(status_rows)
            total_applications = sum(status_map.values())

            total_applied = (
                status_map.get("pending", 0)
                + status_map.get("active", 0)
                + status_map.get("imported", 0)
            )
            total_interviewing = (
                status_map.get("interviewing", 0)
                + status_map.get("screening", 0)
                + status_map.get("interview", 0)
            )
            total_offers = status_map.get("offer", 0)
            total_hired = status_map.get("hired", 0)
            rejected_offers = status_map.get("rejected", 0)

            total_interviews = total_interviewing
            completed_interviews = total_interviewing
            scheduled_interviews = 0
            cancelled_interviews = 0
            accepted_offers = total_hired
            pending_offers = total_offers - total_hired

            interview_rate = (
                (total_interviews / total_applied * 100) if total_applied > 0 else 0
            )
            offer_rate = (
                (total_offers / total_interviews * 100) if total_interviews > 0 else 0
            )
            acceptance_rate = (
                (accepted_offers / total_offers * 100) if total_offers > 0 else 0
            )

            # --- Recent applications (last N days) ---
            recent_applications = (
                _recruiter_filter()
                .filter(Application.created_at >= cutoff_date)
                .count()
            )

            # --- Time-to-hire (SQL aggregation) ---
            avg_time_to_hire = (
                AnalyticsService._alive(
                    db.query(
                        func.avg(func.datediff(func.now(), Application.created_at))
                    ).filter(
                        or_(
                            Application.job_id.in_(all_job_ids)
                            if all_job_ids
                            else False,
                            Application.batch_id.in_(all_batch_ids)
                            if all_batch_ids
                            else False,
                            Application.assigned_to == recruiter_id,
                        ),
                        Application.status == "hired",
                    ),
                    Application,
                ).scalar()
                or 0
            )

            # --- Score metrics (SQL aggregation with EvaluationResult join) ---
            score_base = (
                _recruiter_filter()
                .outerjoin(
                    EvaluationSession,
                    EvaluationSession.application_id == Application.id,
                )
                .outerjoin(
                    EvaluationResult,
                    EvaluationResult.evaluation_session_id == EvaluationSession.id,
                )
            )
            score_row = score_base.with_entities(
                func.avg(EvaluationResult.final_score).label("avg_score"),
                func.sum(case((EvaluationResult.final_score >= 75, 1), else_=0)).label(
                    "ai_matches"
                ),
                func.sum(case((EvaluationResult.fraud_score >= 50, 1), else_=0)).label(
                    "flagged"
                ),
                func.sum(case((EvaluationResult.cv_score >= 75, 1), else_=0)).label(
                    "cv_matches"
                ),
            ).first()
            _missing_sc = score_base.filter(EvaluationResult.id.is_(None)).count()
            if _missing_sc:
                logger.info(
                    "[ANALYTICS] %d applications in scope have no EvaluationResult "
                    "row — excluded from score aggregates",
                    _missing_sc,
                )
            avg_match_score = float(score_row[0] or 0) if score_row else 0
            ai_matches_count = int(score_row[1] or 0) if score_row else 0
            flagged_count = int(score_row[2] or 0) if score_row else 0

            # --- Weekly trend (4 SQL queries instead of iterating 10k objects 4 times) ---
            now = datetime.now()
            weekly_trend = []
            for w in range(3, -1, -1):
                week_start = now - timedelta(days=(w + 1) * 7)
                week_end = now - timedelta(days=w * 7)
                count = (
                    _recruiter_filter()
                    .filter(
                        Application.created_at >= week_start,
                        Application.created_at < week_end,
                    )
                    .count()
                )
                weekly_trend.append({"label": f"Week {4 - w}", "count": count})

            # --- Daily trend (7 SQL queries instead of iterating 10k objects 7 times) ---
            day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
            daily_trend = []
            for d in range(6, -1, -1):
                day_date = (now - timedelta(days=d)).date()
                day_start = datetime(day_date.year, day_date.month, day_date.day)
                day_end = day_start + timedelta(days=1)
                count = (
                    _recruiter_filter()
                    .filter(
                        Application.created_at >= day_start,
                        Application.created_at < day_end,
                    )
                    .count()
                )
                daily_trend.append(
                    {"label": day_names[day_date.weekday()], "count": count}
                )

            # --- Source breakdown (SQL GROUP BY) ---
            source_rows = (
                _recruiter_filter()
                .with_entities(Application.source, func.count(Application.id))
                .group_by(Application.source)
                .all()
            )
            sources_raw = {row[0] or "Direct": row[1] for row in source_rows}

            # --- Funnel (from single status_map above) ---
            funnel = {
                "applied": total_applied,
                "screening": status_map.get("screening", 0),
                "interview": status_map.get("interviewing", 0),
                "offer": total_offers,
                "hired": total_hired,
            }

            # Rubric metrics
            total_rubric_interviews = (
                db.query(EvaluationResult)
                .join(
                    EvaluationSession,
                    EvaluationResult.evaluation_session_id == EvaluationSession.id,
                )
                .join(Application, EvaluationSession.application_id == Application.id)
                .filter(
                    Application.job_id.in_(job_ids),
                    Application.deleted_at.is_(None),
                )
                .count()
            )

            avg_rubric_score = (
                db.query(func.avg(EvaluationResult.final_score))
                .join(
                    EvaluationSession,
                    EvaluationResult.evaluation_session_id == EvaluationSession.id,
                )
                .join(Application, EvaluationSession.application_id == Application.id)
                .filter(
                    Application.job_id.in_(job_ids),
                    Application.deleted_at.is_(None),
                )
                .scalar()
                or 0
            )

            return {
                "period_days": days,
                "candidate_intelligence": {
                    "avg_match_score": round(avg_match_score, 1),
                    "ai_matches_count": ai_matches_count,
                    "flagged_count": flagged_count,
                },
                "applications": {
                    "total": total_applications,
                    "recent": recent_applications,
                    "by_status": status_map,
                    "sources": sources_raw,
                },
                "interviews": {
                    "total": total_interviews,
                    "completed": completed_interviews,
                    "scheduled": scheduled_interviews,
                    "cancelled": cancelled_interviews,
                    "completion_rate": (completed_interviews / total_interviews * 100)
                    if total_interviews > 0
                    else 0,
                },
                "offers": {
                    "total": total_offers,
                    "accepted": accepted_offers,
                    "pending": pending_offers,
                    "rejected": rejected_offers,
                    "acceptance_rate": acceptance_rate,
                },
                "conversion_rates": {
                    "application_to_interview": interview_rate,
                    "interview_to_offer": offer_rate,
                    "offer_to_acceptance": acceptance_rate,
                    "overall_conversion": (accepted_offers / total_applications * 100)
                    if total_applications > 0
                    else 0,
                },
                "time_metrics": {
                    "avg_time_to_hire_days": round(float(avg_time_to_hire), 1),
                    "total_hired": total_hired,
                    "avg_time_in_pipeline": round(float(avg_time_to_hire), 1)
                    if total_hired > 0
                    else (
                        (now - min_created).days
                        if (
                            min_created := _recruiter_filter()
                            .with_entities(func.min(Application.created_at))
                            .scalar()
                        )
                        else 0
                    ),
                },
                "weekly_trend": weekly_trend,
                "daily_trend": daily_trend,
                "funnel": funnel,
                "active_jobs": len([j for j in jobs if j.is_active]),
                "rubric_interviews": total_rubric_interviews,
                "avg_rubric_score": round(avg_rubric_score, 1),
            }

        except Exception as e:
            logger.error(f"Failed to get dashboard metrics: {e}")
            return {
                "period_days": days,
                "candidate_intelligence": {
                    "avg_match_score": 0,
                    "ai_matches_count": 0,
                    "flagged_count": 0,
                },
                "applications": {"total": 0, "recent": 0, "by_status": {}},
                "interviews": {
                    "total": 0,
                    "completed": 0,
                    "scheduled": 0,
                    "cancelled": 0,
                    "completion_rate": 0,
                },
                "offers": {
                    "total": 0,
                    "accepted": 0,
                    "pending": 0,
                    "rejected": 0,
                    "acceptance_rate": 0,
                },
                "conversion_rates": {
                    "application_to_interview": 0,
                    "interview_to_offer": 0,
                    "offer_to_acceptance": 0,
                    "overall_conversion": 0,
                },
                "time_metrics": {"avg_time_to_hire_days": 0, "total_hired": 0},
                "active_jobs": 0,
            }

    @staticmethod
    def get_interview_analytics(recruiter_id: int, db: Session, days: int = 90) -> Dict:
        """Get detailed interview analytics"""
        try:
            cutoff_date = datetime.now(UTC) - timedelta(days=days)

            # Get recruiter's jobs
            jobs = AnalyticsService._alive(
                db.query(Job).filter(Job.recruiter_id == recruiter_id), Job
            ).all()
            job_ids = [job.id for job in jobs]

            # Get interviews
            interviews = (
                db.query(Interview)
                .join(Application)
                .filter(
                    and_(
                        Application.job_id.in_(job_ids),
                        Interview.created_at >= cutoff_date,
                        Application.deleted_at.is_(None),
                    )
                )
                .all()
            )

            # Group by month
            monthly_data = {}
            for interview in interviews:
                if not interview.created_at:
                    continue
                month_key = interview.created_at.strftime("%Y-%m")
                if month_key not in monthly_data:
                    monthly_data[month_key] = {
                        "total": 0,
                        "completed": 0,
                        "scheduled": 0,
                        "cancelled": 0,
                    }
                monthly_data[month_key]["total"] += 1
                if interview.status in monthly_data[month_key]:
                    monthly_data[month_key][interview.status] += 1

            # Interview types breakdown
            type_breakdown = {}
            for interview in interviews:
                type_breakdown[interview.type] = (
                    type_breakdown.get(interview.type, 0) + 1
                )

            # Success metrics
            completed = [i for i in interviews if i.status == "completed"]
            completed_app_ids = [
                i.application_id for i in completed if i.application_id
            ]
            rated_app_ids = set()
            if completed_app_ids:
                rated_rows = (
                    db.query(CandidateRating.application_id)
                    .filter(CandidateRating.application_id.in_(completed_app_ids))
                    .distinct()
                    .all()
                )
                rated_app_ids = {r[0] for r in rated_rows}
            with_ratings = [i for i in completed if i.application_id in rated_app_ids]

            # Rubric gap analysis
            summaries = AnalyticsService._alive(
                db.query(EvaluationResult)
                .join(
                    EvaluationSession,
                    EvaluationResult.evaluation_session_id == EvaluationSession.id,
                )
                .join(Application, EvaluationSession.application_id == Application.id)
                .join(Job, Application.job_id == Job.id)
                .filter(Job.recruiter_id == recruiter_id),
                Application,
            ).all()

            gap_frequency = {}
            cov_total = 0
            cov_count = 0
            for s in summaries:
                breakdown = s.score_breakdown or {}
                gaps = breakdown.get("gaps", [])
                cats = breakdown.get("category_scores", [])
                if gaps:
                    for g in gaps:
                        cat = g.get("category", "unknown")
                        gap_frequency[cat] = gap_frequency.get(cat, 0) + 1
                cats = cats or []
                if isinstance(cats, list):
                    for c in cats:
                        t_scored = (
                            c.get("skills_scored", 0) if isinstance(c, dict) else 0
                        )
                        t_total = c.get("skills_total", 0) if isinstance(c, dict) else 0
                        if t_total > 0:
                            cov_total += t_scored
                            cov_count += t_total

            avg_coverage = round((cov_total / cov_count) * 100) if cov_count > 0 else 0

            return {
                "total_interviews": len(interviews),
                "monthly_trend": monthly_data,
                "by_type": type_breakdown,
                "by_status": dict(
                    db.query(Interview.status, func.count(Interview.id))
                    .join(Application)
                    .filter(
                        and_(
                            Application.job_id.in_(job_ids),
                            Interview.created_at >= cutoff_date,
                            Application.deleted_at.is_(None),
                        )
                    )
                    .group_by(Interview.status)
                    .all()
                ),
                "success_metrics": {
                    "completed": len(completed),
                    "with_feedback": len(with_ratings),
                    "feedback_rate": (len(with_ratings) / len(completed) * 100)
                    if completed
                    else 0,
                },
                "rubric_gap_frequency": gap_frequency,
                "avg_rubric_coverage_pct": avg_coverage,
            }

        except Exception as e:
            logger.error(f"Failed to get interview analytics: {e}")
            return {
                "total_interviews": 0,
                "monthly_trend": {},
                "by_type": {},
                "by_status": {},
                "success_metrics": {
                    "completed": 0,
                    "with_feedback": 0,
                    "feedback_rate": 0,
                },
            }

    @staticmethod
    def get_offer_analytics(recruiter_id: int, db: Session, days: int = 90) -> Dict:
        """Get detailed offer analytics"""
        try:
            cutoff_date = datetime.now(UTC) - timedelta(days=days)

            # Get recruiter's apps
            job_ids = [
                j.id
                for j in AnalyticsService._alive(
                    db.query(Job).filter(Job.recruiter_id == recruiter_id), Job
                ).all()
            ]
            batch_ids = [
                b.id
                for b in AnalyticsService._alive(
                    db.query(BatchJob).filter(BatchJob.recruiter_id == recruiter_id),
                    BatchJob,
                ).all()
            ]
            app_ids = [
                r[0]
                for r in AnalyticsService._alive(
                    db.query(Application.id).filter(
                        or_(
                            Application.job_id.in_(job_ids) if job_ids else False,
                            Application.batch_id.in_(batch_ids) if batch_ids else False,
                        )
                    ),
                    Application,
                ).all()
            ]

            # Get offers
            offers = (
                db.query(Offer)
                .filter(
                    and_(
                        Offer.application_id.in_(app_ids) if app_ids else False,
                        Offer.created_at >= cutoff_date,
                    )
                )
                .all()
            )

            # Monthly trend
            monthly_data = {}
            for offer in offers:
                if not offer.created_at:
                    continue
                month_key = offer.created_at.strftime("%Y-%m")
                if month_key not in monthly_data:
                    monthly_data[month_key] = {
                        "total": 0,
                        "accepted": 0,
                        "rejected": 0,
                        "pending": 0,
                    }
                monthly_data[month_key]["total"] += 1
                if offer.status in monthly_data[month_key]:
                    monthly_data[month_key][offer.status] += 1

            # Salary statistics
            def _clean_salary(s):
                if not s:
                    return None
                try:
                    s_clean = "".join(
                        filter(lambda x: x.isdigit() or x == ".", s.replace(",", ""))
                    )
                    return float(s_clean) if s_clean else None
                except Exception:
                    return None

            salaries = [
                s for s in (_clean_salary(o.salary) for o in offers) if s is not None
            ]
            avg_salary = sum(salaries) / len(salaries) if salaries else 0
            min_salary = min(salaries) if salaries else 0
            max_salary = max(salaries) if salaries else 0

            # Response time (time from offer sent to acceptance/rejection)
            response_times = []
            for offer in offers:
                if offer.status in ["accepted", "rejected"] and offer.created_at:
                    days_to_respond = (datetime.now(UTC) - offer.created_at).days
                    response_times.append(days_to_respond)

            avg_response_time = (
                sum(response_times) / len(response_times) if response_times else 0
            )

            return {
                "total_offers": len(offers),
                "monthly_trend": monthly_data,
                "by_status": dict(
                    db.query(Offer.status, func.count(Offer.id))
                    .filter(
                        and_(
                            Offer.application_id.in_(app_ids) if app_ids else False,
                            Offer.created_at >= cutoff_date,
                        )
                    )
                    .group_by(Offer.status)
                    .all()
                ),
                "salary_stats": {
                    "average": round(avg_salary, 2),
                    "min": min_salary,
                    "max": max_salary,
                    "count": len(salaries),
                },
                "response_metrics": {
                    "avg_response_days": round(avg_response_time, 1),
                    "total_responses": len(response_times),
                },
            }

        except Exception as e:
            logger.error(f"Failed to get offer analytics: {e}")
            return {
                "total_offers": 0,
                "monthly_trend": {},
                "by_status": {},
                "salary_stats": {"average": 0, "min": 0, "max": 0, "count": 0},
                "response_metrics": {"avg_response_days": 0, "total_responses": 0},
            }

    @staticmethod
    def get_candidate_pipeline(recruiter_id: int, db: Session) -> Dict:
        """Get candidate pipeline visualization data"""
        try:
            # Get recruiter's jobs and batch jobs
            job_ids = [
                j.id
                for j in AnalyticsService._alive(
                    db.query(Job).filter(Job.recruiter_id == recruiter_id), Job
                ).all()
            ]
            batch_ids = [
                b.id
                for b in AnalyticsService._alive(
                    db.query(BatchJob).filter(BatchJob.recruiter_id == recruiter_id),
                    BatchJob,
                ).all()
            ]

            base_filter = or_(
                Application.job_id.in_(job_ids) if job_ids else False,
                Application.batch_id.in_(batch_ids) if batch_ids else False,
                Application.assigned_to == recruiter_id,
            )

            applications_query = AnalyticsService._alive(
                db.query(Application).filter(base_filter), Application
            ).subquery()

            apps_with_user = (
                db.query(
                    applications_query.c.status,
                    applications_query.c.user_id,
                )
                .filter(applications_query.c.user_id.isnot(None))
                .distinct(applications_query.c.user_id, applications_query.c.status)
                .subquery()
            )
            dedup_status_counts = dict(
                db.query(
                    apps_with_user.c.status,
                    func.count(apps_with_user.c.user_id),
                )
                .group_by(apps_with_user.c.status)
                .all()
            )
            no_user_status_counts = dict(
                db.query(
                    applications_query.c.status,
                    func.count(applications_query.c.id),
                )
                .filter(applications_query.c.user_id.is_(None))
                .group_by(applications_query.c.status)
                .all()
            )
            status_counts = {}
            for k, v in dedup_status_counts.items():
                status_counts[k] = status_counts.get(k, 0) + v
            for k, v in no_user_status_counts.items():
                status_counts[k] = status_counts.get(k, 0) + v

            total_count = sum(status_counts.values())
            hired_count = status_counts.get("hired", 0)
            offer_count = status_counts.get("offer", 0) + hired_count
            interview_count = status_counts.get("interviewing", 0) + offer_count
            screening_count = status_counts.get("screening", 0) + interview_count
            rejected_count = status_counts.get("rejected", 0)

            pipeline = {
                "applied": total_count,
                "screening": screening_count,
                "interview": interview_count,
                "offer": offer_count,
                "hired": hired_count,
                "rejected": rejected_count,
            }

            return {
                "pipeline": pipeline,
                "absolute_counts": status_counts,
                "total_candidates": total_count,
                "conversion_rate": (hired_count / total_count * 100)
                if total_count > 0
                else 0,
            }

        except Exception as e:
            logger.error(f"Failed to get candidate pipeline: {e}")
            return {
                "pipeline": {
                    "applied": 0,
                    "screening": 0,
                    "interview": 0,
                    "offer": 0,
                    "hired": 0,
                    "rejected": 0,
                },
                "total_candidates": 0,
                "conversion_rate": 0,
            }

    @staticmethod
    def get_team_performance(recruiter_id: int, db: Session, days: int = 30) -> Dict:
        """Get team collaboration metrics - includes pipeline stats by assignee"""
        try:
            cutoff_date = datetime.now(UTC) - timedelta(days=days)

            # Get recruiter's own assigned candidates
            base_candidates = AnalyticsService._alive(
                db.query(Application).filter(Application.assigned_to == recruiter_id),
                Application,
            )
            status_rows = (
                base_candidates.with_entities(
                    Application.status, func.count(Application.id)
                )
                .group_by(Application.status)
                .all()
            )
            status_counts = {s or "pending": c for s, c in status_rows}

            # Comments activity on recruiter's applications
            my_app_ids = [
                r[0] for r in base_candidates.with_entities(Application.id).all()
            ]
            comments = []
            ratings = []
            participants = []

            if my_app_ids:
                comments = (
                    db.query(Comment)
                    .filter(
                        and_(
                            Comment.application_id.in_(my_app_ids),
                            Comment.created_at >= cutoff_date,
                        )
                    )
                    .all()
                )

                ratings = (
                    db.query(CandidateRating)
                    .filter(
                        and_(
                            CandidateRating.application_id.in_(my_app_ids),
                            CandidateRating.created_at >= cutoff_date,
                        )
                    )
                    .all()
                )

                participants = (
                    db.query(InterviewParticipant)
                    .join(Interview)
                    .filter(
                        and_(
                            Interview.application_id.in_(my_app_ids),
                            Interview.created_at >= cutoff_date,
                        )
                    )
                    .all()
                )

            # Group by user - include recruiter's own stats
            user_activity = {}

            # Add recruiter's own pipeline as their activity
            recruiter_total = len(my_app_ids)
            if recruiter_total > 0:
                user_activity[recruiter_id] = {
                    "comments": 0,
                    "ratings": 0,
                    "interviews": 0,
                    "candidates": recruiter_total,
                    "pipeline": status_counts,
                }

            # Add comment activity
            for comment in comments:
                user_id = comment.user_id
                if user_id not in user_activity:
                    user_activity[user_id] = {
                        "comments": 0,
                        "ratings": 0,
                        "interviews": 0,
                        "candidates": 0,
                        "pipeline": {},
                    }
                user_activity[user_id]["comments"] += 1

            # Add rating activity
            for rating in ratings:
                user_id = rating.user_id
                if user_id not in user_activity:
                    user_activity[user_id] = {
                        "comments": 0,
                        "ratings": 0,
                        "interviews": 0,
                        "candidates": 0,
                        "pipeline": {},
                    }
                user_activity[user_id]["ratings"] += 1

            # Add interview participation
            for participant in participants:
                user_id = participant.user_id
                if user_id not in user_activity:
                    user_activity[user_id] = {
                        "comments": 0,
                        "ratings": 0,
                        "interviews": 0,
                        "candidates": 0,
                        "pipeline": {},
                    }
                user_activity[user_id]["interviews"] += 1

            # Resolve user names and calculate scores
            user_ids = list(user_activity.keys())
            users_map = {}
            if user_ids:
                users = db.query(User).filter(User.id.in_(user_ids)).all()
                users_map = {u.id: u.name or u.email.split("@")[0] for u in users}

            # Build named activity with scores
            named_activity = {}
            for user_id, activity in user_activity.items():
                # Score: comments(2) + ratings(5) + interviews(10) + candidates(3)
                activity["score"] = (
                    activity["comments"] * 2
                    + activity["ratings"] * 5
                    + activity["interviews"] * 10
                    + activity["candidates"] * 3
                )
                name = users_map.get(user_id, f"User #{user_id}")
                activity["name"] = name
                activity["total_candidates"] = activity.get("candidates", 0)
                named_activity[str(user_id)] = activity

            return {
                "total_comments": len(comments),
                "total_ratings": len(ratings),
                "total_interviews": len(participants),
                "active_team_members": len(user_activity),
                "user_activity": named_activity,
                "total_candidates": recruiter_total,
                "pipeline_breakdown": status_counts,
            }

        except Exception as e:
            logger.error(f"Failed to get team performance: {e}")
            return {
                "total_comments": 0,
                "total_ratings": 0,
                "total_interviews": 0,
                "active_team_members": 0,
                "user_activity": {},
                "total_candidates": 0,
                "pipeline_breakdown": {},
            }

    @staticmethod
    def get_rubric_analytics(recruiter_id: int, db: Session, days: int = 90) -> Dict:
        """Rubric-specific analytics: coverage, gaps, skill trends."""
        cutoff = datetime.now() - timedelta(days=days)

        job_ids = [
            j.id
            for j in AnalyticsService._alive(
                db.query(Job).filter(Job.recruiter_id == recruiter_id), Job
            ).all()
        ]
        if not job_ids:
            return {"rubric_count": 0, "average_coverage": 0, "top_gaps": []}

        # Active rubrics
        rubric_count = (
            db.query(Rubric)
            .filter(Rubric.job_id.in_(job_ids), Rubric.is_active)
            .count()
        )

        # Skill coverage across all interviews
        summaries = (
            db.query(EvaluationResult)
            .join(
                EvaluationSession,
                EvaluationResult.evaluation_session_id == EvaluationSession.id,
            )
            .join(Application, EvaluationSession.application_id == Application.id)
            .filter(
                Application.job_id.in_(job_ids),
                EvaluationResult.computed_at >= cutoff,
                Application.deleted_at.is_(None),
            )
            .all()
        )

        all_gaps = []
        total_scored = 0
        total_skills = 0
        for s in summaries:
            breakdown = s.score_breakdown or {}
            cats = breakdown.get("category_scores", [])
            if isinstance(cats, list):
                for c in cats:
                    ts = c.get("skills_scored", 0) if isinstance(c, dict) else 0
                    tt = c.get("skills_total", 0) if isinstance(c, dict) else 0
                    total_scored += ts
                    total_skills += tt
            gaps = breakdown.get("gaps", [])
            if gaps:
                for g in gaps:
                    all_gaps.append(g.get("category", "unknown"))

        gap_counter = Counter(all_gaps)
        top_gaps = [
            {"category": cat, "count": cnt} for cat, cnt in gap_counter.most_common(10)
        ]

        # Per-criteria gap analysis (from evaluation_criteria in rubric JSON)
        criteria_gaps = {}
        rubrics = (
            db.query(Rubric).filter(Rubric.job_id.in_(job_ids), Rubric.is_active).all()
        )
        for r in rubrics:
            raw = r.criteria_json or ""
            if isinstance(raw, str):
                import json

                rj = json.loads(raw) if raw else {}
            else:
                rj = raw or {}
            for cat in rj.get("categories", []):
                for crit in cat.get("evaluation_criteria", []):
                    if crit not in criteria_gaps:
                        criteria_gaps[crit] = {"total": 0, "passed": 0}

        for s in summaries:
            breakdown = s.score_breakdown or {}
            cats = breakdown.get("category_scores", [])
            if isinstance(cats, list) and rubrics:
                for cat_data in cats:
                    cat_name = (
                        cat_data.get("name", "") if isinstance(cat_data, dict) else ""
                    )
                    cat_score = (
                        cat_data.get("score", 0) if isinstance(cat_data, dict) else 0
                    )
                    for r in rubrics:
                        raw = r.criteria_json or ""
                        if isinstance(raw, str):
                            import json

                            rj = json.loads(raw) if raw else {}
                        else:
                            rj = raw or {}
                        for rc in rj.get("categories", []):
                            if rc["name"] == cat_name:
                                for crit in rc.get("evaluation_criteria", []):
                                    if crit in criteria_gaps:
                                        criteria_gaps[crit]["total"] += 1
                                        if cat_score >= 60:
                                            criteria_gaps[crit]["passed"] += 1

        return {
            "rubric_count": rubric_count,
            "total_interviews_with_rubric": len(summaries),
            "average_coverage": round((total_scored / total_skills) * 100, 1)
            if total_skills > 0
            else 0,
            "top_gaps": top_gaps,
            "criteria_gaps": {
                k: v
                for k, v in sorted(
                    criteria_gaps.items(),
                    key=lambda x: x[1]["passed"] / max(x[1]["total"], 1),
                )[:20]
            }
            if criteria_gaps
            else {},
        }

    @staticmethod
    def get_skill_pass_rates(
        recruiter_id: int, db: Session, days: int = 90, min_occurrences: int = 3
    ) -> Dict:
        """Per-skill pass rates from RubricScoringResult — skill-level analytics."""
        cutoff = datetime.now() - timedelta(days=days)

        job_ids = [
            j.id
            for j in AnalyticsService._alive(
                db.query(Job).filter(Job.recruiter_id == recruiter_id), Job
            ).all()
        ]
        if not job_ids:
            return {"skills": [], "total_skills_tested": 0, "total_results": 0}

        app_ids = [
            r[0]
            for r in AnalyticsService._alive(
                db.query(Application.id).filter(Application.job_id.in_(job_ids)),
                Application,
            ).all()
        ]
        if not app_ids:
            return {"skills": [], "total_skills_tested": 0, "total_results": 0}

        results = (
            db.query(RubricScoringDetail)
            .join(
                EvaluationResult,
                RubricScoringDetail.evaluation_result_id == EvaluationResult.id,
            )
            .join(
                EvaluationSession,
                EvaluationResult.evaluation_session_id == EvaluationSession.id,
            )
            .filter(
                EvaluationSession.application_id.in_(app_ids),
                EvaluationResult.computed_at >= cutoff,
            )
            .all()
        )

        skill_data = {}
        for r in results:
            name = r.criterion_name.lower().strip()
            if name not in skill_data:
                skill_data[name] = {"scores": [], "keywords": [], "evidence_count": 0}
            skill_data[name]["scores"].append(r.score)
            # RubricScoringDetail has no matched_keywords or evidence_sentences

        skills = []
        for name, data in skill_data.items():
            if len(data["scores"]) < min_occurrences:
                continue
            scores = data["scores"]
            passed = sum(1 for s in scores if s >= 60)
            skills.append(
                {
                    "skill": name,
                    "occurrences": len(scores),
                    "avg_score": round(sum(scores) / len(scores), 1),
                    "pass_rate": round((passed / len(scores)) * 100, 1),
                    "median_score": round(sorted(scores)[len(scores) // 2], 1),
                    "min_score": min(scores),
                    "max_score": max(scores),
                    "std_dev": round(
                        (
                            sum((s - (sum(scores) / len(scores))) ** 2 for s in scores)
                            / len(scores)
                        )
                        ** 0.5,
                        1,
                    )
                    if len(scores) > 1
                    else 0,
                    "evidence_avg": round(data["evidence_count"] / len(scores), 1),
                    "top_keywords": sorted(
                        [
                            (kw, data["keywords"].count(kw))
                            for kw in set(data["keywords"])
                        ],
                        key=lambda x: -x[1],
                    )[:10]
                    if data["keywords"]
                    else [],
                }
            )

        skills.sort(key=lambda x: -x["occurrences"])

        return {
            "skills": skills,
            "total_skills_tested": len(skills),
            "total_results": len(results),
            "lowest_pass_rates": sorted(skills, key=lambda x: x["pass_rate"])[:5],
            "highest_pass_rates": sorted(skills, key=lambda x: -x["pass_rate"])[:5],
        }

    @staticmethod
    def get_keyword_efficacy(
        recruiter_id: int, db: Session, days: int = 90, min_occurrences: int = 3
    ) -> Dict:
        """Analyse which keywords correlate with high vs low rubric scores."""
        cutoff = datetime.now() - timedelta(days=days)

        job_ids = [
            j.id
            for j in AnalyticsService._alive(
                db.query(Job).filter(Job.recruiter_id == recruiter_id), Job
            ).all()
        ]
        if not job_ids:
            return {"keywords": [], "total_keywords_tested": 0}

        app_ids = [
            r[0]
            for r in AnalyticsService._alive(
                db.query(Application.id).filter(Application.job_id.in_(job_ids)),
                Application,
            ).all()
        ]
        if not app_ids:
            return {"keywords": [], "total_keywords_tested": 0}

        results = (
            db.query(RubricScoringDetail)
            .join(
                EvaluationResult,
                RubricScoringDetail.evaluation_result_id == EvaluationResult.id,
            )
            .join(
                EvaluationSession,
                EvaluationResult.evaluation_session_id == EvaluationSession.id,
            )
            .filter(
                EvaluationSession.application_id.in_(app_ids),
                EvaluationResult.computed_at >= cutoff,
            )
            .all()
        )

        keyword_map = {}
        total_high = 0
        total_low = 0
        for r in results:
            # RubricScoringDetail has no matched_keywords; use criterion_name as proxy
            kw_norm = r.criterion_name.lower().strip() if r.criterion_name else ""
            if not kw_norm:
                continue
            is_high = r.score >= 60
            if is_high:
                total_high += 1
            else:
                total_low += 1
            if kw_norm not in keyword_map:
                keyword_map[kw_norm] = {
                    "occurrences": 0,
                    "high_scores": 0,
                    "low_scores": 0,
                    "scores": [],
                }
            keyword_map[kw_norm]["occurrences"] += 1
            keyword_map[kw_norm]["scores"].append(r.score)
            if is_high:
                keyword_map[kw_norm]["high_scores"] += 1
            else:
                keyword_map[kw_norm]["low_scores"] += 1

        keywords = []
        for kw, data in keyword_map.items():
            if data["occurrences"] < min_occurrences:
                continue
            scores = data["scores"]
            keywords.append(
                {
                    "keyword": kw,
                    "occurrences": data["occurrences"],
                    "avg_score": round(sum(scores) / len(scores), 1),
                    "high_ratio": round(
                        (data["high_scores"] / data["occurrences"]) * 100, 1
                    ),
                    "low_ratio": round(
                        (data["low_scores"] / data["occurrences"]) * 100, 1
                    ),
                    "lift": round(
                        (
                            (data["high_scores"] / data["occurrences"])
                            - (total_high / max(total_high + total_low, 1))
                        )
                        * 100,
                        1,
                    ),
                }
            )

        keywords.sort(key=lambda x: -x["occurrences"])

        return {
            "keywords": keywords,
            "total_keywords_tested": len(keywords),
            "total_results_with_keywords": total_high + total_low,
            "baseline_high_pct": round(
                (total_high / max(total_high + total_low, 1)) * 100, 1
            ),
            "most_effective": sorted(keywords, key=lambda x: -x["lift"])[:10],
            "least_effective": sorted(keywords, key=lambda x: x["lift"])[:10],
        }

    @staticmethod
    def get_category_weight_sensitivity(
        recruiter_id: int, db: Session, days: int = 90
    ) -> Dict:
        """Analyse how category weight changes would affect final rubric scores."""
        cutoff = datetime.now() - timedelta(days=days)

        job_ids = [
            j.id
            for j in AnalyticsService._alive(
                db.query(Job).filter(Job.recruiter_id == recruiter_id), Job
            ).all()
        ]
        if not job_ids:
            return {"rubrics": [], "total_rubrics_analyzed": 0}

        rubrics = (
            db.query(Rubric).filter(Rubric.job_id.in_(job_ids), Rubric.is_active).all()
        )

        rubric_analyses = []
        for rubric in rubrics:
            raw = rubric.criteria_json or ""
            if isinstance(raw, str):
                import json

                rj = json.loads(raw) if raw else {}
            else:
                rj = raw or {}

            categories = rj.get("categories", [])
            if not categories:
                continue

            current_weights = {c["name"]: c.get("weight", 1.0) for c in categories}
            total_weight = sum(current_weights.values())

            summaries = (
                db.query(EvaluationResult)
                .filter(
                    EvaluationResult.rubric_id == rubric.id,
                    EvaluationResult.computed_at >= cutoff,
                )
                .all()
            )

            cat_scores_agg = {}
            for s in summaries:
                breakdown = s.score_breakdown or {}
                cats = breakdown.get("category_scores", [])
                if isinstance(cats, list):
                    for c in cats:
                        name = c.get("name", "") if isinstance(c, dict) else ""
                        score = c.get("score", 0) if isinstance(c, dict) else 0
                        if name not in cat_scores_agg:
                            cat_scores_agg[name] = []
                        cat_scores_agg[name].append(score)

            if not cat_scores_agg:
                continue

            # Equal-weight simulation
            equal_weight = 1.0 / len(categories) if categories else 0

            # Uniform weights
            eq_scores = []
            cur_scores = []
            for s in summaries:
                breakdown = s.score_breakdown or {}
                cats = breakdown.get("category_scores", [])
                if isinstance(cats, list):
                    eq_total = 0
                    cur_total = 0
                    for c in cats:
                        name = c.get("name", "") if isinstance(c, dict) else ""
                        score = c.get("score", 0) if isinstance(c, dict) else 0
                        cur_w = current_weights.get(name, 1.0)
                        cur_total += score * cur_w
                        eq_total += score * equal_weight
                    if cur_total > 0:
                        cur_scores.append(
                            round(cur_total / total_weight) if total_weight > 0 else 0
                        )
                        eq_scores.append(round(eq_total))

            avg_current = (
                round(sum(cur_scores) / len(cur_scores), 1) if cur_scores else 0
            )
            avg_equal = round(sum(eq_scores) / len(eq_scores), 1) if eq_scores else 0

            rubric_analyses.append(
                {
                    "rubric_id": rubric.id,
                    "job_title": rubric.job.title if rubric.job else "Unknown",
                    "categories": [
                        {
                            "name": name,
                            "weight": weight,
                            "weight_pct": round((weight / total_weight) * 100, 1),
                            "avg_score": round(
                                sum(cat_scores_agg.get(name, [0]))
                                / max(len(cat_scores_agg.get(name, [0])), 1),
                                1,
                            ),
                            "sample_size": len(cat_scores_agg.get(name, [])),
                        }
                        for name, weight in current_weights.items()
                    ],
                    "current_avg_score": avg_current,
                    "equal_weight_avg_score": avg_equal,
                    "score_delta": round(avg_equal - avg_current, 1),
                    "sample_size": len(cur_scores),
                    "recommendation": (
                        "Weights are well-balanced"
                        if abs(avg_equal - avg_current) < 3
                        else "Equal weighting would significantly change scores — review category weights"
                    ),
                }
            )

        rubric_analyses.sort(key=lambda x: -x["sample_size"])

        return {
            "rubrics": rubric_analyses,
            "total_rubrics_analyzed": len(rubric_analyses),
        }
