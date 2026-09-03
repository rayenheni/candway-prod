"""P1-10 FIX tests: LLM cost observability.

Locks the three cost properties the platform depends on:

1. ``estimate_cost_usd`` returns 0.0 when token counts are
   missing (no silent inflation).
2. ``extract_usage`` understands both OpenAI-style
   (``usage.prompt_tokens``) and Gemini-style
   (``usageMetadata.promptTokenCount``) envelopes.
3. ``monthly_cost_breakdown`` aggregates provider totals.
4. ``record_cost`` is best-effort: when the response is missing
   the usage block, it records 0.0 but does not raise.
"""
import pytest

from backend.llm_cost import (
    PRICING_USD_PER_1M_TOKENS,
    estimate_cost_usd,
    extract_usage,
    monthly_cost_breakdown,
    record_cost,
)


def test_estimate_cost_known_model():
    # 1M input + 1M output of llama-3.3-70b = $0.59 + $0.79 = $1.38
    cost = estimate_cost_usd("llama-3.3-70b-versatile", 1_000_000, 1_000_000)
    assert cost == pytest.approx(1.38, rel=1e-6)


def test_estimate_cost_zero_when_tokens_missing():
    assert estimate_cost_usd("llama-3.3-70b-versatile", None, 500) == 0.0
    assert estimate_cost_usd("llama-3.3-70b-versatile", 500, None) == 0.0


def test_estimate_cost_unknown_model_falls_back():
    # Unknown model should still return > 0 (mid-tier fallback)
    # so dashboards don't silently read $0.
    cost = estimate_cost_usd("future-model-99", 1_000_000, 0)
    assert cost > 0


def test_extract_usage_openai_style():
    response = {
        "usage": {"prompt_tokens": 100, "completion_tokens": 50}
    }
    assert extract_usage(response) == (100, 50)


def test_extract_usage_anthropic_aliases():
    response = {
        "usage": {"input_tokens": 200, "output_tokens": 75}
    }
    assert extract_usage(response) == (200, 75)


def test_extract_usage_gemini_style():
    response = {
        "usageMetadata": {
            "promptTokenCount": 320,
            "candidatesTokenCount": 80,
        }
    }
    assert extract_usage(response) == (320, 80)


def test_extract_usage_no_usage_block():
    assert extract_usage({}) == (None, None)
    assert extract_usage({"usage": {}}) == (None, None)


def test_monthly_breakdown_aggregates_per_provider():
    rows = [
        {"provider": "groq", "model": "llama-3.3-70b-versatile", "cost_usd": 0.10},
        {"provider": "groq", "model": "llama-3.1-8b-instant", "cost_usd": 0.02},
        {"provider": "gemini", "model": "gemini-2.0-flash", "cost_usd": 0.05},
        {"provider": "deepseek", "model": "deepseek-chat", "cost_usd": 0.14},
    ]
    totals = monthly_cost_breakdown(rows)
    assert totals["groq"] == pytest.approx(0.12)
    assert totals["gemini"] == pytest.approx(0.05)
    assert totals["deepseek"] == pytest.approx(0.14)


def test_monthly_breakdown_handles_missing_fields():
    rows = [
        {"provider": "groq"},
        {"cost_usd": 0.05},
    ]
    totals = monthly_cost_breakdown(rows)
    # Both rows should be counted under "groq"/"unknown" without
    # raising.
    assert sum(totals.values()) == pytest.approx(0.05)


def test_record_cost_does_not_raise_on_missing_usage(monkeypatch):
    # No DB needed: record_cost should still log even if the
    # metrics helper fails. Just confirm it doesn't raise.
    cost = record_cost(
        provider="groq",
        model="llama-3.3-70b-versatile",
        response_json={},  # no usage block
    )
    # When usage is missing, the function returns 0.0 — it must
    # not silently inflate the cost.
    assert cost == 0.0


def test_record_cost_pulls_usage_from_response(monkeypatch):
    cost = record_cost(
        provider="groq",
        model="llama-3.3-70b-versatile",
        response_json={
            "usage": {"prompt_tokens": 1_000_000, "completion_tokens": 1_000_000}
        },
    )
    assert cost == pytest.approx(1.38, rel=1e-6)


def test_pricing_table_has_groq_models():
    assert "llama-3.3-70b-versatile" in PRICING_USD_PER_1M_TOKENS
    assert "llama-3.1-8b-instant" in PRICING_USD_PER_1M_TOKENS


def test_pricing_table_has_gemini_models():
    assert "gemini-2.0-flash" in PRICING_USD_PER_1M_TOKENS


def test_pricing_table_has_deepseek_models():
    assert "deepseek-chat" in PRICING_USD_PER_1M_TOKENS
    # Reasoning model is the most expensive — guard against
    # anyone accidentally zeroing it.
    assert PRICING_USD_PER_1M_TOKENS["deepseek-reasoner"][1] > 1.0
