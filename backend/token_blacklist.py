"""
Token Blacklist Service for JWT Invalidation
Implements secure logout, password change invalidation, and account lock token revocation.

Features:
- Redis-backed token blacklist for O(1) lookup
- Automatic expiry based on token TTL
- Fallback to database if Redis unavailable
- Batch invalidation for user sessions
"""

import hashlib
import json
from datetime import UTC, datetime, timedelta

from backend.logger import logger
from backend.redis_manager import redis_manager


class TokenBlacklist:
    """
    Redis-backed JWT token blacklist.
    Supports instant invalidation for logout, security events.
    """

    def __init__(self, key_prefix: str = "candway_blacklist"):
        self.key_prefix = key_prefix

    async def _get_redis(self):
        return await redis_manager.get_client()

    def _get_token_hash(self, token: str) -> str:
        """Hash token for storage (don't store raw tokens)."""
        return hashlib.sha256(token.encode()).hexdigest()

    def _get_user_key(self, user_id: int) -> str:
        """Get Redis key for user's invalidated tokens."""
        return f"{self.key_prefix}:user:{user_id}"

    def _get_token_key(self, token_hash: str) -> str:
        """Get Redis key for specific token."""
        return f"{self.key_prefix}:token:{token_hash}"

    async def add_token(
        self, token: str, user_id: int, expires_at: datetime, reason: str = "logout"
    ) -> bool:
        """
        Add token to blacklist.

        Args:
            token: JWT token to invalidate
            user_id: User ID associated with token
            expires_at: When the token expires (for TTL)
            reason: Why token is being invalidated

        Returns:
            True if successfully added
        """
        redis_client = await self._get_redis()
        token_hash = self._get_token_hash(token)

        # Calculate TTL
        now = datetime.now(UTC)
        ttl_seconds = max(0, int((expires_at - now).total_seconds()))

        if ttl_seconds <= 0:
            # Token already expired, no need to blacklist
            return True

        payload = {
            "user_id": user_id,
            "reason": reason,
            "invalidated_at": now.isoformat(),
            "expires_at": expires_at.isoformat(),
        }

        if redis_client:
            try:
                # Store token hash with TTL
                token_key = self._get_token_key(token_hash)
                await redis_client.setex(token_key, ttl_seconds, json.dumps(payload))

                # Also add to user's set of invalidated tokens
                user_key = self._get_user_key(user_id)
                await redis_client.sadd(user_key, token_hash)
                await redis_client.expire(user_key, ttl_seconds)

                logger.info(f"Token blacklisted for user {user_id}: {reason}")
                return True
            except Exception as e:
                logger.error(f"Failed to blacklist token in Redis: {e}")

        # Fallback to database
        return await self._add_token_db(token_hash, user_id, expires_at, reason)

    async def _add_token_db(
        self, token_hash: str, user_id: int, expires_at: datetime, reason: str
    ) -> bool:
        """Database fallback for token blacklist."""
        try:
            from backend.database import SessionLocal
            from backend.database import TokenBlacklist as TokenBlacklistModel

            db = SessionLocal()
            try:
                entry = TokenBlacklistModel(
                    token_hash=token_hash,
                    user_id=user_id,
                    expires_at=expires_at,
                    reason=reason,
                    invalidated_at=datetime.now(UTC),
                )
                db.add(entry)
                db.commit()
                return True
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Failed to blacklist token in database: {e}")
            return False

    async def is_blacklisted(self, token: str) -> bool:
        """
        Check if token is blacklisted.

        Args:
            token: JWT token to check

        Returns:
            True if token is blacklisted (invalid)
        """
        redis_client = await self._get_redis()
        token_hash = self._get_token_hash(token)

        if redis_client:
            try:
                token_key = self._get_token_key(token_hash)
                exists = await redis_client.exists(token_key)
                return bool(exists)
            except Exception as e:
                logger.error(f"Failed to check token blacklist in Redis: {e}")

        # Fallback to database
        return await self._is_blacklisted_db(token_hash)

    async def _is_blacklisted_db(self, token_hash: str) -> bool:
        """Database fallback for checking blacklist."""
        try:
            from datetime import datetime

            from backend.database import SessionLocal
            from backend.database import TokenBlacklist as TokenBlacklistModel

            db = SessionLocal()
            try:
                # Check if token exists and not expired
                exists = (
                    db.query(TokenBlacklistModel)
                    .filter(
                        TokenBlacklistModel.token_hash == token_hash,
                        TokenBlacklistModel.expires_at > datetime.now(UTC),
                    )
                    .first()
                )
                return exists is not None
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Failed to check token blacklist in database: {e}")
            # Security-first: reject token when DB is unreachable (fail closed)
            return True

    async def invalidate_user_tokens(
        self, user_id: int, reason: str = "security_event"
    ) -> int:
        """
        Invalidate all tokens for a user.
        Used for password change, account lock, etc.

        Args:
            user_id: User ID to invalidate tokens for
            reason: Why tokens are being invalidated

        Returns:
            Number of tokens invalidated
        """
        redis_client = await self._get_redis()
        count = 0

        if redis_client:
            try:
                # Get all token hashes for user
                user_key = self._get_user_key(user_id)
                token_hashes = await redis_client.smembers(user_key)

                # Delete each token
                for token_hash in token_hashes:
                    token_key = self._get_token_key(token_hash)
                    await redis_client.delete(token_key)
                    count += 1

                # Delete user's set
                await redis_client.delete(user_key)

                # Set a flag that all tokens before now are invalid
                invalidate_key = f"{self.key_prefix}:user_invalidated:{user_id}"
                await redis_client.setex(
                    invalidate_key,
                    86400,
                    datetime.now(UTC).isoformat(),
                )

                logger.info(f"Invalidated {count} tokens for user {user_id}: {reason}")
            except Exception as e:
                logger.error(f"Failed to invalidate user tokens in Redis: {e}")

        # Also update database
        await self._invalidate_user_tokens_db(user_id, reason)

        return count

    async def _invalidate_user_tokens_db(self, user_id: int, reason: str) -> bool:
        """Mark all user tokens as invalid in database."""
        try:
            from backend.database import SessionLocal
            from backend.database import TokenBlacklist as TokenBlacklistModel

            db = SessionLocal()
            try:
                # Create a special entry indicating all tokens before now are invalid
                entry = TokenBlacklistModel(
                    token_hash=f"ALL_TOKENS_{user_id}",
                    user_id=user_id,
                    expires_at=datetime.now(UTC) + timedelta(days=7),
                    reason=f"bulk_invalidation:{reason}",
                    invalidated_at=datetime.now(UTC),
                )
                db.add(entry)
                db.commit()
                return True
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Failed to invalidate user tokens in database: {e}")
            return False

    async def is_user_invalidated(
        self, user_id: int, token_issued_at: datetime
    ) -> bool:
        """
        Check if all tokens issued before a time are invalidated for user.

        Args:
            user_id: User ID to check
            token_issued_at: When the token was issued

        Returns:
            True if user's tokens were invalidated after token was issued
        """
        redis_client = await self._get_redis()

        if redis_client:
            try:
                invalidate_key = f"{self.key_prefix}:user_invalidated:{user_id}"
                invalidated_at_str = await redis_client.get(invalidate_key)

                if invalidated_at_str:
                    # Fix: Ensure both datetimes are offset-aware (UTC) to avoid comparison errors
                    invalidated_at = datetime.fromisoformat(invalidated_at_str)
                    if invalidated_at.tzinfo is None:
                        invalidated_at = invalidated_at.replace(tzinfo=UTC)

                    if token_issued_at.tzinfo is None:
                        token_issued_at = token_issued_at.replace(tzinfo=UTC)

                    return token_issued_at < invalidated_at
            except Exception as e:
                logger.error(f"Failed to check user invalidation: {e}")

        return False

    async def cleanup_expired(self) -> int:
        """
        Remove expired entries from blacklist.
        Only needed for database backend; Redis handles this automatically.

        Returns:
            Number of entries removed
        """
        try:
            from backend.database import SessionLocal
            from backend.database import TokenBlacklist as TokenBlacklistModel

            db = SessionLocal()
            try:
                deleted = (
                    db.query(TokenBlacklistModel)
                    .filter(TokenBlacklistModel.expires_at < datetime.now(UTC))
                    .delete()
                )
                db.commit()
                return deleted
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Failed to cleanup expired tokens: {e}")
            return 0


# ============================================
# DATABASE MODEL FOR TOKEN BLACKLIST
# ============================================

# Add this to backend/database.py:
"""
class TokenBlacklist(Base):
    __tablename__ = "token_blacklist"

    id = Column(Integer, primary_key=True, index=True)
    token_hash = Column(String(64), unique=True, index=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    reason = Column(String(100), nullable=False)
    invalidated_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=False, index=True)

    user = relationship("User")
"""


# ============================================
# GLOBAL INSTANCE
# ============================================

token_blacklist = TokenBlacklist()


# ============================================
# FASTAPI MIDDLEWARE
# ============================================

from fastapi import HTTPException, Request, status  # noqa: E402
from jose import jwt  # noqa: E402

from backend.config import get_settings  # noqa: E402

settings = get_settings()


async def validate_token_not_blacklisted(request: Request, call_next):
    """
    Middleware to check if token is blacklisted.
    Add this middleware BEFORE the auth middleware.
    """
    # Only check for authenticated routes
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return await call_next(request)

    token = auth_header.split(" ")[1]

    # Check if token is blacklisted
    if await token_blacklist.is_blacklisted(token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been invalidated. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Check if user's tokens were invalidated (password change, etc.)
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key or settings.secret_key,
            algorithms=[settings.algorithm],
        )
        user_id = payload.get("id") or payload.get("sub")
        iat = payload.get("iat")

        if user_id and iat:
            from datetime import UTC, datetime

            # Ensure issued_at is UTC-aware
            issued_at = datetime.fromtimestamp(iat, UTC)

            # Check if user had bulk invalidation
            if await token_blacklist.is_user_invalidated(int(user_id), issued_at):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Session invalidated due to security event. Please log in again.",
                    headers={"WWW-Authenticate": "Bearer"},
                )
    except Exception as e:
        logger.debug(f"Token validation check failed: {e}")
        # Continue - the auth middleware will handle invalid tokens

    return await call_next(request)


# ============================================
# HELPER FUNCTIONS
# ============================================


async def invalidate_token(token: str, user_id: int, reason: str = "logout"):
    """
    Invalidate a specific token.
    Call this on logout.
    """
    try:
        # Decode token to get expiry
        payload = jwt.decode(
            token,
            settings.jwt_secret_key or settings.secret_key,
            algorithms=[settings.algorithm],
        )
        exp = payload.get("exp")

        if exp:
            expires_at = datetime.fromtimestamp(exp)
            await token_blacklist.add_token(token, user_id, expires_at, reason)
    except Exception as e:
        logger.error(f"Failed to invalidate token: {e}")


async def invalidate_all_user_tokens(user_id: int, reason: str = "security_event"):
    """
    Invalidate all tokens for a user.
    Call this on password change, account lock, etc.
    """
    return await token_blacklist.invalidate_user_tokens(user_id, reason)
