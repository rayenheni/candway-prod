import logging
from collections import defaultdict
from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from backend.database import Application, EEOConsent, Job

logger = logging.getLogger(__name__)

EEO_RACE_GROUPS = [
    "American Indian/Alaskan Native",
    "Asian",
    "Black/African American",
    "Hispanic/Latino",
    "Native Hawaiian/Pacific Islander",
    "White",
    "Two or More Races",
    "Decline",
]

EEO_GENDER_GROUPS = ["Male", "Female", "Non-binary", "Decline"]

EEO_VETERAN_GROUPS = ["Protected Veteran", "Not Protected Veteran", "Decline"]

EEO_DISABILITY_GROUPS = ["Yes", "No", "Decline"]

EEO_AGE_GROUPS = [
    "Under 18",
    "18-24",
    "25-34",
    "35-44",
    "45-54",
    "55-64",
    "65+",
    "Decline",
]

PIPELINE_STAGES = ["applied", "screened", "interviewed", "offered", "hired"]

EEO1_JOB_CATEGORIES = [
    "Executive/Senior Officials",
    "First/Mid-Level Officials",
    "Professionals",
    "Technicians",
    "Sales Workers",
    "Administrative Support",
    "Craft Workers",
    "Operatives",
    "Laborers/Helpers",
    "Service Workers",
]


class EEOAnalyticsService:
    @staticmethod
    def _get_company_applications(company_id: int, filters: dict, db: Session):
        jobs = db.query(Job).filter(Job.company_id == company_id).all()
        job_ids = [j.id for j in jobs]
        query = db.query(Application).filter(
            Application.job_id.in_(job_ids) if job_ids else False
        )
        if filters.get("job_id"):
            query = query.filter(Application.job_id == filters["job_id"])
        if filters.get("date_from"):
            query = query.filter(Application.created_at >= filters["date_from"])
        if filters.get("date_to"):
            query = query.filter(Application.created_at <= filters["date_to"])
        return query.limit(10000).all()

    @staticmethod
    def _get_eeo_for_apps(app_ids: list, db: Session):
        eeo_rows = (
            db.query(EEOConsent)
            .filter(
                EEOConsent.application_id.in_(app_ids),
                EEOConsent.consent_given,
            )
            .all()
        )
        return {e.application_id: e for e in eeo_rows}

    @staticmethod
    def _get_group_field(group_by: str) -> str:
        mapping = {
            "gender": "gender",
            "race": "race_ethnicity",
            "veteran": "veteran_status",
            "disability": "disability_status",
        }
        return mapping.get(group_by, "gender")

    @staticmethod
    def _stage_from_status(status: str) -> str:
        mapping = {
            "pending": "applied",
            "active": "applied",
            "imported": "applied",
            "screening": "screened",
            "interviewing": "interviewed",
            "interview": "interviewed",
            "offer": "offered",
            "hired": "hired",
        }
        return mapping.get(status, "applied")

    @staticmethod
    def get_pipeline_diversity(
        company_id: int,
        filters: dict,
        group_by: str,
        db: Session,
    ) -> dict:
        apps = EEOAnalyticsService._get_company_applications(company_id, filters, db)
        app_ids = [a.id for a in apps]
        eeo_map = EEOAnalyticsService._get_eeo_for_apps(app_ids, db)
        group_field = EEOAnalyticsService._get_group_field(group_by)

        stage_data = {s: defaultdict(int) for s in PIPELINE_STAGES}
        all_groups = set()

        for app in apps:
            eeo = eeo_map.get(app.id)
            group_val = "No Data"
            if eeo:
                val = getattr(eeo, group_field, None)
                if val:
                    group_val = val
            stage = EEOAnalyticsService._stage_from_status(app.status)
            stage_data[stage][group_val] += 1
            all_groups.add(group_val)

        all_groups = sorted(all_groups)
        data = {}
        representation_pct = {}

        for stage in PIPELINE_STAGES:
            stage_total = sum(stage_data[stage].values())
            stage_counts = [stage_data[stage].get(g, 0) for g in all_groups]
            data[stage] = stage_counts
            representation_pct[stage] = {}
            for g in all_groups:
                count = stage_data[stage].get(g, 0)
                representation_pct[stage][g] = (
                    round((count / stage_total * 100), 1) if stage_total > 0 else 0
                )

        return {
            "stages": PIPELINE_STAGES,
            "groups": list(all_groups),
            "data": data,
            "representation_pct": representation_pct,
        }

    @staticmethod
    def get_selection_rates(
        company_id: int,
        filters: dict,
        group_by: str,
        db: Session,
    ) -> dict:
        apps = EEOAnalyticsService._get_company_applications(company_id, filters, db)
        app_ids = [a.id for a in apps]
        eeo_map = EEOAnalyticsService._get_eeo_for_apps(app_ids, db)
        group_field = EEOAnalyticsService._get_group_field(group_by)

        transitions = [
            ("applied_to_screened", "applied", "screened"),
            ("screened_to_interviewed", "screened", "interviewed"),
            ("interviewed_to_offered", "interviewed", "offered"),
            ("offered_to_hired", "offered", "hired"),
        ]

        group_counts = defaultdict(lambda: {s: 0 for s in PIPELINE_STAGES})
        all_groups = set()

        for app in apps:
            eeo = eeo_map.get(app.id)
            group_val = "No Data"
            if eeo:
                val = getattr(eeo, group_field, None)
                if val:
                    group_val = val
            stage = EEOAnalyticsService._stage_from_status(app.status)
            group_counts[group_val][stage] += 1
            all_groups.add(group_val)

        all_groups = sorted(all_groups)
        group_selection_rates = {}
        for g in all_groups:
            rates = {}
            for trans_name, from_stage, to_stage in transitions:
                from_count = group_counts[g][from_stage]
                to_count = group_counts[g][to_stage]
                rate = round((to_count / from_count * 100), 1) if from_count > 0 else 0
                rates[trans_name] = rate
            group_selection_rates[g] = rates

        adverse_impact = {}
        for trans_name, _, _ in transitions:
            rates_for_trans = {
                g: group_selection_rates[g][trans_name] for g in all_groups
            }
            ai_result = EEOAnalyticsService._compute_4_5ths_rule(
                rates_for_trans, all_groups
            )
            adverse_impact[trans_name] = ai_result

        four_fifths_text = None
        for trans_name, ai in adverse_impact.items():
            if not ai["passes_4_5ths"]:
                highest_group = ai.get("highest_group", "N/A")
                highest_rate = ai.get("highest_rate", 0)
                flagged_group = ai.get("flagged_group", "N/A")
                flagged_rate = ai.get("flagged_rate", 0)
                ratio = ai.get("ratio", 0)
                four_fifths_text = (
                    f"The selection rate of {flagged_group} candidates "
                    f"({flagged_rate}%) is less than 4/5ths (80%) of the "
                    f"highest group ({highest_group}, {highest_rate}%) "
                    f"for the '{trans_name}' transition (ratio: {ratio})."
                )
                break

        return {
            "groups": group_selection_rates,
            "adverse_impact": adverse_impact,
            "four_fifths_rule": four_fifths_text,
        }

    @staticmethod
    def _compute_4_5ths_rule(
        group_selection_rates: dict,
        group_names: list,
    ) -> dict:
        max_rate = 0
        max_group = None
        for g in group_names:
            rate = group_selection_rates.get(g, 0)
            if rate > max_rate:
                max_rate = rate
                max_group = g

        if max_rate == 0:
            return {
                "ratio": 1.0,
                "passes_4_5ths": True,
                "highest_group": None,
                "highest_rate": 0,
                "flagged_group": None,
                "flagged_rate": 0,
            }

        four_fifths_threshold = max_rate * 0.8
        flagged_groups = []
        for g in group_names:
            rate = group_selection_rates.get(g, 0)
            if rate < four_fifths_threshold:
                flagged_groups.append(g)

        if flagged_groups:
            worst = min(flagged_groups, key=lambda g: group_selection_rates.get(g, 0))
            worst_rate = group_selection_rates.get(worst, 0)
            ratio = round(worst_rate / max_rate, 2) if max_rate > 0 else 1.0
            return {
                "ratio": ratio,
                "passes_4_5ths": False,
                "highest_group": max_group,
                "highest_rate": max_rate,
                "flagged_group": worst,
                "flagged_rate": worst_rate,
            }

        return {
            "ratio": 1.0,
            "passes_4_5ths": True,
            "highest_group": max_group,
            "highest_rate": max_rate,
            "flagged_group": None,
            "flagged_rate": None,
        }

    @staticmethod
    def _get_eeo_job_category(job_title: str) -> str:
        if not job_title:
            return "Professionals"
        title_lower = job_title.lower()
        if any(
            kw in title_lower
            for kw in [
                "executive",
                "chief",
                "vp ",
                "vice president",
                "director",
                "head of",
            ]
        ):
            return "Executive/Senior Officials"
        if any(
            kw in title_lower for kw in ["manager", "lead", "supervisor", "coordinator"]
        ):
            return "First/Mid-Level Officials"
        if any(
            kw in title_lower
            for kw in [
                "engineer",
                "developer",
                "analyst",
                "designer",
                "scientist",
                "architect",
                "consultant",
            ]
        ):
            return "Professionals"
        if any(
            kw in title_lower
            for kw in ["technician", "technologist", "support engineer"]
        ):
            return "Technicians"
        if any(
            kw in title_lower
            for kw in ["sales", "account executive", "business development"]
        ):
            return "Sales Workers"
        if any(
            kw in title_lower
            for kw in ["administrative", "assistant", "clerk", "receptionist"]
        ):
            return "Administrative Support"
        if any(
            kw in title_lower for kw in ["craft", "mechanic", "electrician", "plumber"]
        ):
            return "Craft Workers"
        if any(
            kw in title_lower for kw in ["operative", "machine", "assembler", "worker"]
        ):
            return "Operatives"
        if any(kw in title_lower for kw in ["laborer", "helper", "maintenance"]):
            return "Laborers/Helpers"
        if any(
            kw in title_lower
            for kw in ["service", "hospitality", "cleaner", "security"]
        ):
            return "Service Workers"
        return "Professionals"

    @staticmethod
    def get_eeo1_report(
        company_id: int,
        year: int,
        db: Session,
    ) -> dict:
        jobs = db.query(Job).filter(Job.company_id == company_id).all()
        job_ids = [j.id for j in jobs]
        start_date = datetime(year, 1, 1)
        end_date = datetime(year + 1, 1, 1) if year < 9999 else datetime.now(UTC)

        apps = (
            db.query(Application)
            .filter(
                Application.job_id.in_(job_ids) if job_ids else False,
                Application.created_at >= start_date,
                Application.created_at < end_date,
            )
            .all()
        )

        app_ids = [a.id for a in apps]
        eeo_map = EEOAnalyticsService._get_eeo_for_apps(app_ids, db)

        job_map = {j.id: j for j in jobs}

        race_groups = [
            "Hispanic/Latino",
            "Non-Hispanic (White Only)",
            "Non-Hispanic (Black or African American Only)",
            "Non-Hispanic (Asian Only)",
            "Non-Hispanic (American Indian/Alaskan Native Only)",
            "Non-Hispanic (Native Hawaiian/Pacific Islander Only)",
            "Non-Hispanic (Two or More Races)",
            "Decline",
        ]

        matrix = {}
        for cat in EEO1_JOB_CATEGORIES:
            matrix[cat] = {}
            for race in race_groups:
                matrix[cat][race] = {
                    "male": 0,
                    "female": 0,
                    "non_binary": 0,
                    "unknown": 0,
                }
            matrix[cat]["total"] = 0

        for app in apps:
            eeo = eeo_map.get(app.id)
            if not eeo or not eeo.consent_given:
                continue
            job = job_map.get(app.job_id)
            category = EEOAnalyticsService._get_eeo_job_category(
                job.title if job else ""
            )
            gender_key = "unknown"
            if eeo.gender in ("Male",):
                gender_key = "male"
            elif eeo.gender in ("Female",):
                gender_key = "female"
            elif eeo.gender in ("Non-binary",):
                gender_key = "non_binary"

            race_val = eeo.race_ethnicity or "Decline"
            race_mapped = race_val
            if race_val not in race_groups:
                race_mapped = "Decline"

            matrix[category][race_mapped][gender_key] += 1
            matrix[category]["total"] += 1

        return {
            "year": year,
            "job_categories": EEO1_JOB_CATEGORIES,
            "race_groups": race_groups,
            "matrix": matrix,
            "generated_at": datetime.now(UTC).isoformat(),
        }

    @staticmethod
    def get_diversity_trends(
        company_id: int,
        months: int,
        db: Session,
    ) -> dict:
        end_date = datetime.now(UTC)
        start_date = end_date - timedelta(days=months * 30)

        jobs = db.query(Job).filter(Job.company_id == company_id).all()
        job_ids = [j.id for j in jobs]
        apps = (
            db.query(Application)
            .filter(
                Application.job_id.in_(job_ids) if job_ids else False,
                Application.created_at >= start_date,
            )
            .all()
        )

        app_ids = [a.id for a in apps]
        eeo_map = EEOAnalyticsService._get_eeo_for_apps(app_ids, db)

        monthly = defaultdict(lambda: defaultdict(int))
        monthly_total = defaultdict(int)

        for app in apps:
            eeo = eeo_map.get(app.id)
            if not eeo or not eeo.consent_given:
                continue
            month_key = app.created_at.strftime("%Y-%m")
            gender = eeo.gender or "Decline"
            monthly[month_key][gender] += 1
            monthly_total[month_key] += 1

        sorted_months = sorted(monthly.keys())
        all_genders = sorted(set(g for m in monthly.values() for g in m.keys()))

        trend_data = {}
        for g in all_genders:
            trend_data[g] = []

        for m in sorted_months:
            total = monthly_total[m]
            for g in all_genders:
                count = monthly[m].get(g, 0)
                pct = round((count / total * 100), 1) if total > 0 else 0
                trend_data[g].append(pct)

        return {
            "months": sorted_months,
            "groups": all_genders,
            "data": trend_data,
        }

    @staticmethod
    def get_aggregate_stats(
        company_id: int,
        db: Session,
    ) -> dict:
        jobs = db.query(Job).filter(Job.company_id == company_id).all()
        job_ids = [j.id for j in jobs]
        apps = (
            db.query(Application)
            .filter(
                Application.job_id.in_(job_ids) if job_ids else False,
            )
            .all()
        )
        app_ids = [a.id for a in apps]

        eeo_rows = (
            db.query(EEOConsent)
            .filter(
                EEOConsent.application_id.in_(app_ids),
            )
            .all()
        )
        total_apps = len(apps)
        total_eeo = sum(1 for e in eeo_rows if e.consent_given)
        coverage_rate = (
            round((total_eeo / total_apps * 100), 1) if total_apps > 0 else 0
        )

        gender_counts = defaultdict(int)
        for e in eeo_rows:
            if e.consent_given and e.gender:
                gender_counts[e.gender] += 1

        male_count = gender_counts.get("Male", 0)
        female_count = gender_counts.get("Female", 0)
        gender_balance = (
            round((female_count / male_count * 100), 1)
            if male_count > 0
            else (100 if female_count > 0 else 0)
        )

        flagged = 0
        if total_eeo >= 10:
            diversity = EEOAnalyticsService.get_pipeline_diversity(
                company_id, {}, "gender", db
            )
            for stage_data in diversity.get("data", {}).values():
                if isinstance(stage_data, dict):
                    total = sum(stage_data.values())
                    for g, c in stage_data.items():
                        if total > 0 and c > 0 and (c / total) < 0.1:
                            flagged += 1

        return {
            "coverage_rate": coverage_rate,
            "total_applicants_with_eeo": total_eeo,
            "total_applicants": total_apps,
            "gender_balance_ratio": gender_balance,
            "adverse_impact_flags": flagged,
            "gender_breakdown": dict(gender_counts),
        }

    @staticmethod
    def get_compliance_summary(
        company_id: int,
        db: Session,
    ) -> dict:
        stats = EEOAnalyticsService.get_aggregate_stats(company_id, db)
        risk_score = "low"
        flags = stats["adverse_impact_flags"]
        coverage = stats["coverage_rate"]

        if flags >= 3 or coverage < 30:
            risk_score = "high"
        elif flags >= 1 or coverage < 60:
            risk_score = "medium"

        suggestions = []
        if coverage < 60:
            suggestions.append(
                "EEO data collection rate is below 60%. Consider adding "
                "EEO form to application process and training recruiters "
                "to explain its importance to candidates."
            )
        if flags > 0:
            suggestions.append(
                f"Adverse impact detected in {flags} area(s). "
                "Review selection criteria and consider expanding "
                "sourcing channels for underrepresented groups."
            )
        if stats.get("gender_balance_ratio", 100) < 50:
            suggestions.append(
                "Gender balance ratio is below 50%. Review job "
                "descriptions for gendered language and expand "
                "outreach to diverse professional networks."
            )

        return {
            "risk_score": risk_score,
            "adverse_impact_flags": flags,
            "coverage_rate": coverage,
            "suggestions": suggestions,
        }

    @staticmethod
    def get_coverage_rate(
        company_id: int,
        db: Session,
    ) -> dict:
        return EEOAnalyticsService.get_aggregate_stats(company_id, db)

    @staticmethod
    def get_coverage_detail(
        company_id: int,
        db: Session,
    ) -> dict:
        jobs = db.query(Job).filter(Job.company_id == company_id).all()
        result = {
            "overall": EEOAnalyticsService.get_aggregate_stats(company_id, db),
            "by_job": [],
            "by_recruiter": [],
            "trend": [],
        }

        job_ids = [j.id for j in jobs]
        eeo_by_job = (
            db.query(
                Application.job_id,
                func.count(Application.id).label("total"),
                func.count(EEOConsent.id).label("eeo_count"),
            )
            .outerjoin(
                EEOConsent,
                and_(
                    EEOConsent.application_id == Application.id,
                    EEOConsent.consent_given,
                ),
            )
            .filter(Application.job_id.in_(job_ids))
            .group_by(Application.job_id)
            .all()
        )
        job_map = {j.id: j for j in jobs}
        for row in eeo_by_job:
            job = job_map.get(row.job_id)
            total = row.total
            eeo_count = row.eeo_count
            rate = round((eeo_count / total * 100), 1) if total > 0 else 0
            result["by_job"].append(
                {
                    "job_id": row.job_id,
                    "job_title": job.title if job else "Unknown",
                    "total_applicants": total,
                    "eeo_provided": eeo_count,
                    "coverage_rate": rate,
                }
            )

        end_date = datetime.now(UTC)
        for i in range(6):
            month_end = end_date - timedelta(days=i * 30)
            month_start = end_date - timedelta(days=(i + 1) * 30)
            month_label = month_start.strftime("%Y-%m")
            job_ids = [j.id for j in jobs]
            apps = (
                db.query(Application)
                .filter(
                    Application.job_id.in_(job_ids) if job_ids else False,
                    Application.created_at >= month_start,
                    Application.created_at < month_end,
                )
                .all()
            )
            app_ids = [a.id for a in apps]
            eeo_count = (
                db.query(EEOConsent)
                .filter(
                    EEOConsent.application_id.in_(app_ids),
                    EEOConsent.consent_given,
                )
                .count()
            )
            total = len(apps)
            rate = round((eeo_count / total * 100), 1) if total > 0 else 0
            result["trend"].append(
                {
                    "month": month_label,
                    "total_applicants": total,
                    "eeo_provided": eeo_count,
                    "coverage_rate": rate,
                }
            )

        result["trend"].reverse()
        return result
