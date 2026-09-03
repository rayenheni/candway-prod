from typing import Any, Dict, List

from fastapi import HTTPException
from sqlalchemy.orm import Session

from backend.database import CompanyMember, EvaluationConfigSnapshot, EvaluationSession


class AdminSnapshotService:
    """Read-only snapshot audit service for administrators.

    Enforces tenant isolation: admins can only access snapshots for
    sessions belonging to their own company (super admins bypass this).
    """

    @staticmethod
    def get_user_company_ids(db: Session, user_id: int) -> List[int]:
        memberships = (
            db.query(CompanyMember)
            .filter(CompanyMember.user_id == user_id, CompanyMember.is_active)
            .all()
        )
        return [m.company_id for m in memberships]

    @staticmethod
    def get_snapshot_for_session(
        db: Session, session_id: int, user_id: int, is_super_admin: bool = False
    ) -> Dict[str, Any]:
        session = (
            db.query(EvaluationSession)
            .filter(EvaluationSession.id == session_id)
            .first()
        )
        if not session:
            raise HTTPException(status_code=404, detail="Evaluation session not found")

        if not is_super_admin:
            user_companies = AdminSnapshotService.get_user_company_ids(db, user_id)
            if session.company_id not in user_companies:
                raise HTTPException(
                    status_code=404, detail="Evaluation session not found"
                )

        snap_id = session.evaluation_config_snapshot_id
        if snap_id is None:
            return {
                "session_id": session_id,
                "evaluation_config_snapshot_id": None,
                "message": "No snapshot associated with this session",
            }

        snap = (
            db.query(EvaluationConfigSnapshot)
            .filter(EvaluationConfigSnapshot.id == snap_id)
            .first()
        )
        if not snap:
            raise HTTPException(
                status_code=404,
                detail="EvaluationConfigSnapshot not found (snapshot_id=%s)" % snap_id,
            )

        return AdminSnapshotService._build_response(snap, session)

    @staticmethod
    def _build_response(
        snap: EvaluationConfigSnapshot, session: EvaluationSession
    ) -> Dict[str, Any]:
        interview_cfg = snap.interview_config_json or {}
        scoring_cfg = snap.scoring_rules_json or {}

        return {
            "session_id": session.id,
            "application_id": session.application_id,
            "company_id": session.company_id,
            "evaluation_config_snapshot_id": snap.id,
            "hash": snap.hash,
            "created_at": snap.created_at.isoformat() if snap.created_at else None,
            "source_type": snap.source_type,
            "source_id": snap.source_id,
            "rubric_id": snap.rubric_id,
            "rubric_version": snap.rubric_version,
            "total_questions": snap.total_questions,
            "time_limit_seconds": snap.time_limit_seconds,
            "passing_score": snap.passing_score,
            "max_score": snap.max_score,
            "language": snap.language,
            "interview_instructions": snap.interview_instructions,
            "question_generation_prompt": snap.question_generation_prompt,
            "interview_config": {
                "language": interview_cfg.get("language"),
                "max_questions": interview_cfg.get("max_questions"),
                "time_limit_seconds": interview_cfg.get("time_limit_seconds"),
                "adaptive_difficulty": interview_cfg.get("adaptive_difficulty"),
            },
            "scoring_rules": {
                "passing_score": scoring_cfg.get("passing_score"),
                "max_score": scoring_cfg.get("max_score"),
                "coverage_multiplier": scoring_cfg.get("coverage_multiplier"),
            },
            "scoring_weights": snap.scoring_weights,
            "source_metadata": snap.source_metadata,
        }
