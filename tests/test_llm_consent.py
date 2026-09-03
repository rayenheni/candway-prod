"""P0-04 FIX tests: per-call LLM consent tracking and provider policy."""
import os
import pytest
from cryptography.fernet import Fernet


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("CANDWAY_FIELD_ENCRYPTION_KEY", Fernet.generate_key().decode("ascii"))
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setenv("SECRET_KEY", "test_secret_key_for_jwt_encoding_12345")
    yield


def test_providers_registry_has_all_known_vendors():
    from backend.llm_consent import PROVIDERS

    for name in ("groq", "gemini", "deepseek", "ollama"):
        assert name in PROVIDERS
        assert PROVIDERS[name].name == name
    # Cloud providers are un-signed.
    for cloud in ("groq", "gemini", "deepseek"):
        assert PROVIDERS[cloud].dpa_signed is False
    # Local providers are always signed.
    assert PROVIDERS["ollama"].dpa_signed is True


def test_ollama_is_always_allowed():
    from backend.llm_consent import is_provider_allowed

    assert is_provider_allowed("ollama") is True
    # Even with the strict env flag, ollama is local.
    os.environ["CANDWAY_BLOCK_UNDPA_PROVIDERS"] = "1"
    assert is_provider_allowed("ollama") is True


def test_unknown_provider_is_denied():
    from backend.llm_consent import is_provider_allowed

    assert is_provider_allowed("some_made_up_vendor") is False


def test_block_undpa_env_blocks_cloud_providers():
    from backend.llm_consent import is_provider_allowed, PROVIDERS
    # Sanity: groq / gemini / deepseek start un-signed.
    assert PROVIDERS["groq"].dpa_signed is False
    assert PROVIDERS["deepseek"].dpa_signed is False

    os.environ["CANDWAY_BLOCK_UNDPA_PROVIDERS"] = "1"
    assert is_provider_allowed("groq") is False
    assert is_provider_allowed("gemini") is False
    assert is_provider_allowed("deepseek") is False
    # Cleaning the env allows them again.
    del os.environ["CANDWAY_BLOCK_UNDPA_PROVIDERS"]
    assert is_provider_allowed("groq") is True


def test_record_llm_call_is_best_effort():
    """The helper must never raise; a DB error must be swallowed."""
    from backend import llm_consent
    from backend.database import SessionLocal

    db = SessionLocal()
    try:
        llm_consent.record_llm_call(
            db=db,
            user_id=None,
            provider="groq",
            application_id=None,
            messages=[{"role": "user", "content": "hi"}],
            outcome="success",
        )
    finally:
        db.close()
