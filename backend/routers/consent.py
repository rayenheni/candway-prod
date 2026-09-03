"""P1-04 FIX: GDPR consent capture endpoint.

A user (or a recruiter) must be able to record explicit consent
for each category of processing we do. The captured consent
rows are written to ``ConsentLog`` (immutable) and used by
:func:`backend.llm_consent.is_provider_allowed` to gate LLM
calls.

Valid agreement types:

* ``terms_and_privacy`` — Terms of Service + Privacy Policy
* ``marketing_emails`` — newsletter / product updates
* ``ai_processing`` — generic AI features (Groq, Gemini, Ollama)
* ``ai_processing_deepseek`` — high-risk provider (requires
  separate explicit consent)
* ``ai_processing_gemini`` — Gemini-specific consent
* ``cookies_analytics`` — non-essential cookies

The endpoint is intentionally small: it does not verify the
user actually read the policy. The legal record of "consent
captured at <timestamp> by <ip>" is enough for an audit.
"""

from datetime import UTC, datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from backend.database import AuditLog, ConsentLog, User
from backend.dependencies import get_current_user, get_db
from backend.logger import logger
from backend.profile_helpers import get_user_admin_permissions, get_user_is_super_admin

router = APIRouter(prefix="/gdpr", tags=["gdpr"])


ALLOWED_AGREEMENT_TYPES = frozenset(
    {
        "terms_and_privacy",
        "marketing_emails",
        "ai_processing",
        "ai_processing_deepseek",
        "ai_processing_gemini",
        "cookies_analytics",
    }
)


class ConsentCaptureRequest(BaseModel):
    agreement_types: List[str] = Field(
        ...,
        min_length=1,
        description="One or more agreement types the user is consenting to.",
    )
    policy_version: str = Field(
        "v1",
        max_length=50,
        description="Version of the policy text the user accepted.",
    )

    @field_validator("agreement_types")
    @classmethod
    def _validate_types(cls, value: List[str]) -> List[str]:
        if not value:
            raise ValueError("at least one agreement_type is required")
        bad = [t for t in value if t not in ALLOWED_AGREEMENT_TYPES]
        if bad:
            raise ValueError(
                f"unknown agreement_types: {bad}. Allowed: "
                f"{sorted(ALLOWED_AGREEMENT_TYPES)}"
            )
        return value


class ConsentCaptureResponse(BaseModel):
    user_id: int
    captured_at: str
    consent_ids: List[int]
    agreement_types: List[str]


@router.post(
    "/consent/{user_id}",
    response_model=ConsentCaptureResponse,
    status_code=201,
)
def capture_consent(
    user_id: int,
    body: ConsentCaptureRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Record explicit consent for one or more processing
    categories. A user can capture consent only for themselves;
    an admin with ``manage_users`` can capture consent on behalf
    of any user."""
    is_self = user_id == current_user.id
    is_admin = (
        get_user_is_super_admin(current_user)
        or (get_user_admin_permissions(current_user) or "").find("manage_users") != -1
    )
    if not (is_self or is_admin):
        raise HTTPException(
            status_code=403,
            detail=(
                "You can only capture consent for your own account; "
                "admins with manage_users can capture consent for any user."
            ),
        )

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="user not found")

    ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent", "")[:500] or None
    captured_at = datetime.now(UTC)
    consent_ids: List[int] = []
    rows: List[ConsentLog] = []
    for agreement_type in body.agreement_types:
        row = ConsentLog(
            user_id=user_id,
            agreement_type=agreement_type,
            version=body.policy_version,
            ip_address=ip,
            user_agent=ua,
            accepted_at=captured_at,
        )
        db.add(row)
        rows.append(row)
    try:
        db.flush()
    except Exception as e:  # noqa: BLE001
        db.rollback()
        logger.error(f"[CONSENT] flush failed for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="consent capture failed")
    consent_ids = [r.id for r in rows]

    db.add(
        AuditLog(
            user_id=current_user.id,
            action="gdpr_consent_captured",
            target_id=str(user_id),
            details=(
                f"types={body.agreement_types} "
                f"version={body.policy_version} "
                f"admin={is_admin}"
            ),
            ip_address=ip,
        )
    )
    db.commit()

    return ConsentCaptureResponse(
        user_id=user_id,
        captured_at=captured_at.isoformat(),
        consent_ids=consent_ids,
        agreement_types=body.agreement_types,
    )


@router.get("/consent/{user_id}")
def list_consents(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return the current consent rows for ``user_id``. A user can
    read their own; an admin with ``manage_users`` can read any."""
    is_self = user_id == current_user.id
    is_admin = (
        get_user_is_super_admin(current_user)
        or (get_user_admin_permissions(current_user) or "").find("manage_users") != -1
    )
    if not (is_self or is_admin):
        raise HTTPException(status_code=403, detail="forbidden")

    rows = (
        db.query(ConsentLog)
        .filter(ConsentLog.user_id == user_id)
        .order_by(ConsentLog.accepted_at.desc())
        .all()
    )
    return {
        "user_id": user_id,
        "consents": [
            {
                "id": r.id,
                "agreement_type": r.agreement_type,
                "version": r.version,
                "accepted_at": (r.accepted_at.isoformat() if r.accepted_at else None),
            }
            for r in rows
        ],
    }
