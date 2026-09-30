"""Regression: the AI rate-limit guard's exception branch referenced an
undefined ``settings`` name (hidden by ``# noqa: F821``), so a limiter
failure raised NameError instead of failing closed (prod) / open (dev)."""

import asyncio
from types import SimpleNamespace

import pytest

from backend.ai import llm


@pytest.fixture
def request_identity():
    tokens = [
        (llm.current_company_id_var, llm.current_company_id_var.set(1)),
        (llm.current_user_id_var, llm.current_user_id_var.set(2)),
        (llm.current_ip_var, llm.current_ip_var.set("203.0.113.9")),
    ]
    yield
    for var, tok in reversed(tokens):
        var.reset(tok)


@pytest.mark.parametrize("is_prod, expected_allowed", [(True, False), (False, True)])
def test_limiter_failure_fails_closed_in_prod_open_in_dev(
    monkeypatch, request_identity, is_prod, expected_allowed
):
    async def exploding_check(**kwargs):
        raise RuntimeError("redis down")

    monkeypatch.setattr(llm.AISecurity, "check_rate_limit", exploding_check)
    monkeypatch.setattr(llm, "get_settings", lambda: SimpleNamespace(is_prod=is_prod))

    allowed, message = asyncio.run(llm._check_ai_security_rate_limit())

    assert allowed is expected_allowed
    if not expected_allowed:
        assert "unavailable" in message
