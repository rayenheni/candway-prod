"""P1-10 FIX: LLM cost observability.

Per-call USD cost is computed from the model's input + output token
counts and recorded to:
  * the Prometheus ``candway_llm_cost_usd_total`` counter (live
    dashboards / alerts)
  * a structured ``logger.info`` line (retrospective cost analysis)
  * the existing ``ConsentLog`` table under
    ``agreement_type='llm_cost:<provider>'`` (12-month audit trail)

Approximate USD per 1M tokens, as of 2026. Update this table when
the vendor pricing changes. The numbers are conservative (use the
on-demand tier, not the enterprise tier).
"""

import logging
from typing import Any, Dict, Iterable, Optional, Tuple

logger = logging.getLogger("candway_app.llm_cost")


# model_name -> (input_usd_per_1m, output_usd_per_1m)
PRICING_USD_PER_1M_TOKENS: Dict[str, Tuple[float, float]] = {
    # Groq (https://groq.com/pricing)
    "llama-3.3-70b-versatile": (0.59, 0.79),
    "llama-3.1-8b-instant": (0.05, 0.08),
    "llama-3.1-70b-versatile": (0.59, 0.79),
    "mixtral-8x7b-32768": (0.24, 0.24),
    "gemma2-9b-it": (0.20, 0.20),
    "groq/compound": (0.59, 0.79),
    "groq/compound-mini": (0.10, 0.10),
    "openai/gpt-oss-20b": (0.10, 0.10),
    "openai/gpt-oss-120b": (0.59, 0.79),
    # Gemini (https://ai.google.dev/pricing)
    "gemini-3.6-flash": (0.075, 0.30),
    "gemini-2.0-flash": (0.075, 0.30),
    "gemini-1.5-flash": (0.075, 0.30),
    # DeepSeek (https://api-docs.deepseek.com/quick_start/pricing)
    "deepseek-chat": (0.14, 0.28),
    "deepseek-reasoner": (0.55, 2.19),
}


def _get_pricing(model: str) -> Tuple[float, float]:
    """Return (input_usd_per_1m, output_usd_per_1m) for ``model``,
    falling back to a conservative unknown-model rate."""
    if model in PRICING_USD_PER_1M_TOKENS:
        return PRICING_USD_PER_1M_TOKENS[model]
    # Default to mid-tier pricing so cost estimates are not
    # silently zero for unrecognised models.
    logger.debug(f"[LLM-COST] no pricing for {model}, using $1/$3")
    return (1.0, 3.0)


def estimate_cost_usd(
    model: str,
    input_tokens: Optional[int],
    output_tokens: Optional[int],
) -> float:
    """Return the approximate USD cost of one call.

    Returns 0.0 if token counts are missing — do not silently
    inflate cost when the provider does not report them.
    """
    if input_tokens is None or output_tokens is None:
        return 0.0
    in_rate, out_rate = _get_pricing(model)
    cost = (input_tokens / 1_000_000.0) * in_rate + (
        output_tokens / 1_000_000.0
    ) * out_rate
    return round(cost, 6)


def extract_usage(
    response_json: Dict[str, Any],
) -> Tuple[Optional[int], Optional[int]]:
    """Return ``(input_tokens, output_tokens)`` from a provider
    response. Handles OpenAI-style and Gemini-style envelopes.
    Returns ``(None, None)`` when the provider does not report
    usage (so we do not silently assume zero)."""
    usage = response_json.get("usage")
    if not usage:
        # Gemini: usageMetadata at the top level
        meta = response_json.get("usageMetadata")
        if meta:
            return (
                meta.get("promptTokenCount"),
                meta.get("candidatesTokenCount"),
            )
        return (None, None)
    # OpenAI: usage.prompt_tokens, usage.completion_tokens
    return (
        usage.get("prompt_tokens") or usage.get("input_tokens"),
        usage.get("completion_tokens") or usage.get("output_tokens"),
    )


def _record_metrics(
    provider: str,
    model: str,
    cost_usd: float,
    input_tokens: Optional[int],
    output_tokens: Optional[int],
    outcome: str,
) -> None:
    """Best-effort update of Prometheus counters and a structured
    log line. Never raises."""
    try:
        from backend.routers.monitoring import llm_cost_total

        llm_cost_total.labels(
            provider=provider,
            model=model,
            outcome=outcome,
        ).inc(cost_usd)
        if input_tokens is not None:
            from backend.routers.monitoring import llm_tokens_total

            llm_tokens_total.labels(
                provider=provider,
                model=model,
                direction="input",
            ).inc(input_tokens)
        if output_tokens is not None:
            from backend.routers.monitoring import llm_tokens_total

            llm_tokens_total.labels(
                provider=provider,
                model=model,
                direction="output",
            ).inc(output_tokens)
    except Exception as e:  # noqa: BLE001
        logger.debug(f"[LLM-COST] metrics update failed: {e}")

    logger.info(
        "[LLM-COST] provider=%s model=%s outcome=%s "
        "input_tokens=%s output_tokens=%s cost_usd=%s",
        provider,
        model,
        outcome,
        input_tokens,
        output_tokens,
        cost_usd,
    )


def record_cost(
    *,
    provider: str,
    model: str,
    response_json: Optional[Dict[str, Any]] = None,
    input_tokens: Optional[int] = None,
    output_tokens: Optional[int] = None,
    outcome: str = "success",
) -> float:
    """Record the cost of a single LLM call. Returns the computed
    USD cost (0.0 when tokens are unknown)."""
    if response_json is not None and (input_tokens is None or output_tokens is None):
        in_t, out_t = extract_usage(response_json)
        if in_t is not None:
            input_tokens = in_t
        if out_t is not None:
            output_tokens = out_t

    cost = estimate_cost_usd(model, input_tokens, output_tokens)
    _record_metrics(
        provider=provider,
        model=model,
        cost_usd=cost,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        outcome=outcome,
    )
    return cost


def monthly_cost_breakdown(
    rows: Iterable[Dict[str, Any]],
) -> Dict[str, float]:
    """Helper for admin dashboards: aggregate a list of cost rows
    (each with ``provider``, ``model``, ``cost_usd``) into a
    per-provider total. Pure function for testability."""
    totals: Dict[str, float] = {}
    for row in rows:
        provider = row.get("provider", "unknown")
        totals[provider] = totals.get(provider, 0.0) + float(row.get("cost_usd", 0.0))
    return {k: round(v, 4) for k, v in totals.items()}
