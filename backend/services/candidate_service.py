"""Single source of truth for Candidate resolution and creation.

No other module may find, create, or merge Candidate records.
"""

import logging

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.models.ats.candidate import Candidate

logger = logging.getLogger(__name__)

_MAX_RETRIES = 3


class CandidateService:
    """Stateless service for Candidate operations."""

    @staticmethod
    def resolve_or_create_candidate(
        db: Session,
        company_id: int | None,
        email: str | None = None,
        phone: str | None = None,
        full_name: str | None = None,
    ) -> Candidate:
        """Find existing Candidate or create one.

        Resolution order (safe under concurrent access via DB unique
        constraints + retry):
          1. (company_id, email) — exact match, case-sensitive
          2. (company_id, phone) — if email didn't match
          3. Create new Candidate row

        Concurrency: relies on the DB-level UNIQUE(company_id, email)
        constraint.  If a concurrent insert wins the race, the
        IntegrityError is caught and a follow-up SELECT returns the row.
        """
        candidate = CandidateService._find_by_email(db, company_id, email)
        if candidate:
            return candidate

        candidate = CandidateService._find_by_phone(db, company_id, phone)
        if candidate:
            return candidate

        return CandidateService._create_with_retry(
            db, company_id, email, phone, full_name
        )

    @staticmethod
    def _find_by_email(
        db: Session,
        company_id: int | None,
        email: str | None,
    ) -> Candidate | None:
        if not email:
            return None
        return (
            db.query(Candidate)
            .filter(
                Candidate.company_id == company_id,
                Candidate.email == email,
                Candidate.deleted_at.is_(None),
            )
            .first()
        )

    @staticmethod
    def _find_by_phone(
        db: Session,
        company_id: int | None,
        phone: str | None,
    ) -> Candidate | None:
        if not phone:
            return None
        return (
            db.query(Candidate)
            .filter(
                Candidate.company_id == company_id,
                Candidate.phone == phone,
                Candidate.deleted_at.is_(None),
            )
            .first()
        )

    @staticmethod
    def _create_with_retry(
        db: Session,
        company_id: int | None,
        email: str | None,
        phone: str | None,
        full_name: str | None,
    ) -> Candidate:
        """INSERT with retry on unique-constraint violation.

        Uses a SAVEPOINT so a concurrent duplicate insert does not
        corrupt the outer transaction.
        """
        for attempt in range(1, _MAX_RETRIES + 1):
            savepoint = db.begin_nested()
            try:
                candidate = Candidate(
                    company_id=company_id,
                    email=email or "",
                    full_name=full_name,
                    phone=phone,
                )
                db.add(candidate)
                db.flush()
                savepoint.commit()
                logger.debug(
                    "Created Candidate id=%s for company=%s email=%s",
                    candidate.id,
                    company_id,
                    email,
                )
                return candidate
            except IntegrityError:
                savepoint.rollback()
                if attempt >= _MAX_RETRIES:
                    logger.warning(
                        "Failed to create Candidate after %d retries "
                        "for company=%s email=%s",
                        _MAX_RETRIES,
                        company_id,
                        email,
                    )
                    raise
                logger.debug(
                    "Retry %d/%d creating Candidate for company=%s email=%s",
                    attempt,
                    _MAX_RETRIES,
                    company_id,
                    email,
                )
                # The concurrent insert won — fetch their row
                candidate = CandidateService._find_by_email(
                    db, company_id, email
                ) or CandidateService._find_by_phone(db, company_id, phone)
                if candidate:
                    return candidate
        raise RuntimeError(
            f"Could not resolve or create Candidate for "
            f"company={company_id} email={email}"
        )
