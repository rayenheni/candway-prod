import json
import logging
from datetime import UTC, date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from backend.adverse_action_service import AdverseActionService
from backend.authz import get_application_for_recruiter, get_offer_for_recruiter
from backend.background_check_service import BackgroundCheckService
from backend.config import get_settings
from backend.database import (
    Application,
    BackgroundCheck,
    BackgroundCheckStatusLog,
    User,
)
from backend.dependencies import get_db, require_recruiter
from backend.email_utils import send_email
from backend.notifications import notify_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/recruiter/background-checks", tags=["Background Checks"])


def _utcnow():
    return datetime.now(UTC).replace(tzinfo=None)


@router.post("/initiate/{application_id}", status_code=status.HTTP_201_CREATED)
async def initiate_background_check(
    application_id: int,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    app = get_application_for_recruiter(application_id, recruiter, db)
    company_id = getattr(recruiter, "_company_id", None)

    existing = (
        db.query(BackgroundCheck)
        .filter(BackgroundCheck.application_id == application_id)
        .first()
    )
    if existing and existing.status not in ("pending",):
        raise HTTPException(
            status_code=400,
            detail=f"Background check already initiated (status: {existing.status})",
        )

    try:
        candidate_result = await BackgroundCheckService.create_candidate(
            application_id, db, company_id=company_id
        )
        bg_check_id = candidate_result["background_check_id"]

        invitation_result = await BackgroundCheckService.create_invitation(
            candidate_result["background_check_id"], db, company_id=company_id
        )

        candidate_email = app.email
        candidate_name = app.full_name

        subject = "Background Check Initiated - Action Required"
        body = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <h2>Background Check Initiated</h2>
            <p>Dear {candidate_name},</p>
            <p>A background check has been initiated for your application. Please authorize the check through the secure link below.</p>
            {f'<a href="{invitation_result.get("invitation_url", "")}" style="display: inline-block; background: #4f46e5; color: white; padding: 14px 28px; text-decoration: none; border-radius: 6px; font-weight: bold; margin: 20px 0;">Authorize Background Check</a>' if invitation_result.get("invitation_url") else ""}
            <p style="color: #6b7280; font-size: 12px; margin-top: 20px;">This link will take you to Checkr's secure portal to authorize the background check.</p>
        </div>
        """
        send_email(candidate_email, subject, body)

        bg_check = (
            db.query(BackgroundCheck).filter(BackgroundCheck.id == bg_check_id).first()
        )
        if bg_check:
            bg_check.candidate_notified_at = _utcnow()
            db.commit()

        await notify_user(
            user_id=str(app.assigned_to or recruiter.id),
            message=f"Background check initiated for {candidate_name}",
            title="Background Check Initiated",
            level="info",
            notification_type="background_check",
            related_type="background_check",
            related_id=bg_check_id,
            db_session=db,
        )

        logger.info(
            f"Background check initiated for application {application_id} by {recruiter.email}"
        )

        return {
            "success": True,
            "background_check_id": bg_check_id,
            "checkr_candidate_id": candidate_result.get("checkr_candidate_id"),
            "invitation_url": invitation_result.get("invitation_url"),
            "status": "invited",
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=f"Checkr API error: {str(e)}")


@router.get("/{application_id}")
def get_background_check(
    application_id: int,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    get_application_for_recruiter(application_id, recruiter, db)

    bg_check = (
        db.query(BackgroundCheck)
        .filter(BackgroundCheck.application_id == application_id)
        .first()
    )
    if not bg_check:
        raise HTTPException(status_code=404, detail="Background check not found")

    app = get_application_for_recruiter(bg_check.application_id, recruiter, db)
    _offer = (
        get_offer_for_recruiter(bg_check.offer_id, recruiter, db)
        if bg_check.offer_id
        else None
    )

    status_logs = (
        db.query(BackgroundCheckStatusLog)
        .filter(BackgroundCheckStatusLog.background_check_id == bg_check.id)
        .order_by(BackgroundCheckStatusLog.created_at.asc())
        .all()
    )

    findings_list = []
    if bg_check.findings:
        try:
            findings_list = json.loads(bg_check.findings)
        except (json.JSONDecodeError, TypeError):
            pass

    return {
        "id": bg_check.id,
        "application_id": bg_check.application_id,
        "offer_id": bg_check.offer_id,
        "candidate_name": app.full_name if app else None,
        "candidate_email": app.email if app else None,
        "provider": bg_check.provider,
        "provider_candidate_id": bg_check.provider_candidate_id,
        "provider_report_id": bg_check.provider_report_id,
        "status": bg_check.status,
        "verdict": bg_check.verdict,
        "findings": findings_list,
        "report_url": bg_check.report_url,
        "candidate_notified_at": bg_check.candidate_notified_at,
        "completed_at": bg_check.completed_at,
        "created_at": bg_check.created_at,
        "updated_at": bg_check.updated_at,
        "status_log": [
            {
                "id": log.id,
                "from_status": log.from_status,
                "to_status": log.to_status,
                "details": log.details,
                "created_at": log.created_at,
            }
            for log in status_logs
        ],
    }


@router.get("")
def list_background_checks(
    status: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    limit: int = 50,
    offset: int = 0,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    company_id = getattr(recruiter, "_company_id", None)
    query = (
        db.query(BackgroundCheck)
        .join(Application)
        .filter(Application.company_id == company_id)
    )

    if status:
        query = query.filter(BackgroundCheck.status == status)
    if date_from:
        query = query.filter(
            BackgroundCheck.created_at
            >= datetime.combine(date_from, datetime.min.time())
        )
    if date_to:
        query = query.filter(
            BackgroundCheck.created_at <= datetime.combine(date_to, datetime.max.time())
        )

    total = query.count()
    checks = (
        query.order_by(BackgroundCheck.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    results = []
    for bg in checks:
        results.append(
            {
                "id": bg.id,
                "application_id": bg.application_id,
                "offer_id": bg.offer_id,
                "candidate_name": bg.application.full_name if bg.application else None,
                "candidate_email": bg.application.email if bg.application else None,
                "status": bg.status,
                "verdict": bg.verdict,
                "provider": bg.provider,
                "created_at": bg.created_at,
                "completed_at": bg.completed_at,
            }
        )

    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "results": results,
    }


@router.post("/{background_check_id}/adverse-action")
def initiate_adverse_action(
    background_check_id: int,
    action_type: str = "pre_adverse",
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    bg_check = (
        db.query(BackgroundCheck)
        .join(Application)
        .filter(
            BackgroundCheck.id == background_check_id,
            Application.company_id == getattr(recruiter, "_company_id", None),
        )
        .first()
    )
    if not bg_check:
        raise HTTPException(status_code=404, detail="Background check not found")
    company_id = getattr(recruiter, "_company_id", None)

    if bg_check.verdict not in ("consider",) and bg_check.status != "report_ready":
        raise HTTPException(
            status_code=400,
            detail=f"Cannot initiate adverse action from status {bg_check.status} / verdict {bg_check.verdict}",
        )

    try:
        if action_type == "pre_adverse":
            result = AdverseActionService.send_pre_adverse(
                background_check_id, db, company_id=company_id
            )
        elif action_type == "final_adverse":
            if not AdverseActionService.check_dispute_period(
                background_check_id, db, company_id=company_id
            ):
                raise HTTPException(
                    status_code=400,
                    detail="Dispute period has not elapsed. Please wait 5 business days.",
                )
            result = AdverseActionService.send_final_adverse(
                background_check_id, db, company_id=company_id
            )
        else:
            raise HTTPException(
                status_code=400,
                detail="Invalid action_type. Use 'pre_adverse' or 'final_adverse'.",
            )

        logger.info(
            f"Adverse action ({action_type}) initiated for background_check {background_check_id} by {recruiter.email}"
        )

        return result

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/stats/summary")
def get_background_check_stats(
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    company_id = getattr(recruiter, "_company_id", None)
    query = (
        db.query(BackgroundCheck)
        .join(Application)
        .filter(Application.company_id == company_id)
    )

    total = query.count()
    pending = query.filter(
        BackgroundCheck.status.in_(
            ["pending", "candidate_created", "invited", "pending_report"]
        )
    ).count()
    completed = query.filter(BackgroundCheck.status == "report_ready").count()
    clear_count = query.filter(BackgroundCheck.verdict == "clear").count()
    consider_count = query.filter(BackgroundCheck.verdict == "consider").count()
    disputed = query.filter(BackgroundCheck.status == "disputed").count()
    adverse_action_count = query.filter(
        BackgroundCheck.status == "adverse_action"
    ).count()

    clear_rate = (clear_count / completed * 100) if completed > 0 else 0

    return {
        "total": total,
        "pending": pending,
        "completed": completed,
        "clear": clear_count,
        "consider": consider_count,
        "disputed": disputed,
        "adverse_action": adverse_action_count,
        "clear_rate": round(clear_rate, 1),
    }


@router.post("/webhook/checkr")
async def checkr_webhook(
    request: Request,
    db: Session = Depends(get_db),
):
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    signature = request.headers.get("X-Checkr-Signature", "")
    settings = get_settings()
    webhook_secret = settings.checkr_webhook_secret or ""

    try:
        event = BackgroundCheckService.handle_webhook(
            payload, signature, webhook_secret
        )
    except ValueError as e:
        logger.warning(f"Checkr webhook signature verification failed: {e}")
        raise HTTPException(status_code=401, detail="Invalid signature")

    event_type = event["event_type"]
    report_id = event.get("report_id")

    if not report_id:
        return {"status": "accepted", "event_type": event_type}

    bg_check = (
        db.query(BackgroundCheck)
        .filter(BackgroundCheck.provider_report_id == report_id)
        .first()
    )

    if not bg_check:
        logger.warning(f"No background check found for Checkr report {report_id}")
        return {"status": "ignored"}

    old_status = bg_check.status
    new_status = event.get("checkr_status")

    if new_status:
        bg_check.status = new_status
        bg_check.updated_at = _utcnow()

        if event_type == "report.completed":
            try:
                report_details = await BackgroundCheckService.get_report_details(
                    report_id
                )
                bg_check.verdict = BackgroundCheckService._determine_verdict(
                    report_details
                )
                findings = BackgroundCheckService._extract_findings(report_details)
                bg_check.findings = json.dumps(findings)
                bg_check.report_url = report_details.get("uri", "")
                bg_check.completed_at = _utcnow()
            except Exception as e:
                logger.error(f"Failed to fetch report details for {report_id}: {e}")

        db.commit()

        BackgroundCheckService._log_status_change(
            bg_check.id,
            old_status,
            new_status,
            db,
            details=f"Checkr webhook: {event_type}",
            company_id=bg_check.company_id,
        )

        app = bg_check.application
        if app:
            recruiter_id = app.assigned_to or app.job.recruiter_id if app.job else None
            if recruiter_id:
                await notify_user(
                    user_id=str(recruiter_id),
                    message=f"Background check {new_status} for {app.full_name}",
                    title=f"Background Check {new_status.replace('_', ' ').title()}",
                    level="info",
                    notification_type="background_check",
                    related_type="background_check",
                    related_id=bg_check.id,
                    db_session=db,
                )

    logger.info(f"Checkr webhook processed: {event_type} for report {report_id}")

    return {"status": "accepted", "event_type": event_type}
