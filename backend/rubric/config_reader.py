"""EvaluationConfigReader — single access point for the AI engine to read
frozen configuration from an ``EvaluationConfigSnapshot``.

Every read goes through this class.  No live DB lookups.
If a required snapshot is missing, the reader raises ``ConfigurationMissingError``.
"""

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from backend.models.evaluation.evaluation import EvaluationSession

logger = logging.getLogger(__name__)


class ConfigurationMissingError(RuntimeError):
    """Raised when the engine tries to read config but no snapshot exists."""

    pass


@dataclass
class ParsedRubric:
    """Lightweight parsed rubric — what the engine actually needs."""

    id: Optional[int] = None
    version: int = 1
    categories: List[Dict[str, Any]] = None
    skills: List[Dict[str, Any]] = None
    seniority: str = "mid"
    raw_json: Optional[Dict[str, Any]] = None

    def get_category_names(self) -> list:
        return [c.get("name", "") for c in (self.categories or [])]

    def get_skill_names(self) -> list:
        return [s.get("name", "") for s in (self.skills or [])]


class EvaluationConfigReader:
    """Read-only access to snapshot config.

    Usage::

        reader = EvaluationConfigReader(session)
        rubric = reader.get_rubric()
        settings = reader.get_interview_settings()

        # Or stateless style:
        reader = EvaluationConfigReader()
        rubric = reader.get_rubric(session)
    """

    def __init__(self, session: Optional[EvaluationSession] = None):
        self._session = session
        self._snap = session.config_snapshot if session else None

    # ── Helper ───────────────────────────────────────────────────

    def _get_snap(self, session: Optional[EvaluationSession] = None):
        snap = session.config_snapshot if session else self._snap
        if snap is None:
            sess_id = (
                session.id
                if session
                else (self._session.id if self._session else "unknown")
            )
            logger.warning(
                "EvaluationSession %s has no evaluation_config_snapshot_id. "
                "A snapshot must be created at interview start.",
                sess_id,
            )
            raise ConfigurationMissingError(
                f"EvaluationSession {sess_id} has no "
                f"evaluation_config_snapshot_id. "
                f"A snapshot must be created at interview start."
            )
        return snap

    # ── Rubric ────────────────────────────────────────────────────

    def get_rubric(self, session: Optional[EvaluationSession] = None) -> ParsedRubric:
        snap = self._get_snap(session)
        raw = snap.resolved_rubric_json
        if raw is None:
            logger.info(
                "Snapshot %s has no resolved_rubric_json; returning empty rubric "
                "(rubric_id=%s, version=%s)",
                snap.id,
                snap.rubric_id,
                snap.rubric_version,
            )
            return ParsedRubric(
                id=snap.rubric_id,
                version=snap.rubric_version or 1,
            )
        return ParsedRubric(
            id=snap.rubric_id,
            version=snap.rubric_version or raw.get("version", 1),
            categories=raw.get("categories", []),
            skills=self.get_skills(session),
            seniority=raw.get("seniority", "mid"),
            raw_json=raw,
        )

    def get_skills(self, session: Optional[EvaluationSession] = None) -> list:
        snap = self._get_snap(session)
        if snap.resolved_skills_json:
            return snap.resolved_skills_json
        return []

    # ── Interview settings ────────────────────────────────────────

    def get_interview_settings(
        self, session: Optional[EvaluationSession] = None
    ) -> dict:
        snap = self._get_snap(session)
        return {
            "language": snap.language or "en",
            "max_questions": snap.total_questions or 15,
            "time_limit_seconds": snap.time_limit_seconds or 1800,
            "question_generation_prompt": snap.question_generation_prompt,
            "interview_instructions": snap.interview_instructions,
            "total_questions": snap.total_questions or 15,
            "adaptive_difficulty": snap.interview_config_json.get(
                "adaptive_difficulty", True
            )
            if snap.interview_config_json
            else True,
        }

    # Convenience accessors
    def get_total_questions(self, session: Optional[EvaluationSession] = None) -> int:
        snap = self._get_snap(session)
        return snap.total_questions or 15

    def get_time_limit(self, session: Optional[EvaluationSession] = None) -> int:
        snap = self._get_snap(session)
        return snap.time_limit_seconds or 1800

    def get_instructions(self, session: Optional[EvaluationSession] = None) -> str:
        snap = self._get_snap(session)
        return snap.interview_instructions or ""

    def get_language(self, session: Optional[EvaluationSession] = None) -> str:
        snap = self._get_snap(session)
        return snap.language or "en"

    def get_question_generation_prompt(
        self, session: Optional[EvaluationSession] = None
    ) -> Optional[str]:
        snap = self._get_snap(session)
        return snap.question_generation_prompt

    def get_question_prompt(
        self, session: Optional[EvaluationSession] = None
    ) -> Optional[str]:
        return self.get_question_generation_prompt(session)

    # ── Scoring ───────────────────────────────────────────────────

    def get_scoring_rules(self, session: Optional[EvaluationSession] = None) -> dict:
        snap = self._get_snap(session)
        return {
            "passing_score": snap.passing_score or 0.0,
            "max_score": snap.max_score or 100.0,
            "scoring_weights": snap.scoring_weights or {},
            "coverage_multiplier": snap.scoring_rules_json.get(
                "coverage_multiplier", 0.10
            )
            if snap.scoring_rules_json
            else 0.10,
        }

    def get_passing_score(self, session: Optional[EvaluationSession] = None) -> float:
        snap = self._get_snap(session)
        return snap.passing_score or 0.0

    def get_max_score(self, session: Optional[EvaluationSession] = None) -> float:
        snap = self._get_snap(session)
        return snap.max_score or 100.0
