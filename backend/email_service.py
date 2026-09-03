import asyncio
import html
import logging
import smtplib
from datetime import UTC, datetime, timedelta
from email.mime.multipart import MIMEMultipart

logger = logging.getLogger(__name__)
from email.mime.text import MIMEText  # noqa: E402

from backend.config import get_settings  # noqa: E402
from backend.profile_helpers import get_user_name  # noqa: E402
from backend.secret_encryption import decrypt_value  # noqa: E402

settings = get_settings()

from backend.database import SessionLocal, SystemConfig  # noqa: E402


# === EMAIL TEMPLATE DESIGN SYSTEM ===
def wrap_in_template(content: str, title: str = "Candway") -> str:
    """Professional email wrapper with consistent branding"""
    return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
</head>
<body style="margin:0;padding:0;background:#f8fafc;font-family:'Outfit',Arial,sans-serif;color:#1e293b;line-height:1.6;">
    <table width="100%" cellpadding="0" cellspacing="0" style="background:#f8fafc;">
        <tr>
            <td align="center" style="padding:20px;">
                <table width="600" cellpadding="0" cellspacing="0" style="max-width:600px;background:#ffffff;border-radius:16px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,0.08);">
                    <!-- Header -->
                    <tr>
                        <td style="background:linear-gradient(135deg,#4f46e5,#7c3aed);padding:32px;text-align:center;">
                            <h1 style="color:#ffffff;margin:0;font-size:28px;font-weight:800;letter-spacing:-0.5px;">CANDWAY</h1>
                            <p style="color:rgba(255,255,255,0.8);margin:8px 0 0;font-size:14px;font-weight:500;">AI-Powered Recruitment</p>
                        </td>
                    </tr>
                    <!-- Content -->
                    <tr>
                        <td style="padding:40px 32px;">
                            {content}
                        </td>
                    </tr>
                    <!-- Footer -->
                    <tr>
                        <td style="background:#f1f5f9;padding:24px 32px;text-align:center;border-top:1px solid #e2e4e8;">
                            <p style="margin:0 0 8px;font-size:13px;color:#64748b;">
                                © 2024 Candway Platform. All rights reserved.
                            </p>
                            <p style="margin:0;font-size:12px;color:#94a3b8;">
                                <a href="{settings.frontend_url}" style="color:#4f46e5;text-decoration:none;">Website</a> ·
                                <a href="{settings.frontend_url}/support" style="color:#4f46e5;text-decoration:none;">Support</a> ·
                                <a href="{settings.frontend_url}/privacy" style="color:#4f46e5;text-decoration:none;">Privacy</a>
                            </p>
                        </td>
                    </tr>
                </table>
                <p style="text-align:center;margin:16px 0 0;font-size:11px;color:#94a3b8;">
                    This email was sent to you as a Candway user.
                </p>
            </td>
        </tr>
    </table>
</body>
</html>
"""


def btn_style(url: str, text: str, primary: bool = True) -> str:
    """Email button"""
    bg = (
        "background:linear-gradient(135deg,#4f46e5,#7c3aed)"
        if primary
        else "background:#f1f5f9;color:#1e293b;border:1px solid #e2e4e8"
    )
    return f'<a href="{url}" style="{bg};color:#fff;padding:14px 28px;text-decoration:none;border-radius:10px;font-weight:600;font-size:15px;display:inline-block;margin:16px 0;">{text}</a>'


class EmailService:
    def __init__(self):
        pass

    def _check_company_email_limit(self, company_id: int) -> bool:
        """Check if company has exceeded daily email limit (atomic read)."""
        from sqlalchemy import func

        from backend.models.ats.campaign import EmailSequenceLog

        today = datetime.now(UTC).replace(tzinfo=None)
        yesterday = today - timedelta(days=1)

        db = SessionLocal()
        try:
            daily_count = (
                db.query(func.count(EmailSequenceLog.id))
                .filter(
                    EmailSequenceLog.company_id == company_id,
                    EmailSequenceLog.sent_at >= yesterday,
                )
                .scalar()
            )
        finally:
            db.close()

        DAILY_LIMIT = 500
        if daily_count is not None and daily_count >= DAILY_LIMIT:
            logger.warning(
                f"Company {company_id} exceeded daily email limit ({daily_count}/{DAILY_LIMIT})"
            )
            return False
        return True

    def get_smtp_config(self):
        db = SessionLocal()
        try:
            username = (
                db.query(SystemConfig)
                .filter(SystemConfig.key == "smtp_username")
                .first()
            )
            password = (
                db.query(SystemConfig)
                .filter(SystemConfig.key == "smtp_password")
                .first()
            )
            host = (
                db.query(SystemConfig).filter(SystemConfig.key == "smtp_host").first()
            )
            port = (
                db.query(SystemConfig).filter(SystemConfig.key == "smtp_port").first()
            )

            raw_password = password.value if password else None
            secret_key = get_settings().secret_key
            if raw_password and secret_key:
                # Fernet tokens always start with "gAAAA". Plaintext (legacy
                # storage) values must pass through unchanged.
                if raw_password.startswith("gAAAA"):
                    raw_password = decrypt_value(raw_password, secret_key) or raw_password

            # Fall back to env-driven settings when SystemConfig has no smtp_* rows.
            settings = get_settings()
            return {
                "username": (username.value if username else None) or settings.smtp_username or None,
                "password": raw_password or settings.smtp_password or None,
                "server": (host.value if host else None) or settings.smtp_host or "smtp.gmail.com",
                "port": int(port.value) if port else (settings.smtp_port or 587),
                "from_email": settings.smtp_from or None,
            }
        finally:
            db.close()

    def send_email(
        self,
        to_email: str,
        subject: str,
        body: str,
        attachment_data: bytes = None,
        attachment_filename: str = None,
        company_id: int = None,
    ):
        if company_id is not None and not self._check_company_email_limit(company_id):
            logger.warning(
                f"Blocked email to {to_email}: company {company_id} exceeded daily limit"
            )
            return

        config = self.get_smtp_config()

        if not config["username"] or not config["password"]:
            logging.warning(
                f"--- MOCK EMAIL (No Params) ---\nTo: {to_email}\nSubject: {subject}"
            )
            return

        try:
            msg = MIMEMultipart()
            msg["From"] = config.get("from_email") or config["username"]
            msg["To"] = to_email
            msg["Subject"] = subject
            msg.attach(MIMEText(body, "html"))

            if attachment_data and attachment_filename:
                from email.mime.application import MIMEApplication

                part = MIMEApplication(attachment_data, Name=attachment_filename)
                part["Content-Disposition"] = (
                    f'attachment; filename="{attachment_filename}"'
                )
                msg.attach(part)

            server = smtplib.SMTP(config["server"], config["port"])
            server.starttls()
            server.login(config["username"], config["password"])
            server.send_message(msg)
            server.quit()
            logging.info(f"Email sent to {to_email}")
        except Exception as e:
            logging.error(f"Failed to send email: {e}")

    def send_password_reset_email(self, to_email: str, reset_token: str):
        reset_link = f"{settings.frontend_url}/auth/reset-password?token={reset_token}"
        subject = "Reset Your Candway Password"
        content = f"""
        <h2 style="margin:0 0 16px;font-size:22px;font-weight:700;color:#1e293b;">Reset Your Password</h2>
        <p style="margin:0 0 24px;color:#475569;font-size:15px;">
            You requested to reset your password. Click the button below to create a new password.
        </p>
        <p style="margin:0 0 24px;color:#64748b;font-size:14px;">
            If you didn't request this, please ignore this email. This link expires in 1 hour.
        </p>
        {btn_style(reset_link, "Reset Password")}
        <div style="margin-top:24px;padding:16px;background:#fef3c7;border-radius:8px;border-left:4px solid #f59e0b;">
            <p style="margin:0;font-size:13px;color:#92400e;">Security Notice: Never share this link with anyone. Candway will never ask for your password.</p>
        </div>
        """
        self.send_email(to_email, subject, wrap_in_template(content, subject))

    def send_verification_email(self, to_email: str, verification_token: str):
        verify_link = (
            f"{settings.frontend_url}/auth/verify-email?token={verification_token}"
        )
        subject = "Verify Your Candway Account"
        content = f"""
        <h2 style="margin:0 0 16px;font-size:22px;font-weight:700;color:#1e293b;">Verify Your Email</h2>
        <p style="margin:0 0 24px;color:#475569;font-size:15px;">
            Welcome to Candway! Please verify your email address to get started.
        </p>
        {btn_style(verify_link, "Verify Email")}
        <p style="margin:24px 0 0;color:#64748b;font-size:14px;">
            This link expires in 24 hours.
        </p>
        """
        self.send_email(to_email, subject, wrap_in_template(content, subject))

    def send_otp_email(self, to_email: str, otp_code: str):
        subject = f"{otp_code} is your Candway verification code"
        content = f"""
        <h2 style="margin:0 0 16px;font-size:24px;font-weight:800;color:#1e293b;text-align:center;">Verification Code</h2>
        <p style="margin:0 0 24px;color:#475569;font-size:16px;text-align:center;">
            Please use the code below to verify your email address.
        </p>
        <div style="margin:32px 0;text-align:center;">
            <div style="display:inline-block;background:#f1f5f9;padding:20px 40px;border-radius:16px;letter-spacing:12px;font-size:36px;font-weight:800;color:#4f46e5;border:2px solid #e2e8f0;">
                {otp_code}
            </div>
        </div>
        <p style="margin:24px 0 0;color:#94a3b8;font-size:14px;text-align:center;">
            This code will expire in 10 minutes. If you didn't request this, please ignore this email.
        </p>
        <div style="margin-top:32px;padding:16px;background:#f8fafc;border-radius:12px;text-align:center;">
            <p style="margin:0;font-size:12px;color:#64748b;">Security Tip: Never share your verification code with anyone. Candway staff will never ask for it.</p>
        </div>
        """
        self.send_email(to_email, subject, wrap_in_template(content, subject))

    def send_welcome_email(self, user):
        subject = "Welcome to Candway!"
        content = f"""
        <h2 style="margin:0 0 16px;font-size:26px;font-weight:800;color:#1e293b;">Welcome, {html.escape(get_user_name(user) or "Candidate")}! 🎉</h2>
        <p style="margin:0 0 24px;color:#475569;font-size:15px;">
            We're thrilled to have you on Candway - the AI-powered recruitment platform.
        </p>

        <div style="margin:24px 0;padding:24px;background:linear-gradient(135deg,#f0f9ff,#e0f2fe);border-radius:12px;border-left:4px solid #0ea5e9;">
            <p style="margin:0 0 12px;font-size:15px;color:#0369a1;font-weight:600;">Your AI-Powered Features:</p>
            <ul style="margin:0;padding-left:20px;color:#075985;font-size:14px;">
                <li style="margin-bottom:8px;">📄 AI CV Analysis & Scoring</li>
                <li style="margin-bottom:8px;">🤖 Practice AI Mock Interviews</li>
                <li style="margin-bottom:8px;">🎯 Smart Job Recommendations</li>
                <li>📚 Personalized Learning Paths</li>
            </ul>
        </div>

        {btn_style(settings.frontend_url + "/login-candidate.html", "Get Started →")}

        <p style="margin:24px 0 0;color:#64748b;font-size:14px;">
            Need help? Reply to this email or visit our <a href="{settings.frontend_url}/support.html" style="color:#4f46e5;">Support Center</a>.
        </p>
        """
        self.send_email(user.email, subject, wrap_in_template(content, subject))

    def send_payment_status_email(self, user, status, item_title):
        subject = f"Payment {status.title()}: {item_title}"
        is_approved = status == "active"
        color = "#10b981" if is_approved else "#ef4444"
        icon = "✅" if is_approved else "❌"

        status_text = "approved" if status == "active" else "declined"
        content = f"""
        <h2 style="margin:0 0 16px;font-size:22px;font-weight:700;color:#1e293b;">{icon} Payment {status.title()}</h2>
        <p style="margin:0 0 24px;color:#475569;font-size:15px;">
            Hello <strong>{html.escape(get_user_name(user))}</strong>,
        </p>
        <p style="margin:0 0 16px;color:#475569;font-size:15px;">
            Your payment for <strong>{html.escape(item_title)}</strong> has been <strong style="color:{color};">{status_text}</strong>.
        </p>
        {"<p>You now have full access to all premium features!</p>" if is_approved else "<p>Please check your payment proof and resubmit. Contact support if you need help.</p>"}
        <div style="margin:24px 0;">
            {btn_style(settings.frontend_url + "/candidate/subscription.html", "View Subscription") if is_approved else btn_style(settings.frontend_url + "/support.html", "Contact Support", False)}
        </div>
        """
        self.send_email(user.email, subject, wrap_in_template(content, subject))

    def send_subscription_status_email(self, user, status, reason=None):
        is_renewal = status == "renewal_reminder"
        is_pending_reminder = status == "pending_reminder"
        subject = (
            f"Subscription {status} 🎉"
            if status == "Succeeded"
            else (
                "Your subscription renews soon"
                if is_renewal
                else (
                    "Complete your payment — subscription pending"
                    if is_pending_reminder
                    else "Subscription Update"
                )
            )
        )
        is_approved = status == "Succeeded"

        if is_renewal:
            status_msg = """
        <p>Your <strong style="color:#4f46e5;">subscription period</strong> is ending soon.</p>
        <p>To keep your plan active, please submit your renewal payment before the period end date. A 3-day grace period follows, after which access is downgraded to the free plan.</p>
        """
        elif is_pending_reminder:
            status_msg = """
        <p>Your subscription <strong style="color:#4f46e5;">upgrade request is still awaiting approval</strong>.</p>
        <p>If you have not yet transferred the payment, please complete the bank transfer and upload your proof of payment so an admin can verify it.</p>
        """
        else:
            declined_reason = (
                f"<p><strong>Reason:</strong> {html.escape(reason)}</p>"
                if reason
                else ""
            )
            status_msg = (
                """
        <p>Congratulations! You are now a <strong style="color:#4f46e5;">PRO member</strong>.</p>
        <p>You have unlimited access to all premium features!</p>
        """
                if is_approved
                else f"""
        <p>Your upgrade request was declined. Please contact support for more information.</p>
        {declined_reason}
        """
            )

        content = f"""
        <h2 style="margin:0 0 16px;font-size:22px;font-weight:700;color:#1e293b;">{"🎉 " if is_approved else ""}Subscription {status}</h2>
        <p style="margin:0 0 24px;color:#475569;font-size:15px;">
            Hello <strong>{html.escape(get_user_name(user))}</strong>,
        </p>
        {status_msg}
        <div style="margin:24px 0;">
            {btn_style(settings.frontend_url + "/billing", "Go to Billing")}
        </div>
        """
        self.send_email(user.email, subject, wrap_in_template(content, subject))

    def send_course_approval_email(self, user_email, course_title):
        subject = f"Course Published: {course_title}"
        content = f"""
        <h2 style="margin:0 0 16px;font-size:22px;font-weight:700;color:#10b981;">🚀 Course Published!</h2>
        <p style="margin:0 0 24px;color:#475569;font-size:15px;">
            Great news! Your course <strong>{html.escape(course_title)}</strong> has been approved and is now live on Candway.
        </p>
        <p style="margin:0 0 24px;color:#475569;font-size:15px;">
            Students can now enroll and start learning. Good luck!
        </p>
        {btn_style(settings.frontend_url + "/mentor/mentor-courses.html", "View Course")}
        """
        self.send_email(user_email, subject, wrap_in_template(content, subject))

    def send_course_rejection_email(self, user_email, course_title):
        subject = f"Course Update: {course_title}"
        content = f"""
        <h2 style="margin:0 0 16px;font-size:22px;font-weight:700;color:#ef4444;">Course Returned for Revision</h2>
        <p style="margin:0 0 16px;color:#475569;font-size:15px;">
            Regarding your course <strong>{html.escape(course_title)}</strong>:
        </p>
        <p style="margin:0 0 16px;color:#475569;font-size:15px;">
            The admin team has reviewed your submission and requested some changes.
        </p>
        <p style="margin:0 0 24px;color:#64748b;font-size:14px;">
            Please check your dashboard for specific feedback and resubmit once updated.
        </p>
        {btn_style(settings.frontend_url + "/mentor/mentor-dashboard.html", "View Feedback")}
        """
        self.send_email(user_email, subject, wrap_in_template(content, subject))

    def send_ticket_reply_email(self, user_email, ticket_subject, reply_message):
        subject = f"Re: {ticket_subject} [Ticket Updated]"
        content = f"""
        <h2 style="margin:0 0 16px;font-size:22px;font-weight:700;color:#1e293b;">Support Update</h2>
        <p style="margin:0 0 24px;color:#475569;font-size:15px;">
            Hello,
        </p>
        <div style="margin:0 0 24px;padding:20px;background:#f8fafc;border-radius:12px;border-left:4px solid #4f46e5;">
            <p style="margin:0;color:#1e293b;font-size:15px;">{html.escape(reply_message)}</p>
        </div>
        <p style="margin:24px 0 0;color:#64748b;font-size:14px;">
            You can reply to this email to update the ticket.
        </p>
        """
        self.send_email(user_email, subject, wrap_in_template(content, subject))

    def send_campaign(self, to_email, subject, content):
        content_wrapped = wrap_in_template(
            f"""
        <h2 style="margin:0 0 16px;font-size:22px;font-weight:700;color:#1e293b;">{subject}</h2>
        <div style="color:#475569;font-size:15px;line-height:1.7;">{content}</div>
        """,
            subject,
        )
        self.send_email(to_email, subject, content_wrapped)

    def send_interview_complete_email(
        self,
        recruiter_email: str,
        candidate_name: str,
        campaign_title: str,
        final_score: float,
        dashboard_url: str,
        attachment_data: bytes = None,
        attachment_filename: str = None,
    ):
        """REC #3: Notify recruiter when a candidate completes their AI interview"""
        subject = f"Interview Complete: {candidate_name} — {campaign_title}"

        score_html = ""
        if final_score is not None:
            score_color = (
                "#10b981"
                if final_score >= 70
                else "#f59e0b"
                if final_score >= 50
                else "#ef4444"
            )
            score_html = f"""
                <div style="margin:16px 0 24px;padding:24px;background:#f8fafc;border-radius:12px;">
                    <p style="margin:0 0 8px;color:#64748b;font-size:14px;">AI Evaluation Score</p>
                    <div style="font-size:40px;font-weight:800;color:{score_color};">{final_score:.1f}%</div>
                </div>
            """

        attachment_msg = ""
        if attachment_data:
            attachment_msg = f'<p style="color:#64748b;font-size:14px;margin-bottom:16px;">📎 The full AI evaluation report ({attachment_filename}) is attached to this email.</p>'

        content = f"""
        <h2 style="margin:0 0 8px;font-size:22px;font-weight:700;color:#1e293b;">🎯 Interview Assessment Ready</h2>
        <p style="margin:0 0 24px;color:#475569;font-size:15px;">
            Candidate <strong>{html.escape(candidate_name)}</strong> has completed the <strong style="color:#4f46e5;">{html.escape(campaign_title)}</strong> interview.
        </p>
        {score_html}
        {attachment_msg}
        {btn_style(dashboard_url, "View Assessment →")}
        """
        self.send_email(
            recruiter_email,
            subject,
            wrap_in_template(content, "Interview Complete"),
            attachment_data,
            attachment_filename,
        )

    def send_candidate_completion_email(
        self,
        candidate_email: str,
        candidate_name: str,
        campaign_title: str,
        final_score: float,
        results_url: str,
    ):
        """FR #3: Notify the candidate when their AI interview is evaluated."""
        subject = f"Your AI Interview Results: {campaign_title}"

        score_html = ""
        if final_score is not None:
            score_color = (
                "#10b981"
                if final_score >= 70
                else "#f59e0b"
                if final_score >= 50
                else "#ef4444"
            )
            score_html = f"""
                <div style="margin:16px 0 24px;padding:24px;background:#f8fafc;border-radius:12px;">
                    <p style="margin:0 0 8px;color:#64748b;font-size:14px;">Your AI Evaluation Score</p>
                    <div style="font-size:40px;font-weight:800;color:{score_color};">{final_score:.1f}%</div>
                </div>
            """

        content = f"""
        <h2 style="margin:0 0 8px;font-size:22px;font-weight:700;color:#1e293b;">🎉 Your Interview Assessment Is Ready</h2>
        <p style="margin:0 0 24px;color:#475569;font-size:15px;">
            Thank you for completing the <strong style="color:#4f46e5;">{html.escape(campaign_title)}</strong>
            AI interview, <strong>{html.escape(candidate_name)}</strong>.
        </p>
        {score_html}
        <p style="margin:0 0 24px;color:#475569;font-size:15px;">
            Sign in with the credentials you used for the interview to view your full analysis,
            per-skill breakdown and feedback.
        </p>
        {btn_style(results_url, "View My Results →")}
        """
        self.send_email(
            candidate_email,
            subject,
            wrap_in_template(content, "Interview Results"),
        )

    def send_bulk_emails(
        self, recipients: list, subject: str, content: str, company_id: int = None
    ):
        """
        Send emails to multiple recipients using a single SMTP connection.
        recipients: list of {"email": str, "name": str} or just ["email", ...]
        """
        if company_id is not None and not self._check_company_email_limit(company_id):
            logger.warning(
                f"Blocked bulk email ({len(recipients)} recipients): company {company_id} exceeded daily limit"
            )
            return

        config = self.get_smtp_config()
        if not config["username"] or not config["password"]:
            logging.warning(
                f"--- MOCK BULK EMAIL ({len(recipients)} recipients) ---\nSubject: {subject}"
            )
            return

        import time

        try:
            # Single Connection
            server = smtplib.SMTP(config["server"], config["port"])
            server.starttls()
            server.login(config["username"], config["password"])

            count = 0
            for recipient in recipients:
                try:
                    to_email = (
                        recipient["email"] if isinstance(recipient, dict) else recipient
                    )

                    msg = MIMEMultipart()
                    msg["From"] = config.get("from_email") or config["username"]
                    msg["To"] = to_email
                    msg["Subject"] = subject

                    # Simple personalization if dict provided
                    body_content = content
                    if isinstance(recipient, dict):
                        if "name" in recipient:
                            body_content = body_content.replace(
                                "{name}", str(recipient["name"])
                            )

                        if "password" in recipient and recipient["password"]:
                            pw = str(recipient["password"])
                            body_content = (
                                body_content.replace("{{password}}", pw)
                                .replace("{{PASSWORD}}", pw)
                                .replace("{password}", pw)
                            )

                        if "email" in recipient:
                            em = str(recipient["email"])
                            body_content = (
                                body_content.replace("{{email}}", em)
                                .replace("{{EMAIL}}", em)
                                .replace("{email}", em)
                            )

                    # Use the professional template
                    html_body = wrap_in_template(
                        f"""
                    <h2 style="margin:0 0 16px;font-size:22px;font-weight:700;color:#1e293b;">{subject}</h2>
                    <div style="color:#475569;font-size:15px;line-height:1.7;">{body_content}</div>
                    """,
                        subject,
                    )

                    msg.attach(MIMEText(html_body, "html"))
                    server.send_message(msg)
                    count += 1

                    # Rate limiting (e.g. 20 emails per second max)
                    if count % 20 == 0:
                        time.sleep(1)

                except Exception as inner_e:
                    logging.error(f"Failed to send to {to_email}: {inner_e}")

            server.quit()
            logging.info(f"Bulk sent {count} emails successfully.")

        except Exception as e:
            logging.error(
                f"Bulk SMTP Connection Failed: ({config['server']}:{config['port']}) Error: {e}"
            )

    async def send_email_async(
        self,
        to_email: str,
        subject: str,
        body: str,
        attachment_data: bytes = None,
        attachment_filename: str = None,
    ):
        """Async wrapper that runs the synchronous send_email in a thread pool
        to avoid blocking the async event loop during SMTP I/O."""
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            None,
            self.send_email,
            to_email,
            subject,
            body,
            attachment_data,
            attachment_filename,
        )


# Singleton Instance (Crucial for imports)
email_service = EmailService()
