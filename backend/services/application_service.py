"""Single entry point for Application creation.

No other module may construct Application instances directly.
"""

import logging
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from backend.models.ats.application import Application
from backend.models.ats.types import ApplicationType
from backend.services.candidate_service import CandidateService

logger = logging.getLogger(__name__)

DIRECT_SOURCES = {"direct", "linkedin", "social_media", "website", "referral", "other"}

_SOURCE_ALIASES = {
    "linked_in": "linkedin",
    "linkedin": "linkedin",
    "social": "social_media",
    "socialmedia": "social_media",
    "social_media": "social_media",
    "facebook": "social_media",
    "instagram": "social_media",
    "tiktok": "social_media",
    "job_board": "website",
    "company_website": "website",
    "website": "website",
    "site": "website",
    "referral": "referral",
    "refer": "referral",
    "direct": "direct",
    "campaign": "campaign",
    "campaign_manager": "campaign",
    "import": "import",
    "upload": "upload",
    "ats": "ats",
    "manual": "manual",
    "other": "other",
}


def normalize_application_source(value: str | None, *, allow_campaign: bool = False) -> str:
    """Canonicalize a candidate-acquisition source string.

    ``allow_campaign=False`` (candidate-facing capture) restricts the result to
    direct acquisition channels (direct/linkedin/social_media/website/referral/
    other); anything else normalizes to ``other``. ``allow_campaign=True`` lets
    backend flows (campaign upload, import) record campaign/import/upload/ats
    sources as-is.
    """
    if not value:
        return "direct"
    key = value.strip().lower().replace(" ", "_").replace("-", "_")
    normalized = _SOURCE_ALIASES.get(key, "other")
    if not allow_campaign and normalized not in DIRECT_SOURCES:
        return "other"
    return normalized


class ApplicationService:
    """Stateless service for Application operations."""

    @staticmethod
    def create_application(
        db: Session,
        company_id: int | None,
        application_type: ApplicationType,
        *,
        candidate_email: str | None = None,
        candidate_phone: str | None = None,
        candidate_name: str | None = None,
        user_id: int | None = None,
        job_id: int | None = None,
        batch_id: int | None = None,
        status: str = "pending",
        declared_role: str | None = None,
        source: str | None = None,
        language: str = "English",
        **extra_fields,
    ) -> Application:
        """Create an Application with guaranteed Candidate linkage.

        Steps:
          1. Resolve or create Candidate via CandidateService
          2. Build Application with candidate_id, type, and metadata
          3. Flush and return
        """
        candidate = CandidateService.resolve_or_create_candidate(
            db,
            company_id=company_id,
            email=candidate_email,
            phone=candidate_phone,
            full_name=candidate_name,
        )

        now = datetime.now(UTC).replace(tzinfo=None)

        app = Application(
            user_id=user_id,
            company_id=company_id,
            candidate_id=candidate.id,
            application_type=application_type,
            full_name=candidate_name,
            email=candidate_email or "",
            phone=candidate_phone,
            job_id=job_id,
            batch_id=batch_id,
            status=status,
            declared_role=declared_role,
            source=source,
            language=language,
            created_at=now,
            updated_at=now,
            **extra_fields,
        )
        db.add(app)
        db.flush()
        logger.debug(
            "Created Application id=%s type=%s candidate_id=%s company=%s",
            app.id,
            application_type.value,
            candidate.id,
            company_id,
        )
        return app
