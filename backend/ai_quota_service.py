"""
AI Quota Management Service
Prevents AI cost explosion by enforcing per-user quotas based on subscription tier.

Features:
- Tier-based AI quotas (free, pro, enterprise)
- Daily/Monthly quota tracking
- Real-time quota enforcement
- Cost tracking and alerts
- Graceful degradation when quota exceeded
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Dict, Optional, Tuple

from backend.logger import logger
from backend.redis_manager import redis_manager

# ============================================
# QUOTA CONFIGURATION
# ============================================


@dataclass
class AIQuota:
    """AI quota configuration for a subscription tier."""

    tier_name: str
    daily_ai_calls: int
    monthly_ai_calls: int
    daily_cv_analyses: int
    monthly_cv_analyses: int
    daily_interviews: int
    monthly_interviews: int
    max_tokens_per_request: int
    cost_limit_usd_daily: float
    cost_limit_usd_monthly: float


# Default quotas by tier
TIER_QUOTAS = {
    "free": AIQuota(
        tier_name="free",
        daily_ai_calls=25,
        monthly_ai_calls=250,
        daily_cv_analyses=10,
        monthly_cv_analyses=50,
        daily_interviews=5,
        monthly_interviews=25,
        max_tokens_per_request=1000,
        cost_limit_usd_daily=0.50,
        cost_limit_usd_monthly=5.00,
    ),
    "pro": AIQuota(
        tier_name="pro",
        daily_ai_calls=500,
        monthly_ai_calls=5000,
        daily_cv_analyses=100,
        monthly_cv_analyses=1000,
        daily_interviews=50,
        monthly_interviews=500,
        max_tokens_per_request=4000,
        cost_limit_usd_daily=10.00,
        cost_limit_usd_monthly=150.00,
    ),
    "enterprise": AIQuota(
        tier_name="enterprise",
        daily_ai_calls=500,
        monthly_ai_calls=10000,
        daily_cv_analyses=100,
        monthly_cv_analyses=2000,
        daily_interviews=100,
        monthly_interviews=2000,
        max_tokens_per_request=8000,
        cost_limit_usd_daily=20.00,
        cost_limit_usd_monthly=500.00,
    ),
    # Admin gets unlimited
    "admin": AIQuota(
        tier_name="admin",
        daily_ai_calls=999999,
        monthly_ai_calls=999999,
        daily_cv_analyses=999999,
        monthly_cv_analyses=999999,
        daily_interviews=999999,
        monthly_interviews=999999,
        max_tokens_per_request=8000,
        cost_limit_usd_daily=1000.00,
        cost_limit_usd_monthly=10000.00,
    ),
}

# Default quota for unknown tiers
DEFAULT_QUOTA = TIER_QUOTAS["free"]


# ============================================
# AI QUOTA SERVICE
# ============================================


class AIQuotaService:
    """
    Manages AI quotas for users.
    Uses Redis for fast, distributed quota tracking.
    """

    def __init__(self, key_prefix: str = "candway_ai_quota"):
        self.key_prefix = key_prefix
        self._memory_fallback: Dict[str, Dict] = {}

    async def _get_redis(self):
        return await redis_manager.get_client()

    def _get_quota(self, tier: str) -> AIQuota:
        """Get quota configuration for a tier."""
        return TIER_QUOTAS.get(tier, DEFAULT_QUOTA)

    def _get_daily_key(self, user_id: int, resource: str) -> str:
        """Get Redis key for daily quota."""
        date_str = datetime.now(UTC).strftime("%Y-%m-%d")
        return f"{self.key_prefix}:daily:{user_id}:{resource}:{date_str}"

    def _get_monthly_key(self, user_id: int, resource: str) -> str:
        """Get Redis key for monthly quota."""
        month_str = datetime.now(UTC).strftime("%Y-%m")
        return f"{self.key_prefix}:monthly:{user_id}:{resource}:{month_str}"

    def _get_cost_key(self, user_id: int, period: str) -> str:
        """Get Redis key for cost tracking."""
        if period == "daily":
            date_str = datetime.now(UTC).strftime("%Y-%m-%d")
        else:
            date_str = datetime.now(UTC).strftime("%Y-%m")
        return f"{self.key_prefix}:cost:{user_id}:{period}:{date_str}"

    async def check_quota(
        self, user_id: int, tier: str, resource: str, tokens: int = 1
    ) -> Tuple[bool, Dict]:
        """
        Check if user has quota remaining for a resource.

        Args:
            user_id: User ID
            tier: User's subscription tier
            resource: Resource type (ai_calls, cv_analyses, interviews)
            tokens: Number of tokens/units to consume

        Returns:
            Tuple of (is_allowed, metadata)
        """
        quota = self._get_quota(tier)

        # Get limits for this resource
        daily_limit = getattr(quota, f"daily_{resource}", 999999)
        monthly_limit = getattr(quota, f"monthly_{resource}", 999999)

        # Check token limit
        if tokens > quota.max_tokens_per_request:
            return False, {
                "allowed": False,
                "reason": "token_limit_exceeded",
                "message": f"Request exceeds max tokens ({quota.max_tokens_per_request})",
                "max_tokens": quota.max_tokens_per_request,
                "requested_tokens": tokens,
            }

        redis_client = await self._get_redis()

        if redis_client:
            return await self._check_quota_redis(
                redis_client, user_id, resource, daily_limit, monthly_limit, tokens
            )
        else:
            return self._check_quota_memory(
                user_id, resource, daily_limit, monthly_limit, tokens
            )

    async def _check_quota_redis(
        self,
        redis_client,
        user_id: int,
        resource: str,
        daily_limit: int,
        monthly_limit: int,
        tokens: int,
    ) -> Tuple[bool, Dict]:
        """Check quota using Redis."""
        daily_key = self._get_daily_key(user_id, resource)
        monthly_key = self._get_monthly_key(user_id, resource)

        try:
            # Get current usage
            daily_usage = int(await redis_client.get(daily_key) or 0)
            monthly_usage = int(await redis_client.get(monthly_key) or 0)

            # Check limits
            if daily_usage + tokens > daily_limit:
                return False, {
                    "allowed": False,
                    "reason": "daily_limit_exceeded",
                    "message": f"Daily {resource} limit exceeded",
                    "daily_usage": daily_usage,
                    "daily_limit": daily_limit,
                    "reset_at": self._get_daily_reset_time(),
                }

            if monthly_usage + tokens > monthly_limit:
                return False, {
                    "allowed": False,
                    "reason": "monthly_limit_exceeded",
                    "message": f"Monthly {resource} limit exceeded",
                    "monthly_usage": monthly_usage,
                    "monthly_limit": monthly_limit,
                    "reset_at": self._get_monthly_reset_time(),
                }

            # Increment usage
            await redis_client.incrby(daily_key, tokens)
            await redis_client.incrby(monthly_key, tokens)

            # Set expiry
            await redis_client.expire(daily_key, 86400)  # 1 day
            await redis_client.expire(monthly_key, 2592000)  # 30 days

            return True, {
                "allowed": True,
                "daily_usage": daily_usage + tokens,
                "daily_limit": daily_limit,
                "monthly_usage": monthly_usage + tokens,
                "monthly_limit": monthly_limit,
                "remaining_daily": daily_limit - daily_usage - tokens,
                "remaining_monthly": monthly_limit - monthly_usage - tokens,
            }

        except Exception as e:
            logger.error(f"Redis quota check failed: {e}")
            # SECURITY FIX (CRIT-06): Fail-CLOSED in production to prevent free unlimited AI usage.
            # Fail-open only in development for convenience.
            from backend.config import get_settings as _get_settings

            _settings = _get_settings()
            if _settings.is_prod:
                return False, {
                    "allowed": False,
                    "reason": "quota_service_unavailable",
                    "message": "Quota service temporarily unavailable. Please try again shortly.",
                }
            # Dev mode: fail open so engineers aren't blocked during local testing
            logger.warning("DEV: Quota Redis error — failing open (dev mode only)")
            return True, {
                "allowed": True,
                "error": "Quota service unavailable",
                "dev_bypass": True,
            }

    def _check_quota_memory(
        self,
        user_id: int,
        resource: str,
        daily_limit: int,
        monthly_limit: int,
        tokens: int,
    ) -> Tuple[bool, Dict]:
        """Fallback memory-based quota check."""
        daily_key = (
            f"{user_id}_{resource}_daily_{datetime.now(UTC).strftime('%Y-%m-%d')}"
        )
        monthly_key = (
            f"{user_id}_{resource}_monthly_{datetime.now(UTC).strftime('%Y-%m')}"
        )

        daily_usage = self._memory_fallback.get(daily_key, 0)
        monthly_usage = self._memory_fallback.get(monthly_key, 0)

        if daily_usage + tokens > daily_limit:
            return False, {
                "allowed": False,
                "reason": "daily_limit_exceeded",
                "daily_usage": daily_usage,
                "daily_limit": daily_limit,
            }

        if monthly_usage + tokens > monthly_limit:
            return False, {
                "allowed": False,
                "reason": "monthly_limit_exceeded",
                "monthly_usage": monthly_usage,
                "monthly_limit": monthly_limit,
            }

        # Increment
        self._memory_fallback[daily_key] = daily_usage + tokens
        self._memory_fallback[monthly_key] = monthly_usage + tokens

        return True, {
            "allowed": True,
            "daily_usage": daily_usage + tokens,
            "daily_limit": daily_limit,
            "monthly_usage": monthly_usage + tokens,
            "monthly_limit": monthly_limit,
        }

    async def track_cost(
        self, user_id: int, tier: str, cost_usd: float
    ) -> Tuple[bool, Dict]:
        """
        Track AI cost for a user.

        Args:
            user_id: User ID
            tier: User's subscription tier
            cost_usd: Cost in USD

        Returns:
            Tuple of (within_budget, cost_info)
        """
        quota = self._get_quota(tier)
        redis_client = await self._get_redis()

        if redis_client:
            try:
                daily_key = self._get_cost_key(user_id, "daily")
                monthly_key = self._get_cost_key(user_id, "monthly")

                # Get current costs
                daily_cost = float(await redis_client.get(daily_key) or 0)
                monthly_cost = float(await redis_client.get(monthly_key) or 0)

                # Check limits
                daily_exceeded = daily_cost + cost_usd > quota.cost_limit_usd_daily
                monthly_exceeded = (
                    monthly_cost + cost_usd > quota.cost_limit_usd_monthly
                )

                if daily_exceeded or monthly_exceeded:
                    return False, {
                        "within_budget": False,
                        "daily_cost": daily_cost + cost_usd,
                        "daily_limit": quota.cost_limit_usd_daily,
                        "monthly_cost": monthly_cost + cost_usd,
                        "monthly_limit": quota.cost_limit_usd_monthly,
                        "exceeded": "daily" if daily_exceeded else "monthly",
                    }

                # Increment costs
                await redis_client.incrbyfloat(daily_key, cost_usd)
                await redis_client.incrbyfloat(monthly_key, cost_usd)
                await redis_client.expire(daily_key, 86400)
                await redis_client.expire(monthly_key, 2592000)

                return True, {
                    "within_budget": True,
                    "daily_cost": daily_cost + cost_usd,
                    "monthly_cost": monthly_cost + cost_usd,
                }

            except Exception as e:
                logger.error(f"Cost tracking failed: {e}")

        return True, {"within_budget": True}

    async def get_usage_stats(self, user_id: int, tier: str) -> Dict:
        """
        Get current usage statistics for a user.

        Returns:
            Dict with usage stats for all resources
        """
        quota = self._get_quota(tier)
        redis_client = await self._get_redis()

        stats = {"tier": tier, "resources": {}}

        for resource in ["ai_calls", "cv_analyses", "interviews"]:
            daily_limit = getattr(quota, f"daily_{resource}")
            monthly_limit = getattr(quota, f"monthly_{resource}")

            if redis_client:
                daily_key = self._get_daily_key(user_id, resource)
                monthly_key = self._get_monthly_key(user_id, resource)

                daily_usage = int(await redis_client.get(daily_key) or 0)
                monthly_usage = int(await redis_client.get(monthly_key) or 0)
            else:
                daily_key = f"{user_id}_{resource}_daily_{datetime.now(UTC).strftime('%Y-%m-%d')}"
                monthly_key = f"{user_id}_{resource}_monthly_{datetime.now(UTC).strftime('%Y-%m')}"

                daily_usage = self._memory_fallback.get(daily_key, 0)
                monthly_usage = self._memory_fallback.get(monthly_key, 0)

            stats["resources"][resource] = {
                "daily_usage": daily_usage,
                "daily_limit": daily_limit,
                "daily_remaining": max(0, daily_limit - daily_usage),
                "monthly_usage": monthly_usage,
                "monthly_limit": monthly_limit,
                "monthly_remaining": max(0, monthly_limit - monthly_usage),
            }

        return stats

    def _get_daily_reset_time(self) -> str:
        """Get ISO timestamp for daily quota reset."""
        tomorrow = datetime.now(UTC).replace(
            hour=0, minute=0, second=0, microsecond=0
        ) + timedelta(days=1)
        return tomorrow.isoformat()

    def _get_monthly_reset_time(self) -> str:
        """Get ISO timestamp for monthly quota reset."""
        next_month = datetime.now(UTC).replace(
            day=1, hour=0, minute=0, second=0, microsecond=0
        ) + timedelta(days=32)
        next_month = next_month.replace(day=1)
        return next_month.isoformat()


# ============================================
# GLOBAL INSTANCE
# ============================================

ai_quota_service = AIQuotaService()


# ============================================
# FASTAPI DEPENDENCIES
# ============================================

from fastapi import Depends, HTTPException, Request, status  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from backend.database import Application, BatchJob, Job, User, get_db  # noqa: E402
from backend.dependencies import get_current_user, get_optional_user  # noqa: E402
from backend.profile_helpers import get_user_tier  # noqa: E402


async def check_ai_quota_dependency(
    resource: str = "ai_calls", tokens: int = 1, user: User = Depends(get_current_user)
):
    """
    FastAPI dependency for AI quota checking.
    """
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required"
        )

    # Admin bypass
    if user.role == "admin":
        return {"allowed": True, "tier": "admin", "bypass": True}

    tier = get_user_tier(user) or "free"
    user_id = user.id

    is_allowed, metadata = await ai_quota_service.check_quota(
        user_id, tier, resource, tokens
    )

    if not is_allowed:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={
                "error": "quota_exceeded",
                "message": metadata.get("message", "AI quota exceeded"),
                "reason": metadata.get("reason"),
                "upgrade_url": "/subscription",
            },
        )

    return metadata


async def check_cv_analysis_quota(user: User = Depends(get_current_user)):
    """Check quota for CV analysis."""
    return await check_ai_quota_dependency("cv_analyses", 1, user)


async def check_interview_quota(
    request: Request,
    user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    """Check quota for AI interview.
    Enforces recruiter/campaign owner quotas even for guest candidates.
    """
    # 1. Identify Application ID from request
    app_id = None
    try:
        # Check query params first
        app_id = (
            request.query_params.get("application_id")
            or request.query_params.get("id")
            or request.query_params.get("app_id")
        )

        # Check JSON body if needed
        if not app_id and request.method == "POST":
            # Peek into body without consuming it (if possible) or assume it's already consumed by FastAPI
            # In FastAPI, we can't easily read body twice without side effects unless we use a specific middleware
            # But generate-interview route has req: InterviewGenRequest which contains application_id
            pass
    except Exception:
        pass

    # If we have an app_id, we should check the RECRUITER'S quota
    if app_id:
        try:
            app_id_int = int(app_id)
            app = db.query(Application).filter(Application.id == app_id_int).first()
            if app:
                # Find the recruiter who owns this job or campaign
                recruiter = None
                if app.job_id:
                    job = db.query(Job).filter(Job.id == app.job_id).first()
                    if job:
                        recruiter = (
                            db.query(User).filter(User.id == job.recruiter_id).first()
                        )
                elif app.batch_id:
                    batch = (
                        db.query(BatchJob).filter(BatchJob.id == app.batch_id).first()
                    )
                    if batch:
                        recruiter = (
                            db.query(User).filter(User.id == batch.recruiter_id).first()
                        )
                elif app.assigned_to:
                    recruiter = (
                        db.query(User).filter(User.id == app.assigned_to).first()
                    )

                if recruiter:
                    # Check recruiter's quota
                    if recruiter.role == "admin":
                        return {"allowed": True, "tier": "admin", "bypass": True}

                    tier = get_user_tier(recruiter) or "free"
                    is_allowed, metadata = await ai_quota_service.check_quota(
                        recruiter.id, tier, "interviews", 1
                    )
                    if not is_allowed:
                        raise HTTPException(
                            status_code=status.HTTP_402_PAYMENT_REQUIRED,
                            detail={
                                "error": "quota_exceeded",
                                "message": "The recruiter's AI interview quota has been exceeded.",
                                "reason": metadata.get("reason"),
                                "upgrade_url": "/subscription",
                            },
                        )
                    return metadata
        except Exception as e:
            logger.error(f"Error checking recruiter quota: {e}")

    # Fallback to user quota if no app_id or recruiter found
    if not user:
        # If it's a guest with no application ID provided in request (unlikely for interview),
        # we might allow if it's not production, or block if it is.
        from backend.config import get_settings as _get_settings

        if _get_settings().is_prod:
            raise HTTPException(
                status_code=401,
                detail="Authentication or valid interview context required",
            )
        return {"allowed": True, "bypass": True}

    # Admin bypass
    if user.role == "admin":
        return {"allowed": True, "tier": "admin", "bypass": True}

    tier = get_user_tier(user) or "free"
    is_allowed, metadata = await ai_quota_service.check_quota(
        user.id, tier, "interviews", 1
    )

    if not is_allowed:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={
                "error": "quota_exceeded",
                "message": metadata.get("message", "AI quota exceeded"),
                "reason": metadata.get("reason"),
                "upgrade_url": "/subscription",
            },
        )

    return metadata


# ============================================
# ESTIMATED COST CALCULATOR
# ============================================

# Approximate costs per 1000 tokens (as of 2024)
MODEL_COSTS = {
    "llama-3.3-70b-versatile": 0.00059,  # Groq
    "llama-3.1-8b-instant": 0.00002,  # Groq
    "mixtral-8x7b-32768": 0.00024,  # Groq
    "groq/compound": 0.00059,  # Groq (compound routing)
    "groq/compound-mini": 0.00010,  # Groq (compound routing)
    "openai/gpt-oss-20b": 0.00010,  # Groq
    "openai/gpt-oss-120b": 0.00059,  # Groq
    "deepseek-chat": 0.00014,  # DeepSeek
    "gemini-pro": 0.00025,  # Gemini
}


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """
    Estimate cost for an AI call.

    Args:
        model: Model name
        input_tokens: Number of input tokens
        output_tokens: Number of output tokens

    Returns:
        Estimated cost in USD
    """
    cost_per_1k = MODEL_COSTS.get(model, 0.0005)  # Default fallback
    total_tokens = input_tokens + output_tokens
    return (total_tokens / 1000) * cost_per_1k
