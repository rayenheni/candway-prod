import threading
import time
from collections import defaultdict
from datetime import date, datetime
from typing import Any, Dict, Optional

from backend.logger import logger

# ---------------------------------------------------------------------------
# Pricing tables
# ---------------------------------------------------------------------------

GROQ_PRICING: Dict[str, Dict[str, float]] = {
    "llama-3.3-70b": {"input": 0.59, "output": 0.79},
    "llama-3.1-8b": {"input": 0.05, "output": 0.08},
}

GEMINI_PRICING: Dict[str, Dict[str, float]] = {
    "gemini-3.6-flash": {"input": 0.10, "output": 0.40},
}

FALLBACK_PRICE_PER_M = 1.00


# ---------------------------------------------------------------------------
# Cost estimation
# ---------------------------------------------------------------------------


def estimate_groq_cost(input_tokens: int, output_tokens: int, model: str) -> float:
    pricing = GROQ_PRICING.get(model)
    if pricing is None:
        return (input_tokens + output_tokens) * FALLBACK_PRICE_PER_M / 1_000_000
    input_cost = input_tokens * pricing["input"] / 1_000_000
    output_cost = output_tokens * pricing["output"] / 1_000_000
    return round(input_cost + output_cost, 6)


def estimate_gemini_cost(input_tokens: int, output_tokens: int, model: str) -> float:
    pricing = GEMINI_PRICING.get(model)
    if pricing is None:
        return (input_tokens + output_tokens) * FALLBACK_PRICE_PER_M / 1_000_000
    input_cost = input_tokens * pricing["input"] / 1_000_000
    output_cost = output_tokens * pricing["output"] / 1_000_000
    return round(input_cost + output_cost, 6)


# ---------------------------------------------------------------------------
# Threshold-based alert helper
# ---------------------------------------------------------------------------


class CostAlert:
    """Logs warnings when usage crosses defined percentage thresholds."""

    def __init__(self, thresholds=(80, 90, 100)):
        self._thresholds = sorted(thresholds)
        self._fired: Dict[str, set] = defaultdict(set)

    def check(self, key: str, used: float, limit: float) -> None:
        if limit <= 0:
            return
        pct = (used / limit) * 100
        for thr in self._thresholds:
            if pct >= thr and thr not in self._fired[key]:
                self._fired[key].add(thr)
                if thr == 100:
                    logger.critical(
                        f"[CostAlert] {key} has reached 100%% of limit "
                        f"({used:.2f} / {limit:.2f})",
                    )
                else:
                    logger.warning(
                        f"[CostAlert] {key} has reached {thr}%% of limit "
                        f"({used:.2f} / {limit:.2f})",
                    )


# ---------------------------------------------------------------------------
# Daily / monthly key helpers
# ---------------------------------------------------------------------------


def _day_key(ts: float) -> str:
    return date.fromtimestamp(ts).isoformat()


def _month_key(ts: float) -> str:
    return datetime.fromtimestamp(ts).strftime("%Y-%m")


# ---------------------------------------------------------------------------
# Main controller
# ---------------------------------------------------------------------------


class AICostController:
    """Per-process budget enforcement for AI API calls.

    All mutable state is protected by ``self._lock`` (a
    ``threading.Lock``) so the same controller can safely be shared across
    background workers and web-handler threads.
    """

    def __init__(
        self,
        company_id: Optional[int] = None,
        *,
        max_daily_cost: float = 50.0,
        max_monthly_cost: float = 500.0,
        max_cost_per_call: float = 5.0,
        max_tokens_per_day: int = 5_000_000,
        max_tokens_per_month: int = 50_000_000,
        max_usage_log_size: int = 10000,
    ):
        self.company_id = company_id
        self.max_daily_cost = max_daily_cost
        self.max_monthly_cost = max_monthly_cost
        self.max_cost_per_call = max_cost_per_call
        self.max_tokens_per_day = max_tokens_per_day
        self.max_tokens_per_month = max_tokens_per_month
        self.max_usage_log_size = max_usage_log_size

        self._lock = threading.Lock()
        self._alert = CostAlert()

        # Per-provider counters keyed by (day, month).
        self._daily_cost: Dict[str, float] = defaultdict(float)
        self._monthly_cost: Dict[str, float] = defaultdict(float)
        self._daily_tokens: Dict[str, int] = defaultdict(int)
        self._monthly_tokens: Dict[str, int] = defaultdict(int)

        # Raw usage log for get_usage_stats.
        self._usage_log: list[Dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Per-company AI rate limiting
    # ------------------------------------------------------------------

    def _check_company_rate_limit(self, company_id: int) -> bool:
        """Check if company has exceeded AI rate limit"""
        from datetime import timedelta

        from sqlalchemy import func

        from backend.models.evaluation.ai import AIAuditLog

        minute_ago = datetime.now().replace(tzinfo=None) - timedelta(minutes=1)

        from backend.database import SessionLocal

        db = SessionLocal()
        try:
            recent_calls = (
                db.query(func.count(AIAuditLog.id))
                .filter(
                    AIAuditLog.company_id == company_id,
                    AIAuditLog.created_at >= minute_ago,
                )
                .scalar()
            )
        finally:
            db.close()

        PER_COMPANY_RATE_LIMIT = 30
        if recent_calls >= PER_COMPANY_RATE_LIMIT:
            logger.warning(
                f"Company {company_id} exceeded AI rate limit ({recent_calls}/min)"
            )
            return False
        return True

    # ------------------------------------------------------------------
    # Budget check
    # ------------------------------------------------------------------

    def check_budget(
        self, provider: str, estimated_cost: float, company_id: int = None
    ) -> bool:
        """Return ``True`` if the request is within budget, ``False`` if
        it should be blocked."""
        if company_id is not None and not self._check_company_rate_limit(company_id):
            logger.warning(
                f"[AICostController] Company {company_id} exceeded AI rate limit — blocking"
            )
            return False

        if estimated_cost > self.max_cost_per_call:
            logger.warning(
                f"[AICostController] Estimated cost {estimated_cost:.4f} exceeds "
                f"max_cost_per_call {self.max_cost_per_call:.4f} — blocking",
            )
            return False

        now = time.time()
        dk = _day_key(now)
        mk = _month_key(now)

        with self._lock:
            daily = self._daily_cost[dk]
            if daily + estimated_cost > self.max_daily_cost:
                logger.warning(
                    f"[AICostController] Daily budget exceeded "
                    f"({daily:.2f} + {estimated_cost:.4f} > {self.max_daily_cost:.2f}) — blocking",
                )
                return False

            monthly = self._monthly_cost[mk]
            if monthly + estimated_cost > self.max_monthly_cost:
                logger.warning(
                    f"[AICostController] Monthly budget exceeded "
                    f"({monthly:.2f} + {estimated_cost:.4f} > {self.max_monthly_cost:.2f}) — blocking",
                )
                return False

            return True

    # ------------------------------------------------------------------
    # Record usage
    # ------------------------------------------------------------------

    def record_usage(
        self,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cost: float,
        company_id: Optional[int] = None,
    ) -> None:
        now = time.time()
        dk = _day_key(now)
        mk = _month_key(now)
        total_tokens = input_tokens + output_tokens

        with self._lock:
            self._daily_cost[dk] += cost
            self._monthly_cost[mk] += cost
            self._daily_tokens[dk] += total_tokens
            self._monthly_tokens[mk] += total_tokens

            self._usage_log.append(
                {
                    "timestamp": datetime.fromtimestamp(now).isoformat(),
                    "provider": provider,
                    "model": model,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "cost": cost,
                    "total_calls": len(self._usage_log),
                    "total_cost": round(
                        sum(
                            e.get("cost", 0)
                            for e in self._usage_log
                            if company_id is None or e.get("company_id") == company_id
                        ),
                        6,
                    ),
                    "company_id": company_id or self.company_id,
                }
            )
            # Trim usage log to prevent unbounded memory growth
            if len(self._usage_log) > self.max_usage_log_size:
                self._usage_log = self._usage_log[-self.max_usage_log_size :]

            # Fire alerts for the company scope.
            scope = f"company:{company_id or self.company_id or 'global'}"

            self._alert.check(
                f"{scope}/daily_cost",
                self._daily_cost[dk],
                self.max_daily_cost,
            )
            self._alert.check(
                f"{scope}/monthly_cost",
                self._monthly_cost[mk],
                self.max_monthly_cost,
            )
            self._alert.check(
                f"{scope}/daily_tokens",
                self._daily_tokens[dk],
                self.max_tokens_per_day,
            )
            self._alert.check(
                f"{scope}/monthly_tokens",
                self._monthly_tokens[mk],
                self.max_tokens_per_month,
            )

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def get_usage_stats(
        self,
        company_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        now = time.time()
        dk = _day_key(now)
        mk = _month_key(now)

        with self._lock:
            return {
                "daily_cost": round(self._daily_cost.get(dk, 0), 6),
                "daily_cost_limit": self.max_daily_cost,
                "daily_tokens": self._daily_tokens.get(dk, 0),
                "daily_tokens_limit": self.max_tokens_per_day,
                "monthly_cost": round(self._monthly_cost.get(mk, 0), 6),
                "monthly_cost_limit": self.max_monthly_cost,
                "monthly_tokens": self._monthly_tokens.get(mk, 0),
                "monthly_tokens_limit": self.max_tokens_per_month,
                "total_calls": len(self._usage_log),
                "total_cost": round(
                    sum(
                        e.get("cost", 0)
                        for e in self._usage_log
                        if company_id is None or e.get("company_id") == company_id
                    ),
                    6,
                ),
                "company_id": company_id or self.company_id,
            }

    # ------------------------------------------------------------------
    # Reset (useful for testing)
    # ------------------------------------------------------------------

    def reset(self) -> None:
        with self._lock:
            self._daily_cost.clear()
            self._monthly_cost.clear()
            self._daily_tokens.clear()
            self._monthly_tokens.clear()
            self._usage_log.clear()
            self._alert._fired.clear()


# ---------------------------------------------------------------------------
# Global singleton & accessor
# ---------------------------------------------------------------------------

_global_controller = AICostController()
_company_controllers: Dict[int, AICostController] = {}
_controllers_lock = threading.Lock()


def get_cost_controller(company_id: Optional[int] = None) -> AICostController:
    """Return a company-scoped controller if ``company_id`` is provided,
    otherwise the global singleton."""
    if company_id is None:
        return _global_controller

    with _controllers_lock:
        ctrl = _company_controllers.get(company_id)
        if ctrl is None:
            ctrl = AICostController(company_id=company_id)
            _company_controllers[company_id] = ctrl
        return ctrl


# ---------------------------------------------------------------------------
# Convenience helpers (intended for use in routers / services)
# ---------------------------------------------------------------------------


def check_ai_budget(company_id: int, estimated_cost: float) -> bool:
    """Shorthand for ``get_cost_controller(company_id).check_budget(...)``."""
    return get_cost_controller(company_id).check_budget(
        "combined", estimated_cost, company_id=company_id
    )


def record_ai_usage(
    company_id: int,
    provider: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    cost: float,
) -> None:
    """Shorthand for ``get_cost_controller(company_id).record_usage(...)``."""
    get_cost_controller(company_id).record_usage(
        provider=provider,
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost=cost,
        company_id=company_id,
    )
