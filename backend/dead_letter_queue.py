"""Dead Letter Queue for failed background jobs"""

import json
import logging
from datetime import UTC, datetime
from typing import Any, Dict, Optional

from sqlalchemy import Column, DateTime, Integer, String, Text
from sqlalchemy.orm import Session

from backend.models.base import Base

logger = logging.getLogger(__name__)


class DeadLetterRecord(Base):
    __tablename__ = "dead_letter_records"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(String(100), nullable=False, index=True)
    error_message = Column(Text, nullable=True)
    payload = Column(Text, nullable=True)
    failed_at = Column(DateTime, default=lambda: datetime.now(UTC).replace(tzinfo=None))
    retry_count = Column(Integer, default=0)


def record_dead_letter(
    db: Session, job_id: str, error: Exception, payload: Optional[Dict[str, Any]] = None
):
    """Record a failed job in the dead letter queue"""
    try:
        record = DeadLetterRecord(
            job_id=job_id,
            error_message=f"{type(error).__name__}: {str(error)}",
            payload=json.dumps(payload) if payload else None,
        )
        db.add(record)
        db.commit()
        logger.warning(f"Dead letter recorded for job {job_id}: {error}")
    except Exception as e:
        logger.error(f"Failed to record dead letter: {e}")
        db.rollback()
