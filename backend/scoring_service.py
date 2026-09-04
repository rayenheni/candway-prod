"""
ScoringService — single canonical writer of EvaluationResult.

Rules:
  1. ONLY this service may write EvaluationResult.final_score
  2. ALL score computation flows through compute_final_score()
  3. No other file may import and write EvaluationResult directly
  4. Ranking reads from EvaluationResult.composite_score (never recomputes from raw scores)

Formula:
  final_score = cv_score * 0.25 + rubric_score * 0.50 + rubric_coverage_pct * 0.25

  With no rubric:
  final_score = cv_score * 0.75 + rubric_coverage_pct * 0.25

  human_integrity_score is preserved in the database for historical
  compatibility but has ZERO weight in the canonical formula.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError

from backend.database import (
    Application,
    EvaluationResult,
    EvaluationSession,
    RubricScoringDetail,
)
from backend.models.evaluation.verdict import Verdict as VerdictModel

logger = logging.getLogger(__name__)

CANONICAL_WEIGHTS = {
    "cv": 0.25,
    "rubric": 0.50,
    "human": 0.0,
    "coverage": 0.25,
}


class ScoringService:
    """Single writer of canonical scores. All scoring goes through here."""

    @staticmethod
    def _ensure_session(app: Application, db: Session) -> EvaluationSession:
        session = (
            db.query(EvaluationSession)
            .filter(EvaluationSession.application_id == app.id)
            .order_by(EvaluationSession.id.desc())
            .first()
        )
        if session is None:
            session = EvaluationSession(
                application_id=app.id,
                company_id=app.company_id,
                rubric_id=app.rubric_id,
                status="completed",
            )
            db.add(session)
            db.flush()
        return session

    @staticmethod
    def _ensure_rubric_snapshot(
        app: Application, db: Session, session: EvaluationSession
    ) -> Optional[int]:
        """Ensure rubric data is accessible via the session's config_snapshot.

        Uses EvaluationConfigReader to read frozen rubric data instead of
        querying live RubricDB.  The rubric_snapshot_id is a legacy field;
        for sessions with a config_snapshot the rubric data lives there.
        """
        if session.rubric_snapshot_id is not None:
            return session.rubric_snapshot_id

        # Snapshot-driven path — no live RubricDB queries
        if session.evaluation_config_snapshot_id is not None:
            from backend.rubric.config_reader import (
                ConfigurationMissingError,
                EvaluationConfigReader,
            )

            try:
                reader = EvaluationConfigReader(session)
                rubric = reader.get_rubric()
                if rubric and rubric.id:
                    session.rubric_id = rubric.id
                    session.rubric_version = rubric.version
                    db.flush()
                return None
            except ConfigurationMissingError:
                logger.warning(
                    "Config snapshot %s missing for session %s",
                    session.evaluation_config_snapshot_id,
                    session.id,
                )

        # No config_snapshot — cannot create RubricSnapshot from live DB
        return None

    @staticmethod
    def compute_final_score(
        app: Application,
        db: Session,
        computed_by: str = "system",
        override_cv_score: Optional[float] = None,
        override_rubric_score: Optional[float] = None,
        override_rubric_coverage_pct: Optional[float] = None,
        extra_breakdown: Optional[Dict[str, Any]] = None,
        confidence_lower: Optional[float] = None,
        confidence_upper: Optional[float] = None,
        rubric_snapshot_id: Optional[int] = None,
    ) -> EvaluationResult:
        """Compute and persist the canonical score for an application.

        This is the ONLY function that writes EvaluationResult.
        All evaluation paths (AI, rubric, manual) MUST call this.
        """
        es = ScoringService._ensure_session(app, db)

        # Load existing record if any to preserve un-overridden values
        existing_record = (
            db.query(EvaluationResult)
            .filter(EvaluationResult.evaluation_session_id == es.id)
            .first()
        )

        if override_cv_score is not None:
            cv_score = max(0.0, min(100.0, float(override_cv_score)))
        elif existing_record is not None and existing_record.cv_score is not None:
            cv_score = float(existing_record.cv_score)
        else:
            cv_score = 0.0

        # Determine rubric existence from the evaluation configuration,
        # NOT from rubric_score presence.
        #
        # A rubric may legitimately have a score of 0, and during an
        # intermediate scoring step the rubric_score may still be NULL.
        # Neither case means "no rubric".
        #
        # rubric_coverage_pct alone does NOT imply a rubric is present:
        # a no-rubric CV-only application can still carry a coverage
        # metric (documented formula: no-rubric weight cv=0.75,
        # coverage=0.25). Only a real rubric signal (session rubric /
        # rubric score override) selects rubric weighting.
        has_rubric = (
            es.rubric_id is not None
            or es.evaluation_config_snapshot_id is not None
            or override_rubric_score is not None
        )

        if override_rubric_score is not None:
            rubric_score = max(0.0, min(100.0, float(override_rubric_score)))
        elif existing_record is not None and existing_record.rubric_score is not None:
            rubric_score = float(existing_record.rubric_score)
        else:
            rubric_score = 0.0

        if override_rubric_coverage_pct is not None:
            rubric_coverage_pct = max(
                0.0, min(100.0, float(override_rubric_coverage_pct))
            )
        elif existing_record is not None and existing_record.rubric_coverage_pct is not None:
            rubric_coverage_pct = float(existing_record.rubric_coverage_pct)
        elif extra_breakdown and extra_breakdown.get("coverage_pct") is not None:
            # CV/rubric analysis stores its canonical coverage in the breakdown.
            # Promote it into EvaluationResult so final_score uses the same source.
            rubric_coverage_pct = max(
                0.0,
                min(100.0, float(extra_breakdown["coverage_pct"])),
            )
        else:
            rubric_coverage_pct = 0.0

        if has_rubric:
            cv_w = CANONICAL_WEIGHTS["cv"]  # 0.25
            rubric_w = CANONICAL_WEIGHTS["rubric"]  # 0.50
            cov_w = CANONICAL_WEIGHTS["coverage"]  # 0.25
        else:
            cv_w = 0.75
            rubric_w = 0.0
            cov_w = CANONICAL_WEIGHTS["coverage"]  # 0.25

        final_score = (
            cv_score * cv_w
            + rubric_score * rubric_w
            + rubric_coverage_pct * cov_w
        )
        final_score = max(0.0, min(100.0, final_score))

        for attempt in range(1, 4):
            try:
                score_record = (
                    db.query(EvaluationResult)
                    .filter(EvaluationResult.evaluation_session_id == es.id)
                    .first()
                )

                if score_record is None:
                    score_record = EvaluationResult(
                        evaluation_session_id=es.id,
                        company_id=es.company_id,
                        rubric_id=es.rubric_id,
                    )
                elif score_record.scoring_status == "FAILED":
                    raise ValueError(
                        f"Cannot re-score application {app.id}: scoring_status is FAILED (fraud). "
                        "Use report_fraud() to update fraud fields, or manually reset status."
                    )

                score_record.cv_score = cv_score
                score_record.rubric_score = rubric_score
                score_record.rubric_coverage_pct = rubric_coverage_pct
                score_record.final_score = round(final_score, 1)
                score_record.scoring_status = "SCORED"
                if rubric_snapshot_id is not None:
                    score_record.rubric_snapshot_id = rubric_snapshot_id
                score_record.scoring_model = score_record.scoring_model or "rubric"
                score_record.rubric_version = score_record.rubric_version or 0
                score_record.computed_at = datetime.now(timezone.utc)
                score_record.computed_by = computed_by
                if confidence_lower is not None:
                    score_record.confidence_lower = confidence_lower
                if confidence_upper is not None:
                    score_record.confidence_upper = confidence_upper

                score_record.score_breakdown = {
                    "cv": round(cv_score, 1),
                    "rubric": round(rubric_score, 1),
                    "coverage_pct": round(rubric_coverage_pct, 1),
                    "weights": {
                        "cv": cv_w,
                        "rubric": rubric_w,
                        "coverage": cov_w,
                    },
                    "final_score": round(final_score, 1),
                    "has_rubric": has_rubric,
                    "cv_only": not has_rubric,
                }
                if extra_breakdown:
                    score_record.score_breakdown.update(extra_breakdown)

                db.add(score_record)
                db.flush()

                return score_record
            except StaleDataError:
                logger.warning(
                    "StaleDataError writing EvaluationResult for app %s "
                    "(attempt %d/3), retrying...",
                    app.id,
                    attempt,
                )
                db.rollback()
                db.refresh(app)

    @staticmethod
    def get_canonical_score(app_id: int, db: Session) -> Optional[EvaluationResult]:
        """Read the canonical score. Returns None if not yet computed."""
        er = (
            db.query(EvaluationResult)
            .join(
                EvaluationSession,
                EvaluationResult.evaluation_session_id == EvaluationSession.id,
            )
            .filter(EvaluationSession.application_id == app_id)
            .order_by(EvaluationSession.id.desc())
            .first()
        )
        return er

    @staticmethod
    def ensure_score(app: Application, db: Session) -> EvaluationResult:
        """Ensure canonical score exists; create from app data if missing."""
        existing = ScoringService.get_canonical_score(app.id, db)
        if existing:
            return existing
        es = ScoringService._ensure_session(app, db)
        snapshot_id = ScoringService._ensure_rubric_snapshot(app, db, es)
        return ScoringService.compute_final_score(
            app,
            db,
            computed_by="ensure_score",
            rubric_snapshot_id=snapshot_id,
        )

    @staticmethod
    def ensure_pending_score(app: Application, db: Session) -> EvaluationResult:
        """Ensure an EvaluationResult exists without finalizing the score.

        Interview turns need a canonical EvaluationResult so that
        RubricScoringDetail rows can reference it, but an interview that is
        still in progress must not become SCORED prematurely.

        Final scoring remains exclusively the responsibility of the final
        aggregation path (e.g. score_all_answers -> compute_final_score).
        """
        existing = ScoringService.get_canonical_score(app.id, db)
        if existing:
            return existing

        es = ScoringService._ensure_session(app, db)

        score_record = EvaluationResult(
            evaluation_session_id=es.id,
            company_id=es.company_id,
            rubric_id=es.rubric_id,
            rubric_snapshot_id=es.rubric_snapshot_id,
            scoring_status="PENDING",
            final_score=None,
            composite_score=None,
            cv_score=None,
            rubric_score=None,
            rubric_coverage_pct=None,
            scoring_model="rubric",
            computed_by="interview_pending",
        )

        db.add(score_record)
        db.flush()

        return score_record

    @staticmethod
    def get_canonical_verdict(app: Application, db: Session) -> Optional[str]:
        """Read the canonical verdict for an application.

        Priority:
        1. EvaluationResult.verdict (canonical)
        2. Verdict table (business decision / override)
        3. None
        """
        er = ScoringService.get_canonical_score(app.id, db)
        if er and er.verdict is not None:
            return er.verdict

        verdict_record = (
            db.query(VerdictModel)
            .filter(VerdictModel.application_id == app.id)
            .order_by(VerdictModel.id.desc())
            .first()
        )
        if verdict_record:
            return verdict_record.decision

        return None

    @staticmethod
    def set_cv_only(
        app: Application,
        db: Session,
        cv_score: float,
        verdict: Optional[str] = None,
        computed_by: str = "system",
    ) -> EvaluationResult:
        """Set CV score, optionally verdict, and recompute final score."""
        record = ScoringService.compute_final_score(
            app,
            db,
            computed_by=computed_by,
            override_cv_score=cv_score,
        )
        if verdict is not None:
            es = ScoringService._ensure_session(app, db)
            er = (
                db.query(EvaluationResult)
                .filter(EvaluationResult.evaluation_session_id == es.id)
                .first()
            )
            if er:
                er.verdict = verdict
                db.add(er)
                db.flush()
        return record

    @staticmethod
    def set_cv_rubric(
        app: Application,
        db: Session,
        cv_score: float,
        breakdown: Optional[Dict[str, Any]] = None,
        verdict: Optional[str] = None,
        computed_by: str = "cv_analysis",
    ) -> EvaluationResult:
        """Persist a deterministic rubric-weighted CV score.

        Writes the rubric-weighted ``cv_score`` to the canonical
        EvaluationResult (via compute_final_score, so the final_score formula
        is untouched) and stores per-skill evidence rows in RubricScoringDetail
        with ``source="cv"``. The ``breakdown`` dict carries the
        ``cv_rubric_weighted`` / ``skill_scores`` / ``normalized_weights`` /
        ``coverage_pct`` / ``missing_skills`` / ``scoring_method`` keys.
        """
        extra_breakdown = dict(breakdown or {})
        extra_breakdown["scoring_method"] = extra_breakdown.get(
            "scoring_method", "deterministic_keyword_weighted"
        )
        record = ScoringService.compute_final_score(
            app,
            db,
            computed_by=computed_by,
            override_cv_score=cv_score,
            extra_breakdown=extra_breakdown,
        )

        # Replace any prior CV-source rows (idempotent re-analysis).
        db.query(RubricScoringDetail).filter(
            RubricScoringDetail.evaluation_result_id == record.id,
            RubricScoringDetail.source == "cv",
        ).delete(synchronize_session=False)
        for row in breakdown.get("detail_rows", []) if breakdown else []:
            db.add(
                RubricScoringDetail(
                    evaluation_result_id=record.id,
                    company_id=record.company_id,
                    criterion_name=row.get("criterion_name", "skill"),
                    score=row.get("score", 0.0),
                    weight=row.get("weight"),
                    feedback=row.get("feedback"),
                    source="cv",
                )
            )
        db.flush()

        if verdict is not None:
            es = ScoringService._ensure_session(app, db)
            er = (
                db.query(EvaluationResult)
                .filter(EvaluationResult.evaluation_session_id == es.id)
                .first()
            )
            if er:
                er.verdict = verdict
                db.add(er)
                db.flush()
        return record

    @staticmethod
    def set_evaluation_result(
        app: Application,
        db: Session,
        eval_score: float,
        skill_metrics: Optional[Dict[str, Any]] = None,
        scored_by: str = "ai",
        cv_score: Optional[float] = None,
        rubric_score: Optional[float] = None,
        rubric_coverage_pct: Optional[float] = None,
        score_breakdown: Optional[Dict[str, Any]] = None,
        raw_analysis: Optional[Dict[str, Any]] = None,
        verdict: Optional[str] = None,
        rubric_version: Optional[int] = None,
        needs_review: bool = False,
        needs_review_reason: Optional[str] = None,
    ) -> EvaluationResult:
        """Persist the result of a completed AI interview evaluation.

        Handles both rubric-aggregation results and LLM fallback results.
        Writes the provided eval_score as-is (never recomputes or fabricates a
        score). Idempotent per evaluation session (upsert keyed by
        evaluation_session_id). Respects the optimistic version lock.
        """
        breakdown = {}
        if score_breakdown:
            breakdown = dict(score_breakdown)
            if "categories" in breakdown and "category_scores" not in breakdown:
                breakdown["category_scores"] = breakdown.pop("categories")

        # IMPORTANT:
        # When a real rubric score is supplied, use it as the canonical
        # rubric component.
        #
        # Legacy / LLM-fallback path:
        # when no rubric score is supplied, eval_score is the only available
        # interview evaluation score, so preserve the historical contract by
        # storing it as the rubric_score component.
        #
        # This keeps set_evaluation_result() backward-compatible while the
        # canonical final-score computation remains centralized in
        # compute_final_score().
        effective_rubric_score = (
            float(rubric_score)
            if rubric_score is not None
            else float(eval_score)
        )

        # Fallback / legacy evaluation has no rubric coverage metric.
        # Preserve the historical contract: the available evaluation score
        # represents the complete evaluated result, so coverage is 100%.
        effective_coverage = (
            float(rubric_coverage_pct)
            if rubric_coverage_pct is not None
            else 100.0
        )

        record = ScoringService.compute_final_score(
            app=app,
            db=db,
            computed_by=scored_by or "ai",
            override_cv_score=cv_score,
            override_rubric_score=effective_rubric_score,
            override_rubric_coverage_pct=effective_coverage,
            extra_breakdown={
                **breakdown,
                "interview_score": round(float(eval_score), 1),
            },
        )

        if verdict is not None:
            record.verdict = verdict
        if rubric_version is not None:
            record.rubric_version = rubric_version
        record.needs_review = bool(needs_review)
        if needs_review_reason is not None:
            record.needs_review_reason = needs_review_reason
        if skill_metrics:
            if not record.score_breakdown:
                record.score_breakdown = {}
            record.score_breakdown["skill_metrics"] = skill_metrics
        if raw_analysis is not None:
            if not record.score_breakdown:
                record.score_breakdown = {}
            record.score_breakdown["raw_analysis"] = raw_analysis

        db.add(record)
        db.flush()
        return record

    @staticmethod
    def set_verdict(
        app: Application,
        db: Session,
        verdict: Optional[str],
        computed_by: str = "manual",
    ) -> EvaluationResult:
        """Set verdict on canonical score record without recomputing score.
        Does NOT change scoring_status — verdict is orthogonal to score state.
        """
        record = ScoringService.get_canonical_score(app.id, db)
        if record is None:
            es = ScoringService._ensure_session(app, db)
            record = EvaluationResult(
                evaluation_session_id=es.id,
                company_id=es.company_id,
                rubric_id=es.rubric_id,
            )
            db.add(record)
        if isinstance(record, EvaluationResult):
            record.verdict = verdict
        record.computed_by = computed_by
        record.computed_at = datetime.now(timezone.utc)
        db.add(record)
        db.flush()
        return record

    @staticmethod
    def report_fraud(
        app: Application,
        db: Session,
        reported_by: int,
        reported_at: datetime,
        fraud_score: float = 100.0,
        verdict: Optional[str] = None,
        computed_by: str = "fraud_detection",
    ) -> EvaluationResult:
        """Report fraud on an application. Sets fraud fields and optional verdict.
        Sets scoring_status to FAILED — no valid final_score exists."""
        record = ScoringService.get_canonical_score(app.id, db)
        if record is None:
            es = ScoringService._ensure_session(app, db)
            record = EvaluationResult(
                evaluation_session_id=es.id,
                company_id=es.company_id,
                rubric_id=es.rubric_id,
            )
            db.add(record)
        record.scoring_status = "FAILED"
        record.final_score = None
        record.fraud_score = fraud_score
        record.fraud_reported_by = reported_by
        record.fraud_reported_at = reported_at
        if verdict is not None:
            record.verdict = verdict
        record.computed_by = computed_by
        record.computed_at = datetime.now(timezone.utc)
        db.add(record)
        db.flush()
        return record
