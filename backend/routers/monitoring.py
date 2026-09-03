"""P0-10 FIX: Prometheus /metrics endpoint.

Exposes the standard Python process metrics, a small set of
HTTP-level metrics, and a snapshot of the LLM circuit breaker
states. The route is intentionally cheap — it is hit on every
Prometheus scrape (default 15s) so we cache the breaker states
in-memory and let prometheus_client format the rest on demand.
"""

from fastapi import APIRouter, Response

try:
    from prometheus_client import (
        CONTENT_TYPE_LATEST,
        CollectorRegistry,
        Counter,
        Gauge,
        Histogram,
        generate_latest,
    )

    PROMETHEUS_AVAILABLE = True
except ImportError:  # pragma: no cover - dependency is in requirements
    PROMETHEUS_AVAILABLE = False
    CONTENT_TYPE_LATEST = "text/plain; version=0.0.4"

from backend.logger import logger

router = APIRouter(tags=["monitoring"])


# Standard HTTP metrics. These are populated by middleware (see
# backend/metrics_middleware.py) and surfaced here.
if PROMETHEUS_AVAILABLE:
    registry = CollectorRegistry(auto_describe=True)

    http_requests_total = Counter(
        "candway_http_requests_total",
        "Total HTTP requests handled, labeled by method/path/status.",
        ["method", "path", "status"],
        registry=registry,
    )
    http_request_duration_seconds = Histogram(
        "candway_http_request_duration_seconds",
        "HTTP request duration in seconds.",
        ["method", "path"],
        registry=registry,
        buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10),
    )
    http_in_flight = Gauge(
        "candway_http_in_flight_requests",
        "Number of HTTP requests currently in flight.",
        registry=registry,
    )

    llm_circuit_state = Gauge(
        "candway_llm_circuit_state",
        "LLM circuit breaker state. 0=CLOSED, 1=HALF_OPEN, 2=OPEN.",
        ["provider"],
        registry=registry,
    )
    llm_call_total = Counter(
        "candway_llm_call_total",
        "Total LLM calls, labeled by provider and outcome.",
        ["provider", "outcome"],
        registry=registry,
    )
    # P1-10 FIX: LLM cost observability. ``candway_llm_cost_usd_total``
    # is monotonically increasing USD spend per (provider, model,
    # outcome) label set. Use ``rate(...)`` in Grafana for $/min and
    # ``increase(...)`` for $ over a window.
    llm_cost_total = Counter(
        "candway_llm_cost_usd_total",
        "Cumulative USD cost of LLM calls, labeled by provider, model, and outcome.",
        ["provider", "model", "outcome"],
        registry=registry,
    )
    llm_tokens_total = Counter(
        "candway_llm_tokens_total",
        "Cumulative token count, labeled by provider, model, and direction.",
        ["provider", "model", "direction"],
        registry=registry,
    )


_STATE_TO_GAUGE = {"CLOSED": 0, "HALF_OPEN": 1, "OPEN": 2}


def _refresh_breaker_metrics() -> None:
    """Pull the live breaker states into Prometheus gauges. Called
    on every /metrics scrape — cheap because the breaker dict is
    only 5 entries."""
    if not PROMETHEUS_AVAILABLE:
        return
    try:
        from backend.ai.resilience import all_breaker_states

        for provider, state in all_breaker_states().items():
            llm_circuit_state.labels(provider=provider).set(
                _STATE_TO_GAUGE.get(state, -1)
            )
    except Exception as e:  # noqa: BLE001
        logger.debug(f"breaker metrics refresh failed: {e}")


@router.get("/metrics", include_in_schema=False)
def metrics() -> Response:
    """Prometheus scrape target. Returns 503 if the client library
    is missing so the scrape target can be marked DOWN rather than
    silently returning empty data."""
    if not PROMETHEUS_AVAILABLE:
        return Response(
            content=b"# prometheus_client not installed\n",
            media_type="text/plain",
            status_code=503,
        )
    _refresh_breaker_metrics()
    return Response(
        content=generate_latest(registry),
        media_type=CONTENT_TYPE_LATEST,
    )


@router.get("/breakers", include_in_schema=False)
def breakers() -> dict:
    """Lightweight admin-style view of the current LLM circuit
    breaker states. Useful when running without Prometheus."""
    if not PROMETHEUS_AVAILABLE:
        return {"error": "prometheus_client not installed"}
    try:
        from backend.ai.resilience import all_breaker_states

        return {"breakers": all_breaker_states()}
    except Exception as e:  # noqa: BLE001
        logger.error(f"breaker endpoint failed: {e}")
        return {"error": "unavailable"}
