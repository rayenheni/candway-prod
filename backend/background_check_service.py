import asyncio
import hashlib
import hmac
import json
import logging
from datetime import UTC, datetime
from typing import Optional

import httpx
from sqlalchemy.orm import Session

from backend.config import get_settings
from backend.database import (
    Application,
    BackgroundCheck,
    BackgroundCheckStatusLog,
    User,
)
from backend.encryption import decrypt_text
from backend.profile_helpers import get_user_name, get_user_phone

logger = logging.getLogger(__name__)

# Shared HTTP client with connection pooling for Checkr API calls
_checkr_client: Optional[httpx.AsyncClient] = None
_checkr_client_lock = asyncio.Lock()


def _get_checkr_client() -> httpx.AsyncClient:
    global _checkr_client
    if _checkr_client is None or _checkr_client.is_closed:
        raise RuntimeError(
            "Checkr HTTP client not initialized. Call init_checkr_client() first."
        )
    return _checkr_client


def init_checkr_client():
    """Initialize the shared Checkr HTTP client with connection pooling.
    Call once at application startup."""
    global _checkr_client
    _checkr_client = httpx.AsyncClient(
        timeout=httpx.Timeout(30.0, connect=10.0),
        limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
    )


CHECKR_EVENTS = {
    "report.created": "pending_report",
    "report.completed": "report_ready",
    "report.dispute_created": "disputed",
    "candidate.created": "candidate_created",
    "invitation.completed": "invited",
}


class BackgroundCheckService:
    API_BASE = "https://api.checkr.com/v1"

    @staticmethod
    def _get_api_key() -> str:
        settings = get_settings()
        key = settings.checkr_api_key
        if not key:
            raise RuntimeError("CHECKR_API_KEY is not configured")
        return key

    @staticmethod
    def _get_headers() -> dict:
        api_key = BackgroundCheckService._get_api_key()
        return {
            "Authorization": f"Basic {api_key}",
            "Content-Type": "application/json",
        }

    @staticmethod
    def _log_status_change(
        bg_check_id: int,
        from_status: Optional[str],
        to_status: str,
        db: Session,
        changed_by: Optional[int] = None,
        details: Optional[str] = None,
        company_id: int = None,
    ):
        log = BackgroundCheckStatusLog(
            background_check_id=bg_check_id,
            from_status=from_status,
            to_status=to_status,
            changed_by=changed_by,
            details=details,
            company_id=company_id,
        )
        db.add(log)
        db.commit()

    @staticmethod
    async def create_candidate(
        application_id: int, db: Session, company_id: int = None
    ) -> dict:
        app = db.query(Application).filter(Application.id == application_id).first()
        if not app:
            raise ValueError(f"Application {application_id} not found")
        if company_id is not None and app.company_id != company_id:
            raise ValueError(
                f"Application {application_id} does not belong to company {company_id}"
            )

        user = db.query(User).filter(User.id == app.user_id).first()
        if not user:
            raise ValueError(f"User not found for application {application_id}")

        dob_raw = getattr(user, "date_of_birth", None) or ""
        ssn_raw = getattr(user, "ssn_last_four", None) or ""
        dob = decrypt_text(dob_raw) if dob_raw else ""
        ssn = decrypt_text(ssn_raw) if ssn_raw else ""

        user_name = get_user_name(user)
        payload = {
            "first_name": (user_name or app.full_name).split(" ")[0],
            "last_name": " ".join((user_name or app.full_name).split(" ")[1:]),
            "email": app.email,
            "phone": app.phone or get_user_phone(user) or "",
        }
        if dob:
            payload["dob"] = dob
        if ssn:
            payload["ssn"] = ssn

        client = _get_checkr_client()
        resp = await client.post(
            f"{BackgroundCheckService.API_BASE}/candidates",
            headers=BackgroundCheckService._get_headers(),
            json=payload,
        )
        if resp.status_code not in (200, 201):
            logger.error(
                f"Checkr create_candidate failed: {resp.status_code} {resp.text}"
            )
            raise RuntimeError(f"Checkr API error: {resp.status_code}")

        data = resp.json()
        candidate_id = data.get("id")
        if not candidate_id:
            raise RuntimeError("No candidate_id in Checkr response")

        bg_check = (
            db.query(BackgroundCheck)
            .filter(BackgroundCheck.application_id == application_id)
            .first()
        )
        if bg_check:
            old_status = bg_check.status
            bg_check.provider_candidate_id = candidate_id
            bg_check.status = "candidate_created"
            bg_check.updated_at = datetime.now(UTC).replace(tzinfo=None)
        else:
            bg_check = BackgroundCheck(
                application_id=application_id,
                provider_candidate_id=candidate_id,
                status="candidate_created",
                company_id=company_id,
            )
            db.add(bg_check)
            old_status = None

        db.commit()
        db.refresh(bg_check)

        BackgroundCheckService._log_status_change(
            bg_check.id,
            old_status,
            "candidate_created",
            db,
            details=f"Checkr candidate: {candidate_id}",
            company_id=company_id,
        )

        return {
            "background_check_id": bg_check.id,
            "checkr_candidate_id": candidate_id,
        }

    @staticmethod
    async def create_invitation(
        background_check_id: int, db: Session, company_id: int = None
    ) -> dict:
        bg_check = (
            db.query(BackgroundCheck)
            .filter(BackgroundCheck.id == background_check_id)
            .first()
        )
        if not bg_check:
            raise ValueError(f"BackgroundCheck {background_check_id} not found")
        if company_id is not None and bg_check.company_id != company_id:
            raise ValueError(
                f"BackgroundCheck {background_check_id} does not belong to company {company_id}"
            )

        candidate_id = bg_check.provider_candidate_id
        if not candidate_id:
            raise ValueError("No Checkr candidate_id found; create candidate first")

        payload = {
            "candidate_id": candidate_id,
            "package": "standard",
            "work_locations": [{"country": "US"}],
        }

        client = _get_checkr_client()
        resp = await client.post(
            f"{BackgroundCheckService.API_BASE}/invitations",
            headers=BackgroundCheckService._get_headers(),
            json=payload,
        )
        if resp.status_code not in (200, 201):
            logger.error(
                f"Checkr create_invitation failed: {resp.status_code} {resp.text}"
            )
            raise RuntimeError(f"Checkr API error: {resp.status_code}")

        data = resp.json()
        invitation_url = data.get("invitation_url")
        report_id = data.get("report_id")

        old_status = bg_check.status
        bg_check.status = "invited"
        if report_id:
            bg_check.provider_report_id = report_id
        bg_check.updated_at = datetime.now(UTC).replace(tzinfo=None)
        db.commit()

        BackgroundCheckService._log_status_change(
            bg_check.id,
            old_status,
            "invited",
            db,
            details="Invitation sent via Checkr",
            company_id=company_id,
        )

        return {
            "invitation_url": invitation_url,
            "report_id": report_id,
            "background_check_id": bg_check.id,
        }

    @staticmethod
    async def get_report_status(checkr_report_id: str) -> dict:
        client = _get_checkr_client()
        resp = await client.get(
            f"{BackgroundCheckService.API_BASE}/reports/{checkr_report_id}",
            headers=BackgroundCheckService._get_headers(),
        )
        if resp.status_code != 200:
            logger.error(f"Checkr get_report failed: {resp.status_code} {resp.text}")
            raise RuntimeError(f"Checkr API error: {resp.status_code}")
        return resp.json()

    @staticmethod
    async def get_report_details(checkr_report_id: str) -> dict:
        client = _get_checkr_client()
        resp = await client.get(
            f"{BackgroundCheckService.API_BASE}/reports/{checkr_report_id}",
            headers=BackgroundCheckService._get_headers(),
        )
        if resp.status_code != 200:
            logger.error(
                f"Checkr get_report_details failed: {resp.status_code} {resp.text}"
            )
            raise RuntimeError(f"Checkr API error: {resp.status_code}")
        return resp.json()

    @staticmethod
    def handle_webhook(payload: dict, signature: str, webhook_secret: str) -> dict:
        if not webhook_secret:
            raise ValueError(
                "CHECKR_WEBHOOK_SECRET is not configured — rejecting unauthenticated webhook"
            )
        raw_body = json.dumps(payload, separators=(",", ":"), sort_keys=True)
        expected_sig = hmac.new(
            webhook_secret.encode("utf-8"),
            raw_body.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(expected_sig, signature):
            raise ValueError("Invalid webhook signature")

        event_type = payload.get("type", "")
        data = payload.get("data", {}).get("object", {})

        checkr_status = CHECKR_EVENTS.get(event_type)
        report_id = data.get("id") or data.get("report_id")

        return {
            "event_type": event_type,
            "checkr_status": checkr_status,
            "report_id": report_id,
            "data": data,
        }

    @staticmethod
    def _determine_verdict(report: dict) -> str:
        adjudication = report.get("adjudication", "")
        if adjudication == "clear":
            return "clear"
        if adjudication in ("consider", "suspended"):
            return "consider"
        if adjudication in ("neutral", ""):
            findings = report.get("findings", []) or []
            if not findings:
                return "clear"
            has_adverse = any(
                f.get("adjudication") in ("consider", "suspended") for f in findings
            )
            return "consider" if has_adverse else "clear"
        return "consider"

    @staticmethod
    def _extract_findings(report: dict) -> list:
        findings = report.get("findings", []) or []
        extracted = []
        for f in findings:
            extracted.append(
                {
                    "name": f.get("name", "Unknown"),
                    "status": f.get("status", ""),
                    "adjudication": f.get("adjudication", ""),
                    "text": f.get("text", ""),
                    "result": f.get("result", ""),
                }
            )
        return extracted
