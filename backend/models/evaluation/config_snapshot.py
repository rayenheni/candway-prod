"""EvaluationConfigSnapshot — immutable, self-contained config captured when an
interview session starts.  Guarantees deterministic, reproducible evaluation
regardless of which entry point triggered the interview.

Once created, a snapshot is NEVER modified.  The AI engine reads only from
this snapshot, never from live Campaign / Job / Rubric tables.
"""

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from sqlalchemy import JSON, Column, DateTime, Float, Index, Integer, String, Text
from sqlalchemy.orm import deferred, relationship

from backend.models.base import Base, TenantMixin, utcnow

# ═══════════════════════════════════════════════════════════════════════
# Pure-Python dataclass — used inside the application layer
# ═══════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class ResolvedEvaluationConfig:
    """Frozen, immutable evaluation configuration.

    Every interview entry point (campaign, job apply, individual audit,
    API, certification, marketplace) normalises into this shape before
    the AI engine touches any data.
    """

    source_type: str
    source_id: Optional[int] = None

    # Rubric
    rubric_id: Optional[int] = None
    rubric_version: Optional[int] = None

    # Interview shape
    total_questions: int = 15
    time_limit_seconds: Optional[int] = 1800

    # Scoring
    passing_score: Optional[float] = 0.0
    max_score: float = 100.0

    # Instructions & prompts
    interview_instructions: Optional[str] = None
    language: str = "en"
    question_generation_prompt: Optional[str] = None

    # Advanced
    evaluation_criteria: Optional[Dict[str, Any]] = None
    scoring_weights: Optional[Dict[str, float]] = None

    # Frozen rubric data (complete isolation from live Rubric table)
    resolved_rubric_json: Optional[Dict[str, Any]] = None
    resolved_skills_json: Optional[List[Dict[str, Any]]] = None
    interview_config_json: Optional[Dict[str, Any]] = None
    scoring_rules_json: Optional[Dict[str, Any]] = None

    # Arbitrary source metadata (campaign name, job title, etc.)
    source_metadata: Optional[Dict[str, Any]] = None

    def compute_hash(self) -> str:
        return hashlib.sha256(
            json.dumps(self._as_dict(), sort_keys=True, default=str).encode()
        ).hexdigest()

    def _as_dict(self) -> Dict[str, Any]:
        d = {
            "source_type": self.source_type,
            "source_id": self.source_id,
            "rubric_id": self.rubric_id,
            "rubric_version": self.rubric_version,
            "total_questions": self.total_questions,
            "time_limit_seconds": self.time_limit_seconds,
            "passing_score": self.passing_score,
            "max_score": self.max_score,
            "interview_instructions": self.interview_instructions,
            "language": self.language,
            "question_generation_prompt": self.question_generation_prompt,
            "evaluation_criteria": self.evaluation_criteria,
            "scoring_weights": self.scoring_weights,
            "resolved_rubric_json": self.resolved_rubric_json,
            "resolved_skills_json": self.resolved_skills_json,
            "interview_config_json": self.interview_config_json,
            "scoring_rules_json": self.scoring_rules_json,
            "source_metadata": self.source_metadata,
        }
        return {k: v for k, v in d.items() if v is not None}


@dataclass
class EntryPoint:
    """Describes how an interview was triggered.

    Passed to ``ConfigurationResolver.resolve()`` so it can walk the
    correct resolution chain for each source type.
    """

    source_type: str
    source_id: Optional[int] = None
    campaign_id: Optional[int] = None
    job_id: Optional[int] = None
    application_id: Optional[int] = None
    explicit_overrides: Optional[Dict[str, Any]] = None


# ═══════════════════════════════════════════════════════════════════════
# SQLAlchemy model — persisted row in ``evaluation_config_snapshots``
# ═══════════════════════════════════════════════════════════════════════


class EvaluationConfigSnapshot(Base, TenantMixin):
    """Immutable, self-contained evaluation configuration.

    Created when an interview session transitions from ``created`` to
    ``in_progress`` (or pre-created by Campaign as an optimisation).

    The AI engine MUST read ALL configuration from this row and NEVER
    from the live Campaign, Job, or Rubric tables.
    """

    __tablename__ = "evaluation_config_snapshots"
    __table_args__ = (
        Index("idx_ecs_source", "source_type", "source_id"),
        Index("idx_ecs_hash", "hash", unique=True),
        Index("idx_ecs_created", "created_at"),
        {"extend_existing": True},
    )

    id = Column(Integer, primary_key=True)

    # Entry-point identification
    source_type = Column(
        String(50), nullable=False
    )  # 'campaign', 'job_apply', 'individual_audit', 'api', etc.
    source_id = Column(Integer, nullable=True)  # PK of the source entity

    # Content-addressable hash — enables deduplication
    hash = Column(String(64), nullable=False, unique=True)

    # Denormalised config fields (also stored inside config_json for
    # queryability without deserialising JSON).
    rubric_id = Column(Integer, nullable=True)
    rubric_version = Column(Integer, nullable=True)
    total_questions = Column(Integer, nullable=False, default=15)
    time_limit_seconds = Column(Integer, nullable=True)
    passing_score = Column(Float, nullable=True)
    max_score = Column(Float, nullable=False, default=100.0)
    interview_instructions = Column(Text, nullable=True)
    language = Column(String(10), nullable=False, default="en")
    question_generation_prompt = Column(Text, nullable=True)
    evaluation_criteria = Column(JSON, nullable=True)
    scoring_weights = Column(JSON, nullable=True)
    source_metadata = Column("source_metadata", JSON, nullable=True)

    # Frozen rubric + skills + interview config (enables complete isolation)
    # Deferred: these JSON blobs can be 200KB+; only loaded when explicitly accessed
    resolved_rubric_json = deferred(Column("resolved_rubric_json", JSON, nullable=True))
    resolved_skills_json = deferred(Column("resolved_skills_json", JSON, nullable=True))
    interview_config_json = deferred(
        Column("interview_config_json", JSON, nullable=True)
    )
    scoring_rules_json = deferred(Column("scoring_rules_json", JSON, nullable=True))

    # Full frozen config blob — ALWAYS the SSOT for the AI engine
    config_json = deferred(Column(JSON, nullable=False))

    created_at = Column(DateTime, default=utcnow, nullable=False)

    # Back-populated from EvaluationSession
    evaluation_sessions = relationship(
        "EvaluationSession",
        back_populates="config_snapshot",
        foreign_keys="EvaluationSession.evaluation_config_snapshot_id",
    )
