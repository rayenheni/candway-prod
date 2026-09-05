"""Regression tests for the central Groq trailing-user normalization.

Groq's compound-family models reject payloads whose last message role is
"system". ``backend.ai.llm`` now normalizes every message list before any
cascade payload is built, so this suite pins the invariant:
  - system-only payloads become ``system + user``;
  - existing user-last payloads (single or multi-turn) pass through
    byte-for-byte;
  - existing messages (system content in particular) are never mutated;
  - JSON mode, retry-without-json and the self-heal path can never send a
    system-last payload;
  - all-fail still returns ``None``.

Bare-string entries are NOT part of the supported message contract and are
deliberately left untouched (reported as a separate pre-existing bug).
"""

import asyncio
from unittest.mock import AsyncMock

import pytest

from backend.ai import llm as llm_module
from backend.ai.llm import (
    _TRAILING_USER_INSTRUCTION,
    _call_groq_cascade_impl,
    _normalize_trailing_user,
)
from backend.ai.security import AISecurity

_OK_CONTENT = '{"ok": true}'


# ---------------------------------------------------------------------------
# Unit tests: _normalize_trailing_user
# ---------------------------------------------------------------------------


def test_system_only_payload_becomes_system_plus_user():
    messages = [{"role": "system", "content": "You are a parsing engine."}]
    normalized = _normalize_trailing_user(messages)
    assert len(normalized) == 2
    assert normalized[0]["role"] == "system"
    assert normalized[0]["content"] == "You are a parsing engine."
    assert normalized[-1]["role"] == "user"
    assert normalized[-1]["content"] == _TRAILING_USER_INSTRUCTION


def test_existing_system_plus_user_is_unchanged():
    messages = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "hello"},
    ]
    normalized = _normalize_trailing_user(messages)
    assert normalized is messages
    assert normalized == messages


def test_multi_turn_history_ending_in_user_is_unchanged():
    messages = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "q1"},
        {"role": "assistant", "content": "a1"},
        {"role": "user", "content": "q2"},
    ]
    normalized = _normalize_trailing_user(messages)
    assert normalized is messages
    assert [m["role"] for m in normalized] == [
        "system",
        "user",
        "assistant",
        "user",
    ]


def test_system_content_remains_byte_for_byte():
    system_content = "Analyse CV — Résumé 𝒟\u200b\n\tend"
    messages = [{"role": "system", "content": system_content}]
    system_msg = messages[0]
    normalized = _normalize_trailing_user(messages)
    # Same dict object, untouched content
    assert normalized[0] is system_msg
    assert normalized[0]["content"] == system_content
    assert (
        normalized[0]["content"].encode("utf-8")
        == system_content.encode("utf-8")
    )
    # Caller's list/messages never mutated
    assert len(messages) == 1
    assert messages[0] == {"role": "system", "content": system_content}


def test_payload_ending_in_system_appends_user_after_system():
    messages = [
        {"role": "system", "content": "sys"},
        {"role": "assistant", "content": "prev"},
        {"role": "system", "content": "last-system"},
    ]
    normalized = _normalize_trailing_user(messages)
    assert [m["role"] for m in normalized] == [
        "system",
        "assistant",
        "system",
        "user",
    ]
    assert normalized[2]["content"] == "last-system"
    assert normalized[-1]["content"] == _TRAILING_USER_INSTRUCTION


def test_normalization_is_idempotent():
    original = [{"role": "system", "content": "sys"}]
    once = _normalize_trailing_user(original)
    twice = _normalize_trailing_user(once)
    assert len(once) == 2
    assert len(twice) == 2
    assert twice[-1]["role"] == "user"


def test_empty_nonlist_and_bare_string_passthrough():
    assert _normalize_trailing_user([]) == []
    assert _normalize_trailing_user(None) is None
    assert _normalize_trailing_user("not a list") == "not a list"
    bare = ["some bare string entry"]
    assert _normalize_trailing_user(bare) is bare


def test_trailing_user_constant_is_injection_safe():
    safe, _reason = AISecurity.detect_prompt_injection(_TRAILING_USER_INSTRUCTION)
    assert safe is True


# ---------------------------------------------------------------------------
# Integration tests: _call_groq_cascade_impl (mocked transport)
# ---------------------------------------------------------------------------


class FakeResponse:
    def __init__(self, status_code=200, content=_OK_CONTENT):
        self.status_code = status_code
        self.text = content
        self._content = content

    def json(self):
        return {"choices": [{"message": {"content": self._content}}]}


class FakeClient:
    """Captures every POSTed payload; responder is a callable -> FakeResponse."""

    def __init__(self, responder):
        self._responder = responder
        self.posted_payloads = []

    async def post(self, url, headers=None, json=None, timeout=None):
        self.posted_payloads.append(json)
        return self._responder()


class _NoopLimiter:
    async def acquire(self):
        return True


def _install_mocks(monkeypatch, responder):
    async def _config():
        return {
            "groq_api_key": "test-key-not-a-placeholder",
            "ai_model": None,
            "use_local_llm": "false",
        }

    client = FakeClient(responder)
    monkeypatch.setattr(llm_module, "_get_cached_system_config", _config)
    monkeypatch.setattr(llm_module, "get_http_client", lambda: client)
    monkeypatch.setattr(llm_module, "groq_rate_limiter", _NoopLimiter())
    monkeypatch.setattr(llm_module, "record_cost", lambda *a, **k: None)
    monkeypatch.setattr("backend.trakin.ai_monitor.log_ai_interaction", AsyncMock())
    monkeypatch.setattr("backend.ai_audit.log_ai_call", lambda **kw: None)
    return client


@pytest.mark.asyncio
async def test_cascade_system_only_ends_with_user_and_returns_parsed_json(
    monkeypatch,
):
    input_messages = [{"role": "system", "content": "Return analysis."}]
    client = _install_mocks(
        monkeypatch,
        responder=lambda: FakeResponse(status_code=200, content='{"ok": true}'),
    )

    result = await _call_groq_cascade_impl(
        list(input_messages), temperature=0.1, max_tokens=1024, json_mode=True
    )

    assert result == {"ok": True}
    sent = client.posted_payloads[0]["messages"]
    assert sent[0]["role"] == "system"
    assert sent[0]["content"] == "Return analysis."
    assert sent[-1]["role"] == "user"
    # JSON-hint landed on the appended trailing user message, not on system
    assert sent[-1]["content"].endswith("Output your response as valid JSON.")
    assert client.posted_payloads[0].get("response_format") == {"type": "json_object"}
    # Caller's list is never mutated
    assert len(input_messages) == 1
    assert input_messages[0] == {"role": "system", "content": "Return analysis."}


@pytest.mark.asyncio
async def test_cascade_system_plus_user_sent_byte_for_byte(monkeypatch):
    input_messages = [
        {"role": "system", "content": "SYS-BODY 中文"},
        {"role": "user", "content": "USER-BODY"},
    ]
    client = _install_mocks(
        monkeypatch,
        responder=lambda: FakeResponse(status_code=200, content=_OK_CONTENT),
    )

    result = await _call_groq_cascade_impl(
        list(input_messages), temperature=0.1, max_tokens=1024, json_mode=False
    )

    assert result == _OK_CONTENT  # json_mode=False returns raw content string
    sent = client.posted_payloads[0]["messages"]
    assert sent == input_messages  # roles + content byte-for-byte identical


@pytest.mark.asyncio
async def test_cascade_multi_turn_history_unchanged(monkeypatch):
    input_messages = [
        {"role": "system", "content": "S"},
        {"role": "user", "content": "U1"},
        {"role": "assistant", "content": "A1"},
        {"role": "user", "content": "U2"},
    ]
    client = _install_mocks(
        monkeypatch,
        responder=lambda: FakeResponse(status_code=200, content=_OK_CONTENT),
    )

    await _call_groq_cascade_impl(
        list(input_messages), temperature=0.1, max_tokens=1024, json_mode=False
    )

    sent = client.posted_payloads[0]["messages"]
    assert sent == input_messages


@pytest.mark.asyncio
async def test_all_fail_returns_none_and_never_sends_system_last(monkeypatch):
    """Every model 400s; cascade falls through retries + self-heal. None/all-fail
    behavior inherited, and no payload (incl. self-heal) is ever system-last."""
    input_messages = [{"role": "system", "content": "S"}]
    client = _install_mocks(
        monkeypatch,
        responder=lambda: FakeResponse(status_code=400, content="bad request"),
    )
    # Remove backoff delays (pre-existing retry behavior preserved otherwise)
    monkeypatch.setattr(asyncio, "sleep", _no_sleep)

    result = await _call_groq_cascade_impl(
        list(input_messages), temperature=0.1, max_tokens=1024, json_mode=True
    )

    assert result is None
    assert len(client.posted_payloads) > 0
    for payload in client.posted_payloads:
        assert payload["messages"][-1]["role"] == "user"
    # Caller's list is never mutated
    assert input_messages == [{"role": "system", "content": "S"}]


async def _no_sleep(_delay=None):
    return None