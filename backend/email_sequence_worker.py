import hashlib
import hmac
import html
import json
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from backend.config import get_settings
from backend.database import Application, BatchJob, EmailSequenceLog
from backend.email_utils import send_email
from backend.logger import logger


def _make_unsubscribe_token(app_id: int) -> str:
    """Generate an HMAC-signed unsubscribe token for an application."""
    import base64

    secret = get_settings().secret_key
    expiry = int(datetime.now(UTC).timestamp()) + 86400 * 90  # 90 days
    msg = f"{app_id}:{expiry}".encode()
    sig = hmac.new(secret.encode(), msg, hashlib.sha256).hexdigest()[:16]
    payload = f"{app_id}:{expiry}:{sig}"
    return base64.urlsafe_b64encode(payload.encode()).decode().rstrip("=")


def process_email_sequences(db: Session):
    now = datetime.now(UTC).replace(tzinfo=None)

    from backend.database import CompanyMember

    active_company_ids = (
        db.query(CompanyMember.company_id)
        .filter(CompanyMember.is_active)
        .distinct()
        .subquery()
    )
    batches = (
        db.query(BatchJob)
        .filter(
            BatchJob.email_sequence_enabled,
            BatchJob.deleted_at.is_(None),
            BatchJob.company_id.in_(active_company_ids),
        )
        .all()
    )

    if not batches:
        return

    total_sent = 0
    for batch in batches:
        try:
            days_config = (
                json.loads(batch.email_sequence_days)
                if batch.email_sequence_days
                else []
            )
            if not days_config:
                continue
        except (json.JSONDecodeError, TypeError):
            continue

        apps = (
            db.query(Application)
            .filter(
                Application.batch_id == batch.id,
                Application.status == "invited",
                Application.email.isnot(None),
                Application.deleted_at.is_(None),
            )
            .all()
        )

        for app in apps:
            try:
                sent_logs = (
                    db.query(EmailSequenceLog)
                    .filter(EmailSequenceLog.application_id == app.id)
                    .order_by(EmailSequenceLog.step_number.desc())
                    .all()
                )

                if not sent_logs:
                    next_step = 0
                else:
                    next_step = len(sent_logs)

                if next_step >= len(days_config):
                    continue

                days_to_wait = days_config[next_step]
                created_delta = now - app.created_at.replace(tzinfo=None)

                if created_delta < timedelta(days=days_to_wait):
                    continue

                last_sent = sent_logs[0].sent_at if sent_logs else app.created_at
                if last_sent and (now - last_sent.replace(tzinfo=None)) < timedelta(
                    days=1
                ):
                    continue

                subject_templates = [
                    f"Following up on your application for {batch.title}",
                    f"We're still interested - {batch.title}",
                    f"Last chance: {batch.title} opportunity",
                ]
                body_templates = [
                    f"""
                    <p>Hi {html.escape(app.full_name or "")},</p>
                    <p>We wanted to follow up on your recent application for <strong>{html.escape(batch.title)}</strong>.</p>
                    <p>We were impressed by your profile and would love to learn more about you.</p>
                    """,
                    f"""
                    <p>Hi {html.escape(app.full_name or "")},</p>
                    <p>We're still reviewing applications for <strong>{html.escape(batch.title)}</strong> and your profile caught our attention.</p>
                    <p>If you're still interested, we'd love to schedule a quick chat.</p>
                    """,
                    f"""
                    <p>Hi {html.escape(app.full_name or "")},</p>
                    <p>This is a final reminder regarding your application for <strong>{html.escape(batch.title)}</strong>.</p>
                    <p>Please let us know if you're still interested by replying to this email.</p>
                    """,
                ]

                subject = (
                    subject_templates[next_step]
                    if next_step < len(subject_templates)
                    else subject_templates[-1]
                )
                body_template = (
                    body_templates[next_step]
                    if next_step < len(body_templates)
                    else body_templates[-1]
                )

                unsub_token = _make_unsubscribe_token(app.id)
                email_body = f"""
                <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                    {body_template}
                    <p style="margin-top: 24px;">
                        <a href="https://candway.com/unsubscribe?token={unsub_token}"
                           style="color: #94a3b8; font-size: 12px;">Unsubscribe</a>
                    </p>
                </div>
                """

                send_email(app.email, subject, email_body)

                log_entry = EmailSequenceLog(
                    company_id=batch.company_id,
                    application_id=app.id,
                    batch_id=batch.id,
                    step_number=next_step,
                    subject=subject,
                    sent_at=now,
                )
                db.add(log_entry)
                total_sent += 1

                logger.info(
                    f"Email sequence step {next_step + 1}/{len(days_config)} "
                    f"sent to {app.email} for batch {batch.id}"
                )

            except Exception as e:
                logger.error(
                    f"Email sequence failed for app {app.id} batch {batch.id}: {e}"
                )
                continue

    db.commit()
    logger.info(f"Email sequence worker sent {total_sent} emails")
