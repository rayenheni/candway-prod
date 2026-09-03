"""
Password hashing + policy tests.

Covers the passlib/bcrypt production incident:
- passlib 1.7.4 is incompatible with bcrypt >= 4.1 (removed __about__,
  raises ValueError on secrets longer than 72 bytes instead of truncating)
  -> requirements.txt must pin bcrypt==4.0.1
- validate_password enforces the bcrypt hard limit (72 UTF-8 bytes) so
  oversized passwords are rejected with a clean 400 at every password-set
  endpoint, never silently truncated and never a 500.
"""

import pytest
from fastapi import HTTPException, status

from backend.dependencies import pwd_context
from backend.password_validator import MAX_PASSWORD_BYTES, validate_password


class TestPasswordHashing:
    """Hash/verify roundtrip + scheme identification via the shared context."""

    def test_roundtrip(self):
        hashed = pwd_context.hash("SecurePass123!")
        assert pwd_context.identify(hashed) == "bcrypt"
        assert pwd_context.verify("SecurePass123!", hashed)
        assert not pwd_context.verify("WrongPass123!", hashed)

    def test_new_hashes_use_bcrypt_14(self):
        hashed = pwd_context.hash("SecurePass123!")
        assert hashed.startswith("$2b$14$")

    def test_legacy_bcrypt_hash_verifies(self):
        legacy = (
            "$2b$12$ipFnTaefxCMOuoUJ/5C1CuGcrlFoTcrcjmGxehp/VUnttVBjSNKUi"  # noqa: E501
        )
        assert pwd_context.identify(legacy) == "bcrypt"
        assert pwd_context.verify("testpassword123", legacy)

    def test_legacy_pbkdf2_sha256_hash_verifies(self):
        legacy = (
            "$pbkdf2-sha256$29000$ai1l7B2D0No$"  # noqa: E501
            "8NqH2ZiM1JuBG.snAPjgdG40T2Zsw4og9u0RNyow3ec"
        )
        assert pwd_context.identify(legacy) == "pbkdf2_sha256"
        assert pwd_context.verify("testpassword123", legacy)


class TestValidatePasswordByteLimit:
    """validate_password must enforce bcrypt's 72-BYTE limit (not chars)."""

    def test_rejects_ascii_over_72_bytes(self):
        with pytest.raises(HTTPException) as exc:
            validate_password("A" * 100)
        assert exc.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "72" in str(exc.value.detail)

    def test_rejects_multibyte_over_72_bytes(self):
        password = "ب" * 40  # 40 chars but 80 bytes in UTF-8
        assert len(password.encode("utf-8")) > MAX_PASSWORD_BYTES
        with pytest.raises(HTTPException) as exc:
            validate_password(password)
        assert exc.value.status_code == status.HTTP_400_BAD_REQUEST

    def test_accepts_exactly_72_bytes(self):
        validate_password("A" * 72)

    def test_rejects_short_password(self):
        with pytest.raises(HTTPException) as exc:
            validate_password("short")
        assert exc.value.status_code == status.HTTP_400_BAD_REQUEST


class TestSignupPasswordPolicyAPI:
    """POST /auth/signup must return clean 4xx for policy violations."""

    def test_signup_long_password_returns_400_not_500(self, client):
        response = client.post(
            "/api/v1/auth/signup",
            json={
                "email": "longpass@example.com",
                "password": "A" * 100,
                "name": "Long Pass User",
                "role": "candidate",
            },
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "72" in response.json()["detail"]

    def test_signup_multibyte_over_72_bytes_returns_400(self, client):
        response = client.post(
            "/api/v1/auth/signup",
            json={
                "email": "multibyte@example.com",
                "password": "ب" * 40,
                "name": "Multibyte User",
                "role": "candidate",
            },
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_signup_boundary_password_accepted(self, client):
        response = client.post(
            "/api/v1/auth/signup",
            json={
                "email": "boundary@example.com",
                "password": "B" * 72,
                "name": "Boundary User",
                "role": "candidate",
            },
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data.get("access_token") or data.get("email_verification_required")

    def test_login_with_long_password_never_500s(self, client):
        response = client.post(
            "/api/v1/auth/login",
            json={"email": "nobody@example.com", "password": "L" * 100},
        )
        assert response.status_code != status.HTTP_500_INTERNAL_SERVER_ERROR
