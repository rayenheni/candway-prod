"""P0-09 FIX tests: Per-provider LLM circuit breakers."""
import asyncio

import pytest

from backend.ai import resilience


@pytest.fixture(autouse=True)
def _reset_breakers():
    """Each test starts with all breakers CLOSED so order does
    not matter."""
    for breaker in resilience.PROVIDER_BREAKERS.values():
        breaker._reset()
    yield
    for breaker in resilience.PROVIDER_BREAKERS.values():
        breaker._reset()


def test_provider_breakers_exist():
    for provider in ("groq", "gemini", "cascade"):
        assert provider in resilience.PROVIDER_BREAKERS
        assert resilience.PROVIDER_BREAKERS[provider].state.name == "CLOSED"


def test_get_breaker_unknown_provider_falls_back_to_cascade():
    breaker = resilience.get_breaker("unknown_provider_xyz")
    assert breaker is resilience.PROVIDER_BREAKERS["cascade"]


def test_get_breaker_known_provider_returns_specific_breaker():
    assert resilience.get_breaker("groq") is resilience.PROVIDER_BREAKERS["groq"]
    assert resilience.get_breaker("gemini") is resilience.PROVIDER_BREAKERS["gemini"]
    assert resilience.get_breaker("cascade") is resilience.PROVIDER_BREAKERS["cascade"]


def test_all_breaker_states_reports_every_provider():
    states = resilience.all_breaker_states()
    assert set(states.keys()) == {"groq", "gemini", "cascade"}
    assert all(v == "CLOSED" for v in states.values())


def test_breaker_opens_on_threshold():
    breaker = resilience.CircuitBreaker(
        "TEST", failure_threshold=3, recovery_timeout=9999
    )

    async def fail():
        raise RuntimeError("boom")

    async def main():
        for _ in range(3):
            with pytest.raises(RuntimeError):
                await breaker.call(fail)
        assert breaker.state.name == "OPEN"

        # Subsequent calls must be short-circuited.
        with pytest.raises(Exception, match="is OPEN"):
            await breaker.call(fail)

    asyncio.run(main())


def test_per_provider_failures_do_not_cascade():
    """P0-09 REGRESSION: a failure on one provider's breaker must
    not flip another provider's breaker."""
    groq = resilience.PROVIDER_BREAKERS["groq"]
    gemini = resilience.PROVIDER_BREAKERS["gemini"]
    assert groq.state.name == "CLOSED"
    assert gemini.state.name == "CLOSED"

    async def fail():
        raise RuntimeError("groq down")

    async def main():
        # Attempt many calls. After the breaker opens, the breaker
        # itself raises "Circuit is OPEN" — we accept any exception
        # so the loop terminates cleanly.
        for _ in range(20):
            try:
                await groq.call(fail)
            except Exception:  # noqa: BLE001
                pass

    asyncio.run(main())

    # Groq may be open, but Gemini's state must remain untouched.
    assert gemini.state.name == "CLOSED"
    # Restore for the next test.
    resilience.PROVIDER_BREAKERS["groq"]._reset()
