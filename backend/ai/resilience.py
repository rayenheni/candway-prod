import time
from enum import Enum
from typing import Any, Callable, Dict

from backend.logger import logger


class CircuitState(Enum):
    CLOSED = "CLOSED"  # Normal operation
    OPEN = "OPEN"  # Failure threshold reached, requests blocked
    HALF_OPEN = "HALF_OPEN"  # Testing if service recovered


class CircuitBreaker:
    """
    Prevents cascading failures by stopping requests to a failing service.
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        expected_exception: type = Exception,
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception

        self.state = CircuitState.CLOSED
        self.failures = 0
        self.last_failure_time = 0
        self.successes = 0

    async def call(self, func: Callable, *args, **kwargs) -> Any:
        if self.state == CircuitState.OPEN:
            if time.time() - self.last_failure_time > self.recovery_timeout:
                logger.info(f"[CircuitBreaker] {self.name} entering HALF_OPEN state")
                self.state = CircuitState.HALF_OPEN
            else:
                logger.warning(
                    f"[CircuitBreaker] {self.name} is OPEN. Blocking request."
                )
                raise Exception(f"Circuit {self.name} is OPEN")

        try:
            result = await func(*args, **kwargs)

            if self.state == CircuitState.HALF_OPEN:
                self.successes += 1
                if self.successes >= 3:  # 3 consecutive successes to close
                    logger.info(
                        f"[CircuitBreaker] {self.name} recovered. Closing circuit."
                    )
                    self._reset()

            return result

        except self.expected_exception as e:
            self.failures += 1
            self.last_failure_time = time.time()

            logger.error(
                f"[CircuitBreaker] {self.name} failure {self.failures}/{self.failure_threshold}: {e}"
            )

            if self.state in [CircuitState.CLOSED, CircuitState.HALF_OPEN]:
                if self.failures >= self.failure_threshold:
                    logger.critical(
                        f"[CircuitBreaker] {self.name} threshold reached. OPENING circuit."
                    )
                    self.state = CircuitState.OPEN

            raise e

    def _reset(self):
        self.state = CircuitState.CLOSED
        self.failures = 0
        self.successes = 0
        self.last_failure_time = 0


# P0-09 FIX: Per-provider circuit breakers.
#
# MVP: Groq-only. DeepSeek/Gemini breakers removed.
# The "cascade" breaker is kept for the internal Groq model-level fallback.
PROVIDER_BREAKERS: Dict[str, CircuitBreaker] = {
    "groq": CircuitBreaker("GROQ", failure_threshold=5, recovery_timeout=30),
    "gemini": CircuitBreaker("GEMINI", failure_threshold=5, recovery_timeout=30),
    "cascade": CircuitBreaker("LLM_CASCADE", failure_threshold=10, recovery_timeout=30),
}


def get_breaker(provider: str) -> CircuitBreaker:
    """Return the circuit breaker for ``provider`` (groq or cascade).

    Unknown providers fall back to the cascade breaker so the
    request still benefits from global protection."""
    return PROVIDER_BREAKERS.get(provider.lower(), PROVIDER_BREAKERS["cascade"])


def all_breaker_states() -> Dict[str, str]:
    """Snapshot the current state of every breaker. Used by the
    ``/monitoring/breakers`` admin endpoint and the Prometheus
    exporter."""
    return {name: breaker.state.value for name, breaker in PROVIDER_BREAKERS.items()}


# Backwards-compatibility alias — the old single-name import
# (``from backend.ai.resilience import llm_circuit_breaker``) keeps
# working but now points at the cascade breaker.
llm_circuit_breaker = PROVIDER_BREAKERS["cascade"]
