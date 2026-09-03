import logging
import os
import uuid
from datetime import datetime, timedelta
from datetime import timezone as dt_timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from backend.database import Application, AuditLog, LoginAttempt, Qualification, User
from backend.dependencies import get_current_user, get_db
from backend.models.ats.types import ApplicationType
from backend.profile_helpers import get_user_email, get_user_headline, get_user_name
from backend.services.application_service import ApplicationService

router = APIRouter(tags=["candidate"])

logger = logging.getLogger(__name__)


# Per-candidate upload limit. The audit noted that this endpoint had
# no rate limit, letting a candidate create dozens of "qualification"
# rows in a few seconds and ballooning the analysis_json JSON-bag.
# (The storage is a 20-purpose JSON-bag today; it will become a real
# Qualification table in a follow-up.)
QUALIFICATIONS_PER_HOUR = 20
QUALIFICATIONS_PER_DAY = 60


def _check_qualifications_rate_limit(current_user: User, db: Session) -> None:
    """429 the request if the candidate has uploaded too many
    qualifications recently.

    Tracked via ``LoginAttempt`` with ``ip_address="qual_upload"`` so
    we don't need a new table for a single counter.
    """
    now = datetime.now(dt_timezone.utc)
    one_hour_ago = now - timedelta(hours=1)
    one_day_ago = now - timedelta(days=1)

    try:
        recent_hour = (
            db.query(LoginAttempt)
            .filter(
                LoginAttempt.email == current_user.email,
                LoginAttempt.ip_address == "qual_upload",
                LoginAttempt.timestamp > one_hour_ago,
            )
            .count()
        )
        if recent_hour >= QUALIFICATIONS_PER_HOUR:
            raise HTTPException(
                status_code=429,
                detail=(
                    f"Upload limit reached: max "
                    f"{QUALIFICATIONS_PER_HOUR} qualifications per hour. "
                    f"Try again later."
                ),
                headers={"Retry-After": "3600"},
            )

        recent_day = (
            db.query(LoginAttempt)
            .filter(
                LoginAttempt.email == current_user.email,
                LoginAttempt.ip_address == "qual_upload",
                LoginAttempt.timestamp > one_day_ago,
            )
            .count()
        )
        if recent_day >= QUALIFICATIONS_PER_DAY:
            raise HTTPException(
                status_code=429,
                detail=(
                    f"Daily upload limit reached: max "
                    f"{QUALIFICATIONS_PER_DAY} qualifications per day."
                ),
                headers={"Retry-After": "86400"},
            )
    except HTTPException:
        raise
    except Exception as e:
        # Don't block uploads on a counter failure; just log it.
        logger.warning(f"[QUAL] Rate-limit counter check failed: {e}")


def _record_qualification_upload(current_user: User, db: Session) -> None:
    try:
        db.add(
            LoginAttempt(
                email=current_user.email,
                success=True,
                ip_address="qual_upload",
                timestamp=datetime.now(dt_timezone.utc),
            )
        )
        db.commit()
    except Exception as e:
        # Roll back the counter if the audit row can't be written
        # so we don't double-charge on a future re-attempt.
        logger.warning(f"[QUAL] Failed to record upload counter: {e}")
        db.rollback()


@router.post("/qualifications/upload")
async def upload_qualification(
    file: UploadFile = File(...),
    category: str = Form("other"),
    title: str = Form(""),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Role gate: only candidates can upload their own
    # qualifications. Recruiters / admins have their own upload
    # paths (e.g. company logos, recruiter materials).
    if current_user.role != "candidate":
        raise HTTPException(
            status_code=403,
            detail="Only candidates can upload qualifications",
        )

    _check_qualifications_rate_limit(current_user, db)

    valid_categories = ["degree", "certificate", "transcript", "license", "other"]
    if category not in valid_categories:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid category. Must be one of: {', '.join(valid_categories)}",
        )

    if not title or len(title.strip()) < 3:
        raise HTTPException(
            status_code=400, detail="Document title must be at least 3 characters"
        )
    if len(title.strip()) > 200:
        raise HTTPException(
            status_code=400, detail="Document title too long (max 200 characters)"
        )

    ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg"}
    ALLOWED_MIME = {"application/pdf", "image/png", "image/jpeg", "image/jpg"}

    ext = os.path.splitext(file.filename)[1].lower() if file.filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400, detail="Only PDF, PNG, or JPG files allowed"
        )

    if file.content_type and file.content_type.lower() not in ALLOWED_MIME:
        raise HTTPException(status_code=400, detail="Invalid file type")

    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(
            status_code=400, detail="File too large. Maximum 10MB allowed."
        )

    if len(content) < 100:
        raise HTTPException(
            status_code=400, detail="File appears to be empty or corrupted"
        )

    try:
        from backend.file_security import scan_for_malware
        from backend.security import secure_filename

        safe_filename = secure_filename(file.filename or "document")
        is_safe, scan_result = scan_for_malware(content, safe_filename)
        if not is_safe:
            logger.warning(
                f"MALWARE DETECTED in qualification upload by user {current_user.id}: {scan_result}"
            )
            raise HTTPException(
                status_code=400,
                detail="File contains potentially malicious content and was rejected.",
            )
    except ImportError:
        logger.warning("Security module not available, skipping malware scan")

    UPLOAD_DIR = "uploads/qualifications"
    os.makedirs(UPLOAD_DIR, exist_ok=True)

    secure_ext = ext.lstrip(".")
    secure_name = f"{current_user.id}_{uuid.uuid4().hex[:12]}_{category}.{secure_ext}"
    file_path = os.path.join(UPLOAD_DIR, secure_name)

    abs_upload_dir = os.path.abspath(UPLOAD_DIR)
    abs_file_path = os.path.abspath(file_path)
    if not abs_file_path.startswith(abs_upload_dir):
        raise HTTPException(status_code=400, detail="Invalid file path")

    with open(file_path, "wb") as buffer:
        buffer.write(content)

    # Find an existing application to link the qualification to.
    # The old flow auto-created an Application with status="pending"
    # if none existed; we keep that behaviour so existing clients
    # don't break, but a future round could split them.
    app = (
        db.query(Application)
        .filter(Application.user_id == current_user.id)
        .order_by(Application.created_at.desc())
        .first()
    )

    company_id = getattr(app, "company_id", None) or getattr(
        current_user, "_company_id", None
    )

    # Create a holding Application only when a company context exists;
    # otherwise the qualification is stored user-scoped (application_id
    # NULL) until the candidate applies somewhere.
    if not app and company_id:
        app = ApplicationService.create_application(
            db,
            company_id=company_id,
            application_type=ApplicationType.MANUAL,
            user_id=current_user.id,
            candidate_email=get_user_email(current_user),
            candidate_name=get_user_name(current_user),
            status="pending",
            declared_role=get_user_headline(current_user) or "General",
        )

    # Bug B-30: previously the qualification list was stored in
    # ``app.analysis_json`` as a JSON bag. That made every
    # Application row O(N) in upload count and offered no unique
    # constraint enforcement. We now write to the dedicated
    # ``qualifications`` table; the JSON-bag copy is *not* kept
    # in sync (the column is being deprecated in a follow-up).
    # Candidates are user-scoped, so company_id may be NULL until
    # they apply to a company's job (see m53).

    # Enforce (user_id, title, category) uniqueness via the DB.
    # The unique constraint is on the model so any race is caught
    # by SQLAlchemy and translated to IntegrityError.
    new_id = uuid.uuid4().hex[:8]
    qual = Qualification(
        id=new_id,
        user_id=current_user.id,
        application_id=app.id if app else None,
        title=title.strip(),
        category=category,
        filename=secure_name,
        file_url=f"/uploads/qualifications/{secure_name}",
        file_size=len(content),
        mime_type=file.content_type or "application/octet-stream",
        verified=False,
        uploaded_at=datetime.now(dt_timezone.utc),
    )
    try:
        db.add(qual)
        db.flush()
    except Exception as e:
        db.rollback()
        # Detect the integrity-error from the unique constraint
        # and return a clean 400. Other DB errors bubble.
        msg = str(e).lower()
        if "uq_qual_user_title_cat" in msg or "unique" in msg:
            raise HTTPException(
                status_code=400,
                detail="A document with this title and type already exists",
            )
        raise

    qualification_record = {
        "id": new_id,
        "title": title.strip(),
        "category": category,
        "filename": secure_name,
        "file_url": f"/uploads/qualifications/{secure_name}",
        "file_size": len(content),
        "mime_type": file.content_type or "application/octet-stream",
        "uploaded_at": qual.uploaded_at.isoformat(),
        "verified": False,
        "user_id": current_user.id,
    }

    audit = AuditLog(
        user_id=current_user.id,
        company_id=company_id,
        action="qualification_upload",
        target_id=str(app.id) if app else None,
        details=f"Uploaded {category}: {title.strip()} ({secure_name})",
        ip_address="system",
    )
    db.add(audit)
    db.commit()

    # Bug B-27: charge the rate-limit counter on success only.
    # Recording before the commit risks double-counting if the
    # commit above rolls back; recording here is safe because the
    # qualification row is already persisted.
    _record_qualification_upload(current_user, db)

    logger.info(
        f"Qualification uploaded by user {current_user.id}: {title.strip()} ({category})"
    )

    return {
        "message": "Qualification uploaded securely",
        "qualification": qualification_record,
    }


@router.get("/qualifications")
def get_qualifications(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    rows = (
        db.query(Qualification)
        .filter(
            Qualification.user_id == current_user.id,
            Qualification.deleted_at.is_(None),
        )
        .order_by(Qualification.uploaded_at.desc())
        .all()
    )
    return {
        "qualifications": [
            {
                "id": q.id,
                "title": q.title,
                "category": q.category,
                "filename": q.filename,
                "file_url": q.file_url,
                "file_size": q.file_size,
                "mime_type": q.mime_type,
                "uploaded_at": q.uploaded_at.isoformat() if q.uploaded_at else None,
                "verified": q.verified,
                "user_id": q.user_id,
            }
            for q in rows
        ]
    }


@router.delete("/qualifications/{qual_id}")
def delete_qualification(
    qual_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    qual = (
        db.query(Qualification)
        .filter(
            Qualification.id == qual_id,
            Qualification.user_id == current_user.id,
            Qualification.deleted_at.is_(None),
        )
        .first()
    )
    if not qual:
        raise HTTPException(status_code=404, detail="Qualification not found")

    # Remove the file from disk. We don't fail the request if the
    # file is already gone (it's possible to manually clean up).
    try:
        file_path = os.path.join("uploads/qualifications", qual.filename)
        if os.path.exists(file_path):
            os.remove(file_path)
    except Exception as e:
        logger.warning(f"Failed to delete qualification file: {e}")

    # Soft-delete so a future audit can recover; cascade-removal
    # is left to a cron. Hard-deletes break the audit trail.
    qual.deleted_at = datetime.now(dt_timezone.utc)

    audit = AuditLog(
        user_id=current_user.id,
        action="qualification_delete",
        target_id=str(qual.id),
        details=f"Deleted qualification: {qual.title}",
        ip_address="system",
    )
    db.add(audit)
    db.commit()

    return {"message": "Qualification deleted successfully"}
