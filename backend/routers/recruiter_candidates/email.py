import itertools
import json
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.authz import get_batch_for_recruiter
from backend.config import get_settings
from backend.database import Application, User
from backend.dependencies import get_db, require_recruiter
from backend.email_service import btn_style, email_service, wrap_in_template
from backend.logger import logger
from backend.models.evaluation.profile import RecruiterProfile

settings = get_settings()
router = APIRouter(tags=["Recruiter Candidates"])

STATUS_EMAIL_TEMPLATES = {
    "pending": {
        "subject": "Application Received - We're Reviewing Your Profile",
        "emoji": "",
        "title": "Thank You for Applying!",
        "description": "We've received your application for <strong>{job_title}</strong> and our team is currently reviewing your profile.",
        "action": "We'll keep you updated on any progress. Thank you for your interest in {company_name}!",
        "color": "#3b82f6",
    },
    "screening": {
        "subject": "Great News! Your Application Passed Initial Screening",
        "emoji": "",
        "title": "You've Passed Initial Screening!",
        "description": "Congratulations! Your application for <strong>{job_title}</strong> has passed our initial screening phase.",
        "action": "Our team will be in touch soon with next steps. Stay tuned!",
        "color": "#10b981",
    },
    "interviewing": {
        "subject": "Interview Invitation - You're Invited!",
        "emoji": "",
        "title": "You're Invited to Interview!",
        "description": "Congratulations! You've been selected to interview for <strong>{job_title}</strong>.",
        "action": "Please log in to your candidate portal to schedule your interview slot.",
        "button_text": "Schedule Interview",
        "button_url": "/candidate/dashboard",
        "color": "#8b5cf6",
    },
    "shortlisted": {
        "subject": "You've Been Shortlisted! - Next Steps Coming",
        "emoji": "",
        "title": "You've Been Shortlisted!",
        "description": "Great news! You've made the shortlist for <strong>{job_title}</strong>. The hiring team is impressed with your qualifications.",
        "action": "We'll be in touch soon with interview details. Prepare for the next step!",
        "color": "#f59e0b",
    },
    "offer": {
        "subject": "Job Offer - Congratulations!",
        "emoji": "",
        "title": "We Want to Hire You!",
        "description": "We're thrilled to offer you the position of <strong>{job_title}</strong> at {company_name}!",
        "action": "Please check your candidate portal to review the offer details and accept.",
        "button_text": "View Offer Details",
        "button_url": "/candidate/dashboard",
        "color": "#ec4899",
    },
    "hired": {
        "subject": "Welcome Aboard! - You're Hired!",
        "emoji": "",
        "title": "Welcome to the Team!",
        "description": "Congratulations! Your application for <strong>{job_title}</strong> has been successful. We're excited to have you join us!",
        "action": "The HR team will contact you shortly with onboarding details and next steps.",
        "color": "#14b8a6",
    },
    "rejected": {
        "subject": "Application Update - Thank You",
        "emoji": "",
        "title": "Thank You for Your Interest",
        "description": "Thank you for applying for <strong>{job_title}</strong>. After careful consideration, we've decided to move forward with other candidates at this time.",
        "action": "We encourage you to apply for other positions that match your skills. We wish you the best in your career journey!",
        "color": "#64748b",
    },
    "invited": {
        "subject": "You're Invited! - Complete Your Profile",
        "emoji": "",
        "title": "You're Invited to Apply!",
        "description": "You've been invited to apply for <strong>{job_title}</strong> at {company_name}.",
        "action": "Please complete your profile to start the application process.",
        "button_text": "Complete Profile",
        "button_url": "/candidate/onboarding",
        "color": "#6366f1",
    },
    "withdrawn": {
        "subject": "Application Withdrawn",
        "emoji": "",
        "title": "Application Withdrawn",
        "description": "Your application for <strong>{job_title}</strong> has been withdrawn.",
        "action": "If this was a mistake, please contact the recruiter.",
        "color": "#f97316",
    },
    "accepted": {
        "subject": "Offer Accepted - Welcome Aboard!",
        "emoji": "",
        "title": "Offer Accepted - Welcome!",
        "description": "Thank you for accepting the offer for <strong>{job_title}</strong>! We're excited to have you join the team.",
        "action": "HR will be in touch soon with onboarding details.",
        "color": "#10b981",
    },
    "applied": {
        "subject": "Application Submitted Successfully",
        "emoji": "",
        "title": "Application Submitted!",
        "description": "Your application for <strong>{job_title}</strong> has been submitted successfully.",
        "action": "We'll review your application and get back to you soon.",
        "color": "#3b82f6",
    },
}


def get_status_email_content(
    status: str, job_title: str, company_name: str = "the company"
) -> tuple:
    status = status.lower().strip()
    template = STATUS_EMAIL_TEMPLATES.get(status)

    if not template:
        subject = f"Application Status Update - {status.title()}"
        content = f"""
        <h2 style="margin:0 0 16px;font-size:22px;font-weight:700;color:#1e293b;">Status Update</h2>
        <p style="margin:0 0 16px;color:#475569;font-size:15px;">
            Your application for <strong>{job_title}</strong> status has been updated to: <strong>{status.upper()}</strong>
        </p>
        <p style="margin:0;color:#64748b;font-size:14px;">
            Please log in to your candidate portal for more details.
        </p>
        {btn_style(f"{settings.frontend_url}/candidate/dashboard", "View Dashboard")}
        """
        return subject, content

    button_html = ""
    if template.get("button_text") and template.get("button_url"):
        button_html = btn_style(
            f"{settings.frontend_url}{template['button_url']}", template["button_text"]
        )

    subject = template["subject"].format(job_title=job_title, company_name=company_name)
    content = f"""
    <div style="text-align:center;margin-bottom:24px;">
        <span style="font-size:48px;">{template["emoji"]}</span>
    </div>
    <h2 style="margin:0 0 16px;font-size:24px;font-weight:700;color:{template["color"]};text-align:center;">
        {template["title"]}
    </h2>
    <p style="margin:0 0 20px;color:#475569;font-size:16px;text-align:center;line-height:1.7;">
        {template["description"].format(job_title=job_title, company_name=company_name)}
    </p>
    <div style="background:linear-gradient(135deg,#f8fafc,#f1f5f9);border-radius:12px;padding:20px;margin:24px 0;text-align:center;">
        <p style="margin:0;color:#64748b;font-size:15px;font-weight:500;">
            {template["action"].format(job_title=job_title, company_name=company_name)}
        </p>
    </div>
    {button_html}
    <div style="margin-top:32px;padding-top:20px;border-top:1px solid #e2e4e8;text-align:center;">
        <p style="margin:0;font-size:13px;color:#94a3b8;">
            Current Status: <strong style="color:{template["color"]};">{status.upper()}</strong>
        </p>
    </div>
    """
    return subject, content


def get_recruiter_email_settings(db: Session, recruiter_id: int) -> dict:
    from backend.profile_helpers import get_user_email_settings

    user = db.query(User).filter(User.id == recruiter_id).first()
    if not user:
        return {"auto_email_enabled": True, "templates": {}}
    raw = get_user_email_settings(user)
    if not raw:
        return {"auto_email_enabled": True, "templates": {}}
    try:
        import json

        return json.loads(raw)
    except Exception:
        return {"auto_email_enabled": True, "templates": {}}


def save_recruiter_email_settings(db: Session, recruiter_id: int, settings: dict):
    profile = (
        db.query(RecruiterProfile)
        .filter(RecruiterProfile.user_id == recruiter_id)
        .first()
    )
    if profile:
        payload = json.dumps(settings)
        profile.email_settings = payload
        db.commit()


# === HELPER: SEND STATUS EMAIL WITH CUSTOM TEMPLATES ===
def send_status_email(
    db: Session,
    recruiter_id: int,
    candidate_email: str,
    status: str,
    job_title: str,
    company_name: str,
    background_tasks: BackgroundTasks,
):
    recruiter_settings = get_recruiter_email_settings(db, recruiter_id)
    if not recruiter_settings.get("auto_email_enabled", True):
        return False
    custom_templates = recruiter_settings.get("templates", {})
    if status.lower() in custom_templates:
        custom = custom_templates[status.lower()]
        subject = custom.get(
            "subject",
            STATUS_EMAIL_TEMPLATES.get(status.lower(), {}).get(
                "subject", "Status Update"
            ),
        )
        content = custom.get("content", "")
    else:
        subject, content = get_status_email_content(status, job_title, company_name)
    try:
        background_tasks.add_task(
            email_service.send_email,
            candidate_email,
            subject,
            wrap_in_template(content, subject),
        )
        return True
    except Exception as e:
        logger.error(f"Failed to send status email: {e}")
        return False


class EmailUpdateRequest(BaseModel):
    app_id: int
    email: str


class EmailSettingsUpdate(BaseModel):
    auto_email_enabled: Optional[bool] = True
    templates: Optional[dict] = None
    automations: Optional[dict] = None


@router.post("/campaigns/{batch_id}/update-emails")
def bulk_update_emails(
    batch_id: int,
    email_updates: List[EmailUpdateRequest],
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    """Bulk update candidate emails for a campaign via JSON array."""
    batch = get_batch_for_recruiter(batch_id, recruiter, db)
    if not batch:
        raise HTTPException(status_code=404, detail="Campaign not found")

    updated = 0
    failed = []

    for req in email_updates:
        app = (
            db.query(Application)
            .filter(Application.id == req.app_id, Application.batch_id == batch_id)
            .first()
        )

        if not app:
            failed.append(
                {"app_id": req.app_id, "reason": "Application not found in this batch"}
            )
            continue

        new_email = req.email.strip()
        if "@" not in new_email:
            failed.append({"app_id": app.id, "reason": "Invalid email format"})
            continue

        app.email = new_email
        updated += 1

    db.commit()

    return {"success": True, "updated": updated, "failed": failed}


@router.post("/campaigns/{batch_id}/update-emails-csv")
async def bulk_update_emails_csv(
    batch_id: int,
    file: UploadFile = File(...),
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    """Bulk update candidate emails for a campaign via CSV upload.
    CSV format: old_email,new_email (header optional)
    """
    import csv
    import io

    batch = get_batch_for_recruiter(batch_id, recruiter, db)
    if not batch:
        raise HTTPException(status_code=404, detail="Campaign not found")

    content = await file.read()
    text = content.decode("utf-8")
    reader = csv.reader(io.StringIO(text))

    updated = 0
    failed = []

    # Skip header if present
    headers = next(reader, None)
    if headers and "old" not in headers[0].lower():
        # It might be a header, process it as data
        pass
    else:
        # Put back the row we skipped
        reader = itertools.chain([headers], reader) if headers else reader

    for row in reader:
        if len(row) < 2:
            continue

        old_email_pattern = row[0].strip()
        new_email = row[1].strip()

        if "@" not in new_email:
            failed.append({"old": old_email_pattern, "reason": "Invalid new email"})
            continue

        # Find candidate by EXACT match (prevent wildcard mass-update)
        app = (
            db.query(Application)
            .filter(
                Application.batch_id == batch_id, Application.email == old_email_pattern
            )
            .first()
        )

        if not app:
            failed.append({"old": old_email_pattern, "reason": "Candidate not found"})
            continue

        app.email = new_email
        updated += 1

    db.commit()

    return {"success": True, "updated": updated, "failed": failed}


@router.get("/email-settings")
def get_email_settings(
    recruiter: User = Depends(require_recruiter), db: Session = Depends(get_db)
):
    settings = get_recruiter_email_settings(db, recruiter.id)
    return {
        "auto_email_enabled": settings.get("auto_email_enabled", True),
        "templates": settings.get("templates", {}),
        "default_templates": STATUS_EMAIL_TEMPLATES,
    }


@router.put("/email-settings")
def update_email_settings(
    settings_update: EmailSettingsUpdate,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    current = get_recruiter_email_settings(db, recruiter.id)
    if settings_update.auto_email_enabled is not None:
        current["auto_email_enabled"] = settings_update.auto_email_enabled
    if settings_update.templates:
        current["templates"] = settings_update.templates
    save_recruiter_email_settings(db, recruiter.id, current)
    return {"message": "Email settings updated", "settings": current}


@router.put("/email-settings/templates/{status}")
def update_template(
    status: str,
    template_data: dict,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    current = get_recruiter_email_settings(db, recruiter.id)
    if "templates" not in current:
        current["templates"] = {}
    current["templates"][status.lower()] = template_data
    save_recruiter_email_settings(db, recruiter.id, current)
    return {"message": f"Template for {status} updated"}


@router.delete("/email-settings/templates/{status}")
def reset_template(
    status: str,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    current = get_recruiter_email_settings(db, recruiter.id)
    if current.get("templates") and status.lower() in current["templates"]:
        del current["templates"][status.lower()]
        save_recruiter_email_settings(db, recruiter.id, current)
    return {"message": f"Template for {status} reset to default"}
