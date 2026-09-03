"""
One-shot migration: encrypt PII columns on the ``applications`` table.

Bug B-23 / S-04: candidate PII (CV text, AI analysis, interview
transcripts) was previously stored in plaintext on disk and in DB
backups. This script backfills the affected columns with Fernet
ciphertext so the new ``EncryptedText`` type can decrypt them
transparently at read time.

Run::

    python -m backend.migrations.encrypt_pii_columns

Idempotent: rows that are already encrypted (start with ``ENC1:``)
are skipped. Run it during a maintenance window if your DB is large
— the backfill does ``UPDATE ... LIMIT N`` to avoid long locks.
"""

import logging
import os
import sys
import time

import pymysql

from backend.encryption import (
    PII_TEXT_COLUMNS,
    encrypt_text,
    is_encrypted,
)

logger = logging.getLogger(__name__)

BATCH_SIZE = 500
SLEEP_BETWEEN_BATCHES = 0.1  # seconds


def _connect():
    return pymysql.connect(
        host=os.getenv("DB_HOST", "localhost"),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", ""),
        database=os.getenv("DB_NAME", "candway_db"),
        autocommit=False,
    )


def run_migration() -> int:
    """Backfill encrypted PII columns. Returns number of rows updated."""
    if not os.environ.get("CANDWAY_FIELD_ENCRYPTION_KEY"):
        logger.error(
            "Refusing to run without CANDWAY_FIELD_ENCRYPTION_KEY. "
            "Set the env var first, then re-run."
        )
        return 0

    conn = _connect()
    total_updated = 0
    try:
        with conn.cursor() as cursor:
            # Sanity check: which columns actually exist on this
            # schema? Migration runs against older deploys where some
            # of the new columns may not yet be present.
            cursor.execute("DESCRIBE applications")
            existing = {row[0] for row in cursor.fetchall()}
            targets = [c for c in PII_TEXT_COLUMNS if c in existing]
            if not targets:
                logger.info("No PII columns present — nothing to do")
                return 0

            logger.info(f"Backfilling columns: {targets}")

            # Walk the table in primary-key order, one batch at a time.
            last_id = 0
            while True:
                cursor.execute(
                    f"SELECT id, {','.join(targets)} "
                    f"FROM applications "
                    f"WHERE id > %s "
                    f"ORDER BY id ASC "
                    f"LIMIT {BATCH_SIZE}",
                    (last_id, *targets),
                )
                rows = cursor.fetchall()
                if not rows:
                    break

                updated_in_batch = 0
                for row in rows:
                    row_id = row[0]
                    updates = []
                    params = []
                    for i, col in enumerate(targets):
                        raw = row[i + 1]
                        if raw is None or raw == "":
                            continue
                        if is_encrypted(raw):
                            continue
                        try:
                            # Test that the value is decodable as the
                            # expected type (e.g. JSON). If not, log
                            # and skip — the column might contain
                            # a legacy marker string we shouldn't
                            # touch.
                            if col in (
                                "analysis_json",
                                "interview_log",
                                "interview_qa_structured",
                                "video_analysis_json",
                                "calibration_json",
                            ):
                                import json

                                if raw and not raw.startswith("["):
                                    try:
                                        json.loads(raw)
                                    except Exception:
                                        logger.warning(
                                            f"Row {row_id}.{col} is not "
                                            f"valid JSON; skipping"
                                        )
                                        continue
                        except Exception:
                            pass
                        updates.append(f"{col} = %s")
                        params.append(encrypt_text(raw))
                    if updates:
                        params.append(row_id)
                        cursor.execute(
                            f"UPDATE applications SET {','.join(updates)} "
                            f"WHERE id = %s",
                            params,
                        )
                        updated_in_batch += 1
                    last_id = row_id

                conn.commit()
                total_updated += updated_in_batch
                logger.info(
                    f"Backfilled batch up to id={last_id} "
                    f"({updated_in_batch} rows updated)"
                )
                time.sleep(SLEEP_BETWEEN_BATCHES)

            logger.info(f"Migration complete: {total_updated} rows updated")
    finally:
        conn.close()

    return total_updated


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    sys.exit(0 if run_migration() >= 0 else 1)
