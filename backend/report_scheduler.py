import json
import logging
from datetime import UTC, datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from backend.database import ReportSnapshot, SavedReport
from backend.email_service import email_service
from backend.report_builder import ReportBuilder

logger = logging.getLogger(__name__)


class ReportScheduler:
    FREQUENCIES = {
        "daily": {"label": "Daily at 9 AM", "cron": "0 9 * * *"},
        "weekly": {"label": "Weekly on Monday at 9 AM", "cron": "0 9 * * 1"},
        "monthly": {"label": "Monthly on 1st at 9 AM", "cron": "0 9 1 * *"},
        "quarterly": {
            "label": "Quarterly on Jan 1 at 9 AM",
            "cron": "0 9 1 1,4,7,10 *",
        },
    }

    @staticmethod
    async def generate_scheduled_report(schedule_id: int, db: Session) -> dict:
        saved = db.query(SavedReport).filter(SavedReport.id == schedule_id).first()
        if not saved:
            raise ValueError(f"Scheduled report {schedule_id} not found")

        config = (
            json.loads(saved.config) if isinstance(saved.config, str) else saved.config
        )
        report_data = ReportBuilder.build_report(
            config, saved.recruiter_id, db, company_id=saved.company_id
        )

        snapshot = ReportSnapshot(
            report_id=saved.id,
            report_data=json.dumps(report_data),
        )
        db.add(snapshot)
        db.commit()
        db.refresh(snapshot)

        saved.last_generated_at = datetime.now(UTC).replace(tzinfo=None)
        saved.next_scheduled_at = ReportScheduler.get_next_run(
            saved.schedule_frequency, saved.last_generated_at
        )
        db.commit()

        recipients = []
        if saved.schedule_recipients:
            try:
                recipients = json.loads(saved.schedule_recipients)
            except (json.JSONDecodeError, TypeError):
                pass

        if recipients:
            await ReportScheduler.send_report_via_email(
                report_data, recipients, saved.name, format="pdf"
            )

        return {"snapshot_id": snapshot.id, "report_data": report_data}

    @staticmethod
    async def send_report_via_email(
        report_data: dict,
        recipients: list,
        report_name: str,
        format: str = "pdf",
    ):
        csv_data = None
        pdf_bytes = None
        if format == "csv":
            csv_data = ReportBuilder.export_csv(report_data)
        else:
            pdf_bytes = ReportBuilder.export_pdf(report_data, report_name)

        summary_lines = []
        data = report_data.get("report_data", {})
        for key, val in data.items():
            if isinstance(val, dict) and val.get("type") == "number_card":
                summary_lines.append(
                    f"<li><strong>{ReportBuilder.RECRUITER_METRICS.get(key, key)}:</strong> "
                    f"{val.get('value', '')}{val.get('suffix', '')} "
                    f"(Trend: {val.get('change', 0)}%)</li>"
                )

        summary_html = (
            "<ul>" + "".join(summary_lines) + "</ul>"
            if summary_lines
            else "<p>See attached report.</p>"
        )

        for recipient in recipients:
            try:
                if format == "csv" and csv_data:
                    email_service.send_email(
                        to_email=recipient,
                        subject=f"Candway Report: {report_name}",
                        body=f"""
                        <h2>{report_name}</h2>
                        <p>Your scheduled report has been generated.</p>
                        {summary_html}
                        <p><small>Generated at: {report_data.get("generated_at", "")}</small></p>
                        """,
                    )
                elif pdf_bytes:
                    email_service.send_email(
                        to_email=recipient,
                        subject=f"Candway Report: {report_name}",
                        body=f"""
                        <h2>{report_name}</h2>
                        <p>Your scheduled report PDF is attached.</p>
                        {summary_html}
                        <p><small>Generated at: {report_data.get("generated_at", "")}</small></p>
                        """,
                    )
            except Exception as e:
                logger.error(f"Failed to email report to {recipient}: {e}")

    @staticmethod
    def get_next_run(
        schedule_frequency: str, last_run: Optional[datetime] = None
    ) -> datetime:
        now = datetime.now(UTC).replace(tzinfo=None)
        if schedule_frequency == "daily":
            next_run = now.replace(hour=9, minute=0, second=0, microsecond=0)
            if last_run and next_run <= last_run:
                next_run += timedelta(days=1)
            if next_run <= now:
                next_run += timedelta(days=1)
        elif schedule_frequency == "weekly":
            days_ahead = (0 - now.weekday()) % 7
            next_run = (now + timedelta(days=days_ahead)).replace(
                hour=9, minute=0, second=0, microsecond=0
            )
            if last_run and next_run <= last_run:
                next_run += timedelta(days=7)
            if next_run <= now:
                next_run += timedelta(days=7)
        elif schedule_frequency == "monthly":
            next_run = now.replace(day=1, hour=9, minute=0, second=0, microsecond=0)
            if last_run and next_run <= last_run:
                if next_run.month == 12:
                    next_run = next_run.replace(year=next_run.year + 1, month=1)
                else:
                    next_run = next_run.replace(month=next_run.month + 1)
            if next_run <= now:
                if next_run.month == 12:
                    next_run = next_run.replace(year=next_run.year + 1, month=1)
                else:
                    next_run = next_run.replace(month=next_run.month + 1)
        elif schedule_frequency == "quarterly":
            current_q = (now.month - 1) // 3
            next_q_start_month = current_q * 3 + 1
            if now.month >= next_q_start_month + 2:
                next_q_start_month += 3
            next_run = now.replace(
                month=min(next_q_start_month, 12),
                day=1,
                hour=9,
                minute=0,
                second=0,
                microsecond=0,
            )
            if next_run.month > 12:
                next_run = next_run.replace(year=next_run.year + 1, month=1)
            if last_run and next_run <= last_run:
                next_run = next_run.replace(month=min(next_run.month + 3, 12))
                if next_run.month > 12:
                    next_run = next_run.replace(year=next_run.year + 1, month=1)
        else:
            next_run = now + timedelta(days=1)

        return next_run.replace(tzinfo=None)


async def check_scheduled_reports():
    db = SessionLocal()
    try:
        now = datetime.now(UTC).replace(tzinfo=None)
        due = (
            db.query(SavedReport)
            .filter(
                SavedReport.is_scheduled,
                SavedReport.next_scheduled_at <= now,
            )
            .all()
        )
        for report in due:
            try:
                await ReportScheduler.generate_scheduled_report(report.id, db)
                logger.info(f"Scheduled report #{report.id} generated")
            except Exception as e:
                logger.error(f"Failed to generate scheduled report #{report.id}: {e}")
        db.commit()
    except Exception as e:
        logger.error(f"check_scheduled_reports failed: {e}")
    finally:
        db.close()


from backend.database import SessionLocal  # noqa: E402
