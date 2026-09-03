"""Tests for backend/gemini_service.py — Gemini AI fallback provider."""

import json

import httpx
import pytest

from backend.gemini_service import (
    GeminiService,
    generate_question_with_gemini,
    init_gemini_service,
)


class FakeGeminiResponse:
    """Simulates httpx.Response for Gemini API."""

    def __init__(self, status_code=200, json_data=None):
        self.status_code = status_code
        self._json_data = json_data or {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {
                                "text": json.dumps(
                                    {
                                        "question": "Test Q?",
                                        "options": [
                                            "A. opt1",
                                            "B. opt2",
                                            "C. opt3",
                                            "D. opt4",
                                        ],
                                        "correct_answer": "A. opt1",
                                        "cv_reference": "Project X",
                                    }
                                )
                            }
                        ]
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
        return FakeGeminiResponse()


class TestGeminiService:
    def test_init(self):
        service = GeminiService(api_key="test-key")
        assert service.api_key == "test-key"
        assert service.model == "gemini-2.0-flash"

    @pytest.mark.asyncio
    async def test_generate_question_success(self, monkeypatch):
        service = GeminiService(api_key="test-key")

        monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)

        result = await service.generate_question(prompt="test prompt")
        assert result["question"] == "Test Q?"
        assert result["correct_answer"] == "A. opt1"
        assert result["cv_reference"] == "Project X"

    @pytest.mark.asyncio
    async def test_generate_question_json_parse_error(self, monkeypatch):
        service = GeminiService(api_key="test-key")

        class BadJsonFakeResponse(FakeGeminiResponse):
            def __init__(self, status_code=200, json_data=None):
                self.status_code = status_code
                self._json_data = {
                    "candidates": [{"content": {"parts": [{"text": "not valid json"}]}}]
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
        service = GeminiService(api_key="test-key")

        class ErrorFakeAsyncClient:
            def __init__(self, timeout=30.0):
                self.timeout = timeout

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                pass

            async def post(self, url, json=None, headers=None):
                return FakeGeminiResponse(
                    status_code=500, json_data={"error": "Internal"}
                )

        monkeypatch.setattr(httpx, "AsyncClient", ErrorFakeAsyncClient)

        with pytest.raises(Exception, match="Gemini API failed"):
            await service.generate_question(prompt="test prompt")

    @pytest.mark.asyncio
    async def test_generate_question_empty_response(self, monkeypatch):
        service = GeminiService(api_key="test-key")

        class EmptyFakeAsyncClient:
            def __init__(self, timeout=30.0):
                self.timeout = timeout

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                pass

            async def post(self, url, json=None, headers=None):
                return FakeGeminiResponse(json_data={"candidates": []})

        monkeypatch.setattr(httpx, "AsyncClient", EmptyFakeAsyncClient)

        with pytest.raises(Exception, match="Gemini returned empty response"):
            await service.generate_question(prompt="test prompt")


class TestGeminiServiceWrapper:
    def teardown_method(self):
        global gemini_service
        import backend.gemini_service as gs

        gs.gemini_service = None

    @pytest.mark.asyncio
    async def test_wrapper_not_initialized(self):
        with pytest.raises(Exception, match="Gemini service not initialized"):
            await generate_question_with_gemini(prompt="test")

    @pytest.mark.asyncio
    async def test_wrapper_success(self, monkeypatch):
        init_gemini_service(api_key="test-key")
        monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)

        result = await generate_question_with_gemini(prompt="test prompt")
        assert result["question"] == "Test Q?"
