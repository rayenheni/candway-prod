"""ConfigurationResolver — normalises any interview entry point into an
immutable ``ResolvedEvaluationConfig`` and persists it as an
``EvaluationConfigSnapshot``.

Usage from an entry-point handler::

    from backend.rubric.config_resolver import ConfigurationResolver

    snapshot = ConfigurationResolver.resolve(
        db, entry_point,
        rubric_record=rubric,
        job=job,
        campaign_config=campaign_config,   # optional
        explicit_overrides={"language": "fr"},
    )
    session.evaluation_config_snapshot_id = snapshot.id
"""

import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from backend.models.evaluation.config_snapshot import (
    EntryPoint,
    EvaluationConfigSnapshot,
    ResolvedEvaluationConfig,
)

logger = logging.getLogger(__name__)


@dataclass
class _ScratchConfig:
    """Mutable scratchpad used internally during resolution.

    All fields start at ``None`` so each resolution layer can override.
    System defaults are applied as the final step.
    """

    source_type: str
    source_id: Optional[int] = None
    rubric_id: Optional[int] = None
    rubric_version: Optional[int] = None
    total_questions: Optional[int] = None
    time_limit_seconds: Optional[int] = None
    passing_score: Optional[float] = None
    max_score: Optional[float] = None
    interview_instructions: Optional[str] = None
    language: Optional[str] = None
    question_generation_prompt: Optional[str] = None
    evaluation_criteria: Optional[Dict[str, Any]] = None
    scoring_weights: Optional[Dict[str, float]] = None
    resolved_rubric_json: Optional[Dict[str, Any]] = None
    resolved_skills_json: Optional[List[Dict[str, Any]]] = None
    interview_config_json: Optional[Dict[str, Any]] = None
    scoring_rules_json: Optional[Dict[str, Any]] = None
    source_metadata: Optional[Dict[str, Any]] = None


def _set_if_not_none(cfg: _ScratchConfig, attr: str, value: Any) -> None:
    """Set ``attr`` on *cfg* only when *value* is not ``None``."""
    if value is not None:
        setattr(cfg, attr, value)


class ConfigurationResolver:
    """One-shot resolver that applies the config hierarchy and persists."""

    # ── Resolution defaults (lowest priority) ────────────────────
    DEFAULT_TOTAL_QUESTIONS = 15
    DEFAULT_TIME_LIMIT = 1800
    DEFAULT_PASSING_SCORE = 0.0
    DEFAULT_MAX_SCORE = 100.0
    DEFAULT_LANGUAGE = "en"

    @classmethod
    def resolve(
        cls,
        db: Session,
        entry_point: EntryPoint,
        *,
        company_id: int,
        rubric_record: Optional[Any] = None,
        db_rubric_id: Optional[int] = None,
        job: Optional[Any] = None,
        campaign_config: Optional[Dict[str, Any]] = None,
        explicit_overrides: Optional[Dict[str, Any]] = None,
    ) -> EvaluationConfigSnapshot:
        """Apply the resolution hierarchy and persist the snapshot.

        Hierarchy (highest to lowest priority):
          1. explicit_overrides
          2. campaign_config
          3. job fields
          4. rubric_record fields
          5. system defaults

        Raises:
            RuntimeError: if resolution or persistence fails.
        """
        # If rubric_record is not passed, load it using the job or rubric_id
        if rubric_record is None:
            try:
                from backend.rubric.rubric_loader import (
                    load_current_rubric_record,
                    load_rubric_by_id,
                )

                if job is not None:
                    rubric_id = getattr(job, "rubric_id", None)
                    if rubric_id:
                        rubric_record = load_rubric_by_id(
                            rubric_id,
                            db=db,
                            company_id=company_id,
                        )
                    if rubric_record is None:
                        rubric_record, _ = load_current_rubric_record(
                            job.id,
                            company_id=company_id,
                        )
            except Exception as exc:
                logger.warning(
                    "Failed to load rubric record for job %s: %s",
                    getattr(job, "id", None),
                    exc,
                )

        cfg = _ScratchConfig(
            source_type=entry_point.source_type,
            source_id=entry_point.source_id or entry_point.source_id,
        )

        # ── 4. Rubric defaults ────────────────────────────────────
        if rubric_record is not None:
            try:
                cls._apply_rubric(cfg, rubric_record)
            except Exception as exc:
                logger.warning("Failed to apply rubric record: %s", exc)

        # Override rubric_id with the DB integer ID if provided
        if db_rubric_id is not None:
            cfg.rubric_id = db_rubric_id

        # ── 3. Job overrides ──────────────────────────────────────
        if job is not None:
            try:
                cls._apply_job(cfg, job)
            except Exception as exc:
                logger.warning(
                    "Failed to apply job overrides for job %s: %s",
                    getattr(job, "id", None),
                    exc,
                )

        # ── 2. Campaign overrides ─────────────────────────────────
        if campaign_config is not None:
            try:
                cls._apply_campaign(cfg, campaign_config)
            except Exception as exc:
                logger.warning("Failed to apply campaign config: %s", exc)

        # ── 1. Explicit overrides (highest priority) ──────────────
        if explicit_overrides is not None:
            cls._apply_overrides(cfg, explicit_overrides)

        # ── 0. System defaults (lowest priority) ──────────────────
        cls._apply_defaults(cfg)

        # ── Build frozen config and persist ───────────────────────
        try:
            resolved = ResolvedEvaluationConfig(
                source_type=cfg.source_type,
                source_id=cfg.source_id,
                rubric_id=cfg.rubric_id,
                rubric_version=cfg.rubric_version,
                total_questions=cfg.total_questions,
                time_limit_seconds=cfg.time_limit_seconds,
                passing_score=cfg.passing_score,
                max_score=cfg.max_score,
                interview_instructions=cfg.interview_instructions,
                language=cfg.language,
                question_generation_prompt=cfg.question_generation_prompt,
                evaluation_criteria=cfg.evaluation_criteria,
                scoring_weights=cfg.scoring_weights,
                resolved_rubric_json=cfg.resolved_rubric_json,
                resolved_skills_json=cfg.resolved_skills_json,
                interview_config_json=cfg.interview_config_json,
                scoring_rules_json=cfg.scoring_rules_json,
                source_metadata=cfg.source_metadata,
            )
        except Exception as exc:
            logger.error("Failed to build ResolvedEvaluationConfig: %s", exc)
            raise RuntimeError(f"Config resolution failed: {exc}") from exc

        try:
            return cls._persist(db, resolved, company_id=company_id)
        except Exception as exc:
            logger.error("Failed to persist EvaluationConfigSnapshot: %s", exc)
            db.rollback()
            raise RuntimeError(f"Snapshot persistence failed: {exc}") from exc

    # ── Internal helpers ────────────────────────────────────────────

    @classmethod
    def _apply_rubric(cls, cfg: _ScratchConfig, rubric) -> None:
        _set_if_not_none(cfg, "rubric_id", getattr(rubric, "id", None))
        _set_if_not_none(cfg, "rubric_version", getattr(rubric, "version", None))
        _set_if_not_none(cfg, "passing_score", getattr(rubric, "passing_score", None))
        rubric_max = getattr(rubric, "max_score", None)
        if rubric_max is not None:
            _set_if_not_none(cfg, "max_score", rubric_max)

        # Parse criteria_json -> full rubric dict + skills
        if hasattr(rubric, "model_dump"):
            raw = rubric.model_dump()
        else:
            raw = getattr(rubric, "criteria_json", None) or getattr(
                rubric, "rubric_json", None
            )
        if raw is not None:
            if isinstance(raw, str):
                try:
                    raw = json.loads(raw)
                except (json.JSONDecodeError, TypeError) as exc:
                    logger.warning(
                        "Failed to parse rubric criteria_json for rubric_id=%s: %s",
                        getattr(rubric, "id", None),
                        exc,
                    )
                    raw = None
            if raw:
                _set_if_not_none(cfg, "evaluation_criteria", raw)
                _set_if_not_none(cfg, "resolved_rubric_json", raw)
                skills = cls._extract_skills_from_rubric(raw)
                if skills:
                    _set_if_not_none(cfg, "resolved_skills_json", skills)

    @classmethod
    def _extract_skills_from_rubric(cls, rubric_dict: dict) -> list:
        skills = []
        for cat in rubric_dict.get("categories") or []:
            for sub in cat.get("subcategories") or []:
                for skill in sub.get("skills") or []:
                    skills.append(
                        {
                            "name": skill.get("name"),
                            "category": cat.get("name"),
                            "subcategory": sub.get("name"),
                            "weight": skill.get("weight", 1.0),
                            "is_required": skill.get("is_required", False),
                            "keywords": skill.get("keywords", []),
                        }
                    )
        return skills

    @classmethod
    def _apply_job(cls, cfg: _ScratchConfig, job) -> None:
        _set_if_not_none(
            cfg, "interview_instructions", getattr(job, "interview_instructions", None)
        )
        _set_if_not_none(cfg, "total_questions", getattr(job, "total_questions", None))
        _set_if_not_none(cfg, "rubric_id", getattr(job, "rubric_id", None))
        lang = getattr(job, "language", None) or getattr(job, "lang", None)
        _set_if_not_none(cfg, "language", lang)
        time_limit = (
            getattr(job, "time_limit_seconds", None)
            or getattr(job, "time_limit", None)
            or (
                getattr(job, "duration_minutes", None) * 60
                if getattr(job, "duration_minutes", None)
                else None
            )
        )
        _set_if_not_none(
            cfg,
            "question_generation_prompt",
            getattr(job, "custom_question_prompt", None)
            or getattr(job, "question_generation_prompt", None),
        )
        _set_if_not_none(cfg, "time_limit_seconds", time_limit)

    @classmethod
    def _apply_campaign(
        cls, cfg: _ScratchConfig, campaign_config: Dict[str, Any]
    ) -> None:
        _set_if_not_none(cfg, "total_questions", campaign_config.get("total_questions"))
        _set_if_not_none(
            cfg, "time_limit_seconds", campaign_config.get("time_limit_seconds")
        )
        _set_if_not_none(
            cfg, "interview_instructions", campaign_config.get("interview_instructions")
        )
        _set_if_not_none(cfg, "language", campaign_config.get("language"))
        _set_if_not_none(
            cfg,
            "question_generation_prompt",
            campaign_config.get("question_generation_prompt"),
        )
        _set_if_not_none(cfg, "scoring_weights", campaign_config.get("scoring_weights"))
        _set_if_not_none(
            cfg, "source_metadata", campaign_config.get("metadata", campaign_config)
        )

    @classmethod
    def _apply_defaults(cls, cfg: _ScratchConfig) -> None:
        if cfg.total_questions is None:
            cfg.total_questions = cls.DEFAULT_TOTAL_QUESTIONS
        if cfg.time_limit_seconds is None:
            cfg.time_limit_seconds = cls.DEFAULT_TIME_LIMIT
        if cfg.passing_score is None:
            cfg.passing_score = cls.DEFAULT_PASSING_SCORE
        if cfg.max_score is None:
            cfg.max_score = cls.DEFAULT_MAX_SCORE
        if cfg.language is None:
            cfg.language = cls.DEFAULT_LANGUAGE

        # Build frozen interview_config_json
        cfg.interview_config_json = {
            "language": cfg.language,
            "max_questions": cfg.total_questions,
            "time_limit_seconds": cfg.time_limit_seconds,
            "question_generation_prompt": cfg.question_generation_prompt,
        }

        # Build frozen scoring_rules_json
        cfg.scoring_rules_json = {
            "passing_score": cfg.passing_score,
            "max_score": cfg.max_score,
            "scoring_weights": cfg.scoring_weights,
        }

    @classmethod
    def _apply_overrides(cls, cfg: _ScratchConfig, overrides: Dict[str, Any]) -> None:
        for key in (
            "total_questions",
            "time_limit_seconds",
            "passing_score",
            "max_score",
            "interview_instructions",
            "language",
            "question_generation_prompt",
            "evaluation_criteria",
            "scoring_weights",
            "source_metadata",
            "rubric_id",
            "rubric_version",
            "resolved_rubric_json",
            "resolved_skills_json",
            "interview_config_json",
            "scoring_rules_json",
        ):
            val = overrides.get(key)
            if val is not None:
                setattr(cfg, key, val)

    @classmethod
    def _persist(
        cls, db: Session, resolved: ResolvedEvaluationConfig, *, company_id: int
    ) -> EvaluationConfigSnapshot:
        config_hash = resolved.compute_hash()

        existing = (
            db.query(EvaluationConfigSnapshot)
            .filter(
                EvaluationConfigSnapshot.company_id == company_id,
                EvaluationConfigSnapshot.hash == config_hash,
            )
            .first()
        )
        if existing is not None:
            logger.debug(
                "Reusing existing EvaluationConfigSnapshot id=%s hash=%s",
                existing.id,
                config_hash,
            )
            return existing

        snapshot = EvaluationConfigSnapshot(
            company_id=company_id,
            source_type=resolved.source_type,
            source_id=resolved.source_id,
            hash=config_hash,
            rubric_id=resolved.rubric_id,
            rubric_version=resolved.rubric_version,
            total_questions=resolved.total_questions,
            time_limit_seconds=resolved.time_limit_seconds,
            passing_score=resolved.passing_score,
            max_score=resolved.max_score,
            interview_instructions=resolved.interview_instructions,
            language=resolved.language,
            question_generation_prompt=resolved.question_generation_prompt,
            evaluation_criteria=resolved.evaluation_criteria,
            scoring_weights=resolved.scoring_weights,
            resolved_rubric_json=resolved.resolved_rubric_json,
            resolved_skills_json=resolved.resolved_skills_json,
            interview_config_json=resolved.interview_config_json,
            scoring_rules_json=resolved.scoring_rules_json,
            source_metadata=resolved.source_metadata,
            config_json=resolved._as_dict(),
        )
        db.add(snapshot)
        db.flush()
        logger.info(
            "Created EvaluationConfigSnapshot id=%s source=%s/%s hash=%s",
            snapshot.id,
            resolved.source_type,
            resolved.source_id,
            config_hash,
        )
        return snapshot
