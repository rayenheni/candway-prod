"""
One-shot backfill: lift turns out of the
``interview_qa_structured`` JSON bag and into the new
``interview_turns`` table.

**Phase 3B (June 2026) complete** — the ``Application.interview_qa_structured``
column has been dropped. All turn data now lives in the ``InterviewTurn``
table. This script is a no-op; kept only for import compatibility.
"""

import logging

from backend.logger import logger


def backfill() -> None:
    logger.info("[TURN-BACKFILL] Phase 3B complete — no backfill needed.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    backfill()
