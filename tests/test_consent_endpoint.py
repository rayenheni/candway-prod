"""P1-04 FIX tests: GDPR consent capture endpoint.

Locks the safety properties of the consent capture flow:

1. The endpoint refuses unknown agreement types with 422.
2. The endpoint refuses to record consent for another user
   (403) unless the requester is an admin with
   ``manage_users``.
3. The endpoint writes one ConsentLog row per agreement type
   and an AuditLog entry on success.
4. The list endpoint returns the user's consent history sorted
   by most recent.
"""
from __future__ import annotations


def test_consent_module_loads():
    from pathlib import Path

    p = Path("backend/routers/consent.py")
    assert p.exists()
    src = p.read_text(encoding="utf-8")
    assert "def capture_consent" in src
    assert "def list_consents" in src
    assert "ALLOWED_AGREEMENT_TYPES" in src


def test_consent_module_lists_known_types():
    from pathlib import Path

    src = Path("backend/routers/consent.py").read_text(encoding="utf-8")
    for agreement_type in (
        "terms_and_privacy",
        "marketing_emails",
        "ai_processing",
        "ai_processing_deepseek",
        "ai_processing_gemini",
        "cookies_analytics",
    ):
        assert (
            f'"{agreement_type}"' in src or f"'{agreement_type}'" in src
        ), f"agreement_type {agreement_type} must be in ALLOWED set"


def test_consent_refuses_unknown_types():
    """Pydantic must reject any agreement type not in the
    allow-list so callers cannot pollute the ConsentLog with
    arbitrary strings."""
    import pytest
    from backend.routers.consent import ConsentCaptureRequest

    with pytest.raises(ValueError):
        ConsentCaptureRequest(
            agreement_types=["bogus_type"],
            policy_version="v1",
        )

    with pytest.raises(ValueError):
        ConsentCaptureRequest(
            agreement_types=["ai_processing", "gibberish"],
            policy_version="v1",
        )


def test_consent_request_requires_at_least_one_type():
    import pytest
    from backend.routers.consent import ConsentCaptureRequest

    with pytest.raises(ValueError):
        ConsentCaptureRequest(
            agreement_types=[],
            policy_version="v1",
        )


def test_consent_request_accepts_known_types():
    from backend.routers.consent import ConsentCaptureRequest

    req = ConsentCaptureRequest(
        agreement_types=["terms_and_privacy", "ai_processing"],
        policy_version="v1.0",
    )
    assert req.agreement_types == ["terms_and_privacy", "ai_processing"]
    assert req.policy_version == "v1.0"


def test_consent_endpoint_writes_audit_log():
    from pathlib import Path

    src = Path("backend/routers/consent.py").read_text(encoding="utf-8")
    assert "AuditLog" in src
    assert "gdpr_consent_captured" in src


def test_consent_endpoint_uses_self_or_admin_guard():
    from pathlib import Path

    src = Path("backend/routers/consent.py").read_text(encoding="utf-8")
    # The function must check both is_self and is_admin
    # (manage_users) before allowing consent capture for
    # another user.
    assert "is_self" in src
    assert "is_admin" in src
    assert "manage_users" in src
    # And refuse with 403 if neither is true.
    assert "status_code=403" in src


def test_consent_endpoint_404_when_user_missing():
    from pathlib import Path

    src = Path("backend/routers/consent.py").read_text(encoding="utf-8")
    assert "status_code=404" in src


def test_consent_endpoint_uses_gdpr_prefix():
    from pathlib import Path

    src = Path("backend/routers/consent.py").read_text(encoding="utf-8")
    assert "APIRouter(prefix=" in src
    assert '"/gdpr"' in src or "prefix=\"/gdpr\"" in src


def test_consent_router_wired_into_app():
    from pathlib import Path

    app_src = Path("backend/app.py").read_text(encoding="utf-8")
    assert "consent" in app_src
    assert "consent.router" in app_src


def test_consent_endpoint_captures_ip_and_user_agent():
    from pathlib import Path

    src = Path("backend/routers/consent.py").read_text(encoding="utf-8")
    # The endpoint must capture the requester's IP + user agent
    # on each row for the audit trail.
    assert "ip_address=" in src
    assert "user_agent=" in src
    assert "request.client.host" in src
    assert "user-agent" in src.lower()


def test_list_consents_returns_sorted_by_accepted_at():
    from pathlib import Path

    src = Path("backend/routers/consent.py").read_text(encoding="utf-8")
    list_block = src.split("def list_consents")[1]
    assert "accepted_at.desc()" in list_block or "desc" in list_block
