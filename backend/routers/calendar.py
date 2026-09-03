"""
Calendar Integration API Endpoints
Handles ICS file generation, Google Calendar, and Outlook Calendar integration
"""

from datetime import UTC, datetime, timedelta

import requests
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.calendar_service import CalendarService, GoogleCalendarIntegration
from backend.config import get_settings
from backend.database import Application, Interview, InterviewParticipant, User
from backend.dependencies import get_current_user, get_db, require_recruiter
from backend.encryption import encrypt_text
from backend.logger import logger
from backend.models.evaluation.profile import RecruiterProfile

router = APIRouter(prefix="/calendar", tags=["Calendar Integration"])


def _get_calendar_settings(user) -> dict:
    """Read calendar_settings from RecruiterProfile, fall back to User column."""
    rp = getattr(user, "recruiter_profile", None)
    if rp and rp.calendar_settings:
        import json

        try:
            return json.loads(rp.calendar_settings)
        except (json.JSONDecodeError, TypeError):
            pass
    raw = getattr(user, "calendar_settings", None)
    return raw if isinstance(raw, dict) else {}


def _save_calendar_settings(user, db, settings: dict):
    """Write calendar_settings to RecruiterProfile (SSOT)."""
    import json

    rp = getattr(user, "recruiter_profile", None)
    if not rp:
        rp = (
            db.query(RecruiterProfile)
            .filter(RecruiterProfile.user_id == user.id)
            .first()
        )
    if rp:
        rp.calendar_settings = json.dumps(settings)


# ============================================
# SCHEMAS
# ============================================


class ICSDownloadRequest(BaseModel):
    interview_id: int


class GoogleCalendarConnect(BaseModel):
    authorization_code: str


class OutlookCalendarConnect(BaseModel):
    access_token: str


class CalendarEventCreate(BaseModel):
    interview_id: int
    calendar_type: str  # 'google' or 'outlook'


# ============================================
# ICS FILE GENERATION
# ============================================


@router.get("/ics/interview/{interview_id}")
async def download_interview_ics(
    interview_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Download ICS file for an interview
    Can be imported into any calendar application
    """
    try:
        # Get interview
        interview = db.query(Interview).filter(Interview.id == interview_id).first()
        if not interview:
            raise HTTPException(status_code=404, detail="Interview not found")

        # Get application and candidate
        app = (
            db.query(Application)
            .filter(Application.id == interview.application_id)
            .first()
        )
        if not app:
            raise HTTPException(status_code=404, detail="Application not found")

        candidate = app.owner
        if not candidate:
            raise HTTPException(status_code=404, detail="Candidate not found")

        # Check access (user must be interviewer, recruiter, or candidate)
        is_participant = (
            db.query(InterviewParticipant)
            .filter(
                InterviewParticipant.interview_id == interview_id,
                InterviewParticipant.user_id == user.id,
            )
            .first()
        )

        is_candidate = user.id == candidate.id
        is_recruiter = user.role in ["recruiter", "admin"]

        if not (is_participant or is_candidate or is_recruiter):
            raise HTTPException(status_code=404, detail="Interview not found")

        # Tenant isolation: recruiters must belong to the interview's company
        if is_recruiter and interview.company_id != getattr(user, "_company_id", None):
            raise HTTPException(status_code=404, detail="Interview not found")

        # Calculate end time
        end_time = interview.scheduled_time + timedelta(
            minutes=interview.duration_minutes
        )

        # Get attendees
        participants = (
            db.query(InterviewParticipant)
            .filter(InterviewParticipant.interview_id == interview_id)
            .all()
        )
        attendees = [p.user.email for p in participants if p.user]
        attendees.append(candidate.email)

        # Generate ICS content
        ics_content = CalendarService.generate_ics_file(
            title=f"{interview.type.capitalize()} Interview - {candidate.name}",
            description=interview.agenda or f"Interview with {candidate.name}",
            start_time=interview.scheduled_time,
            end_time=end_time,
            location=interview.location,
            attendees=attendees,
            organizer_email=user.email,
            meeting_link=interview.meeting_link,
        )

        # Return ICS file
        filename = f"interview_{interview_id}_{candidate.name.replace(' ', '_')}.ics"

        return Response(
            content=ics_content,
            media_type="text/calendar",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to generate ICS file: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate calendar file")


@router.get("/links/interview/{interview_id}")
async def get_calendar_links(
    interview_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get "Add to Calendar" links for Google Calendar and Outlook
    """
    try:
        # Get interview with tenant isolation
        interview = db.query(Interview).filter(Interview.id == interview_id).first()
        if not interview:
            raise HTTPException(status_code=404, detail="Interview not found")

        # Verify tenant access for recruiters
        user_company_id = getattr(user, "_company_id", None)
        if user_company_id and user.role in ["recruiter", "admin"]:
            if interview.company_id != user_company_id:
                raise HTTPException(status_code=404, detail="Interview not found")

        # Get application and candidate
        app = (
            db.query(Application)
            .filter(Application.id == interview.application_id)
            .first()
        )
        candidate = app.owner if app else None

        if not candidate:
            raise HTTPException(status_code=404, detail="Candidate not found")

        # Candidate access check: only the candidate themselves can see their links
        is_candidate = user.id == candidate.id
        is_participant = any(
            p.user_id == user.id for p in (interview.participants or [])
        )
        if not (is_candidate or is_participant or user.role in ["recruiter", "admin"]):
            raise HTTPException(status_code=404, detail="Interview not found")

        # Calculate end time
        end_time = interview.scheduled_time + timedelta(
            minutes=interview.duration_minutes
        )

        # Get attendees
        participants = (
            db.query(InterviewParticipant)
            .filter(InterviewParticipant.interview_id == interview_id)
            .all()
        )
        attendees = [p.user.email for p in participants if p.user]

        # Generate description
        description = interview.agenda or f"Interview with {candidate.name}"
        if interview.meeting_link:
            description += f"\n\nJoin Meeting: {interview.meeting_link}"

        # Generate links
        google_link = CalendarService.create_google_calendar_link(
            title=f"{interview.type.capitalize()} Interview - {candidate.name}",
            description=description,
            start_time=interview.scheduled_time,
            end_time=end_time,
            location=interview.location,
            attendees=attendees,
        )

        outlook_link = CalendarService.create_outlook_calendar_link(
            title=f"{interview.type.capitalize()} Interview - {candidate.name}",
            description=description,
            start_time=interview.scheduled_time,
            end_time=end_time,
            location=interview.location,
        )

        return {
            "google_calendar_url": google_link,
            "outlook_calendar_url": outlook_link,
            "ics_download_url": f"/api/v1/calendar/ics/interview/{interview_id}",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to generate calendar links: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate calendar links")


# ============================================
# GOOGLE CALENDAR INTEGRATION
# ============================================


@router.post("/google/connect")
async def connect_google_calendar(
    data: GoogleCalendarConnect,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Connect user's Google Calendar account
    Exchanges OAuth authorization code for access/refresh tokens
    """
    try:
        settings = get_settings()

        cal = _get_calendar_settings(user)

        # Exchange auth code for tokens
        if settings.google_client_id and settings.google_client_secret:
            token_url = "https://oauth2.googleapis.com/token"
            token_data = {
                "code": data.authorization_code,
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "redirect_uri": settings.google_redirect_uri or settings.base_url,
                "grant_type": "authorization_code",
            }
            token_response = requests.post(token_url, data=token_data, timeout=15)
            if token_response.ok:
                tokens = token_response.json()
                cal["google_access_token"] = encrypt_text(tokens.get("access_token"))
                cal["google_refresh_token"] = encrypt_text(tokens.get("refresh_token"))
                cal["google_token_expiry"] = str(
                    datetime.now(UTC).timestamp() + tokens.get("expires_in", 3600)
                )
                cal.pop("google_auth_code", None)
            else:
                logger.error(f"Google token exchange failed: {token_response.text}")
                raise HTTPException(
                    status_code=502,
                    detail="Failed to exchange authorization code with Google. Check OAuth configuration.",
                )
        else:
            cal["google_auth_code"] = encrypt_text(data.authorization_code)

        cal["google_connected"] = True
        _save_calendar_settings(user, db, cal)
        db.commit()

        logger.info(f"Google Calendar connected for user {user.id}")

        return {
            "success": True,
            "message": "Google Calendar connected successfully",
            "provider": "google",
        }

    except HTTPException:
        raise
    except requests.RequestException as e:
        logger.error(f"Google token exchange network error: {e}")
        raise HTTPException(
            status_code=502, detail="Failed to reach Google OAuth endpoint"
        )
    except Exception as e:
        logger.error(f"Failed to connect Google Calendar: {e}")
        raise HTTPException(status_code=500, detail="Failed to connect Google Calendar")


@router.post("/google/sync/interview/{interview_id}")
async def sync_interview_to_google(
    interview_id: int,
    user: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    """
    Sync interview to Google Calendar
    Creates event in user's Google Calendar
    """
    try:
        # Check if Google Calendar is connected
        if not hasattr(user, "calendar_settings") or not user.calendar_settings.get(
            "google_connected"
        ):
            raise HTTPException(
                status_code=400,
                detail="Google Calendar not connected. Please connect your calendar first.",
            )

        # Get interview with tenant isolation
        user_company_id = getattr(user, "_company_id", None)
        query = db.query(Interview).filter(Interview.id == interview_id)
        if user_company_id:
            query = query.filter(Interview.company_id == user_company_id)
        interview = query.first()
        if not interview:
            raise HTTPException(status_code=404, detail="Interview not found")

        # Get application and candidate
        app = (
            db.query(Application)
            .filter(Application.id == interview.application_id)
            .first()
        )
        candidate = app.owner if app else None

        # Get credentials (in production, retrieve from secure storage)
        credentials = user.calendar_settings.get("google_credentials", {})

        # Initialize Google Calendar integration
        google_cal = GoogleCalendarIntegration(credentials)

        # Calculate end time
        end_time = interview.scheduled_time + timedelta(
            minutes=interview.duration_minutes
        )

        # Get attendees
        participants = (
            db.query(InterviewParticipant)
            .filter(InterviewParticipant.interview_id == interview_id)
            .all()
        )
        attendees = [p.user.email for p in participants if p.user]
        if candidate:
            attendees.append(candidate.email)

        # Create event
        event_id = google_cal.create_event(
            title=f"{interview.type.capitalize()} Interview - {candidate.name if candidate else 'Candidate'}",
            description=interview.agenda or "Interview",
            start_time=interview.scheduled_time,
            end_time=end_time,
            attendees=attendees,
            location=interview.location,
            meeting_link=interview.meeting_link,
        )

        if event_id:
            # Store event ID for future updates/deletions
            interview.google_calendar_event_id = event_id
            db.commit()

            return {
                "success": True,
                "message": "Interview synced to Google Calendar",
                "event_id": event_id,
            }
        else:
            raise HTTPException(
                status_code=500, detail="Failed to create Google Calendar event"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to sync to Google Calendar: {e}")
        raise HTTPException(status_code=500, detail="Failed to sync to Google Calendar")


# ============================================
# OUTLOOK CALENDAR INTEGRATION
# ============================================


@router.post("/outlook/connect")
async def connect_outlook_calendar(
    data: OutlookCalendarConnect,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Connect user's Outlook Calendar account
    Requires Microsoft Graph API access token
    """
    try:
        cal = _get_calendar_settings(user)
        cal["outlook_connected"] = True
        cal["outlook_access_token"] = encrypt_text(data.access_token)
        _save_calendar_settings(user, db, cal)
        db.commit()

        logger.info(f"Outlook Calendar connected for user {user.id}")

        return {
            "success": True,
            "message": "Outlook Calendar connected successfully",
            "provider": "outlook",
        }

    except Exception as e:
        logger.error(f"Failed to connect Outlook Calendar: {e}")
        raise HTTPException(
            status_code=500, detail="Failed to connect Outlook Calendar"
        )


@router.get("/status")
async def get_calendar_status(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """
    Get user's calendar connection status
    """
    try:
        cal = _get_calendar_settings(user)

        return {
            "google_connected": cal.get("google_connected", False),
            "outlook_connected": cal.get("outlook_connected", False),
            "ics_available": True,
        }

    except Exception as e:
        logger.error(f"Failed to get calendar status: {e}")
        raise HTTPException(status_code=500, detail="Failed to get calendar status")


@router.post("/disconnect/{provider}")
async def disconnect_calendar(
    provider: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """
    Disconnect calendar provider
    """
    try:
        if provider not in ["google", "outlook"]:
            raise HTTPException(status_code=400, detail="Invalid provider")

        cal = _get_calendar_settings(user)

        if provider == "google":
            cal["google_connected"] = False
            cal.pop("google_auth_code", None)
            cal.pop("google_access_token", None)
            cal.pop("google_refresh_token", None)
            cal.pop("google_token_expiry", None)
            cal.pop("google_credentials", None)
        elif provider == "outlook":
            cal["outlook_connected"] = False
            cal.pop("outlook_access_token", None)

        _save_calendar_settings(user, db, cal)
        db.commit()

        return {
            "success": True,
            "message": f"{provider.capitalize()} Calendar disconnected",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to disconnect calendar: {e}")
        raise HTTPException(status_code=500, detail="Failed to disconnect calendar")
