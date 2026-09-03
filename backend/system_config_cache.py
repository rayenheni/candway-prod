"""SystemConfig cache for AI runtime settings.

Provides a simple in-memory TTL cache so ``call_groq_cascade`` can read
admin-panel settings (ai_model, groq_api_key, etc.) without hitting the
database on every AI call.

Sensitive keys (API keys) are decrypted so the AI pipeline can use them
directly. For multi-worker deployments a Redis-backed implementation can
replace the in-memory one; the interface is the same.
"""

import logging
import time

logger = logging.getLogger(__name__)

_TTL_SECONDS = 30  # settings refresh interval

_cache: dict = {}
_cache_ts: float = 0.0


async def get_system_config() -> dict:
    """Return SystemConfig key→value dict, cached for ``_TTL_SECONDS``.

    Sensitive keys are decrypted so callers don't need to handle encryption.
    """
    global _cache, _cache_ts

    now = time.monotonic()
    if _cache and (now - _cache_ts) < _TTL_SECONDS:
        return _cache

    try:
        from backend.database import SessionLocal, SystemConfig
        from backend.secret_encryption import decrypt_value, is_sensitive_key
        from backend.config import get_settings

        secret_key = get_settings().secret_key

        db = SessionLocal()
        try:
            rows = db.query(SystemConfig.key, SystemConfig.value).all()
            new_cache = {}
            for k, v in rows:
                if v and is_sensitive_key(k):
                    try:
                        v = decrypt_value(v, secret_key)
                    except Exception:
                        pass  # keep encrypted value as fallback
                new_cache[k] = v
            _cache = new_cache
            _cache_ts = now
            return _cache
        finally:
            db.close()
    except Exception as e:
        logger.warning(f"SystemConfig cache refresh failed: {e}")
        return _cache  # return stale cache on error
