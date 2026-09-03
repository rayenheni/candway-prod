import html
from typing import List, Optional
from urllib.parse import quote

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.ai.llm import call_groq_cascade
from backend.authz import get_application_for_recruiter, get_job_for_recruiter
from backend.config import get_settings
from backend.database import (
    ActivityLog,
    Application,
    EvaluationResult,
    EvaluationSession,
    SystemConfig,
    User,
)
from backend.dependencies import (
    generate_interview_token,
    get_db,
    require_recruiter,
)
from backend.email_service import email_service
from backend.logger import logger
from backend.profile_helpers import (
    get_user_email,
    get_user_name,
    get_user_smtp_host,
    get_user_smtp_password,
    get_user_smtp_port,
    get_user_smtp_user,
)
from backend.routers.tracking import make_tracking_token
from backend.utils.account_service import ensure_candidate_account

settings = get_settings()
router = APIRouter(tags=["Recruiter Candidates"])


class InviteGenerationRequest(BaseModel):
    app_id: int
    template_id: Optional[int] = None


class EmailRequest(BaseModel):
    subject: str
    body: str


class BulkInviteRequest(BaseModel):
    application_ids: List[int]
    campaign_id: Optional[int] = None
    subject: str
    email_template: str


@router.post("/campaigns/{batch_id}/reinvite-unregistered")
async def reinvite_unregistered(
    batch_id: int,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    """Re-send invitation to all unregistered candidates in a campaign.
    FIX (MAJ-09): Enforces 24h per-candidate cooldown to prevent spam."""
    from backend.config import get_settings
    from backend.dependencies import generate_interview_token
    from backend.email_service import email_service

    settings = get_settings()

    from backend.authz import get_batch_for_recruiter

    batch = get_batch_for_recruiter(batch_id, recruiter, db)
    if not batch:
        raise HTTPException(status_code=404, detail="Campaign not found")

    candidates = (
        db.query(Application)
        .filter(
            Application.batch_id == batch_id,
            Application.email.notlike("%@import.local%"),
            Application.status.in_(["imported", "pending"]),
        )
        .all()
    )

    # SECURITY FIX (MAJ-09): 24h per-candidate cooldown via Redis.
    REINVITE_COOLDOWN_SECONDS = 86400  # 24 hours
    redis_client = None
    try:
        import redis

        redis_client = redis.Redis.from_url(
            settings.redis_url
            if hasattr(settings, "redis_url")
            else "redis://localhost:6379/0",
            socket_connect_timeout=2,
            socket_timeout=2,
        )
        redis_client.ping()
    except Exception:
        redis_client = None  # Fall through to send without cooldown (log a warning)
        logger.warning(
            "Reinvite: Redis unavailable, cooldown not enforced for batch=%s", batch_id
        )

    sent = 0
    skipped_cooldown = 0
    failed = []

    for app in candidates:
        is_registered = bool(app.owner and app.owner.hashed_password)
        if is_registered:
            continue  # Skip already registered

        # Ensure user has a temp password
        generated_password = None
        if app.owner and not app.owner.hashed_password:
            if not app.owner.temp_password:
                import secrets
                import string

                import bcrypt

                generated_password = "".join(
                    secrets.choice(string.ascii_letters + string.digits + "!@#$%^&*")
                    for _ in range(12)
                )
                app.owner.temp_password = generated_password
                app.owner.hashed_password = bcrypt.hashpw(
                    generated_password.encode("utf-8"), bcrypt.gensalt()
                ).decode("utf-8")
                db.commit()
            else:
                generated_password = app.owner.temp_password

        # Check cooldown
        if redis_client:
            cooldown_key = f"reinvite_cooldown:app:{app.id}"
            try:
                if redis_client.exists(cooldown_key):
                    skipped_cooldown += 1
                    continue
            except Exception:
                pass  # Redis error — allow send

        try:
            token_data = generate_interview_token(app.id)
            token = token_data["token"]
            access_url = f"{settings.frontend_url}/auth/interview-access?app_id={app.id}&token={token}"

            subject = f"🔔 Reminder: Complete Your AI Interview - {batch.title}"
            login_section = ""
            if generated_password:
                login_section = """
                <div style="background:#f0fdf4;border:1px solid #bbf7d0;color:#166534;border-radius:10px;padding:14px 16px;margin:0 0 20px">
                    <strong>One-Click Login:</strong><br>
                    Click the button below to sign in and start your interview instantly.
                </div>
                """
            body = f"""
            <div style="font-family:'Segoe UI',Arial,sans-serif;max-width:600px;margin:0 auto;background:#fff;border-radius:16px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,0.08)">
                <div style="background:linear-gradient(135deg,#4f46e5,#7c3aed);padding:36px 32px;text-align:center">
                    <h1 style="color:#fff;margin:0;font-size:26px;font-weight:800">Complete Your AI Interview</h1>
                    <p style="color:rgba(255,255,255,0.8);margin:8px 0 0;font-size:15px">Powered by Candway Intelligence</p>
                </div>
                <div style="padding:36px 32px">
                    <p style="font-size:16px;color:#1e293b;margin:0 0 12px">Dear <strong>{app.full_name or "Candidate"}</strong>,</p>
                    <p style="font-size:15px;color:#475569;line-height:1.7;margin:0 0 24px">
                        We noticed you haven't completed your AI interview for the <strong>{batch.target_role or batch.title}</strong> position.
                        It's quick and convenient - just 20-30 minutes!
                    </p>
                    {login_section}
                    <div style="text-align:center;margin:32px 0">
                        <a href="{access_url}"
                           style="background:linear-gradient(135deg,#4f46e5,#7c3aed);color:#fff;padding:16px 40px;
                                  text-decoration:none;border-radius:12px;font-weight:700;font-size:16px;
                                  display:inline-block;box-shadow:0 8px 24px rgba(79,70,229,0.35)">
                            Start Your AI Interview →
                        </a>
                    </div>
                    <p style="font-size:13px;color:#94a3b8;margin:0">
                            Best regards,<br><strong>{get_user_name(recruiter) or "The Recruiting Team"}</strong> via Candway Platform
                    </p>
                </div>
            </div>
            """

            email_service.send_email(app.email, subject, body)

            # Clear temp password after sending
            if app.owner and app.owner.temp_password:
                app.owner.temp_password = None

            # Set cooldown key
            if redis_client:
                try:
                    redis_client.setex(
                        f"reinvite_cooldown:app:{app.id}",
                        REINVITE_COOLDOWN_SECONDS,
                        "1",
                    )
                except Exception:
                    pass
            sent += 1

        except Exception:
            failed.append(
                {"app_id": app.id, "email": app.email, "reason": "Email send failed"}
            )

    db.commit()

    # Notify recruiter with bulk summary
    if sent > 0:
        try:
            from backend.notifications import notify_user

            await notify_user(
                str(recruiter.id),
                f"Sent {sent} interview reminders",
                title="Reminders Sent",
                level="success",
                body=f"Campaign: {batch.title}\nTotal Sent: {sent}\nSkipped (Cooldown): {skipped_cooldown}\nFailed: {len(failed)}\n\nContent: Reminder for candidates to complete their AI Interview.",
            )
        except Exception as ne:
            logger.error(f"Failed to notify recruiter: {ne}")

    return {
        "success": True,
        "sent": sent,
        "skipped_cooldown": skipped_cooldown,
        "failed": failed,
    }


@router.post("/applications/bulk-invite")
def send_bulk_invite(
    request: BulkInviteRequest,
    background_tasks: BackgroundTasks,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    # SECURITY FIX (MAJ-04): Hard cap on bulk emails per request to prevent spam weaponisation.
    MAX_BULK_RECIPIENTS = 500
    if len(request.application_ids) > MAX_BULK_RECIPIENTS:
        raise HTTPException(
            status_code=400,
            detail=f"Bulk invite limited to {MAX_BULK_RECIPIENTS} recipients per request.",
        )

    # 1. Validate Campaign/Job
    if request.campaign_id:
        from backend.authz import get_batch_for_recruiter

        try:
            get_batch_for_recruiter(request.campaign_id, recruiter, db)
        except HTTPException:
            raise HTTPException(404, "Campaign not found")
    # 2. Process Candidates
    recipients = []
    skipped = 0
    for app_id in request.application_ids:
        try:
            app = get_application_for_recruiter(app_id, recruiter, db)
        except HTTPException:
            logger.warning(
                f"[SECURITY] Recruiter {recruiter.id} attempted to invite unauthorized application {app_id}"
            )
            skipped += 1
            continue
        # Get email
        email = app.email
        if not email:
            user = db.query(User).filter(User.id == app.user_id).first()
            if user:
                email = get_user_email(user)
        if email:
            # --- Personalization: Ensure account exists & get password ---
            candidate_user, plain_password = ensure_candidate_account(
                db, email, app.full_name or "Candidate"
            )

            # Link app to user if not linked
            if not app.user_id and candidate_user:
                app.user_id = candidate_user.id

            recipients.append(
                {
                    "email": email,
                    "name": app.full_name or "Candidate",
                    "password": plain_password or "Your existing password",
                }
            )
            # Update status and pre-start session/snapshot
            app.status = "invited"
            try:
                from backend.rubric.interview_starter import InterviewStarter

                InterviewStarter.start(db, app)
            except Exception as e:
                logger.warning(
                    f"InterviewStarter pre-start failed in bulk_invite for app {app.id}: {e}"
                )
                existing_session = (
                    db.query(EvaluationSession)
                    .filter(EvaluationSession.application_id == app.id)
                    .first()
                )
                if not existing_session:
                    db.add(
                        EvaluationSession(
                            application_id=app.id,
                            company_id=app.company_id,
                            rubric_id=app.rubric_id,
                            status="pending",
                            interview_state="not_started",
                        )
                    )

            # Log activity
            log_entry = ActivityLog(
                user_id=recruiter.id,
                company_id=app.company_id,
                action="bulk_invite",
                details=f"Invited candidate {app.id} to interview",
            )
            db.add(log_entry)
        else:
            skipped += 1
    db.commit()
    if not recipients:
        raise HTTPException(status_code=400, detail="No valid recipients found.")

    # 3. Queue Real Sending
    background_tasks.add_task(
        email_service.send_bulk_emails,
        recipients,
        request.subject,
        # If using rich text editor, content is HTML
        request.email_template,
    )
    return {
        "message": f"Bulk invite started for {len(recipients)} candidates.",
        "skipped": skipped,
    }


@router.post("/generate-invitation")
async def generate_invitation(
    req: InviteGenerationRequest,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    app = get_application_for_recruiter(req.app_id, recruiter, db)
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")

    user = db.query(User).filter(User.id == app.user_id).first()
    candidate_name = (get_user_name(user) if user else app.full_name) or "Candidate"
    job_title = (
        app.job.title if app.job else getattr(app.cv_document, "declared_role", None)
    ) or "the position"
    company_name = (
        getattr(getattr(recruiter, "recruiter_profile", None), "company_name", None)
        or "our company"
    )
    system_prompt = f"""You are a recruiter for {company_name}. Draft a professional invite email for {candidate_name} applying for {job_title}.
    Using only JSON. return 'subject' and 'body'.
    IMPORTANT: Include these placeholders:
    - Interview Link: {{INTERVIEW_LINK}}
    - Login Email: {{EMAIL}}
    - Temporary Password: {{PASSWORD}}
    Explain that they MUST login using these credentials first to access their secure interview portal.
    """
    user_prompt = "Draft the invitation email."

    credit_tx = None
    try:
        from backend.credit_service import consume_credits_or_402, rollback_credits

        credit_tx = consume_credits_or_402(
            db,
            recruiter,
            1,
            "ai_invitation",
            reference_type="application",
            reference_id=req.app_id,
        )
        data = await call_groq_cascade(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            json_mode=True,
        )
        return {
            "subject": data.get("subject", f"Interview: {job_title}"),
            "body": data.get(
                "body", f"Dear {candidate_name}, join us: {{INTERVIEW_LINK}}"
            ),
        }
    except HTTPException:
        raise
    except Exception as e:
        if credit_tx is not None:
            try:
                rollback_credits(db, credit_tx)
            except Exception:
                pass
        logger.error(f"Error generating invitation: {e}")
        return {
            "subject": f"Interview: {job_title}",
            "body": f"Dear {candidate_name}, please join: {{INTERVIEW_LINK}}",
        }


@router.post("/send-invitation")
async def send_invitation_email(
    request: Request,
    app_id: int = Query(...),
    email_data: EmailRequest = None,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    app = get_application_for_recruiter(app_id, recruiter, db)
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")

    try:
        from backend.dependencies import generate_interview_token

        base_url = str(request.base_url).rstrip("/")
        token_data = generate_interview_token(app.id)
        token = token_data["token"]
        tracking_token = make_tracking_token(app.id)
        click_url = f"{base_url}/api/v1/track/click/{tracking_token}?token={token}&email={quote(app.email or '')}"
        open_pixel_url = f"{base_url}/api/v1/track/open/{tracking_token}"
        return _send_invite_helper(
            recruiter, app, email_data, click_url, open_pixel_url, db
        )
    except Exception as e:
        logger.error(f"Failed to send invitation: {e}")
        raise HTTPException(status_code=500, detail="Failed to send email")


def _send_invite_helper(
    current_user: User,
    app: Application,
    email_data: EmailRequest,
    click_url: str,
    open_pixel_url: str,
    db: Session,
):
    import smtplib
    import socket
    import ssl
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText

    # --- Personalization: Ensure account exists & get password ---
    email = app.email
    candidate_user, plain_password = ensure_candidate_account(
        db, email, app.full_name or "Candidate"
    )

    # Link app to user if not linked
    if not app.user_id and candidate_user:
        app.user_id = candidate_user.id
        db.commit()

    if not email_data or not email_data.body:
        email_data = EmailRequest(
            subject="You're Invited! - AI Interview",
            body="<p>Dear Candidate,</p><p>You have been invited for an AI-powered interview. Please click the button below to start.</p>",
        )
    is_html = email_data.body.strip().startswith("<")
    button_html = f'<a href="{click_url}" style="display:inline-block; background:#4f46e5; color:white; padding:12px 24px; border-radius:6px; text-decoration:none; font-weight:bold;">Start AI Interview</a>'

    password_text = plain_password or "Your existing password"

    if is_html:
        content_html = email_data.body.replace("{{INTERVIEW_LINK}}", click_url).replace(
            "{INTERVIEW_LINK}", click_url
        )
        content_html = content_html.replace("{{PASSWORD}}", password_text).replace(
            "{{EMAIL}}", email
        )
        plain_content = "Please enable HTML to view this interview invitation."
    else:
        raw_body = email_data.body.replace("{{INTERVIEW_LINK}}", click_url).replace(
            "{INTERVIEW_LINK}", click_url
        )
        raw_body = raw_body.replace("{{PASSWORD}}", password_text).replace(
            "{{EMAIL}}", email
        )
        plain_content = raw_body
        content_html = raw_body.replace("\n", "<br>") + f"<br><br>{button_html}"

    # Premium SaaS Branded Wrapper (Apply only if not already wrapped/templated)
    if "CANDWAY" in content_html.upper() or "<TABLE" in content_html.upper():
        html_content = content_html
    else:
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <meta http-equiv="Content-Type" content="text/html; charset=UTF-8">
        </head>
        <body style="margin: 0; padding: 0; background-color: #F8F9FC; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;">
            <table border="0" cellpadding="0" cellspacing="0" width="100%" style="background-color: #F8F9FC; background-image: radial-gradient(#E5E7EB 1px, transparent 1px); background-size: 20px 20px;">
                <tr>
                    <td align="center" style="padding: 40px 0;">
                        <table border="0" cellpadding="0" cellspacing="0" width="100%" style="max-width: 600px; background-color: #ffffff; border: 1px solid #E5E7EB; border-radius: 16px; overflow: hidden; box-shadow: 0 4px 20px rgba(0, 0, 0, 0.05);">
                            <!-- Logo -->
                            <tr>
                                <td align="center" style="padding: 40px 0 20px 0;">
                                    <h1 style="margin: 0; font-size: 20px; font-weight: 800; color: #4F46E5; letter-spacing: -0.02em;">CANDWAY</h1>
                                </td>
                            </tr>
                            <!-- Content -->
                            <tr>
                                <td style="padding: 0 40px 40px 40px; color: #4B5563; font-size: 16px; line-height: 1.6;">
                                    {content_html}
                                </td>
                            </tr>
                            <!-- Footer -->
                            <tr>
                                <td align="center" style="padding: 30px; background-color: #f9fafb; border-top: 1px solid #E5E7EB; border-radius: 0 0 16px 16px;">
                                    <p style="margin: 0; font-size: 12px; color: #9CA3AF;">&copy; 2024 Candway Intelligence Platform. All rights reserved.</p>
                                </td>
                            </tr>
                        </table>
                    </td>
                </tr>
            </table>
        </body>
        </html>
        """

    # Always ensure open pixel is tracked
    if open_pixel_url not in html_content:
        html_content += f'<img src="{open_pixel_url}" width="1" height="1" style="display:none !important;">'

    # Fallback Logic
    smtp_host = get_user_smtp_host(current_user)
    smtp_port = get_user_smtp_port(current_user)
    smtp_user = get_user_smtp_user(current_user)
    smtp_password = get_user_smtp_password(current_user)

    if not all([smtp_host, smtp_user, smtp_password]):
        configs = db.query(SystemConfig).all()
        settings_dict = {c.key: c.value for c in configs}
        smtp_host = settings_dict.get("smtp_host")
        smtp_port = settings_dict.get("smtp_port")
        smtp_user = settings_dict.get("smtp_username")
        smtp_password = settings_dict.get("smtp_password")
        # The password may be Fernet-encrypted (admin save path encrypts it).
        from backend.secret_encryption import decrypt_value as _decrypt

        if smtp_password and smtp_password.startswith("gAAAA"):
            smtp_password = (
                _decrypt(smtp_password, get_settings().secret_key) or smtp_password
            )
        try:
            smtp_port = int(smtp_port) if smtp_port else 587
        except (TypeError, ValueError):
            smtp_port = 587
        if not all([smtp_host, smtp_user, smtp_password]):
            # Fail softly but honestly
            logger.error(
                "SMTP Configuration Missing for both Recruiter and System. Email NOT sent."
            )
            raise HTTPException(
                status_code=500, detail="Email not sent: SMTP not configured."
            )

    message = MIMEMultipart("alternative")
    message["Subject"] = email_data.subject
    message["From"] = smtp_user
    user = db.query(User).filter(User.id == app.user_id).first()
    to_email = get_user_email(user) if user else app.email
    if not to_email:
        raise ValueError("No email")
    message["To"] = to_email
    message.attach(MIMEText(plain_content, "plain"))
    message.attach(MIMEText(html_content, "html"))

    try:
        context = ssl.create_default_context()
        socket.setdefaulttimeout(30)
        with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as server:
            server.starttls(context=context)
            server.login(smtp_user, smtp_password)
            server.sendmail(smtp_user, to_email, message.as_string())
    except Exception as e:
        logger.error(f"SMTP Error sending invitation: {e}")
        raise HTTPException(
            status_code=502, detail="Failed to send email. Check SMTP configuration."
        )
    app.status = "invited"
    db.commit()
    return {"message": "Invitation sent successfully", "new_status": "invited"}


# ---------------------------------------------------------------------------
# Recruiter-controlled AI interview invitations
# ---------------------------------------------------------------------------
# Candidates who self-apply to public jobs must be explicitly invited by the
# recruiter before they can start the AI interview (chat/resume gate on the
# application status being in {invited, interviewing}). The campaign invite
# flow (recruiter_campaigns/candidates.py) is the canonical pattern: it creates
# (or reuses) the EvaluationSession, generates a single-use interview token,
# emails the access link, and moves the application to "invited". These generic
# endpoints expose the same behaviour for job applications (no campaign).


class InterviewInviteRequest(BaseModel):
    application_ids: List[int]


class QualifiedInviteRequest(BaseModel):
    threshold: float = 70.0


def _utcnow():
    from datetime import UTC, datetime

    return datetime.now(UTC)


def _invite_app_for_interview(
    app: Application, recruiter: User, db: Session
) -> dict:
    """Invite one application to its AI interview (shared by all invite paths).

    Creates/reuses the EvaluationSession, generates the access link, emails the
    candidate, and moves the application to "invited". Raises HTTPException on
    placeholder emails or missing recipient.
    """
    if app.email and app.email.endswith("@import.local"):
        raise HTTPException(
            status_code=400,
            detail="Cannot invite candidate with placeholder email. Please update their email first.",
        )
    if not app.email:
        raise HTTPException(
            status_code=400, detail="Candidate has no email address to invite."
        )

    token_data = generate_interview_token(app.id)
    token = token_data["token"]
    access_url = f"{settings.frontend_url}/auth/interview-access?app_id={app.id}&token={token}"

    candidate_user, plain_password = ensure_candidate_account(
        db, app.email, app.full_name or "Candidate"
    )

    if not app.user_id and candidate_user:
        app.user_id = candidate_user.id
        db.commit()

    candidate_name = get_user_name(candidate_user) or app.full_name or "Candidate"
    if candidate_name.startswith("Name: "):
        candidate_name = candidate_name[6:].strip()
    recruiter_name = get_user_name(recruiter) or "The Recruiting Team"

    job_title = (
        app.job.title
        if app.job
        else getattr(getattr(app, "cv_document", None), "declared_role", None)
    ) or "the position"

    is_registered = plain_password is None
    password_block = ""
    if plain_password:
        password_block = f"""
            <div style="margin:0 0 24px;padding:16px;background:#f8fafc;border:1px solid #e2e8f0;border-radius:12px;">
                <p style="margin:0 0 8px;font-size:13px;color:#64748b;font-weight:600;">YOUR LOGIN DETAILS</p>
                <p style="margin:0 0 4px;font-size:14px;color:#1e293b;">Email: <strong>{html.escape(app.email)}</strong></p>
                <p style="margin:0;font-size:14px;color:#1e293b;">Temporary password: <strong>{html.escape(plain_password)}</strong></p>
                <p style="margin:8px 0 0;font-size:12px;color:#94a3b8;">Use these to sign in afterwards and view your interview results. You can change your password once signed in.</p>
            </div>
        """

    subject = f"🚀 Invitation to AI Interview: {job_title}"
    account_text = (
        "Click the button below to start your interview. Your login details are shown below, "
        "so you can sign in afterwards and view your interview results."
        if plain_password
        else "Click the button below to start your interview. An account already exists for this email — "
        "sign in with your existing password afterwards to view your interview results."
    )

    email_body = f"""
    <div style="font-family:'Segoe UI',Arial,sans-serif;max-width:600px;margin:0 auto;background:#fff;border-radius:16px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,0.08)">
        <div style="background:linear-gradient(135deg,#4f46e5,#7c3aed);padding:36px 32px;text-align:center">
            <h1 style="color:#fff;margin:0;font-size:26px;font-weight:800;letter-spacing:-0.5px">AI Interview Invitation</h1>
            <p style="color:rgba(255,255,255,0.8);margin:8px 0 0;font-size:15px">Powered by Candway Intelligence</p>
        </div>
        <div style="padding:36px 32px">
            <p style="font-size:16px;color:#1e293b;margin:0 0 12px">Dear <strong>{candidate_name}</strong>,</p>
            <p style="font-size:15px;color:#475569;line-height:1.7;margin:0 0 24px">
                We have reviewed your profile and are pleased to invite you to an AI-powered interview for the
                <strong>{html.escape(job_title)}</strong> position.
            </p>
            <p style="font-size:15px;color:#475569;line-height:1.7;margin:0 0 24px">
                {account_text}
            </p>
            {password_block}
            <div style="text-align:center;margin:32px 0">
                <a href="{access_url}"
                   style="background:linear-gradient(135deg,#4f46e5,#7c3aed);color:#fff;padding:16px 40px;
                          text-decoration:none;border-radius:12px;font-weight:700;font-size:16px;
                          display:inline-block;box-shadow:0 8px 24px rgba(79,70,229,0.35)">
                    Start Your AI Interview →
                </a>
            </div>
            <hr style="border:0;border-top:1px solid #f1f5f9;margin:32px 0">
            <p style="font-size:13px;color:#94a3b8;margin:0">
                Best regards,<br><strong style="color:#475569">{recruiter_name}</strong> via Candway Platform
            </p>
        </div>
    </div>
    """

    try:
        from backend.rubric.interview_starter import InterviewStarter

        InterviewStarter.start(db, app)
    except Exception as e:
        logger.warning(
            f"InterviewStarter pre-start failed for app {app.id}: {e}"
        )
        existing_session = (
            db.query(EvaluationSession)
            .filter(EvaluationSession.application_id == app.id)
            .first()
        )
        if not existing_session:
            db.add(
                EvaluationSession(
                    application_id=app.id,
                    company_id=app.company_id,
                    rubric_id=app.rubric_id,
                    status="pending",
                    interview_state="not_started",
                )
            )

    email_service.send_email(app.email, subject, email_body)
    app.status = "invited"
    app.invited_at = _utcnow()

    log_entry = ActivityLog(
        user_id=recruiter.id,
        company_id=app.company_id,
        action="invite_interview",
        details=f"Invited candidate {app.id} to AI interview for {job_title}",
    )
    db.add(log_entry)

    return {
        "success": True,
        "application_id": app.id,
        "access_url": access_url,
        "candidate_registered": is_registered,
    }


@router.post("/applications/{app_id}/invite-interview")
def invite_application_to_interview(
    app_id: int,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    """Invite a single job application to its AI interview."""
    app = get_application_for_recruiter(app_id, recruiter, db)
    result = _invite_app_for_interview(app, recruiter, db)
    db.commit()
    logger.info(
        f"Interview invite sent to app {app_id} by recruiter {recruiter.id}"
    )
    return result


@router.post("/applications/invite-interviews")
def invite_applications_to_interview(
    request: InterviewInviteRequest,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    """Invite multiple selected applications to their AI interviews."""
    MAX_BULK = 500
    if len(request.application_ids) > MAX_BULK:
        raise HTTPException(
            status_code=400,
            detail=f"Bulk invite limited to {MAX_BULK} recipients per request.",
        )
    invited = []
    skipped = []
    for app_id in request.application_ids:
        try:
            app = get_application_for_recruiter(app_id, recruiter, db)
            result = _invite_app_for_interview(app, recruiter, db)
            invited.append(result)
        except HTTPException as exc:
            skipped.append(
                {
                    "application_id": app_id,
                    "reason": exc.detail,
                }
            )
            continue
    db.commit()
    if not invited:
        raise HTTPException(
            status_code=400,
            detail="No valid recipients found to invite.",
        )
    return {
        "message": f"Interview invites sent to {len(invited)} candidates.",
        "invited": invited,
        "skipped": skipped,
    }


@router.post("/jobs/{job_id}/invite-qualified")
def invite_qualified_candidates(
    job_id: int,
    request: QualifiedInviteRequest = None,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    """Invite candidates whose CV score meets a threshold for a job.

    Only applications in recruiter-reviewable pre-interview statuses are
    considered; already-invited/interviewing/rejected/withdrawn applications
    are left untouched. Default threshold is 70.
    """
    if request is None:
        request = QualifiedInviteRequest()
    threshold = request.threshold if request.threshold is not None else 70.0

    job = get_job_for_recruiter(job_id, recruiter, db)
    eligible_statuses = [
        "applied",
        "analyzing",
        "screening",
        "analyzed",
        "reviewed",
    ]
    apps = (
        db.query(Application)
        .join(
            EvaluationSession,
            EvaluationSession.application_id == Application.id,
        )
        .join(
            EvaluationResult,
            EvaluationResult.evaluation_session_id == EvaluationSession.id,
        )
        .filter(
            Application.job_id == job.id,
            Application.company_id == job.company_id,
            EvaluationResult.cv_score.isnot(None),
            EvaluationResult.cv_score >= threshold,
            Application.status.in_(eligible_statuses),
        )
        .distinct()
        .all()
    )

    invited = []
    skipped = []
    for app in apps:
        try:
            result = _invite_app_for_interview(app, recruiter, db)
            invited.append(result)
        except HTTPException as exc:
            skipped.append(
                {
                    "application_id": app.id,
                    "reason": exc.detail,
                }
            )
            continue
    db.commit()
    return {
        "message": f"{len(invited)} qualified candidate(s) invited for '{job.title}'.",
        "job_id": job.id,
        "threshold": threshold,
        "candidates_considered": len(apps),
        "invited": invited,
        "skipped": skipped,
    }
