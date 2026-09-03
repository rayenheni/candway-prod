import csv
import io
import json
import logging
from datetime import UTC, datetime
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from backend.database import Application, EvaluationResult, EvaluationSession, Job
from backend.pdf_generator import PDFReport

logger = logging.getLogger(__name__)

RECRUITER_METRICS = {
    "total_applications": "Total Applications",
    "applications_per_job": "Applications Per Job",
    "screening_rate": "Screening Rate",
    "interview_rate": "Interview Rate",
    "offer_rate": "Offer Rate",
    "hire_rate": "Hire Rate (Conversion)",
    "avg_time_to_hire": "Avg Time to Hire (days)",
    "avg_time_to_interview": "Avg Time to Interview (days)",
    "avg_cv_score": "Avg CV Score",
    "avg_interview_score": "Avg Interview Score",
    "offer_acceptance_rate": "Offer Acceptance Rate",
    "candidates_per_job": "Avg Candidates Per Job",
    "source_effectiveness": "Source Effectiveness",
    "pipeline_conversion": "Pipeline Stage Conversion",
    "recruiter_activity": "Recruiter Activity",
    "interviews_per_recruiter": "Interviews Per Recruiter",
    "applications_by_source": "Applications by Source",
    "applications_by_status": "Applications by Status",
    "applications_over_time": "Applications Over Time",
    "hires_over_time": "Hires Over Time",
}

FILTER_TYPES = {
    "date_range": "Date Range",
    "recruiter": "Recruiter",
    "job": "Job",
    "status": "Status",
    "source": "Source",
    "score_range": "Score Range",
}

VISUALIZATION_TYPES = [
    "number_card",
    "bar_chart",
    "line_chart",
    "pie_chart",
    "table",
    "funnel",
    "metric_comparison",
    "trendline",
]


class ReportBuilder:
    @staticmethod
    def build_report(
        config: dict, recruiter_id: int, db: Session, company_id: Optional[int] = None
    ) -> dict:
        metrics = config.get("metrics", [])
        filters = config.get("filters", {})
        group_by = config.get("group_by")
        visualizations = config.get("visualizations", [])

        report_data = {}
        for metric in metrics:
            try:
                result = ReportBuilder._compute_metric(
                    metric, filters, group_by, recruiter_id, db, company_id
                )
                report_data[metric] = result
            except Exception as e:
                logger.error(f"Failed to compute metric {metric}: {e}")
                report_data[metric] = {"error": str(e)}

        if visualizations:
            for viz in visualizations:
                m = viz.get("metric")
                if m and m not in report_data:
                    try:
                        result = ReportBuilder._compute_metric(
                            m, filters, group_by, recruiter_id, db, company_id
                        )
                        report_data[m] = result
                    except Exception as e:
                        logger.error(f"Failed to compute viz metric {m}: {e}")
                        report_data[m] = {"error": str(e)}

        return {
            "report_data": report_data,
            "generated_at": datetime.now(UTC).isoformat(),
            "config": config,
        }

    @staticmethod
    def _compute_metric(
        metric: str,
        filters: dict,
        group_by: Optional[str],
        recruiter_id: int,
        db: Session,
        company_id: Optional[int] = None,
    ) -> dict:
        job_filters = [Job.recruiter_id == recruiter_id, Job.deleted_at.is_(None)]
        if company_id is not None:
            job_filters.append(Job.company_id == company_id)
        jobs = db.query(Job).filter(*job_filters).all()
        job_ids = [j.id for j in jobs]

        apps_query = (
            db.query(Application)
            .options(
                selectinload(Application.evaluation_sessions).selectinload(
                    EvaluationSession.evaluation_result
                )
            )
            .filter(
                Application.job_id.in_(job_ids) if job_ids else False,
                Application.deleted_at.is_(None),
            )
        )
        apps_query = ReportBuilder._apply_filters(apps_query, filters, recruiter_id, db)
        apps = apps_query.limit(10000).all()

        if metric == "total_applications":
            return ReportBuilder._compute_number_card({"value": len(apps), "change": 0})

        if metric == "applications_per_job":
            val = round(len(apps) / len(jobs), 1) if jobs else 0
            return ReportBuilder._compute_number_card({"value": val, "change": 0})

        if metric == "screening_rate":
            screened = sum(1 for a in apps if a.status == "screening")
            rate = round((screened / len(apps) * 100), 1) if apps else 0
            return ReportBuilder._compute_number_card(
                {"value": rate, "suffix": "%", "change": 0}
            )

        if metric == "interview_rate":
            interviewing = sum(1 for a in apps if a.status == "interviewing")
            rate = round((interviewing / len(apps) * 100), 1) if apps else 0
            return ReportBuilder._compute_number_card(
                {"value": rate, "suffix": "%", "change": 0}
            )

        if metric == "offer_rate":
            offered = sum(1 for a in apps if a.status == "offer")
            interviewing = sum(1 for a in apps if a.status == "interviewing")
            rate = round((offered / interviewing * 100), 1) if interviewing else 0
            return ReportBuilder._compute_number_card(
                {"value": rate, "suffix": "%", "change": 0}
            )

        if metric == "hire_rate":
            hired = sum(1 for a in apps if a.status == "hired")
            rate = round((hired / len(apps) * 100), 1) if apps else 0
            return ReportBuilder._compute_number_card(
                {"value": rate, "suffix": "%", "change": 0}
            )

        if metric == "avg_time_to_hire":
            hired_apps = [a for a in apps if a.status == "hired" and a.created_at]
            if hired_apps:
                days = [
                    ((a.updated_at or datetime.now()) - a.created_at).days
                    for a in hired_apps
                ]
                avg = round(sum(days) / len(days), 1)
            else:
                avg = 0
            return ReportBuilder._compute_number_card(
                {"value": avg, "suffix": " days", "change": 0}
            )

        if metric == "avg_time_to_interview":
            interviewed = [
                a for a in apps if a.status == "interviewing" and a.created_at
            ]
            if interviewed:
                days = [
                    ((a.updated_at or datetime.now()) - a.created_at).days
                    for a in interviewed
                ]
                avg = round(sum(days) / len(days), 1)
            else:
                avg = 0
            return ReportBuilder._compute_number_card(
                {"value": avg, "suffix": " days", "change": 0}
            )

        if metric == "avg_cv_score":
            scored = [
                a
                for a in apps
                if a.evaluation_sessions
                and a.evaluation_sessions[0].evaluation_result
                and a.evaluation_sessions[0].evaluation_result.cv_score is not None
            ]
            avg = (
                round(
                    sum(
                        a.evaluation_sessions[0].evaluation_result.cv_score
                        for a in scored
                    )
                    / len(scored),
                    1,
                )
                if scored
                else 0
            )
            return ReportBuilder._compute_number_card(
                {"value": avg, "suffix": "/100", "change": 0}
            )

        if metric == "avg_interview_score":
            scored = [
                a
                for a in apps
                if a.evaluation_sessions
                and a.evaluation_sessions[0].evaluation_result
                and a.evaluation_sessions[0].evaluation_result.final_score is not None
            ]
            avg = (
                round(
                    sum(
                        a.evaluation_sessions[0].evaluation_result.final_score
                        for a in scored
                    )
                    / len(scored),
                    1,
                )
                if scored
                else 0
            )
            return ReportBuilder._compute_number_card(
                {"value": avg, "suffix": "/100", "change": 0}
            )

        if metric == "offer_acceptance_rate":
            offered = [a for a in apps if a.status in ("offer", "hired")]
            accepted = sum(1 for a in offered if a.status == "hired")
            rate = round((accepted / len(offered) * 100), 1) if offered else 0
            return ReportBuilder._compute_number_card(
                {"value": rate, "suffix": "%", "change": 0}
            )

        if metric == "candidates_per_job":
            val = round(len(apps) / len(jobs), 1) if jobs else 0
            return ReportBuilder._compute_number_card({"value": val, "change": 0})

        if metric == "source_effectiveness":
            sources = {}
            for a in apps:
                s = a.source or "Direct"
                if s not in sources:
                    sources[s] = {"total": 0, "interviewing": 0, "hired": 0}
                sources[s]["total"] += 1
                if a.status == "interviewing":
                    sources[s]["interviewing"] += 1
                if a.status == "hired":
                    sources[s]["hired"] += 1
            for s in sources:
                src = sources[s]
                src["conversion"] = (
                    round((src["hired"] / src["total"]) * 100, 1) if src["total"] else 0
                )
            return {"type": "table", "data": sources}

        if metric == "pipeline_conversion":
            return ReportBuilder._compute_funnel(
                ["pending", "screening", "interviewing", "offer", "hired"],
                filters,
                recruiter_id,
                db,
                company_id,
            )

        if metric == "recruiter_activity":
            recruiters_map = {}
            for a in apps:
                rid = a.assigned_to or recruiter_id
                if rid not in recruiters_map:
                    recruiters_map[rid] = {
                        "applications": 0,
                        "interviews": 0,
                        "offers": 0,
                    }
                recruiters_map[rid]["applications"] += 1
            return {"type": "bar_chart", "data": recruiters_map}

        if metric == "interviews_per_recruiter":
            interview_counts = {}
            for a in apps:
                rid = a.assigned_to or recruiter_id
                if rid not in interview_counts:
                    interview_counts[rid] = 0
                if a.status == "interviewing":
                    interview_counts[rid] += 1
            return {"type": "bar_chart", "data": interview_counts}

        if metric == "applications_by_source":
            sources = {}
            for a in apps:
                s = a.source or "Direct"
                sources[s] = sources.get(s, 0) + 1
            return {
                "type": "pie_chart",
                "labels": list(sources.keys()),
                "values": list(sources.values()),
            }

        if metric == "applications_by_status":
            statuses = {}
            for a in apps:
                s = a.status or "pending"
                statuses[s] = statuses.get(s, 0) + 1
            return {
                "type": "pie_chart",
                "labels": list(statuses.keys()),
                "values": list(statuses.values()),
            }

        if metric == "applications_over_time":
            return ReportBuilder._compute_time_series(apps, "created_at", group_by)

        if metric == "hires_over_time":
            hired = [a for a in apps if a.status == "hired"]
            return ReportBuilder._compute_time_series(hired, "created_at", group_by)

        return {"error": f"Unknown metric: {metric}"}

    @staticmethod
    def _apply_filters(query, filters: dict, recruiter_id: int, db: Session):
        if not filters:
            return query

        date_range = filters.get("date_range", {})
        if date_range.get("start"):
            from datetime import datetime as dt

            try:
                start = dt.fromisoformat(date_range["start"])
                query = query.filter(Application.created_at >= start)
            except (ValueError, TypeError):
                pass
        if date_range.get("end"):
            try:
                end = dt.fromisoformat(date_range["end"])
                query = query.filter(Application.created_at <= end)
            except (ValueError, TypeError):
                pass

        statuses = filters.get("statuses")
        if statuses:
            query = query.filter(Application.status.in_(statuses))

        sources = filters.get("sources")
        if sources:
            query = query.filter(Application.source.in_(sources))

        job_ids = filters.get("job_ids")
        if job_ids:
            query = query.filter(Application.job_id.in_(job_ids))

        score_min = filters.get("score_min")
        if score_min is not None:
            score_sq = (
                select(EvaluationResult.final_score)
                .join(
                    EvaluationSession,
                    EvaluationResult.evaluation_session_id == EvaluationSession.id,
                )
                .where(EvaluationSession.application_id == Application.id)
                .correlate(Application)
                .scalar_subquery()
            )
            query = query.filter(func.coalesce(score_sq, 0) >= score_min)

        score_max = filters.get("score_max")
        if score_max is not None:
            score_sq = (
                select(EvaluationResult.final_score)
                .join(
                    EvaluationSession,
                    EvaluationResult.evaluation_session_id == EvaluationSession.id,
                )
                .where(EvaluationSession.application_id == Application.id)
                .correlate(Application)
                .scalar_subquery()
            )
            query = query.filter(func.coalesce(score_sq, 0) <= score_max)

        return query

    @staticmethod
    def _compute_number_card(data: dict) -> dict:
        return {
            "type": "number_card",
            "value": data.get("value", 0),
            "suffix": data.get("suffix", ""),
            "change": data.get("change", 0),
            "change_type": "up" if (data.get("change", 0) or 0) >= 0 else "down",
        }

    @staticmethod
    def _compute_time_series(
        data: list, date_field: str, group_by: Optional[str]
    ) -> dict:
        if not data:
            return {"type": "line_chart", "labels": [], "datasets": []}

        buckets = {}
        for item in data:
            dt_val = getattr(item, date_field, None)
            if not dt_val:
                continue
            key = ReportBuilder._group_key(dt_val, group_by)
            buckets[key] = buckets.get(key, 0) + 1

        sorted_keys = sorted(buckets.keys())
        return {
            "type": "line_chart",
            "labels": sorted_keys,
            "datasets": [
                {
                    "label": "Count",
                    "data": [buckets[k] for k in sorted_keys],
                }
            ],
        }

    @staticmethod
    def _group_key(dt_val, group_by: Optional[str]) -> str:
        if group_by == "day":
            return dt_val.strftime("%Y-%m-%d")
        elif group_by == "week":
            return dt_val.strftime("%Y-W%W")
        elif group_by == "month":
            return dt_val.strftime("%Y-%m")
        elif group_by == "quarter":
            q = (dt_val.month - 1) // 3 + 1
            return f"{dt_val.year}-Q{q}"
        elif group_by == "year":
            return str(dt_val.year)
        return dt_val.strftime("%Y-%m-%d")

    @staticmethod
    def _compute_funnel(
        stages: list,
        filters: dict,
        recruiter_id: int,
        db: Session,
        company_id: Optional[int] = None,
    ) -> dict:
        job_filters = [Job.recruiter_id == recruiter_id, Job.deleted_at.is_(None)]
        if company_id is not None:
            job_filters.append(Job.company_id == company_id)
        jobs = db.query(Job).filter(*job_filters).all()
        job_ids = [j.id for j in jobs]
        apps_query = db.query(Application).filter(
            Application.job_id.in_(job_ids) if job_ids else False,
            Application.deleted_at.is_(None),
        )
        apps_query = ReportBuilder._apply_filters(apps_query, filters, recruiter_id, db)
        apps = apps_query.limit(10000).all()

        stage_counts = {}
        for stage in stages:
            if stage == "hired":
                count = sum(1 for a in apps if a.status == "hired")
            elif stage == "offer":
                count = sum(1 for a in apps if a.status in ("offer", "hired"))
            elif stage == "interviewing":
                count = sum(
                    1 for a in apps if a.status in ("interviewing", "offer", "hired")
                )
            elif stage == "screening":
                count = sum(
                    1
                    for a in apps
                    if a.status in ("screening", "interviewing", "offer", "hired")
                )
            else:
                count = len(apps)
            stage_counts[stage] = count

        total = len(apps)
        funnel_data = []
        for stage in stages:
            count = stage_counts[stage]
            conversion = round((count / total * 100), 1) if total else 0
            funnel_data.append(
                {"stage": stage, "count": count, "conversion": conversion}
            )

        return {"type": "funnel", "stages": funnel_data, "total": total}

    @staticmethod
    def export_csv(report_data: dict) -> str:
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["Metric", "Value", "Details"])

        for metric_key, metric_val in report_data.get("report_data", {}).items():
            if isinstance(metric_val, dict):
                if metric_val.get("type") == "number_card":
                    writer.writerow(
                        [
                            RECRUITER_METRICS.get(metric_key, metric_key),
                            f"{metric_val.get('value', '')}{metric_val.get('suffix', '')}",
                            f"Change: {metric_val.get('change', 0)}%",
                        ]
                    )
                elif metric_val.get("type") == "funnel":
                    for stage in metric_val.get("stages", []):
                        writer.writerow(
                            [
                                f"Funnel - {stage['stage']}",
                                stage["count"],
                                f"Conversion: {stage['conversion']}%",
                            ]
                        )
                elif metric_val.get("type") in ("line_chart", "bar_chart"):
                    labels = metric_val.get("labels", [])
                    datasets = metric_val.get("datasets", [])
                    for ds in datasets:
                        for i, label in enumerate(labels):
                            val = ds["data"][i] if i < len(ds["data"]) else ""
                            writer.writerow(
                                [
                                    f"{RECRUITER_METRICS.get(metric_key, metric_key)} - {label}",
                                    val,
                                    "",
                                ]
                            )
                elif metric_val.get("type") == "pie_chart":
                    labels = metric_val.get("labels", [])
                    values = metric_val.get("values", [])
                    for i, label in enumerate(labels):
                        val = values[i] if i < len(values) else ""
                        writer.writerow(
                            [
                                f"{RECRUITER_METRICS.get(metric_key, metric_key)} - {label}",
                                val,
                                "",
                            ]
                        )
                elif metric_val.get("type") == "table":
                    data = metric_val.get("data", {})
                    for key, row in data.items():
                        writer.writerow(
                            [
                                f"{RECRUITER_METRICS.get(metric_key, metric_key)} - {key}",
                                json.dumps(row),
                                "",
                            ]
                        )

        return output.getvalue()

    @staticmethod
    def export_pdf(report_data: dict, report_name: str) -> bytes:
        pdf = PDFReport()
        pdf.add_page()
        pdf.set_auto_page_break(auto=True, margin=15)

        pdf.set_font("Helvetica", "B", 16)
        pdf.cell(0, 12, report_name or "Custom Report", ln=True)
        pdf.set_font("Helvetica", "I", 9)
        pdf.cell(
            0,
            8,
            f"Generated: {report_data.get('generated_at', datetime.now(UTC).isoformat())}",
            ln=True,
        )
        pdf.ln(8)

        data = report_data.get("report_data", {})
        for metric_key, metric_val in data.items():
            if not isinstance(metric_val, dict):
                continue
            pdf.set_font("Helvetica", "B", 12)
            pdf.cell(0, 10, RECRUITER_METRICS.get(metric_key, metric_key), ln=True)

            mtype = metric_val.get("type")
            if mtype == "number_card":
                pdf.set_font("Helvetica", "", 11)
                pdf.cell(
                    0,
                    8,
                    f"Value: {metric_val.get('value', '')}{metric_val.get('suffix', '')}",
                    ln=True,
                )
                pdf.cell(0, 8, f"Trend: {metric_val.get('change', 0)}%", ln=True)
            elif mtype == "funnel":
                pdf.set_font("Helvetica", "", 10)
                for stage in metric_val.get("stages", []):
                    pdf.cell(
                        0,
                        7,
                        f"  {stage['stage']}: {stage['count']} ({stage['conversion']}%)",
                        ln=True,
                    )
            elif mtype in ("line_chart", "bar_chart", "pie_chart"):
                pdf.set_font("Helvetica", "", 10)
                labels = metric_val.get("labels", [])
                datasets = metric_val.get("datasets", [])
                for ds in datasets:
                    for i, label in enumerate(labels):
                        val = ds["data"][i] if i < len(ds["data"]) else ""
                        pdf.cell(0, 6, f"  {label}: {val}", ln=True)
            elif mtype == "table":
                pdf.set_font("Helvetica", "", 9)
                data_map = metric_val.get("data", {})
                for key, row in data_map.items():
                    row_str = ", ".join(f"{k}={v}" for k, v in row.items())
                    pdf.cell(0, 5, f"  {key}: {row_str}", ln=True)

            pdf.ln(4)

        return bytes(pdf.output())
