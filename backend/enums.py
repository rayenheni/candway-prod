"""
Application Enums for Candway ATS
Provides consistent status values across the platform
"""

from enum import Enum


class ApplicationStatus(str, Enum):
    """Application status workflow.

    Bug L-02: the codebase previously used four overlapping raw
    strings on ``Application.status`` that were not represented in
    this enum:

    * ``"applied"``  — written by the candidate-facing apply flow.
    * ``"invited"``  — written by recruiter invitation flows.
    * ``"imported"`` — written by bulk-recruiter import tools.
    * ``"pending"``  — the existing enum value, but also written
      as a default everywhere else in the code.

    Different services treated these as semantically different
    states, so a candidate's dashboard could show "applied" while
    the recruiter view treated it as "pending". We now centralise
    all four. The values are unchanged so existing rows remain
    valid; new code should use the enum rather than the raw
    string.

    The five analysis-lifecycle statuses written by CV-analysis /
    background flows (``analyzing``, ``analyzed``,
    ``analysis_failed``, ``failed``, ``active``) are also valid DB
    values under ``ck_application_status`` and are represented here
    so ``canonicalize_status`` never collapses them to ``pending``.
    """

    APPLIED = "applied"
    INVITED = "invited"
    IMPORTED = "imported"
    PENDING = "pending"
    SCREENING = "screening"
    ANALYZING = "analyzing"
    ANALYZED = "analyzed"
    ANALYSIS_FAILED = "analysis_failed"
    FAILED = "failed"
    ACTIVE = "active"
    REVIEWED = "reviewed"
    SHORTLISTED = "shortlisted"
    INTERVIEWING = "interviewing"
    OFFER = "offer"
    OFFER_DECLINED = "offer_declined"  # B2 FIX: candidate declined the offer letter
    HIRED = "hired"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"


# Legacy aliases — the strings the codebase used to write directly
# are still legal as enum members, so an Application row with
# ``status="applied"`` still matches ``ApplicationStatus.APPLIED``.
# These aliases let older call-sites that import the enum and write
# ``ApplicationStatus.PENDING`` keep working even if a future
# rename drops the ``pending`` alias in favour of a richer state.
_LEGACY_STATUS_ALIASES = {
    "applied": "applied",
    "invited": "invited",
    "imported": "imported",
    "offer_declined": "offer_declined",  # B2 FIX: honour legacy rows written before enum existed
}


def canonicalize_status(value: str) -> str:
    """Normalise a raw ``Application.status`` string to a known enum value.

    Empty / unknown values collapse to ``"pending"`` so the column
    always carries a value the rest of the system understands.
    """
    if not value:
        return "pending"
    v = value.strip().lower()
    if v in _LEGACY_STATUS_ALIASES:
        return _LEGACY_STATUS_ALIASES[v]
    if v in {member.value for member in ApplicationStatus}:
        return v
    return "pending"


class InterviewStatus(str, Enum):
    """Interview status tracking"""

    SCHEDULED = "scheduled"
    RESCHEDULED = "rescheduled"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    NO_SHOW = "no_show"


class InterviewType(str, Enum):
    """Types of interviews"""

    PHONE = "phone"
    VIDEO = "video"
    ONSITE = "onsite"
    TECHNICAL = "technical"
    BEHAVIORAL = "behavioral"
    PANEL = "panel"


class OfferStatus(str, Enum):
    """Offer tracking statuses"""

    PENDING = "pending"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    EXPIRED = "expired"
    WITHDRAWN = "withdrawn"


class InteractionType(str, Enum):
    """Types of candidate interactions"""

    EMAIL = "email"
    CALL = "call"
    NOTE = "note"
    INTERVIEW = "interview"
    OFFER = "offer"
    MESSAGE = "message"
    MEETING = "meeting"


class FeedbackRecommendation(str, Enum):
    """Interview feedback recommendations"""

    STRONG_YES = "strong_yes"
    YES = "yes"
    MAYBE = "maybe"
    NO = "no"
    STRONG_NO = "strong_no"
