"""
AI Audit Trail — full reproducibility for every AI decision.

Logs every LLM call with:
- Full prompt used
- Model version
- Response (truncated)
- Duration
- Success/failure
- Input snapshot (candidate state)
- Scoring breakdown
- Cryptographic hash chaining for tamper detection

This enables reproducing any interview decision on demand.
"""

import hashlib
import json
from datetime import UTC, datetime
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session as SASession

from backend.database import AIAuditLog, SessionLocal
from backend.logger import logger


def _utcnow():
    return datetime.now(UTC).replace(tzinfo=None)


def _compute_record_hash(
    previous_hash: Optional[str],
    action: str,
    model_version: Optional[str],
    prompt_preview: str,
    timestamp: str,
) -> str:
    """Compute a SHA-256 hash chaining this record to the previous one."""
    seed = (
        str(previous_hash or "")
        + str(action)
        + str(model_version or "")
        + str(prompt_preview)
        + str(timestamp)
    )
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()


def log_ai_call(
    application_id: Optional[int] = None,
    company_id: Optional[int] = None,
    turn_number: Optional[int] = None,
    action: str = "llm_call",
    prompt: Optional[str] = None,
    prompt_version: Optional[str] = None,
    model_version: Optional[str] = None,
    response_content: Optional[str] = None,
    scoring_breakdown: Optional[Dict[str, Any]] = None,
    input_snapshot: Optional[Dict[str, Any]] = None,
    duration_ms: Optional[int] = None,
    success: bool = True,
    error_message: Optional[str] = None,
    prompt_injection_blocked: Optional[bool] = None,
):
    """Log an AI interaction to the audit trail with hash chaining."""
    try:
        db = SessionLocal()
        now = _utcnow()
        timestamp = now.isoformat()

        last_record = (
            db.query(AIAuditLog).order_by(AIAuditLog.created_at.desc()).first()
        )
        previous_hash = last_record.record_hash if last_record else None

        prompt_preview = (prompt or "")[:100]
        record_hash = _compute_record_hash(
            previous_hash, action, model_version, prompt_preview, timestamp
        )

        audit = AIAuditLog(
            application_id=application_id,
            company_id=company_id,
            turn_number=turn_number,
            action=action,
            prompt_used=prompt[:50000] if prompt else None,
            prompt_version=prompt_version,
            model_version=model_version,
            response_content=response_content[:25000] if response_content else None,
            scoring_breakdown=json.dumps(scoring_breakdown)
            if scoring_breakdown
            else None,
            input_snapshot=json.dumps(input_snapshot) if input_snapshot else None,
            duration_ms=duration_ms,
            success=success,
            error_message=error_message,
            prompt_injection_blocked=prompt_injection_blocked,
            previous_hash=previous_hash,
            record_hash=record_hash,
            created_at=now,
        )
        db.add(audit)
        db.commit()
        db.close()
    except Exception as e:
        logger.error(f"[AUDIT] Failed to log AI call: {e}")


def get_audit_trail(
    application_id: int,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    """Retrieve full audit trail for a given application."""
    try:
        db = SessionLocal()
        records = (
            db.query(AIAuditLog)
            .filter(AIAuditLog.application_id == application_id)
            .order_by(AIAuditLog.created_at.desc())
            .limit(limit)
            .all()
        )
        db.close()
        return [
            {
                "id": r.id,
                "turn_number": r.turn_number,
                "action": r.action,
                "model_version": r.model_version,
                "scoring_breakdown": json.loads(r.scoring_breakdown)
                if r.scoring_breakdown
                else None,
                "duration_ms": r.duration_ms,
                "success": r.success,
                "error_message": r.error_message,
                "created_at": r.created_at.isoformat(),
            }
            for r in records
        ]
    except Exception as e:
        logger.error(f"[AUDIT] Failed to query audit trail: {e}")
        return []


def get_audit_detail(audit_id: int) -> Optional[Dict[str, Any]]:
    """Retrieve full detail (including prompt) for a specific audit record."""
    try:
        db = SessionLocal()
        r = db.query(AIAuditLog).filter(AIAuditLog.id == audit_id).first()
        db.close()
        if not r:
            return None
        return {
            "id": r.id,
            "application_id": r.application_id,
            "turn_number": r.turn_number,
            "action": r.action,
            "prompt_used": r.prompt_used,
            "model_version": r.model_version,
            "response_content": r.response_content,
            "scoring_breakdown": json.loads(r.scoring_breakdown)
            if r.scoring_breakdown
            else None,
            "input_snapshot": json.loads(r.input_snapshot)
            if r.input_snapshot
            else None,
            "duration_ms": r.duration_ms,
            "success": r.success,
            "error_message": r.error_message,
            "created_at": r.created_at.isoformat(),
        }
    except Exception as e:
        logger.error(f"[AUDIT] Failed to get audit detail: {e}")
        return None


def verify_audit_chain(db: SASession = None) -> Tuple[bool, List[str]]:
    """Walk the full audit chain and verify every link's integrity.

    Returns (is_valid: bool, errors: List[str]).
    """
    own_session = db is None
    if own_session:
        db = SessionLocal()
    try:
        records = db.query(AIAuditLog).order_by(AIAuditLog.created_at.asc()).all()
        if not records:
            return True, []

        errors: List[str] = []
        for i, r in enumerate(records):
            prompt_preview = (r.prompt_used or "")[:100]
            timestamp = r.created_at.isoformat() if r.created_at else ""
            expected_hash = _compute_record_hash(
                r.previous_hash,
                r.action,
                r.model_version,
                prompt_preview,
                timestamp,
            )
            if r.record_hash != expected_hash:
                errors.append(
                    f"Record {r.id} (turn={r.turn_number}, action={r.action}): "
                    f"stored hash {r.record_hash} != computed {expected_hash}"
                )

            if i == 0:
                if r.previous_hash is not None:
                    errors.append(
                        f"First record {r.id} has non-null previous_hash={r.previous_hash}"
                    )
            else:
                prev = records[i - 1]
                if r.previous_hash != prev.record_hash:
                    errors.append(
                        f"Chain break at record {r.id}: "
                        f"previous_hash={r.previous_hash} != prev.record_hash={prev.record_hash}"
                    )

        return len(errors) == 0, errors
    except Exception as e:
        logger.error(f"[AUDIT] verify_audit_chain failed: {e}")
        return False, [str(e)]
    finally:
        if own_session:
            db.close()


def detect_tampering(db: SASession = None) -> List[Dict]:
    """Return a list of broken-chain entries with details.

    Each entry contains the record id, expected vs actual hash,
    and a severity classification.
    """
    own_session = db is None
    if own_session:
        db = SessionLocal()
    try:
        is_valid, errors = verify_audit_chain(db)
        if is_valid:
            return []

        results = []
        records = db.query(AIAuditLog).order_by(AIAuditLog.created_at.asc()).all()
        for i, r in enumerate(records):
            prompt_preview = (r.prompt_used or "")[:100]
            timestamp = r.created_at.isoformat() if r.created_at else ""
            expected_hash = _compute_record_hash(
                r.previous_hash,
                r.action,
                r.model_version,
                prompt_preview,
                timestamp,
            )
            if r.record_hash != expected_hash:
                results.append(
                    {
                        "id": r.id,
                        "action": r.action,
                        "turn_number": r.turn_number,
                        "application_id": r.application_id,
                        "stored_hash": r.record_hash,
                        "computed_hash": expected_hash,
                        "severity": "CRITICAL",
                        "description": "Record content modified after creation",
                    }
                )

            if i > 0:
                prev = records[i - 1]
                if r.previous_hash != prev.record_hash:
                    results.append(
                        {
                            "id": r.id,
                            "action": r.action,
                            "turn_number": r.turn_number,
                            "application_id": r.application_id,
                            "stored_hash": r.record_hash,
                            "expected_previous": prev.record_hash,
                            "severity": "CRITICAL",
                            "description": "Chain link broken - records reordered or tampered",
                        }
                    )

        return results
    except Exception as e:
        logger.error(f"[AUDIT] detect_tampering failed: {e}")
        return [{"error": str(e), "severity": "ERROR"}]
    finally:
        if own_session:
            db.close()
