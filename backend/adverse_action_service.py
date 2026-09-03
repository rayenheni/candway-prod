from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from backend.database import Application, BackgroundCheck, BackgroundCheckStatusLog
from backend.email_utils import send_email
from backend.logger import logger


class AdverseActionService:
    DISPUTE_DAYS = 5

    @staticmethod
    def send_pre_adverse(
        background_check_id: int, db: Session, company_id: int = None
    ) -> dict:
        q = db.query(BackgroundCheck).filter(BackgroundCheck.id == background_check_id)
        if company_id is not None:
            q = q.filter(BackgroundCheck.company_id == company_id)
        bg_check = q.first()
        if not bg_check:
            raise ValueError(f"BackgroundCheck {background_check_id} not found")

        app = (
            db.query(Application)
            .filter(Application.id == bg_check.application_id)
            .first()
        )
        if not app:
            raise ValueError(f"Application {bg_check.application_id} not found")

        candidate_email = app.email
        candidate_name = app.full_name

        subject = "Pre-Adverse Action Notice - Candway Background Check"
        body = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <h2>Pre-Adverse Action Notice</h2>
            <p>Dear {candidate_name},</p>
            <p>We are writing to inform you that, based on the results of your background check, we are considering taking an adverse action regarding your application.</p>

            <h3>Your Rights Under FCRA</h3>
            <p>You have the right to:</p>
            <ul>
                <li>Receive a free copy of your background check report</li>
                <li>Dispute the accuracy or completeness of any information in the report</li>
                <li>Submit additional information to explain any findings</li>
            </ul>

            <p>You have <strong>{AdverseActionService.DISPUTE_DAYS} business days</strong> from receipt of this notice to dispute the findings.</p>

            <h3>Next Steps</h3>
            <p>If you believe any information in the report is inaccurate or incomplete, please contact us immediately. You may also contact Checkr directly to dispute the report.</p>

            <p>If we do not hear from you within {AdverseActionService.DISPUTE_DAYS} business days, or if your dispute does not change the results, we may proceed with the adverse action.</p>

            <p>Sincerely,<br>Candway Hiring Team</p>
        </div>
        """

        send_email(candidate_email, subject, body)

        old_status = bg_check.status
        bg_check.status = "adverse_action"
        bg_check.updated_at = datetime.now(UTC).replace(tzinfo=None)

        status_log = BackgroundCheckStatusLog(
            background_check_id=bg_check.id,
            from_status=old_status,
            to_status="adverse_action",
            details="Pre-adverse action notice sent to candidate",
            company_id=company_id,
        )
        db.add(status_log)
        db.commit()

        logger.info(
            f"Pre-adverse action notice sent for background_check {background_check_id}"
        )

        return {
            "success": True,
            "message": "Pre-adverse action notice sent",
            "background_check_id": bg_check.id,
            "status": bg_check.status,
        }

    @staticmethod
    def send_final_adverse(
        background_check_id: int, db: Session, company_id: int = None
    ) -> dict:
        q = db.query(BackgroundCheck).filter(BackgroundCheck.id == background_check_id)
        if company_id is not None:
            q = q.filter(BackgroundCheck.company_id == company_id)
        bg_check = q.first()
        if not bg_check:
            raise ValueError(f"BackgroundCheck {background_check_id} not found")

        app = (
            db.query(Application)
            .filter(Application.id == bg_check.application_id)
            .first()
        )
        if not app:
            raise ValueError(f"Application {bg_check.application_id} not found")

        candidate_email = app.email
        candidate_name = app.full_name

        subject = "Final Adverse Action Notice - Candway Background Check"
        body = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <h2>Final Adverse Action Notice</h2>
            <p>Dear {candidate_name},</p>
            <p>Following our pre-adverse action notice and the dispute period, we have made the final decision regarding your application.</p>

            <h3>Decision</h3>
            <p>Based on the background check results and after consideration of any information you provided, we have decided to proceed with an adverse action.</p>

            <h3>Your Rights</h3>
            <ul>
                <li>You have the right to obtain a free copy of your consumer report from Checkr within 60 days</li>
                <li>You have the right to dispute the accuracy or completeness of the report with Checkr</li>
                <li>You may request additional information about the decision</li>
            </ul>

            <p>Sincerely,<br>Candway Hiring Team</p>
        </div>
        """

        send_email(candidate_email, subject, body)

        old_status = bg_check.status
        bg_check.verdict = "suspended"
        bg_check.updated_at = datetime.now(UTC).replace(tzinfo=None)

        status_log = BackgroundCheckStatusLog(
            background_check_id=bg_check.id,
            from_status=old_status,
            to_status="adverse_action",
            details="Final adverse action notice sent to candidate",
            company_id=company_id,
        )
        db.add(status_log)
        db.commit()

        logger.info(
            f"Final adverse action notice sent for background_check {background_check_id}"
        )

        return {
            "success": True,
            "message": "Final adverse action notice sent",
            "background_check_id": bg_check.id,
            "status": bg_check.status,
            "verdict": bg_check.verdict,
        }

    @staticmethod
    def check_dispute_period(
        background_check_id: int, db: Session, company_id: int = None
    ) -> bool:
        q = db.query(BackgroundCheck).filter(BackgroundCheck.id == background_check_id)
        if company_id is not None:
            q = q.filter(BackgroundCheck.company_id == company_id)
        bg_check = q.first()
        if not bg_check:
            raise ValueError(f"BackgroundCheck {background_check_id} not found")

        status_log = (
            db.query(BackgroundCheckStatusLog)
            .filter(
                BackgroundCheckStatusLog.background_check_id == background_check_id,
                BackgroundCheckStatusLog.to_status == "adverse_action",
            )
            .order_by(BackgroundCheckStatusLog.created_at.desc())
            .first()
        )

        if not status_log:
            return True

        now = datetime.now(UTC).replace(tzinfo=None)
        dispute_end = status_log.created_at + timedelta(
            days=AdverseActionService.DISPUTE_DAYS
        )
        return now >= dispute_end
