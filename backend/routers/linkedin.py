import json
import os
import secrets

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.config import get_settings
from backend.database import Job, SystemConfig, User
from backend.dependencies import get_db, require_recruiter
from backend.linkedin_service import LinkedInService
from backend.logger import logger

router = APIRouter(prefix="/linkedin", tags=["LinkedIn Integration"])


class ImportProfileRequest(BaseModel):
    profile_url: str


class PostJobRequest(BaseModel):
    company_urn: str = ""
    poster_urn: str = ""


def _get_li_credentials(db: Session) -> dict:
    client_id = (
        db.query(SystemConfig).filter(SystemConfig.key == "linkedin_client_id").first()
    )
    client_secret = (
        db.query(SystemConfig)
        .filter(SystemConfig.key == "linkedin_client_secret")
        .first()
    )
    return {
        "client_id": client_id.value
        if client_id
        else os.getenv("LINKEDIN_CLIENT_ID", ""),
        "client_secret": client_secret.value
        if client_secret
        else os.getenv("LINKEDIN_CLIENT_SECRET", ""),
    }


def _get_recruiter_profile(db: Session, recruiter: User):
    """Load the recruiter's RecruiterProfile row by user_id (may be None)."""
    from backend.models.evaluation.profile import RecruiterProfile

    return (
        db.query(RecruiterProfile)
        .filter(RecruiterProfile.user_id == recruiter.id)
        .first()
    )


def _get_or_create_recruiter_profile(db: Session, recruiter: User):
    from backend.models.evaluation.profile import RecruiterProfile

    profile = _get_recruiter_profile(db, recruiter)
    if profile is None:
        profile = RecruiterProfile(
            user_id=recruiter.id,
            name=recruiter.name,
            email=recruiter.email,
        )
        db.add(profile)
        db.flush()
    return profile


def _load_linkedin_settings(db: Session, recruiter: User) -> dict:
    profile = _get_recruiter_profile(db, recruiter)
    raw = getattr(profile, "linkedin_settings", None) if profile else None
    if not raw:
        return {}
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, AttributeError):
        return {}


def _get_stored_tokens(recruiter: User, db: Session) -> dict:
    settings = _load_linkedin_settings(db, recruiter)
    return {
        "access_token": settings.get("access_token", ""),
        "refresh_token": settings.get("refresh_token", ""),
        "expires_at": settings.get("expires_at", 0),
        "linkedin_user_id": settings.get("linkedin_user_id", ""),
    }


def _store_tokens(recruiter: User, tokens: dict, db: Session):
    current = _load_linkedin_settings(db, recruiter)

    current.update(
        {
            "access_token": tokens.get("access_token", current.get("access_token", "")),
            "refresh_token": tokens.get(
                "refresh_token", current.get("refresh_token", "")
            ),
            "expires_at": tokens.get("expires_at", current.get("expires_at", 0)),
        }
    )

    profile = _get_or_create_recruiter_profile(db, recruiter)
    profile.linkedin_settings = json.dumps(current)
    db.commit()


@router.get("/auth-url")
async def get_linkedin_auth_url(
    request: Request,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    creds = _get_li_credentials(db)
    if not creds["client_id"]:
        raise HTTPException(status_code=400, detail="LinkedIn API not configured")

    state = secrets.token_urlsafe(32)

    from backend.config import get_settings

    settings = get_settings()
    redirect_uri = f"{settings.base_url}/api/v1/linkedin/callback"

    auth_url = LinkedInService.get_oauth_url(
        client_id=creds["client_id"],
        redirect_uri=redirect_uri,
        state=state,
    )

    return {"auth_url": auth_url, "state": state}


@router.get("/callback")
async def linkedin_callback(
    request: Request,
    code: str = None,
    state: str = None,
    error: str = None,
    db: Session = Depends(get_db),
):
    if error:
        logger.error(f"LinkedIn OAuth error: {error}")
        from fastapi.responses import RedirectResponse

        return RedirectResponse(
            url=f"{get_settings().frontend_url}/recruiter/settings?linkedin=error"
        )

    if not code:
        from fastapi.responses import RedirectResponse

        return RedirectResponse(
            url=f"{get_settings().frontend_url}/recruiter/settings?linkedin=error"
        )

    creds = _get_li_credentials(db)
    if not creds["client_id"] or not creds["client_secret"]:
        from fastapi.responses import RedirectResponse

        return RedirectResponse(
            url=f"{get_settings().frontend_url}/recruiter/settings?linkedin=error"
        )

    settings = get_settings()
    redirect_uri = f"{settings.base_url}/api/v1/linkedin/callback"

    try:
        tokens = await LinkedInService.exchange_code(
            code=code,
            client_id=creds["client_id"],
            client_secret=creds["client_secret"],
            redirect_uri=redirect_uri,
        )

        profile = await LinkedInService.get_user_profile(tokens.get("access_token", ""))

        token_cookie = request.cookies.get("access_token")
        user = None
        if token_cookie:
            from jose import jwt as jose_jwt

            from backend.dependencies import ALGORITHM, SECRET_KEY

            try:
                payload = jose_jwt.decode(
                    token_cookie, SECRET_KEY, algorithms=[ALGORITHM]
                )
                user = db.query(User).filter(User.email == payload.get("sub")).first()
            except Exception:
                pass

        if not user:
            user = db.query(User).filter(User.email == profile.get("email", "")).first()

        if user:
            _store_tokens(
                user,
                {
                    "access_token": tokens.get("access_token"),
                    "refresh_token": tokens.get("refresh_token", ""),
                    "expires_at": tokens.get("expires_at", 0),
                    "linkedin_user_id": profile.get("sub", ""),
                    "name": profile.get("name", ""),
                    "email": profile.get("email", ""),
                },
                db,
            )
            logger.info(f"LinkedIn connected for user {user.id}")

        from fastapi.responses import RedirectResponse

        return RedirectResponse(
            url=f"{settings.frontend_url}/recruiter/settings?linkedin=connected"
        )
    except Exception as e:
        logger.error(f"LinkedIn OAuth callback error: {e}")
        from fastapi.responses import RedirectResponse

        return RedirectResponse(
            url=f"{get_settings().frontend_url}/recruiter/settings?linkedin=error"
        )


@router.post("/post-job/{job_id}")
async def post_job_to_linkedin(
    job_id: int,
    data: PostJobRequest = None,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    job = (
        db.query(Job).filter(Job.id == job_id, Job.recruiter_id == recruiter.id).first()
    )
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    tokens = _get_stored_tokens(recruiter, db)
    access_token = tokens.get("access_token")
    if not access_token:
        raise HTTPException(status_code=400, detail="LinkedIn not connected")

    company_urn = data.company_urn if data and data.company_urn else ""
    poster_urn = data.poster_urn if data and data.poster_urn else ""

    if not company_urn:
        settings = _load_linkedin_settings(db, recruiter)
        company_urn = settings.get("company_id", "")

    if not company_urn:
        raise HTTPException(
            status_code=400, detail="LinkedIn company ID not configured"
        )

    employment_type_map = {
        "Full-time": "FULL_TIME",
        "Part-time": "PART_TIME",
        "Contract": "CONTRACT",
        "Internship": "INTERNSHIP",
        "Temporary": "TEMPORARY",
        "Volunteer": "VOLUNTEER",
    }

    job_data = {
        "company_urn": company_urn,
        "poster_urn": poster_urn
        or f"urn:li:person:{tokens.get('linkedin_user_id', '')}",
        "title": job.title,
        "description": job.description,
        "location": job.location,
        "employmentType": employment_type_map.get(job.type, "FULL_TIME"),
    }

    try:
        result = await LinkedInService.post_job(access_token, job_data)
        return result
    except Exception as e:
        logger.error(f"LinkedIn post job error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to post job: {str(e)}")


@router.post("/import-profile")
async def import_linkedin_profile(
    data: ImportProfileRequest,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    tokens = _get_stored_tokens(recruiter, db)
    access_token = tokens.get("access_token")
    if not access_token:
        raise HTTPException(status_code=400, detail="LinkedIn not connected")

    try:
        result = await LinkedInService.import_profile(access_token, data.profile_url)
        return result
    except Exception as e:
        logger.error(f"LinkedIn import profile error: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to import profile: {str(e)}"
        )


@router.post("/disconnect")
async def disconnect_linkedin(
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    profile = _get_or_create_recruiter_profile(db, recruiter)
    profile.linkedin_settings = json.dumps({})
    db.commit()
    return {"message": "LinkedIn disconnected"}


@router.get("/status")
async def linkedin_status(
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    tokens = _get_stored_tokens(recruiter, db)
    connected = bool(tokens.get("access_token"))

    settings_data = _load_linkedin_settings(db, recruiter)

    return {
        "connected": connected,
        "profile": {
            "name": settings_data.get("name", ""),
            "email": settings_data.get("email", ""),
            "linkedin_user_id": settings_data.get("linkedin_user_id", ""),
        }
        if connected
        else None,
        "company_id": settings_data.get("company_id", ""),
        "company_name": settings_data.get("company_name", ""),
    }
