"""RubricSnapshotter — creates immutable rubric snapshots for evaluation sessions.

Usage::

    snapshot = RubricSnapshotter.create_snapshot(db, session, rubric_record)
    session.rubric_snapshot_id = snapshot.id

Snapshots are created ONCE per evaluation session and never modified.
"""

import json
import logging
from typing import Optional

from sqlalchemy.orm import Session

from backend.models.evaluation.rubric_snapshot import RubricSnapshot

logger = logging.getLogger(__name__)


class RubricSnapshotter:
    @staticmethod
    def create_snapshot(
        db: Session,
        *,
        rubric_id: Optional[int] = None,
        company_id: Optional[int] = None,
        job_id: Optional[int] = None,
        version: int = 1,
        criteria_json: Optional[dict] = None,
        skill_weights_json: Optional[dict] = None,
        scoring_rules_json: Optional[dict] = None,
        rubric_title: Optional[str] = None,
        passing_score: Optional[float] = None,
        max_score: Optional[float] = None,
    ) -> RubricSnapshot:
        snapshot = RubricSnapshot(
            original_rubric_id=rubric_id,
            company_id=company_id,
            job_id=job_id,
            version=version,
            criteria_json=criteria_json,
            skill_weights_json=skill_weights_json,
            scoring_rules_json=scoring_rules_json,
            rubric_title=rubric_title,
            passing_score=passing_score,
            max_score=max_score,
        )
        db.add(snapshot)
        db.flush()
        logger.info(
            "Created RubricSnapshot id=%s for rubric_id=%s v=%s",
            snapshot.id,
            rubric_id,
            version,
        )
        return snapshot

    @staticmethod
    def create_from_rubric_record(
        db: Session,
        rubric_record,
    ) -> RubricSnapshot:
        """Create a snapshot from a Rubric DB model instance."""
        criteria = None
        skill_weights = None
        if hasattr(rubric_record, "criteria_json") and rubric_record.criteria_json:
            try:
                criteria = (
                    json.loads(rubric_record.criteria_json)
                    if isinstance(rubric_record.criteria_json, str)
                    else rubric_record.criteria_json
                )
            except (json.JSONDecodeError, TypeError):
                criteria = rubric_record.criteria_json
        if hasattr(rubric_record, "skill_weights") and rubric_record.skill_weights:
            try:
                skill_weights = (
                    json.loads(rubric_record.skill_weights)
                    if isinstance(rubric_record.skill_weights, str)
                    else rubric_record.skill_weights
                )
            except (json.JSONDecodeError, TypeError):
                skill_weights = rubric_record.skill_weights

        return RubricSnapshotter.create_snapshot(
            db,
            rubric_id=getattr(rubric_record, "id", None),
            company_id=getattr(rubric_record, "company_id", None),
            job_id=getattr(rubric_record, "job_id", None),
            version=getattr(rubric_record, "version", 1),
            criteria_json=criteria,
            skill_weights_json=skill_weights,
            rubric_title=getattr(rubric_record, "title", None),
            passing_score=getattr(rubric_record, "passing_score", None),
            max_score=getattr(rubric_record, "max_score", None),
        )
