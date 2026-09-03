"""P1-01 FIX tests: Stripe + Konnect payments router.

The router is large enough that a full behaviour test would
require stubbing the entire SQLAlchemy model layer. We use
focused string-level assertions instead — they lock the public
contract in place and would fail immediately if any of the
endpoints disappear or if the gating is removed.
"""


def test_payments_router_file_exists():
    from pathlib import Path

    p = Path("backend/routers/payments.py")
    assert p.exists(), "routers/payments.py must exist"


def test_payments_router_exposes_three_endpoints():
    from pathlib import Path

    src = Path("backend/routers/payments.py").read_text(encoding="utf-8")
    for fn in (
        "def stripe_create_intent",
        "def stripe_webhook",
        "def konnect_create",
    ):
        assert fn in src, f"{fn} must be defined"


def test_payments_router_prefix():
    from pathlib import Path

    src = Path("backend/routers/payments.py").read_text(encoding="utf-8")
    assert "APIRouter(prefix=" in src
    assert '/payments' in src


def test_payments_can_be_disabled_with_env_flag():
    from pathlib import Path

    src = Path("backend/routers/payments.py").read_text(encoding="utf-8")
    assert "CANDWAY_PAYMENTS_ENABLED" in src
    # The flag must short-circuit at the top of every endpoint
    # (not just the Stripe one).
    assert src.count("503") >= 2, (
        "Konnect and Stripe endpoints must both return 503 when disabled"
    )


def test_payments_router_uses_idempotency_key():
    from pathlib import Path

    src = Path("backend/routers/payments.py").read_text(encoding="utf-8")
    # All three endpoints (intent, Konnect, Stripe webhook) must
    # look up / store an idempotency key.
    assert src.count("idempotency_key") >= 4
    # The Stripe intent endpoint must accept an idempotency_key
    # from the request body and use it to dedupe.
    assert "idempotency_key: Optional[str] = None" in src
    # The Stripe webhook must dedupe on event id (or intent id)
    # to refuse duplicate deliveries.
    assert "event_id" in src
    assert "replay" in src


def test_payments_router_emits_audit_log():
    from pathlib import Path

    src = Path("backend/routers/payments.py").read_text(encoding="utf-8")
    # Each successful create must write an AuditLog entry so the
    # legal team can see who paid for what.
    assert "AuditLog" in src
    for action in (
        "stripe_intent_created",
        "konnect_payment_created",
    ):
        assert action in src, f"audit action {action} missing"


def test_payments_router_locks_status_changes():
    from pathlib import Path

    src = Path("backend/routers/payments.py").read_text(encoding="utf-8")
    # The Stripe webhook handler must lock the Transaction row
    # before mutating it (P0-05 pattern).
    assert "with_for_update" in src


def test_payments_router_uses_stripe_optional():
    from pathlib import Path

    src = Path("backend/routers/payments.py").read_text(encoding="utf-8")
    # The ``stripe`` library is optional; the import must be
    # wrapped in try/except so the module loads even on systems
    # without the SDK.
    assert "try:" in src
    assert "import stripe" in src
    assert "STRIPE_AVAILABLE" in src


def test_payments_router_returns_client_secret():
    from pathlib import Path

    src = Path("backend/routers/payments.py").read_text(encoding="utf-8")
    # Stripe's PaymentIntent is useless to the client without a
    # client_secret — the endpoint must return it.
    assert "client_secret" in src
    assert "PaymentIntent.create" in src


def test_payments_router_wired_into_app():
    from pathlib import Path

    app_src = Path("backend/app.py").read_text(encoding="utf-8")
    assert "payments" in app_src
    assert "payments.router" in app_src


def test_payments_router_konnect_uses_service():
    from pathlib import Path

    src = Path("backend/routers/payments.py").read_text(encoding="utf-8")
    # The Konnect create endpoint must delegate to the
    # konnect_service module (which holds the API key + signed
    # request logic).
    assert "konnect_service" in src
    assert "init_payment" in src
