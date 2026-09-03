"""Tests for backend/deepseek_service.py — DeepSeek AI fallback provider."""

import json

import httpx
import pytest

from backend.deepseek_service import (
    DeepSeekService,
    generate_question_with_deepseek,
    init_deepseek_service,
)


class FakeDeepSeekResponse:
    """Simulates httpx.Response for DeepSeek API."""

    def __init__(self, status_code=200, json_data=None):
        self.status_code = status_code
        self._json_data = json_data or {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "question": "Test Q?",
                                "options": ["A. opt1", "B. opt2", "C. opt3", "D. opt4"],
                                "correct_answer": "A. opt1",
                                "cv_reference": "Project X",
                            }
                        )
                    }
                }
            ]
        }
        self.text = json.dumps(self._json_data)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    def json(self):
        return self._json_data


class FakeAsyncClient:
    """Simulates httpx.AsyncClient."""

    def __init__(self, timeout=30.0):
        self.timeout = timeout

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    async def post(self, url, json=None, headers=None):
        return FakeDeepSeekResponse()


class TestDeepSeekService:
    def test_init(self):
        service = DeepSeekService(api_key="test-key")
        assert service.api_key == "test-key"
        assert service.model == "deepseek-chat"

    @pytest.mark.asyncio
    async def test_generate_question_success(self, monkeypatch):
        service = DeepSeekService(api_key="test-key")

        monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)

        result = await service.generate_question(prompt="test prompt")
        assert result["question"] == "Test Q?"
        assert result["correct_answer"] == "A. opt1"
        assert result["cv_reference"] == "Project X"

    @pytest.mark.asyncio
    async def test_generate_question_json_parse_error(self, monkeypatch):
        service = DeepSeekService(api_key="test-key")

        class BadJsonFakeResponse(FakeDeepSeekResponse):
            def __init__(self, status_code=200, json_data=None):
                self.status_code = status_code
                self._json_data = {
                    "choices": [{"message": {"content": "not valid json"}}]
                }
                self.text = json.dumps(self._json_data)

            def json(self):
                return self._json_data

        class BadJsonFakeAsyncClient:
            def __init__(self, timeout=30.0):
                self.timeout = timeout

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                pass

            async def post(self, url, json=None, headers=None):
                return BadJsonFakeResponse()

        monkeypatch.setattr(httpx, "AsyncClient", BadJsonFakeAsyncClient)

        with pytest.raises(json.JSONDecodeError):
            await service.generate_question(prompt="test prompt")

    @pytest.mark.asyncio
    async def test_generate_question_api_error(self, monkeypatch):
        service = DeepSeekService(api_key="test-key")

        class ErrorFakeAsyncClient:
            def __init__(self, timeout=30.0):
                self.timeout = timeout

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                pass

            async def post(self, url, json=None, headers=None):
                return FakeDeepSeekResponse(
                    status_code=500, json_data={"error": "Internal"}
                )

        monkeypatch.setattr(httpx, "AsyncClient", ErrorFakeAsyncClient)

        with pytest.raises(Exception, match="DeepSeek API failed"):
            await service.generate_question(prompt="test prompt")

    @pytest.mark.asyncio
    async def test_generate_question_empty_response(self, monkeypatch):
        service = DeepSeekService(api_key="test-key")

        class EmptyFakeAsyncClient:
            def __init__(self, timeout=30.0):
                self.timeout = timeout

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                pass

            async def post(self, url, json=None, headers=None):
                return FakeDeepSeekResponse(json_data={"choices": []})

        monkeypatch.setattr(httpx, "AsyncClient", EmptyFakeAsyncClient)

        with pytest.raises(Exception, match="DeepSeek returned empty response"):
            await service.generate_question(prompt="test prompt")


class TestDeepSeekServiceWrapper:
    def teardown_method(self):
        import backend.deepseek_service as ds

        ds.deepseek_service = None

    @pytest.mark.asyncio
    async def test_wrapper_not_initialized(self):
        with pytest.raises(Exception, match="DeepSeek service not initialized"):
            await generate_question_with_deepseek(prompt="test")

    @pytest.mark.asyncio
    async def test_wrapper_success(self, monkeypatch):
        init_deepseek_service(api_key="test-key")
        monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)

        result = await generate_question_with_deepseek(prompt="test prompt")
        assert result["question"] == "Test Q?"
