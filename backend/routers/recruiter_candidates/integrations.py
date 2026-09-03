from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.database import User
from backend.dependencies import get_db, require_recruiter
from backend.routers.recruiter_candidates.email import (
    get_recruiter_email_settings,
    save_recruiter_email_settings,
)

router = APIRouter(tags=["Recruiter Candidates"])


@router.get("/automation-settings")
def get_automation_settings(
    recruiter: User = Depends(require_recruiter), db: Session = Depends(get_db)
):
    settings = get_recruiter_email_settings(db, recruiter.id)
    return {
        "followup_enabled": settings.get("automations", {}).get(
            "followup_enabled", True
        ),
        "followup_days": settings.get("automations", {}).get("followup_days", 3),
        "digest_enabled": settings.get("automations", {}).get("digest_enabled", True),
        "digest_time": settings.get("automations", {}).get("digest_time", "07:00"),
    }


@router.put("/automation-settings")
def update_automation_settings(
    settings_update: dict,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    current = get_recruiter_email_settings(db, recruiter.id)
    if "automations" not in current:
        current["automations"] = {}
    if "followup_enabled" in settings_update:
        current["automations"]["followup_enabled"] = settings_update["followup_enabled"]
    if "followup_days" in settings_update:
        current["automations"]["followup_days"] = settings_update["followup_days"]
    if "digest_enabled" in settings_update:
        current["automations"]["digest_enabled"] = settings_update["digest_enabled"]
    if "digest_time" in settings_update:
        current["automations"]["digest_time"] = settings_update["digest_time"]
    save_recruiter_email_settings(db, recruiter.id, current)
    return {
        "message": "Automation settings updated",
        "automations": current["automations"],
    }
