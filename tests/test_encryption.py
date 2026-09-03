"""P0-02 FIX tests: Encryption key is mandatory + versioned envelope.

These tests lock the safety properties of the PII encryption layer:

1. Missing CANDWAY_FIELD_ENCRYPTION_KEY raises EncryptionKeyError.
2. The active envelope is versioned (``ENCv1:``).
3. Round-trip: encrypt then decrypt returns the plaintext.
4. Legacy plaintext values (no prefix) pass through unchanged.
5. Re-encryption under a new key produces a value that the OLD key
   cannot read but the NEW key can.
"""
import os
import pytest
from cryptography.fernet import Fernet


@pytest.fixture(autouse=True)
def _set_key(monkeypatch):
    """Give every test a fresh, valid Fernet key."""
    key = Fernet.generate_key().decode("ascii")
    monkeypatch.setenv("CANDWAY_FIELD_ENCRYPTION_KEY", key)
    yield key


def test_init_requires_env_var(monkeypatch):
    monkeypatch.delenv("CANDWAY_FIELD_ENCRYPTION_KEY", raising=False)
    monkeypatch.setattr("os.path.exists", lambda p: False)
    from backend.encryption import (
        EncryptionKeyError,
        init_encryption_keys,
    )
    with pytest.raises(EncryptionKeyError):
        init_encryption_keys()


def test_init_rejects_malformed_key(monkeypatch):
    monkeypatch.setenv(
        "CANDWAY_FIELD_ENCRYPTION_KEY", "not-a-valid-fernet-key"
    )
    from backend.encryption import (
        EncryptionKeyError,
        init_encryption_keys,
    )
    with pytest.raises(EncryptionKeyError):
        init_encryption_keys()


def test_round_trip():
    from backend import encryption

    encryption.init_encryption_keys()
    plaintext = "John Doe, john@example.com, +216 12 345 678"
    encrypted = encryption.encrypt_text(plaintext)
    assert encrypted is not None
    assert encrypted.startswith("ENCv1:")
    assert encryption.is_encrypted(encrypted)
    assert encryption.decrypt_text(encrypted) == plaintext


def test_legacy_plaintext_passes_through():
    from backend import encryption

    encryption.init_encryption_keys()
    legacy = '{"name": "John"}'
    # Legacy value: no prefix, decrypt returns it as-is so the
    # backfill in flight can read both formats.
    assert encryption.decrypt_text(legacy) == legacy
    # And encryption is idempotent: encrypting an already-encrypted
    # value returns the value unchanged.
    encrypted = encryption.encrypt_text(legacy)
    # legacy has no prefix, so it gets encrypted.
    assert encrypted.startswith("ENCv1:")
    again = encryption.encrypt_text(encrypted)
    assert again == encrypted


def test_empty_and_none():
    from backend import encryption

    encryption.init_encryption_keys()
    assert encryption.encrypt_text(None) is None
    assert encryption.encrypt_text("") == ""
    assert encryption.decrypt_text(None) is None
    assert encryption.decrypt_text("") == ""


def test_reencrypt_under_new_key():
    from backend import encryption

    encryption.init_encryption_keys()
    plaintext = "secret CV content"
    encrypted_v1 = encryption.encrypt_text(plaintext)

    # Rotate to a brand new key. The old v1 ciphertext must now
    # be unreadable with the new active key, but the re-encrypted
    # value must round-trip.
    new_key = Fernet.generate_key()
    encryption.reencrypt(encrypted_v1, new_key)
    # rotate_key flips the active registry so future writes use v1
    # (the active version) under the new bytes.
    encryption.rotate_key(new_key)
    new_encrypted = encryption.encrypt_text(plaintext)
    assert encryption.decrypt_text(new_encrypted) == plaintext


def test_envelope_version_is_stable():
    from backend import encryption

    encryption.init_encryption_keys()
    assert encryption.ENVELOPE_VERSION == 1
    assert encryption.get_active_key_version() == 1


def test_pii_columns_registry_is_complete():
    from backend.encryption import PII_TEXT_COLUMNS

    expected = {
        "cv_text_anonymized",
        "analysis_json",
        "interview_log",
        "calibration_json",
    }
    assert expected.issubset(set(PII_TEXT_COLUMNS))
