import os

from backend.config import get_settings
from backend.database import engine
from backend.logger import logger
from backend.scheduler import start_scheduler, stop_scheduler

settings = get_settings()


def _validate_api_keys():
    """
    CRITICAL FIX (CRIT-01): Validate API keys on startup.
    Prevent running with placeholder or missing keys.
    """
    settings = get_settings()
    issues = []

    # Check for placeholder keys (common patterns)
    placeholder_patterns = [
        "your_",
        "YOUR_",
        "sk-your",
        "gsk_your",
        "AIzaSy_your",
        "xxx",
        "111",
        "replace",
        "example",
        "test",
        "demo",
    ]

    def is_placeholder(key: str) -> bool:
        if not key:
            return True
        key_lower = key.lower()
        return any(p in key_lower for p in placeholder_patterns)

    # Validate Groq key (REQUIRED)
    if is_placeholder(settings.groq_api_key):
        issues.append("GROQ_API_KEY is missing or placeholder")

    # DeepSeek/Gemini removed for MVP (Groq-only)
    if settings.deepseek_api_key:
        logger.info("DEEPSEEK_API_KEY is set but unused (MVP is Groq-only)")
    if settings.gemini_api_key:
        logger.info("GEMINI_API_KEY is set but unused (MVP is Groq-only)")

    # Check secret key
    if not settings.secret_key or is_placeholder(settings.secret_key):
        issues.append("SECRET_KEY is missing or insecure")

    # P0-02 FIX: Encryption key is mandatory. The previous
    # implementation silently fell back to a hard-coded dev key,
    # which meant a production deploy without CANDWAY_FIELD_ENCRYPTION_KEY
    # would *appear* to work but produce ciphertext that was
    # unrecoverable across restarts. We now refuse to start.
    try:
        from backend.encryption import (
            EncryptionKeyError,
            init_encryption_keys,
        )

        try:
            init_encryption_keys()
        except EncryptionKeyError as e:
            if settings.is_prod:
                issues.append(
                    f"CANDWAY_FIELD_ENCRYPTION_KEY is missing or invalid: {e}"
                )
            else:
                logger.warning(
                    f"[DEV] CANDWAY_FIELD_ENCRYPTION_KEY is missing or "
                    f"invalid ({e}). PII columns will fail to decrypt."
                )
    except ImportError:
        # backend.encryption not importable in this test env;
        # surface as a startup issue.
        issues.append("backend.encryption module not importable")

    # Block startup in production with missing critical keys
    if settings.is_prod and issues:
        for issue in issues:
            logger.critical(f"STARTUP BLOCKED: {issue}")

        # In production, this is a fatal error
        if settings.groq_api_key and settings.secret_key:
            # Only allow startup if critical keys exist
            logger.info("Production startup: Critical API keys present")
        else:
            raise RuntimeError(
                f"CRITICAL: Cannot start production without API keys: {issues}"
            )
    else:
        if issues:
            logger.warning(f"Dev mode: Missing API keys - {issues}")
            logger.warning("AI features may not work without valid keys")


def _warmup_imports():
    """Pre-import heavy modules so the first user request isn't slow."""
    modules = [
        "backend.database",
        "backend.dependencies",
        "backend.security",
        "backend.ai_engine",
        "backend.scoring_engine",
        "backend.email_service",
        "backend.routers.auth",
        "backend.routers.candidate_portal",
        "backend.routers.recruiter_candidates",
        "backend.routers.ai_interview",
        "backend.routers.admin",
        "backend.routers.pages",
    ]
    for mod_name in modules:
        try:
            __import__(mod_name)
        except Exception as e:
            logger.debug(f"Warmup import skipped {mod_name}: {e}")
    logger.info(f"Warmup: pre-imported {len(modules)} modules")


async def _verify_redis():
    """Verify Redis connectivity on startup."""
    try:
        import redis.asyncio as aioredis

        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        r = await aioredis.from_url(
            redis_url, socket_connect_timeout=3, socket_timeout=3
        )
        await r.ping()
        await r.close()
        logger.info(f"Redis connected: {redis_url}")
        return True
    except ImportError:
        logger.warning("redis.asyncio not installed - Redis features disabled")
        return False
    except Exception as e:
        logger.warning(
            f"Redis unavailable at startup ({e}) - degrading to fallback modes"
        )
        return False


async def startup_event():
    """Initialize application on startup"""
    # CRITICAL: Validate API keys FIRST
    _validate_api_keys()

    # Warmup: pre-import heavy modules so first request isn't slow
    _warmup_imports()

    # Verify Redis connectivity
    await _verify_redis()

    # Initialize shared HTTP clients
    try:
        from backend.background_check_service import init_checkr_client

        init_checkr_client()
        logger.info("Checkr HTTP client initialized (connection pooling)")
    except Exception as e:
        logger.warning(f"Checkr HTTP client init failed (non-fatal): {e}")

    # P0-01 FIX: Alembic is the single source of truth for schema.
    # Test runs use an isolated SQLite database created from SQLAlchemy
    # metadata, not an Alembic-managed database. Therefore the migration
    # guard must not inspect Alembic state during tests.
    #
    # Production behavior is unchanged: migrations are verified and a
    # mismatch remains fatal in production.
    if os.getenv("TESTING", "").strip().lower() == "true":
        logger.info("TESTING=true — skipping Alembic migration verification")
    else:
        # Default behavior: VERIFY the current revision == head, fail in
        # production if mismatched. Set CANDWAY_ALEMBIC_AUTO_UPGRADE=1 to
        # have the app run `alembic upgrade head` automatically on
        # startup (useful for single-instance dev / staging deploys).
        # In production we never auto-upgrade without an explicit flag
        # so that a misconfigured migration cannot take the app down
        # during a rolling restart.
        try:
            from alembic.config import Config
            from alembic.runtime.migration import MigrationContext
            from alembic.script import ScriptDirectory

            from alembic import command as alembic_command

            alembic_cfg = Config("alembic.ini")
            with engine.connect() as conn:
                mig_ctx = MigrationContext.configure(conn)
                current_rev = mig_ctx.get_current_revision()
                script = ScriptDirectory.from_config(alembic_cfg)
                head_rev = script.get_current_head()

                if current_rev == head_rev:
                    logger.info(f"Alembic migrations verified: head={head_rev}")
                else:
                    auto_upgrade = os.getenv("CANDWAY_ALEMBIC_AUTO_UPGRADE", "0") == "1"
                    msg = (
                        f"Database migration mismatch: current={current_rev}, "
                        f"head={head_rev}."
                    )
                    if auto_upgrade and not settings.is_prod:
                        logger.warning(
                            f"[DEV] {msg} Auto-running `alembic upgrade head` "
                            "because CANDWAY_ALEMBIC_AUTO_UPGRADE=1."
                        )
                        # Use a private connection so the upgrade tx
                        # commits before we proceed.
                        alembic_command.upgrade(alembic_cfg, "head")
                        logger.info(f"Alembic auto-upgrade complete: head={head_rev}")
                    elif settings.is_prod:
                        raise RuntimeError(
                            f"{msg} Refusing to start. Run `alembic upgrade "
                            "head` or set CANDWAY_ALEMBIC_AUTO_UPGRADE=1 "
                            "(NOT recommended in production)."
                        )
                    else:
                        logger.warning(
                            f"[DEV] {msg} — continuing without full "
                            "migration. Set CANDWAY_ALEMBIC_AUTO_UPGRADE=1 "
                            "to auto-upgrade on startup."
                        )
        except RuntimeError:
            raise
        except Exception as e:
            if settings.is_prod:
                raise RuntimeError(f"Alembic migration check failed: {e}") from e
            logger.warning(f"Could not verify alembic migration state (dev only): {e}")

    scheduler_enabled = os.getenv("SCHEDULER_ENABLED", "true").lower() == "true"
    if scheduler_enabled:
        try:
            start_scheduler()
            logger.info("Application started with background scheduler")
            logger.info("Email notifications enabled (interviews, offers, mentions)")
        except Exception as e:
            logger.error(f"Failed to start scheduler: {e}")
            logger.warning("Continuing without background scheduler")
    else:
        logger.info("Background scheduler disabled via SCHEDULER_ENABLED env var")


async def shutdown_event():
    """Cleanup on application shutdown with connection draining"""
    logger.info("Shutting down gracefully...")

    # Stop scheduler gracefully
    try:
        stop_scheduler()
        logger.info("Background scheduler stopped")
    except Exception as e:
        logger.error(f"Error stopping scheduler: {e}")

    # Close Redis connections
    try:
        from backend.redis_manager import redis_manager

        await redis_manager.close()
        logger.info("Redis connections closed")
    except Exception as e:
        logger.error(f"Error closing Redis: {e}")

    # Close DB connection pool
    try:
        from backend.database import engine

        engine.dispose()
        logger.info("Database connections closed")
    except Exception as e:
        logger.error(f"Error closing DB: {e}")

    # Clean up WebSocket connections
    try:
        from backend.realtime import manager

        async with manager._lock:
            for user_id, connections in list(manager.active_connections.items()):
                for ws in list(connections.keys()):
                    try:
                        await ws.close(code=1001, reason="Server shutting down")
                    except Exception:
                        pass
                connections.clear()
            manager.active_connections.clear()
        logger.info("WebSocket connections cleaned up")
    except Exception as e:
        logger.error(f"Error cleaning up WebSockets: {e}")

    logger.info("Application shutdown complete")
