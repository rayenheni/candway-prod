"""
Tests for HMAC signed CV URLs (bug B-29).

The signed-URL helper issues 5-minute HMAC tokens bound to a file,
a subject (candidate) user, and a bearer (recruiter) user. The
``/uploads`` route accepts such a token in lieu of the candidate
being the logged-in user.
"""

import os
import time

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("SECRET_KEY", "test_secret_key_for_jwt_encoding_12345")
os.environ.setdefault("TESTING", "true")


from backend.signed_url import (  # noqa: E402
    make_signed_cv_token,
    verify_signed_cv_token,
)


def test_round_trip():
    signed = make_signed_cv_token(
        file_path="upload_42_abc.pdf",
        subject_user_id=42,
        bearer_user_id=7,
    )
    assert signed["expires_at"] > int(time.time())
    assert verify_signed_cv_token(
        file_path="upload_42_abc.pdf",
        token=signed["token"],
        bearer_user_id=7,
    )


def test_expired_token_rejected():
    signed = make_signed_cv_token(
        file_path="upload_42_abc.pdf",
        subject_user_id=42,
        bearer_user_id=7,
        ttl_seconds=-1,  # already expired
    )
    assert not verify_signed_cv_token(
        file_path="upload_42_abc.pdf",
        token=signed["token"],
        bearer_user_id=7,
    )


def test_bearer_mismatch_rejected():
    signed = make_signed_cv_token(
        file_path="upload_42_abc.pdf",
        subject_user_id=42,
        bearer_user_id=7,
    )
    # Recruiter #99 tries to use a token issued for recruiter #7
    assert not verify_signed_cv_token(
        file_path="upload_42_abc.pdf",
        token=signed["token"],
        bearer_user_id=99,
    )


def test_subject_mismatch_rejected():
    signed = make_signed_cv_token(
        file_path="upload_42_abc.pdf",
        subject_user_id=42,
        bearer_user_id=7,
    )
    # Even the original bearer can't use the token against a
    # different file (signature covers the file path).
    assert not verify_signed_cv_token(
        file_path="upload_99_xyz.pdf",
        token=signed["token"],
        bearer_user_id=7,
    )


def test_tampered_token_rejected():
    signed = make_signed_cv_token(
        file_path="upload_42_abc.pdf",
        subject_user_id=42,
        bearer_user_id=7,
    )
    tampered = signed["token"].replace("42", "99")
    assert not verify_signed_cv_token(
        file_path="upload_42_abc.pdf",
        token=tampered,
        bearer_user_id=7,
    )


def test_missing_token_rejected():
    assert not verify_signed_cv_token(
        file_path="upload_42_abc.pdf",
        token=None,
        bearer_user_id=7,
    )


def test_malformed_token_rejected():
    assert not verify_signed_cv_token(
        file_path="upload_42_abc.pdf",
        token="not-a-real-token",
        bearer_user_id=7,
    )
    assert not verify_signed_cv_token(
        file_path="upload_42_abc.pdf",
        token="a.b.c",  # only 3 parts
        bearer_user_id=7,
    )


def test_url_format_contains_token_query():
    signed = make_signed_cv_token(
        file_path="upload_42_abc.pdf",
        subject_user_id=42,
        bearer_user_id=7,
    )
    assert signed["url"].startswith("/uploads/upload_42_abc.pdf?token=")
    assert signed["token"] in signed["url"]
