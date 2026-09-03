"""
Email Notification System for Candway ATS
Handles all automated email notifications including:
- Interview reminders
- Offer expiration alerts
- @mention notifications
- Comment notifications
- Status change notifications
"""

import html
import logging
from datetime import UTC, datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from backend.database import Application, Comment, Interview, Offer, User
from backend.email_utils import send_email
from backend.profile_helpers import get_user_name

logger = logging.getLogger(__name__)


class NotificationService:
    """Centralized notification service for all email notifications"""

    @staticmethod
    def _get_frontend_url():
        from backend.config import get_settings

        settings = get_settings()
        return settings.frontend_url

    @staticmethod
    def send_interview_reminder(interview: Interview, hours_before: int, db: Session):
        """
        Send interview reminder email

        Args:
            interview: Interview object
            hours_before: How many hours before (24 or 1)
            db: Database session
        """
        try:
            # Get candidate and interviewers
            app = (
                db.query(Application)
                .filter(Application.id == interview.application_id)
                .first()
            )
            if not app or not app.owner:
                logger.error(
                    f"Application or owner not found for interview {interview.id}"
                )
                return False

            candidate = app.owner
            interviewers = [p.user for p in interview.participants if p.user]

            # Format interview details
            interview_time = interview.scheduled_time.strftime("%B %d, %Y at %I:%M %p")
            interview_type = interview.type.capitalize()

            # Email to candidate
            candidate_subject = f"Reminder: {interview_type} Interview in {hours_before} hour{'s' if hours_before > 1 else ''}"
            candidate_body = f"""
            <html>
            <body style="font-family: 'Segoe UI', Arial, sans-serif; line-height: 1.6; color: #333;">
                <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                    <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 30px; border-radius: 10px 10px 0 0; text-align: center;">
                        <h1 style="color: white; margin: 0; font-size: 24px;">Interview Reminder</h1>
                    </div>

                    <div style="background: #f8f9fa; padding: 30px; border-radius: 0 0 10px 10px;">
                        <p style="font-size: 16px; margin-bottom: 20px;">Hi {html.escape(get_user_name(candidate) or "")},</p>

                        <p style="font-size: 16px; margin-bottom: 20px;">
                            This is a friendly reminder that your <strong>{interview_type} Interview</strong> is coming up in <strong>{hours_before} hour{"s" if hours_before > 1 else ""}</strong>.
                        </p>

                        <div style="background: white; padding: 20px; border-radius: 8px; border-left: 4px solid #667eea; margin: 20px 0;">
                            <h3 style="margin-top: 0; color: #667eea;">Interview Details</h3>
                            <p style="margin: 10px 0;"><strong>📅 Date & Time:</strong> {interview_time}</p>
                            <p style="margin: 10px 0;"><strong>⏱️ Duration:</strong> {interview.duration_minutes} minutes</p>
                            {f'<p style="margin: 10px 0;"><strong>📍 Location:</strong> {interview.location}</p>' if interview.location else ""}
                            {f'<p style="margin: 10px 0;"><strong>🔗 Meeting Link:</strong> <a href="{interview.meeting_link}" style="color: #667eea;">{interview.meeting_link}</a></p>' if interview.meeting_link else ""}
                        </div>

                        {f'<div style="background: #e3f2fd; padding: 15px; border-radius: 8px; margin: 20px 0;"><h4 style="margin-top: 0; color: #1976d2;">Agenda</h4><p style="margin: 0;">{interview.agenda}</p></div>' if interview.agenda else ""}

                        <p style="font-size: 14px; color: #666; margin-top: 30px;">
                            Good luck! We're excited to speak with you.
                        </p>

                        <div style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #ddd; text-align: center;">
                            <p style="font-size: 12px; color: #999;">
                                This is an automated reminder from Candway ATS<br>
                                <a href="#" style="color: #667eea; text-decoration: none;">Manage notification preferences</a>
                            </p>
                        </div>
                    </div>
                </div>
            </body>
            </html>
            """

            send_email(
                to_email=candidate.email, subject=candidate_subject, body=candidate_body
            )

            # Email to interviewers
            for interviewer in interviewers:
                interviewer_subject = f"Reminder: Interview with {get_user_name(candidate)} in {hours_before} hour{'s' if hours_before > 1 else ''}"
                interviewer_body = f"""
                <html>
                <body style="font-family: 'Segoe UI', Arial, sans-serif; line-height: 1.6; color: #333;">
                    <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                        <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 30px; border-radius: 10px 10px 0 0; text-align: center;">
                            <h1 style="color: white; margin: 0; font-size: 24px;">Interview Reminder</h1>
                        </div>

                        <div style="background: #f8f9fa; padding: 30px; border-radius: 0 0 10px 10px;">
                            <p style="font-size: 16px; margin-bottom: 20px;">Hi {html.escape(get_user_name(interviewer) or "")},</p>

                            <p style="font-size: 16px; margin-bottom: 20px;">
                                You have a <strong>{interview_type} Interview</strong> with <strong>{html.escape(get_user_name(candidate))}</strong> in <strong>{hours_before} hour{"s" if hours_before > 1 else ""}</strong>.
                            </p>

                            <div style="background: white; padding: 20px; border-radius: 8px; border-left: 4px solid #667eea; margin: 20px 0;">
                                <h3 style="margin-top: 0; color: #667eea;">Interview Details</h3>
                                <p style="margin: 10px 0;"><strong>👤 Candidate:</strong> {html.escape(get_user_name(candidate))}</p>
                                <p style="margin: 10px 0;"><strong>📅 Date & Time:</strong> {interview_time}</p>
                                <p style="margin: 10px 0;"><strong>⏱️ Duration:</strong> {interview.duration_minutes} minutes</p>
                                {f'<p style="margin: 10px 0;"><strong>📍 Location:</strong> {interview.location}</p>' if interview.location else ""}
                                {f'<p style="margin: 10px 0;"><strong>🔗 Meeting Link:</strong> <a href="{interview.meeting_link}" style="color: #667eea;">{interview.meeting_link}</a></p>' if interview.meeting_link else ""}
                            </div>

                            {f'<div style="background: #e3f2fd; padding: 15px; border-radius: 8px; margin: 20px 0;"><h4 style="margin-top: 0; color: #1976d2;">Agenda</h4><p style="margin: 0;">{interview.agenda}</p></div>' if interview.agenda else ""}

                            <div style="text-align: center; margin: 30px 0;">
                                <a href="{NotificationService._get_frontend_url()}/candidates/{app.id}"
                                   style="display: inline-block; background: #667eea; color: white; padding: 12px 30px; border-radius: 6px; text-decoration: none; font-weight: bold;">
                                    View Candidate Profile
                                </a>
                            </div>

                            <div style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #ddd; text-align: center;">
                                <p style="font-size: 12px; color: #999;">
                                    This is an automated reminder from Candway ATS<br>
                                    <a href="#" style="color: #667eea; text-decoration: none;">Manage notification preferences</a>
                                </p>
                            </div>
                        </div>
                    </div>
                </body>
                </html>
                """

                send_email(
                    to_email=interviewer.email,
                    subject=interviewer_subject,
                    body=interviewer_body,
                )

            logger.info(
                f"Interview reminder sent for interview {interview.id} ({hours_before}h before)"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to send interview reminder: {e}")
            return False

    @staticmethod
    def send_offer_expiration_alert(offer: Offer, days_until_expiry: int, db: Session):
        """
        Send offer expiration alert
        """
        try:
            # Get application and recruiter
            app = (
                db.query(Application)
                .filter(Application.id == offer.application_id)
                .first()
            )
            if not app or not app.owner:
                return False

            candidate = app.owner
            recruiter = db.query(User).filter(User.id == offer.created_by).first()

            if days_until_expiry == 0:
                urgency = "has expired"
                color = "#dc2626"
            elif days_until_expiry == 1:
                urgency = "expires tomorrow"
                color = "#f59e0b"
            else:
                urgency = f"expires in {days_until_expiry} days"
                color = "#3b82f6"

            # Email to recruiter
            subject = f"⚠️ Offer {urgency}: {get_user_name(candidate)}"
            body = f"""
            <html>
            <body style="font-family: 'Segoe UI', Arial, sans-serif; line-height: 1.6; color: #333;">
                <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                    <div style="background: {color}; padding: 30px; border-radius: 10px 10px 0 0; text-align: center;">
                        <h1 style="color: white; margin: 0; font-size: 24px;">Offer Expiration Alert</h1>
                    </div>
                    <div style="background: #f8f9fa; padding: 30px; border-radius: 0 0 10px 10px;">
                        <p>Hi {html.escape(get_user_name(recruiter)) if recruiter else "there"},</p>
                        <p>The job offer for <strong>{html.escape(get_user_name(candidate))}</strong> <strong style="color: {color};">{urgency}</strong>.</p>
                    </div>
                </div>
            </body>
            </html>
            """

            send_email(
                to_email=recruiter.email if recruiter else "admin@candway.com",
                subject=subject,
                body=body,
            )
            return True
        except Exception as e:
            logger.error(f"Failed to send offer expiration alert: {e}")
            return False

    @staticmethod
    def send_mention_notification(comment: Comment, mentioned_user: User, db: Session):
        """
        Send @mention notification
        """
        try:
            app = (
                db.query(Application)
                .filter(Application.id == comment.application_id)
                .first()
            )
            if not app or not app.owner:
                return False

            candidate = app.owner
            commenter = comment.user

            subject = f"💬 {get_user_name(commenter)} mentioned you in a comment"
            body = f"Hi {html.escape(get_user_name(mentioned_user))}, {html.escape(get_user_name(commenter))} mentioned you in a comment on {html.escape(get_user_name(candidate))}'s application."

            send_email(to_email=mentioned_user.email, subject=subject, body=body)
            return True
        except Exception as e:
            logger.error(f"Failed to send mention notification: {e}")
            return False


# Scheduled job functions (to be called by scheduler)
def check_interview_reminders(db: Session):
    """Check for interviews that need reminders (24h and 1h before)"""
    now = datetime.now(UTC)

    from backend.database import Application

    valid_company_apps = (
        db.query(Application.id)
        .filter(
            Application.company_id.in_(
                db.query(Application.company_id)
                .filter(Application.company_id.isnot(None))
                .distinct()
            )
        )
        .subquery()
    )

    # 24-hour reminders
    reminder_24h = now + timedelta(hours=24)
    interviews_24h = (
        db.query(Interview)
        .filter(
            Interview.scheduled_time >= reminder_24h - timedelta(minutes=15),
            Interview.scheduled_time <= reminder_24h + timedelta(minutes=15),
            Interview.status == "scheduled",
            not Interview.reminder_sent_24h,
            Interview.application_id.in_(valid_company_apps),
        )
        .all()
    )

    for interview in interviews_24h:
        if NotificationService.send_interview_reminder(interview, 24, db):
            interview.reminder_sent_24h = True
            db.commit()

    # 1-hour reminders
    reminder_1h = now + timedelta(hours=1)
    interviews_1h = (
        db.query(Interview)
        .filter(
            Interview.scheduled_time >= reminder_1h - timedelta(minutes=5),
            Interview.scheduled_time <= reminder_1h + timedelta(minutes=5),
            Interview.status == "scheduled",
            not Interview.reminder_sent_1h,
            Interview.application_id.in_(valid_company_apps),
        )
        .all()
    )

    for interview in interviews_1h:
        if NotificationService.send_interview_reminder(interview, 1, db):
            interview.reminder_sent_1h = True
            db.commit()

    logger.info(
        f"Checked interview reminders: {len(interviews_24h)} 24h, {len(interviews_1h)} 1h"
    )


def check_offer_expirations(db: Session):
    """Check for offers that are expiring soon and send alerts"""
    now = datetime.now(UTC).replace(tzinfo=None)
    warning_window = now + timedelta(days=3)

    expiring_offers = (
        db.query(Offer)
        .filter(
            Offer.status == "sent",
            Offer.expires_at <= warning_window,
            Offer.expires_at > now,
        )
        .all()
    )

    for offer in expiring_offers:
        try:
            days_until_expiry = (offer.expires_at - now).days
            NotificationService.send_offer_expiration_alert(
                offer, days_until_expiry, db
            )
        except Exception as e:
            logger.error(
                f"Failed to send offer expiration alert for offer {offer.id}: {e}"
            )

    logger.info(f"Checked offer expirations: {len(expiring_offers)} alerts sent")


async def notify_user(
    user_id: str,
    message: str,
    title: str = "Notification",
    level: str = "info",
    body: Optional[str] = None,
    extra: Optional[dict] = None,
    notification_type: str = "notification",
    related_type: Optional[str] = None,
    related_id: Optional[int] = None,
    db_session=None,
):
    """
    Send a real-time in-app notification to a user via WebSocket.
    Also persists the notification to the database for retrieval via API.
    """
    try:
        target_user_id = int(user_id)
        from backend.realtime import manager as realtime_manager

        # Send real-time WebSocket notification
        await realtime_manager.send_personal_message(
            {
                "type": notification_type,
                "title": title,
                "level": level,
                "message": message,
                "body": body,
                "timestamp": datetime.now(UTC).isoformat(),
                "extra": extra,
            },
            target_user_id,
        )

        # Persist to database
        if db_session:
            try:
                import json as _json

                from backend.database import Notification

                payload = extra or {}
                if body:
                    payload["body"] = body

                notification = Notification(
                    user_id=target_user_id,
                    type=notification_type,
                    title=title,
                    message=message,
                    level=level,
                    related_type=related_type,
                    related_id=related_id,
                    payload_json=_json.dumps(payload) if payload else None,
                )
                db_session.add(notification)
                db_session.commit()
            except Exception as db_err:
                if db_session:
                    db_session.rollback()
                logger.error(f"Failed to persist notification to database: {db_err}")

    except Exception as e:
        logger.error(f"Failed to send realtime notification: {e}")
