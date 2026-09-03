"""Single source of truth for ALL metric computation.

RULES:
1. Every function is self-contained — never calls another metric function
2. Every aggregation is SQL-level — no in-memory len()/set()/Counter()
3. Every function accepts company_id — tenant isolation is mandatory
4. Every function returns a typed dataclass or primitive
"""

from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, case, func, or_
from sqlalchemy.orm import Session

from backend.database import (
    Application,
    ApplicationStageHistory,
    CampaignCost,
    EvaluationResult,
    EvaluationSession,
    Interview,
    Job,
    Rubric,
    RubricScoringDetail,
    User,
)
from backend.profile_helpers import get_user_name
from backend.repository._query_builders import (
    base_application_query,
    base_interview_query,
    base_job_query,
    evaluation_join,
)
from backend.repository._schemas import (
    CampaignStats,
    ConversionRates,
    DashboardMetrics,
    FunnelMetrics,
    InterviewMetrics,
)


class MetricsRepository:
    def __init__(self, db: Session):
        self.db = db

    # ── Application Counts ──────────────────────────────

    def get_total_applications(self, company_id: int, recruiter_id: int = None) -> int:
        q = base_application_query(self.db, company_id, recruiter_id)
        return q.with_entities(func.count(Application.id)).scalar() or 0

    def get_status_counts(
        self, company_id: int, recruiter_id: int = None
    ) -> dict[str, int]:
        q = base_application_query(self.db, company_id, recruiter_id)
        rows = (
            q.with_entities(Application.status, func.count(Application.id))
            .group_by(Application.status)
            .all()
        )
        return {row.status: row[1] for row in rows}

    def get_hired_count(self, company_id: int, recruiter_id: int = None) -> int:
        q = base_application_query(self.db, company_id, recruiter_id)
        return (
            q.filter(Application.status == "hired")
            .with_entities(func.count(Application.id))
            .scalar()
            or 0
        )

    def get_new_this_week(self, company_id: int, recruiter_id: int = None) -> int:
        cutoff = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=7)
        q = base_application_query(self.db, company_id, recruiter_id)
        return (
            q.filter(Application.created_at >= cutoff)
            .with_entities(func.count(Application.id))
            .scalar()
            or 0
        )

    # ── Candidate Counts ────────────────────────────────

    def get_total_candidates(self, company_id: int, recruiter_id: int = None) -> int:
        q = base_application_query(self.db, company_id, recruiter_id)
        return (
            q.filter(Application.candidate_id.isnot(None))
            .with_entities(func.count(func.distinct(Application.candidate_id)))
            .scalar()
            or 0
        )

    # ── Funnel (NON-CUMULATIVE only) ────────────────────

    def get_funnel(self, company_id: int, recruiter_id: int = None) -> FunnelMetrics:
        q = base_application_query(self.db, company_id, recruiter_id)
        row = q.with_entities(
            func.sum(
                case(
                    (
                        Application.status.in_(
                            [
                                "applied",
                                "imported",
                                "pending",
                                "new",
                                "invited",
                                "withdrawn",
                                "archived",
                                "offer_declined",
                                "reviewed",
                            ]
                        ),
                        1,
                    ),
                    else_=0,
                )
            ).label("applied"),
            func.sum(
                case(
                    (
                        Application.status.in_(
                            ["screening", "screened", "shortlisted", "analyzed", "analyzing", "analysis_failed"]
                        ),
                        1,
                    ),
                    else_=0,
                )
            ).label("screening"),
            func.sum(
                case(
                    (
                        Application.status.in_(
                            ["interviewing", "interview", "completed", "active"]
                        ),
                        1,
                    ),
                    else_=0,
                )
            ).label("interview"),
            func.sum(
                case((Application.status.in_(["offer", "offered"]), 1), else_=0)
            ).label("offer"),
            func.sum(case((Application.status == "hired", 1), else_=0)).label("hired"),
            func.sum(
                case((Application.status.in_(["rejected", "failed"]), 1), else_=0)
            ).label("rejected"),
        ).first()
        return FunnelMetrics(
            applied=int(row.applied or 0),
            screening=int(row.screening or 0),
            interview=int(row.interview or 0),
            offer=int(row.offer or 0),
            hired=int(row.hired or 0),
            rejected=int(row.rejected or 0),
        )

    # ── Conversion Rates ────────────────────────────────

    def get_conversion_rates(
        self, company_id: int, recruiter_id: int = None
    ) -> ConversionRates:
        q = base_application_query(self.db, company_id, recruiter_id)
        row = q.with_entities(
            func.count(Application.id).label("total"),
            func.sum(
                case(
                    (
                        Application.status.in_(
                            ["interviewing", "completed", "interview"]
                        ),
                        1,
                    ),
                    else_=0,
                )
            ).label("interviewing"),
            func.sum(
                case((Application.status.in_(["offer", "offered"]), 1), else_=0)
            ).label("offered"),
            func.sum(case((Application.status == "hired", 1), else_=0)).label("hired"),
        ).first()
        total = int(row.total or 0)
        interviewing = int(row.interviewing or 0)
        offered = int(row.offered or 0)
        hired = int(row.hired or 0)
        interview_cumulative = interviewing + offered + hired
        offer_cumulative = offered + hired
        return ConversionRates(
            app_to_interview=round(interview_cumulative / total * 100, 1)
            if total
            else 0,
            interview_to_offer=round(offer_cumulative / interview_cumulative * 100, 1)
            if interview_cumulative
            else 0,
            offer_to_hired=round(hired / offer_cumulative * 100, 1)
            if offer_cumulative
            else 0,
            overall=round(hired / total * 100, 1) if total else 0,
        )

    # ── Time Metrics ────────────────────────────────────

    def get_avg_time_to_hire(
        self, company_id: int, recruiter_id: int = None
    ) -> float | None:
        q = base_application_query(self.db, company_id, recruiter_id)
        result = (
            q.filter(Application.status == "hired")
            .with_entities(
                func.avg(
                    func.datediff(
                        func.coalesce(Application.updated_at, Application.created_at),
                        Application.created_at,
                    )
                )
            )
            .scalar()
        )
        return round(float(result), 1) if result else None

    # ── Score Metrics ───────────────────────────────────

    def get_avg_score(self, company_id: int, recruiter_id: int = None) -> float | None:
        q = evaluation_join(base_application_query(self.db, company_id, recruiter_id))
        result = q.with_entities(func.avg(EvaluationResult.final_score)).scalar()
        return round(float(result), 1) if result else None

    def get_score_distribution(
        self, company_id: int, recruiter_id: int = None
    ) -> dict[str, int]:
        q = evaluation_join(base_application_query(self.db, company_id, recruiter_id))
        row = q.with_entities(
            func.sum(case((EvaluationResult.final_score < 25, 1), else_=0)).label(
                "r0_25"
            ),
            func.sum(
                case(
                    (
                        and_(
                            EvaluationResult.final_score >= 25,
                            EvaluationResult.final_score < 50,
                        ),
                        1,
                    ),
                    else_=0,
                )
            ).label("r25_50"),
            func.sum(
                case(
                    (
                        and_(
                            EvaluationResult.final_score >= 50,
                            EvaluationResult.final_score < 75,
                        ),
                        1,
                    ),
                    else_=0,
                )
            ).label("r50_75"),
            func.sum(case((EvaluationResult.final_score >= 75, 1), else_=0)).label(
                "r75_100"
            ),
        ).first()
        if row:
            return {
                "0-25": int(row[0] or 0),
                "25-50": int(row[1] or 0),
                "50-75": int(row[2] or 0),
                "75-100": int(row[3] or 0),
            }
        return {"0-25": 0, "25-50": 0, "50-75": 0, "75-100": 0}

    # ── Source Breakdown ────────────────────────────────

    def get_source_breakdown(
        self, company_id: int, recruiter_id: int = None
    ) -> dict[str, int]:
        q = base_application_query(self.db, company_id, recruiter_id)
        rows = (
            q.filter(Application.source.isnot(None))
            .with_entities(Application.source, func.count(Application.id))
            .group_by(Application.source)
            .all()
        )
        return {(row.source or "Direct"): row[1] for row in rows}

    # ── Trend Metrics ───────────────────────────────────

    def get_weekly_trend(
        self, company_id: int, weeks: int = 4, recruiter_id: int = None
    ) -> list[dict]:
        q = base_application_query(self.db, company_id, recruiter_id)
        cutoff = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=weeks * 7)
        rows = (
            q.filter(Application.created_at >= cutoff)
            .with_entities(
                func.floor(func.datediff(func.now(), Application.created_at) / 7).label(
                    "week_offset"
                ),
                func.count(Application.id).label("count"),
            )
            .group_by("week_offset")
            .order_by("week_offset")
            .all()
        )
        counts = {int(r.week_offset): int(r.count) for r in rows}
        return [{"week_offset": w, "count": counts.get(w, 0)} for w in range(weeks)]

    def get_daily_trend(
        self, company_id: int, days: int = 7, recruiter_id: int = None
    ) -> list[dict]:
        q = base_application_query(self.db, company_id, recruiter_id)
        cutoff = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=days)
        rows = (
            q.filter(Application.created_at >= cutoff)
            .with_entities(
                func.date(Application.created_at).label("day"),
                func.count(Application.id).label("count"),
            )
            .group_by(func.date(Application.created_at))
            .order_by(func.date(Application.created_at))
            .all()
        )
        counts = {str(row.day): int(row.count) for row in rows}
        today = datetime.now(UTC).replace(tzinfo=None).date()
        return [
            {
                "date": str(today - timedelta(days=d)),
                "count": counts.get(str(today - timedelta(days=d)), 0),
            }
            for d in range(days - 1, -1, -1)
        ]

    # ── Job Metrics ─────────────────────────────────────

    def get_job_metrics(self, company_id: int) -> list[dict]:
        q = base_job_query(self.db, company_id)
        rows = (
            q.outerjoin(Application, Application.job_id == Job.id)
            .with_entities(
                Job.id,
                Job.title,
                Job.is_active,
                func.count(Application.id).label("applicant_count"),
                func.sum(case((Application.status == "hired", 1), else_=0)).label(
                    "hired_count"
                ),
            )
            .group_by(Job.id)
            .all()
        )
        return [
            {
                "id": r.id,
                "title": r.title,
                "is_active": bool(r.is_active),
                "applicant_count": int(r.applicant_count),
                "hired_count": int(r.hired_count),
            }
            for r in rows
        ]

    def get_active_job_count(self, company_id: int) -> int:
        q = base_job_query(self.db, company_id)
        return q.filter(Job.is_active).count()

    # ── AI Interview Metrics ────────────────────────────

    def get_interview_metrics(
        self, company_id: int, recruiter_id: int = None
    ) -> InterviewMetrics:
        q = base_interview_query(self.db, company_id, recruiter_id)
        rows = (
            q.with_entities(Interview.status, func.count(Interview.id))
            .group_by(Interview.status)
            .all()
        )
        statuses = {s: c for s, c in rows}
        today_start = (
            datetime.now(UTC)
            .replace(hour=0, minute=0, second=0, microsecond=0)
            .replace(tzinfo=None)
        )
        today_count = q.filter(
            Interview.scheduled_time >= today_start,
            Interview.scheduled_time < today_start + timedelta(days=1),
        ).count()
        return InterviewMetrics(
            total=sum(statuses.values()),
            scheduled=statuses.get("scheduled", 0),
            completed=statuses.get("completed", 0),
            cancelled=statuses.get("cancelled", 0),
            today=today_count,
            no_show=statuses.get("no_show", 0),
        )

    def get_interview_weekly_trend(
        self, company_id: int, weeks: int = 4, recruiter_id: int = None
    ) -> list[dict]:
        q = base_interview_query(self.db, company_id, recruiter_id)
        cutoff = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=weeks * 7)
        rows = (
            q.filter(Interview.scheduled_time >= cutoff)
            .with_entities(
                func.floor(
                    func.datediff(func.now(), Interview.scheduled_time) / 7
                ).label("week_offset"),
                Interview.status,
                func.count(Interview.id).label("count"),
            )
            .group_by("week_offset", Interview.status)
            .all()
        )
        weeks_data = {}
        for r in rows:
            offset = int(r.week_offset)
            if offset not in weeks_data:
                weeks_data[offset] = {
                    "total": 0,
                    "completed": 0,
                    "no_show": 0,
                    "scheduled": 0,
                }
            cnt = int(r.count)
            weeks_data[offset]["total"] += cnt
            if r.status == "completed":
                weeks_data[offset]["completed"] += cnt
            elif r.status == "no_show":
                weeks_data[offset]["no_show"] += cnt
            elif r.status in ("scheduled", "rescheduled"):
                weeks_data[offset]["scheduled"] += cnt
        return [
            {
                "week_offset": w,
                **weeks_data.get(
                    w, {"total": 0, "completed": 0, "no_show": 0, "scheduled": 0}
                ),
            }
            for w in range(weeks)
        ]

    # ── Campaign Stats ──────────────────────────────────

    def get_campaign_stats(self, batch_id: int, company_id: int) -> CampaignStats:
        q = self.db.query(Application).filter(
            Application.batch_id == batch_id,
            Application.company_id == company_id,
        )
        total = q.count()
        avg_cv = (
            q.join(
                EvaluationSession, EvaluationSession.application_id == Application.id
            )
            .join(
                EvaluationResult,
                EvaluationResult.evaluation_session_id == EvaluationSession.id,
            )
            .with_entities(func.avg(EvaluationResult.cv_score))
            .scalar()
        )
        invited = q.filter(Application.status == "invited").count()
        interviewed = q.filter(
            Application.status.in_(["interviewing", "completed", "offer", "hired"])
        ).count()
        opened = q.filter(Application.opened_at.isnot(None)).count()
        return CampaignStats(
            total_candidates=total,
            avg_cv_score=round(float(avg_cv), 1) if avg_cv else None,
            interviewed=interviewed,
            invited=invited,
            opened=opened,
        )

    # ── Campaign List Metrics ──────────────────────────

    def get_campaign_list_metrics(
        self, company_id: int, recruiter_id: int = None
    ) -> dict[int, dict[str, int]]:
        """Returns {batch_id: {application_count, candidate_count}}."""
        q = base_application_query(self.db, company_id, recruiter_id)
        rows = (
            q.filter(Application.batch_id.isnot(None))
            .with_entities(
                Application.batch_id,
                func.count(Application.id).label("application_count"),
                func.count(func.distinct(Application.candidate_id)).label(
                    "candidate_count"
                ),
            )
            .group_by(Application.batch_id)
            .all()
        )
        return {
            row.batch_id: {
                "application_count": int(row.application_count),
                "candidate_count": int(row.candidate_count),
            }
            for row in rows
        }

    # ── Paginated Entity Queries ────────────────────────

    def get_paginated_applications(
        self,
        company_id: int,
        page: int,
        per_page: int,
        recruiter_id: int = None,
        job_id: int = None,
        batch_id: int = None,
        status: str = None,
        role_filter: str = None,
        min_score: int = None,
        search: str = None,
    ) -> tuple[list, int, int]:
        """Returns (applications, total_count, unique_candidate_count)."""
        base = base_application_query(self.db, company_id, recruiter_id)

        if job_id:
            base = base.filter(Application.job_id == job_id)
        if batch_id:
            base = base.filter(Application.batch_id == batch_id)
        if status and status != "all":
            base = base.filter(Application.status == status)
        if role_filter:
            base = base.filter(Application.declared_role.ilike(f"%{role_filter}%"))
        if min_score:
            base = evaluation_join(base).filter(
                EvaluationResult.final_score >= min_score
            )
        if search:
            term = f"%{search}%"
            base = base.filter(
                or_(
                    Application.full_name.ilike(term),
                    Application.email.ilike(term),
                )
            )

        total_count = base.with_entities(func.count(Application.id)).scalar() or 0

        unique_count = (
            base.filter(Application.candidate_id.isnot(None))
            .with_entities(func.count(func.distinct(Application.candidate_id)))
            .scalar()
            or 0
        )

        paginated_ids = (
            base.with_entities(Application.id)
            .order_by(Application.created_at.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
            .subquery()
        )

        from sqlalchemy.orm import joinedload, selectinload

        apps = (
            self.db.query(Application)
            .options(
                joinedload(Application.job),
                joinedload(Application.batch_job),
                joinedload(Application.owner),
                joinedload(Application.assignee),
                selectinload(Application.evaluation_sessions).selectinload(
                    EvaluationSession.evaluation_result
                ),
            )
            .filter(Application.id.in_(self.db.query(paginated_ids.c.id)))
            .all()
        )

        return apps, total_count, unique_count

    # ── Candidate Search Facets ─────────────────────────

    def get_search_facets(
        self, company_id: int, recruiter_id: int = None
    ) -> dict[str, dict[str, int]]:
        base = base_application_query(self.db, company_id, recruiter_id)

        status_rows = (
            base.with_entities(
                Application.status, func.count(func.distinct(Application.candidate_id))
            )
            .group_by(Application.status)
            .all()
        )
        status_counts = {row[0]: row[1] for row in status_rows}

        source_rows = (
            base.with_entities(
                Application.source, func.count(func.distinct(Application.id))
            )
            .filter(Application.source.isnot(None))
            .group_by(Application.source)
            .all()
        )
        source_counts = {(row[0] or "Direct"): row[1] for row in source_rows}

        role_rows = (
            base.with_entities(
                Application.declared_role, func.count(func.distinct(Application.id))
            )
            .filter(Application.declared_role.isnot(None))
            .group_by(Application.declared_role)
            .all()
        )
        role_counts = {row[0]: row[1] for row in role_rows}

        eq = evaluation_join(base_application_query(self.db, company_id, recruiter_id))
        score_row = eq.with_entities(
            func.sum(case((EvaluationResult.final_score < 25, 1), else_=0)).label(
                "r0_25"
            ),
            func.sum(
                case(
                    (
                        and_(
                            EvaluationResult.final_score >= 25,
                            EvaluationResult.final_score < 50,
                        ),
                        1,
                    ),
                    else_=0,
                )
            ).label("r25_50"),
            func.sum(
                case(
                    (
                        and_(
                            EvaluationResult.final_score >= 50,
                            EvaluationResult.final_score < 75,
                        ),
                        1,
                    ),
                    else_=0,
                )
            ).label("r50_75"),
            func.sum(case((EvaluationResult.final_score >= 75, 1), else_=0)).label(
                "r75_100"
            ),
        ).first()
        score_ranges = (
            {
                "0-25": int(score_row[0] or 0),
                "25-50": int(score_row[1] or 0),
                "50-75": int(score_row[2] or 0),
                "75-100": int(score_row[3] or 0),
            }
            if score_row
            else {"0-25": 0, "25-50": 0, "50-75": 0, "75-100": 0}
        )

        location_rows = (
            base.join(User, Application.user_id == User.id)
            .with_entities(User.location, func.count(func.distinct(Application.id)))
            .filter(User.location.isnot(None))
            .group_by(User.location)
            .all()
        )
        location_counts = {row[0]: row[1] for row in location_rows}

        return {
            "status": status_counts,
            "source": source_counts,
            "role": role_counts,
            "score_range": score_ranges,
            "location": location_counts,
        }

    # ── Paginated Unique Candidates ─────────────────────

    def get_paginated_candidates(
        self,
        company_id: int,
        page: int,
        per_page: int,
        recruiter_id: int = None,
        status: str = None,
        job_id: int = None,
        min_score: int = None,
        search: str = None,
    ) -> tuple[list, int]:
        base = base_application_query(self.db, company_id, recruiter_id)

        if status and status != "all":
            base = base.filter(Application.status == status)
        if job_id:
            base = base.filter(Application.job_id == job_id)
        if min_score:
            base = evaluation_join(base).filter(
                EvaluationResult.final_score >= min_score
            )
        if search:
            term = f"%{search}%"
            base = base.filter(
                or_(
                    Application.full_name.ilike(term),
                    Application.email.ilike(term),
                )
            )

        total_count = (
            base.filter(Application.candidate_id.isnot(None))
            .with_entities(func.count(func.distinct(Application.candidate_id)))
            .scalar()
            or 0
        )

        window = (
            func.row_number()
            .over(
                partition_by=Application.candidate_id,
                order_by=Application.created_at.desc(),
            )
            .label("rn")
        )

        app_id_col = Application.id.label("app_id")

        ranked = (
            base.add_columns(window, app_id_col)
            .filter(Application.candidate_id.isnot(None))
            .subquery()
        )

        paginated_ids = (
            self.db.query(ranked.c.app_id)
            .filter(ranked.c.rn == 1)
            .order_by(ranked.c.created_at.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
            .all()
        )
        paginated_ids = [r[0] for r in paginated_ids]

        from sqlalchemy.orm import joinedload, selectinload

        apps = (
            self.db.query(Application)
            .options(
                joinedload(Application.job),
                joinedload(Application.batch_job),
                joinedload(Application.owner),
                joinedload(Application.assignee),
                selectinload(Application.candidate),
                selectinload(Application.evaluation_sessions).selectinload(
                    EvaluationSession.evaluation_result
                ),
            )
            .filter(Application.id.in_(paginated_ids))
            .all()
        )

        id_order = {aid: i for i, aid in enumerate(paginated_ids)}
        apps.sort(key=lambda a: id_order.get(a.id, 0))

        return apps, total_count

    # ── Search Paginated Candidates ─────────────────────

    def search_paginated_candidates(
        self,
        company_id: int,
        page: int,
        per_page: int,
        recruiter_id: int = None,
        q: str = None,
        skills: str = None,
        min_score: float = None,
        max_score: float = None,
        status: str = None,
        role: str = None,
        location: str = None,
        source: str = None,
        has_interview: bool = None,
        sort_by: str = "overall_score",
        sort_order: str = "desc",
    ) -> tuple[list, int]:
        from backend.database import Interview

        base = evaluation_join(
            base_application_query(self.db, company_id, recruiter_id)
        )
        base = base.outerjoin(User, Application.user_id == User.id)

        if q:
            term = f"%{q}%"
            base = base.filter(
                or_(
                    Application.full_name.ilike(term),
                    Application.declared_role.ilike(term),
                    Application.detected_role.ilike(term),
                    Application.cv_text_anonymized.ilike(term),
                    User.skills.ilike(term),
                )
            )

        if skills:
            skill_list = [s.strip() for s in skills.split(",") if s.strip()]
            for skill in skill_list:
                base = base.filter(User.skills.ilike(f"%{skill}%"))

        if min_score is not None:
            base = base.filter(EvaluationResult.final_score >= min_score)
        if max_score is not None:
            base = base.filter(EvaluationResult.final_score <= max_score)

        if status:
            statuses = [s.strip() for s in status.split(",") if s.strip()]
            base = base.filter(Application.status.in_(statuses))

        if role:
            base = base.filter(
                or_(
                    Application.declared_role.ilike(f"%{role}%"),
                    Application.detected_role.ilike(f"%{role}%"),
                )
            )

        if location:
            base = base.filter(User.location.ilike(f"%{location}%"))

        if source:
            base = base.filter(Application.source == source)

        if has_interview is not None:
            subq = self.db.query(Interview.application_id).filter(
                Interview.application_id == Application.id
            )
            if has_interview:
                base = base.filter(subq.exists())
            else:
                base = base.filter(~subq.exists())

        total_count = (
            base.filter(Application.candidate_id.isnot(None))
            .with_entities(func.count(func.distinct(Application.candidate_id)))
            .scalar()
            or 0
        )

        sort_col = getattr(Application, sort_by, None)
        if sort_col is None:
            sort_col = EvaluationResult.final_score
        order_fn = sort_col.desc if sort_order == "desc" else sort_col.asc
        base = base.order_by(order_fn(), Application.created_at.desc())

        window = (
            func.row_number()
            .over(
                partition_by=Application.candidate_id,
                order_by=Application.created_at.desc(),
            )
            .label("rn")
        )

        app_id_col = Application.id.label("app_id")

        ranked = (
            base.add_columns(window, app_id_col)
            .filter(Application.candidate_id.isnot(None))
            .subquery()
        )

        paginated_ids = (
            self.db.query(ranked.c.app_id)
            .filter(ranked.c.rn == 1)
            .order_by(ranked.c.created_at.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
            .all()
        )
        paginated_ids = [r[0] for r in paginated_ids]

        from sqlalchemy.orm import joinedload, selectinload

        apps = (
            self.db.query(Application)
            .options(
                joinedload(Application.job),
                joinedload(Application.batch_job),
                joinedload(Application.owner),
                joinedload(Application.assignee),
                selectinload(Application.evaluation_sessions),
            )
            .filter(Application.id.in_(paginated_ids))
            .all()
        )

        id_order = {aid: i for i, aid in enumerate(paginated_ids)}
        apps.sort(key=lambda a: id_order.get(a.id, 0))

        return apps, total_count

    # ── Dashboard Bundle ────────────────────────────────

    def get_dashboard_metrics(
        self, company_id: int, recruiter_id: int = None
    ) -> DashboardMetrics:
        """Bundled dashboard metrics in minimal queries.

        WARNING: this function MUST return EXACTLY the same values as
        calling individual metric functions. It is a performance optimization
        that duplicates query logic.
        """
        q = base_application_query(self.db, company_id, recruiter_id)

        # Query 1: Status counts
        status_rows = (
            q.with_entities(Application.status, func.count(Application.id))
            .group_by(Application.status)
            .all()
        )
        status_counts = {s: c for s, c in status_rows}
        total_apps = sum(status_counts.values())
        hired = status_counts.get("hired", 0)

        # Query 2: Unique candidates
        candidates = (
            q.filter(Application.candidate_id.isnot(None))
            .with_entities(func.count(func.distinct(Application.candidate_id)))
            .scalar()
            or 0
        )

        # Query 3: Score aggregates
        eq = evaluation_join(base_application_query(self.db, company_id, recruiter_id))
        score_row = eq.with_entities(
            func.avg(EvaluationResult.final_score).label("avg_score"),
            func.sum(case((EvaluationResult.final_score >= 75, 1), else_=0)).label(
                "ai_matches"
            ),
            func.sum(case((EvaluationResult.fraud_score >= 50, 1), else_=0)).label(
                "flagged"
            ),
        ).first()
        avg_score = (
            round(float(score_row.avg_score), 1)
            if score_row and score_row.avg_score
            else None
        )
        ai_matches = (
            int(score_row.ai_matches) if score_row and score_row.ai_matches else 0
        )
        flagged = int(score_row.flagged) if score_row and score_row.flagged else 0

        # Query 4: Time to hire
        tth_result = (
            q.filter(Application.status == "hired")
            .with_entities(
                func.avg(
                    func.datediff(
                        func.coalesce(Application.updated_at, Application.created_at),
                        Application.created_at,
                    )
                )
            )
            .scalar()
        )
        avg_tth = round(float(tth_result), 1) if tth_result else None

        # Query 5: Source breakdown
        sources = dict(
            q.filter(Application.source.isnot(None))
            .with_entities(Application.source, func.count(Application.id))
            .group_by(Application.source)
            .all()
        )

        # Query 6: Active jobs
        active_jobs = base_job_query(self.db, company_id).filter(Job.is_active).count()

        return DashboardMetrics(
            total_applications=total_apps,
            total_candidates=candidates,
            hired=hired,
            status_counts=status_counts,
            avg_score=avg_score,
            ai_matches=ai_matches,
            flagged=flagged,
            avg_time_to_hire=avg_tth,
            sources=sources,
            active_jobs=active_jobs,
        )

    def get_recent_applications(
        self, company_id: int, recruiter_id: int = None, limit: int = 5
    ) -> list[dict]:
        q = base_application_query(self.db, company_id, recruiter_id)
        from sqlalchemy.orm import joinedload, selectinload

        apps = (
            q.options(
                joinedload(Application.owner),
                selectinload(Application.evaluation_sessions),
            )
            .order_by(Application.created_at.desc())
            .limit(limit)
            .all()
        )
        result = []
        for app in apps:
            user = app.owner
            score = 0
            try:
                es = app.evaluation_sessions
                if es and es[0] and es[0].evaluation_result:
                    er = es[0].evaluation_result
                    score = int(
                        er.final_score
                        if er.final_score and er.final_score > 0
                        else (er.cv_score or 0)
                    )
            except Exception:
                pass
            result.append(
                {
                    "id": app.id,
                    "full_name": app.full_name
                    or (get_user_name(user) if user else "Candidate"),
                    "email": app.email or "",
                    "score": score,
                    "status": app.status,
                    "created_at": app.created_at.isoformat()
                    if app.created_at
                    else None,
                }
            )
        return result

    def get_top_scored_applications(
        self,
        company_id: int,
        recruiter_id: int = None,
        limit: int = 3,
        min_score: int = 75,
    ) -> list[dict]:
        from sqlalchemy.orm import joinedload, selectinload

        ranked = (
            evaluation_join(base_application_query(self.db, company_id, recruiter_id))
            .filter(
                EvaluationResult.final_score >= min_score,
                Application.status.notin_(["hired", "rejected"]),
            )
            .with_entities(
                Application.id,
                EvaluationResult.final_score,
                func.row_number()
                .over(
                    partition_by=Application.candidate_id,
                    order_by=EvaluationResult.final_score.desc(),
                )
                .label("rn"),
            )
            .subquery()
        )

        top = (
            self.db.query(ranked.c.id)
            .filter(ranked.c.rn == 1)
            .order_by(ranked.c.final_score.desc())
            .limit(limit)
            .subquery()
        )

        apps = (
            self.db.query(Application)
            .options(
                joinedload(Application.owner),
                selectinload(Application.evaluation_sessions),
            )
            .filter(Application.id.in_(self.db.query(top.c.id)))
            .all()
        )

        result = []
        for app in apps:
            user = app.owner
            score = 0
            try:
                es = app.evaluation_sessions
                if es and es[0] and es[0].evaluation_result:
                    score = int(es[0].evaluation_result.final_score or 0)
            except Exception:
                pass
            result.append(
                {
                    "id": app.id,
                    "candidate_name": app.full_name
                    or (get_user_name(user) if user else "Top Talent"),
                    "score": score,
                    "reason": "High Potential",
                }
            )
        return result

    # ── JD Bias Analytics ────────────────────────────────

    def get_jd_bias_analytics(self, company_id: int, days: int = 30) -> dict:
        from backend.bias_detection_jd import JDBiasDetector

        cutoff = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=days)

        jobs = (
            self.db.query(Job)
            .filter(
                Job.company_id == company_id, Job.is_active, Job.created_at >= cutoff
            )
            .all()
        )

        if not jobs:
            return {
                "avg_score": None,
                "avg_grade": None,
                "total_analyzed": 0,
                "top_category": None,
                "category_breakdown": {},
                "suggestions": [],
                "jobs": [],
            }

        job_scores = []
        all_scores = []
        category_totals = {}
        all_flags = []

        for job in jobs:
            flags = JDBiasDetector.rule_based_scan(job.description or "")
            if not flags:
                continue

            llm_fallback = {
                "gender_inclusivity_score": 70,
                "age_inclusivity_score": 70,
                "requirement_fairness_score": 70,
                "confidence_balance_score": 70,
                "accessibility_score": 70,
                "overall_inclusivity_score": 70,
            }
            scores = JDBiasDetector.compute_score(flags, llm_fallback)

            job_scores.append(
                {
                    "id": job.id,
                    "title": job.title,
                    "score": scores["overall_score"],
                    "grade": scores["grade"],
                    "category": " | ".join(
                        [f"{k}: {v}" for k, v in scores["category_scores"].items()]
                    ),
                    "flag_count": len(flags),
                }
            )
            all_scores.append(scores["overall_score"])
            all_flags.extend(flags)

            for cat, val in scores["category_scores"].items():
                if cat not in category_totals:
                    category_totals[cat] = {"total": 0, "count": 0}
                category_totals[cat]["total"] += val
                category_totals[cat]["count"] += 1

        category_breakdown = {}
        for cat, data in category_totals.items():
            category_breakdown[cat] = (
                round(data["total"] / data["count"]) if data["count"] > 0 else 0
            )

        low_categories = sorted(
            [(k, v) for k, v in category_breakdown.items() if v < 70],
            key=lambda x: x[1],
        )
        suggestions = []
        suggestion_map = {
            "gender_inclusivity": "Review job descriptions for gendered language — consider using more neutral terms.",
            "age_inclusivity": "Avoid age-specific language like 'young', 'junior', or 'recent grad' that may discourage older applicants.",
            "requirement_fairness": "Review minimum requirements — unnecessary degree requirements can filter out qualified candidates.",
            "confidence_balance": "Balance confident and hedging language. Too much of either can bias who applies.",
            "accessibility": "Improve readability by using simpler language, shorter sentences, and clear section headers.",
        }
        for cat, _ in low_categories:
            if cat in suggestion_map:
                suggestions.append(suggestion_map[cat])

        avg_score = round(sum(all_scores) / len(all_scores)) if all_scores else None
        avg_grade = (
            JDBiasDetector.get_grade(avg_score) if avg_score is not None else None
        )

        cat_counts = {}
        for f in all_flags:
            c = f["category"]
            cat_counts[c] = cat_counts.get(c, 0) + 1
        top_category = max(cat_counts, key=cat_counts.get) if cat_counts else None

        return {
            "avg_score": avg_score,
            "avg_grade": avg_grade,
            "total_analyzed": len(job_scores),
            "top_category": top_category,
            "category_breakdown": category_breakdown,
            "suggestions": suggestions,
            "jobs": sorted(job_scores, key=lambda x: x["score"]),
        }

    # ── Time-in-Stage Analytics ──────────────────────────

    def get_time_in_stage_analytics(
        self, company_id: int, recruiter_id: int = None, days: int = 30
    ) -> dict:
        cutoff = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=days)

        app_ids_q = (
            base_application_query(self.db, company_id, recruiter_id)
            .with_entities(Application.id)
            .subquery()
        )

        rows = (
            self.db.query(
                ApplicationStageHistory.stage_slug,
                func.count(ApplicationStageHistory.id).label("transition_count"),
                func.avg(ApplicationStageHistory.duration_seconds).label("avg_seconds"),
                func.min(ApplicationStageHistory.duration_seconds).label("min_seconds"),
                func.max(ApplicationStageHistory.duration_seconds).label("max_seconds"),
            )
            .filter(
                ApplicationStageHistory.application_id.in_(
                    self.db.query(app_ids_q.c.id)
                ),
                ApplicationStageHistory.entered_at >= cutoff,
                ApplicationStageHistory.duration_seconds.isnot(None),
                ApplicationStageHistory.duration_seconds > 0,
            )
            .group_by(ApplicationStageHistory.stage_slug)
            .all()
        )

        total_transitions = (
            self.db.query(func.count(ApplicationStageHistory.id))
            .filter(
                ApplicationStageHistory.application_id.in_(
                    self.db.query(app_ids_q.c.id)
                ),
                ApplicationStageHistory.entered_at >= cutoff,
            )
            .scalar()
            or 0
        )

        stages = {}
        for row in rows:
            stages[row.stage_slug] = {
                "avg_duration_hours": round(float(row.avg_seconds) / 3600, 1)
                if row.avg_seconds
                else 0,
                "avg_duration_days": round(float(row.avg_seconds) / 86400, 1)
                if row.avg_seconds
                else 0,
                "min_duration_hours": round(float(row.min_seconds) / 3600, 1)
                if row.min_seconds
                else 0,
                "max_duration_hours": round(float(row.max_seconds) / 3600, 1)
                if row.max_seconds
                else 0,
                "sample_size": int(row.transition_count),
            }

        return {
            "period_days": days,
            "stages": stages,
            "total_transitions": total_transitions,
        }

    # ── Source Attribution ───────────────────────────────

    def get_source_attribution(
        self, company_id: int, recruiter_id: int = None, days: int = 90
    ) -> dict:
        cutoff = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=days)

        app_ids_q = (
            base_application_query(self.db, company_id, recruiter_id)
            .with_entities(Application.id)
            .subquery()
        )

        source_stats = (
            self.db.query(
                func.coalesce(Application.source, "Direct").label("source"),
                func.count(Application.id).label("total"),
                func.sum(func.case((Application.status == "hired", 1), else_=0)).label(
                    "hired"
                ),
            )
            .filter(
                Application.id.in_(self.db.query(app_ids_q.c.id)),
                Application.created_at >= cutoff,
            )
            .group_by(func.coalesce(Application.source, "Direct"))
            .all()
        )

        interviewed_stats = (
            self.db.query(
                func.coalesce(Application.source, "Direct").label("source"),
                func.count(func.distinct(Application.id)).label("interviewed"),
            )
            .filter(
                Application.id.in_(self.db.query(app_ids_q.c.id)),
                Application.created_at >= cutoff,
            )
            .join(EvaluationSession, EvaluationSession.application_id == Application.id)
            .filter(EvaluationSession.interview_state == "completed")
            .group_by(func.coalesce(Application.source, "Direct"))
            .all()
        )

        avg_score_rows = (
            self.db.query(
                func.coalesce(Application.source, "Direct").label("source"),
                func.avg(EvaluationResult.final_score).label("avg_score"),
            )
            .filter(
                Application.id.in_(self.db.query(app_ids_q.c.id)),
                Application.created_at >= cutoff,
                EvaluationResult.final_score.isnot(None),
                EvaluationResult.final_score > 0,
            )
            .join(EvaluationSession, EvaluationSession.application_id == Application.id)
            .join(
                EvaluationResult,
                EvaluationResult.evaluation_session_id == EvaluationSession.id,
            )
            .group_by(func.coalesce(Application.source, "Direct"))
            .all()
        )

        interviewed_map = {r.source: int(r.interviewed) for r in interviewed_stats}
        avg_score_map = {r.source: float(r.avg_score) for r in avg_score_rows}

        sources = {}
        for row in source_stats:
            source = row.source
            total = int(row.total)
            hired_val = int(row.hired)
            interviewed_val = interviewed_map.get(source, 0)
            avg_score_val = avg_score_map.get(source)

            sources[source] = {
                "total": total,
                "interviewed": interviewed_val,
                "hired": hired_val,
                "avg_score": round(avg_score_val, 1) if avg_score_val else 0,
                "conversion_rate": round(hired_val / total * 100, 1)
                if total > 0
                else 0,
            }

        total_apps = sum(s["total"] for s in sources.values())

        return {
            "period_days": days,
            "sources": sources,
            "total_applications": total_apps,
        }

    # ── Cost-per-Hire Analytics ─────────────────────────

    def get_cost_per_hire(
        self, company_id: int, recruiter_id: int = None, days: int = 90
    ) -> dict:
        cutoff = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=days)

        cost_rows = (
            self.db.query(
                CampaignCost.cost_type,
                func.sum(CampaignCost.amount).label("total"),
            )
            .filter(
                CampaignCost.company_id == company_id,
                CampaignCost.created_at >= cutoff,
            )
            .group_by(CampaignCost.cost_type)
            .all()
        )

        total_cost = sum(float(row.total) for row in cost_rows)
        cost_by_type = {row.cost_type: float(row.total) for row in cost_rows}

        app_ids_q = (
            base_application_query(self.db, company_id, recruiter_id)
            .with_entities(Application.id)
            .subquery()
        )

        hired = (
            self.db.query(func.count(Application.id))
            .filter(
                Application.id.in_(self.db.query(app_ids_q.c.id)),
                Application.status == "hired",
                Application.created_at >= cutoff,
            )
            .scalar()
            or 0
        )

        cost_per_hire = round(total_cost / hired, 2) if hired > 0 else 0

        return {
            "period_days": days,
            "total_cost": total_cost,
            "cost_by_type": cost_by_type,
            "total_hires": hired,
            "cost_per_hire": cost_per_hire,
            "currency": "TND",
        }

    # ── Rubric Deep Analytics ────────────────────────────

    def get_rubric_deep_analytics(
        self,
        company_id: int,
        recruiter_id: int = None,
        days: int = 90,
        min_occurrences: int = 3,
    ) -> dict:
        import json as _json

        cutoff = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=days)

        app_ids_q = (
            base_application_query(self.db, company_id, recruiter_id)
            .with_entities(Application.id)
            .subquery()
        )
        apps_subq = self.db.query(app_ids_q.c.id)

        # ── Skill Pass Rates (SQL GROUP BY) ──
        skill_rows = (
            self.db.query(
                func.lower(func.trim(RubricScoringDetail.criterion_name)).label(
                    "skill"
                ),
                func.count(RubricScoringDetail.id).label("occurrences"),
                func.avg(RubricScoringDetail.score).label("avg_score"),
                func.sum(
                    func.case((RubricScoringDetail.score >= 60, 1), else_=0)
                ).label("passed_count"),
                func.min(RubricScoringDetail.score).label("min_score"),
                func.max(RubricScoringDetail.score).label("max_score"),
            )
            .join(
                EvaluationResult,
                RubricScoringDetail.evaluation_result_id == EvaluationResult.id,
            )
            .join(
                EvaluationSession,
                EvaluationResult.evaluation_session_id == EvaluationSession.id,
            )
            .filter(
                EvaluationSession.application_id.in_(apps_subq),
                EvaluationResult.computed_at >= cutoff,
            )
            .group_by(func.lower(func.trim(RubricScoringDetail.criterion_name)))
            .having(func.count(RubricScoringDetail.id) >= min_occurrences)
            .all()
        )

        skills = []
        for row in skill_rows:
            skills.append(
                {
                    "skill": row.skill,
                    "occurrences": int(row.occurrences),
                    "avg_score": round(float(row.avg_score), 1) if row.avg_score else 0,
                    "pass_rate": round(
                        (int(row.passed_count) / int(row.occurrences)) * 100, 1
                    ),
                    "min_score": int(row.min_score) if row.min_score else 0,
                    "max_score": int(row.max_score) if row.max_score else 0,
                }
            )

        skills.sort(key=lambda x: -x["occurrences"])

        skill_pass_rates = {
            "skills": skills,
            "total_skills_tested": len(skills),
            "total_results": sum(s["occurrences"] for s in skills),
            "lowest_pass_rates": sorted(skills, key=lambda x: x["pass_rate"])[:5],
            "highest_pass_rates": sorted(skills, key=lambda x: -x["pass_rate"])[:5],
        }

        # ── Keyword Efficacy (SQL GROUP BY) ──
        kw_rows = (
            self.db.query(
                func.lower(func.trim(RubricScoringDetail.criterion_name)).label(
                    "keyword"
                ),
                func.count(RubricScoringDetail.id).label("occurrences"),
                func.avg(RubricScoringDetail.score).label("avg_score"),
                func.sum(
                    func.case((RubricScoringDetail.score >= 60, 1), else_=0)
                ).label("high_scores"),
                func.sum(func.case((RubricScoringDetail.score < 60, 1), else_=0)).label(
                    "low_scores"
                ),
            )
            .join(
                EvaluationResult,
                RubricScoringDetail.evaluation_result_id == EvaluationResult.id,
            )
            .join(
                EvaluationSession,
                EvaluationResult.evaluation_session_id == EvaluationSession.id,
            )
            .filter(
                EvaluationSession.application_id.in_(apps_subq),
                EvaluationResult.computed_at >= cutoff,
            )
            .group_by(func.lower(func.trim(RubricScoringDetail.criterion_name)))
            .having(func.count(RubricScoringDetail.id) >= min_occurrences)
            .all()
        )

        total_high = sum(int(row.high_scores) for row in kw_rows)
        total_low = sum(int(row.low_scores) for row in kw_rows)
        total_all = total_high + total_low

        keywords = []
        for row in kw_rows:
            occ = int(row.occurrences)
            high = int(row.high_scores)
            low = int(row.low_scores)
            keywords.append(
                {
                    "keyword": row.keyword,
                    "occurrences": occ,
                    "avg_score": round(float(row.avg_score), 1) if row.avg_score else 0,
                    "high_ratio": round((high / occ) * 100, 1),
                    "low_ratio": round((low / occ) * 100, 1),
                    "lift": round(
                        ((high / occ) - (total_high / max(total_all, 1))) * 100, 1
                    ),
                }
            )

        keywords.sort(key=lambda x: -x["occurrences"])

        keyword_efficacy = {
            "keywords": keywords,
            "total_keywords_tested": len(keywords),
            "total_results_with_keywords": total_all,
            "baseline_high_pct": round((total_high / max(total_all, 1)) * 100, 1),
            "most_effective": sorted(keywords, key=lambda x: -x["lift"])[:10],
            "least_effective": sorted(keywords, key=lambda x: x["lift"])[:10],
        }

        # ── Weight Sensitivity (Python-based, needs JSON parsing) ──
        rubrics = (
            self.db.query(Rubric)
            .join(Job, Rubric.job_id == Job.id)
            .filter(
                Job.company_id == company_id,
                Rubric.is_active,
            )
            .all()
        )

        rubric_analyses = []
        for rubric in rubrics:
            raw = rubric.criteria_json or ""
            if isinstance(raw, str):
                rj = _json.loads(raw) if raw else {}
            else:
                rj = raw or {}

            categories = rj.get("categories", [])
            if not categories:
                continue

            current_weights = {c["name"]: c.get("weight", 1.0) for c in categories}
            total_weight = sum(current_weights.values())

            summaries = (
                self.db.query(EvaluationResult)
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
                        score_val = c.get("score", 0) if isinstance(c, dict) else 0
                        if name not in cat_scores_agg:
                            cat_scores_agg[name] = []
                        cat_scores_agg[name].append(score_val)

            if not cat_scores_agg:
                continue

            equal_weight = 1.0 / len(categories) if categories else 0

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
                        score_val = c.get("score", 0) if isinstance(c, dict) else 0
                        cur_w = current_weights.get(name, 1.0)
                        cur_total += score_val * cur_w
                        eq_total += score_val * equal_weight
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

        weight_sensitivity = {
            "rubrics": rubric_analyses,
            "total_rubrics_analyzed": len(rubric_analyses),
        }

        return {
            "skill_pass_rates": skill_pass_rates,
            "keyword_efficacy": keyword_efficacy,
            "weight_sensitivity": weight_sensitivity,
        }

    # ── Applicant Counts per Job ─────────────────────────

    def get_job_applicant_counts(self, job_ids: list[int]) -> dict[int, int]:
        if not job_ids:
            return {}
        rows = (
            self.db.query(Application.job_id, func.count(Application.id))
            .filter(Application.job_id.in_(job_ids))
            .group_by(Application.job_id)
            .all()
        )
        return {row.job_id: row[1] for row in rows}

    # ── Application Count for a Job ─────────────────────

    def get_application_count_for_job(self, job_id: int, company_id: int) -> int:
        return (
            self.db.query(func.count(Application.id))
            .filter(Application.job_id == job_id, Application.company_id == company_id)
            .scalar()
        ) or 0

    # ── Rating Stats for an Application ─────────────────

    def get_rating_stats(self, application_id: int) -> dict:
        from backend.database import CandidateRating

        avg, cnt = 0, 0
        rows = (
            self.db.query(
                func.avg(CandidateRating.rating).label("average"),
                func.count(CandidateRating.id).label("count"),
            )
            .filter(CandidateRating.application_id == application_id)
            .first()
        )
        if rows:
            avg = round(float(rows.average), 1) if rows.average else 0
            cnt = rows.count or 0
        return {"average": avg, "count": cnt}
