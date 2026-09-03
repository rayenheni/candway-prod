from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.authz import get_application_for_candidate
from backend.database import EEOConsent, User
from backend.dependencies import get_current_user, get_db

router = APIRouter(tags=["candidate-eeo"])


class EEOSubmitRequest(BaseModel):
    application_id: int
    consent_given: bool = True
    gender: str | None = Field(None, max_length=50)
    race_ethnicity: str | None = Field(None, max_length=100)
    veteran_status: str | None = Field(None, max_length=50)
    disability_status: str | None = Field(None, max_length=50)
    age_group: str | None = Field(None, max_length=20)


@router.post("/eeo/submit")
async def submit_eeo(
    body: EEOSubmitRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    app = get_application_for_candidate(body.application_id, current_user, db)

    existing = (
        db.query(EEOConsent)
        .filter(EEOConsent.application_id == body.application_id)
        .first()
    )

    if existing:
        existing.consent_given = body.consent_given
        existing.gender = body.gender
        existing.race_ethnicity = body.race_ethnicity
        existing.veteran_status = body.veteran_status
        existing.disability_status = body.disability_status
        existing.age_group = body.age_group
        existing.updated_at = datetime.now(UTC)
    else:
        eeo = EEOConsent(
            application_id=body.application_id,
            company_id=app.company_id,
            consent_given=body.consent_given,
            gender=body.gender,
            race_ethnicity=body.race_ethnicity,
            veteran_status=body.veteran_status,
            disability_status=body.disability_status,
            age_group=body.age_group,
        )
        db.add(eeo)

    db.commit()
    return {"success": True, "message": "EEO data submitted successfully"}


@router.get("/eeo/status/{application_id}")
async def get_eeo_status(
    application_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    get_application_for_candidate(application_id, current_user, db)
    eeo = (
        db.query(EEOConsent).filter(EEOConsent.application_id == application_id).first()
    )
    return {
        "submitted": eeo is not None,
        "consent_given": eeo.consent_given if eeo else False,
        "application_id": application_id,
    }


@router.get("/eeo/my-data")
async def get_my_eeo_data(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    eeo = (
        db.query(EEOConsent)
        .join(EEOConsent.application)
        .filter(EEOConsent.application.has(user_id=current_user.id))
        .order_by(EEOConsent.created_at.desc())
        .first()
    )
    if not eeo:
        return {"found": False}
    return {
        "found": True,
        "gender": eeo.gender,
        "ethnicity": eeo.race_ethnicity,
        "disability_status": eeo.disability_status,
        "veteran_status": eeo.veteran_status,
        "date_of_birth": eeo.age_group or "",
    }
