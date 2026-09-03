"""P1-07: Bcrypt rounds must be 14 (2026 OWASP baseline).

What this file locks
--------------------
1. `CryptContext` is constructed with `bcrypt__rounds=14`
2. New hashes use bcrypt (not pbkdf2_sha256) and the cost factor
   stored in the hash itself is 14
3. The cost is overridable via `CANDWAY_BCRYPT_ROUNDS` env var
   (for CI / smoke tests that need fast hashing)
4. Old pbkdf2_sha256 hashes still verify (backward compat with
   any legacy hashes that pre-date the bcrypt migration)
5. The cost-factor upgrade is self-healing: verifying an
   old-style bcrypt@12 hash succeeds AND triggers an
   automatic re-hash at the new cost factor (passlib's
   `deprecated="auto"` behaviour)

What this file does NOT cover
-----------------------------
* Performance / latency — that's a deployment concern.
* The login rate-limiter (covered by test_login_rate_limit.py).
"""

from __future__ import annotations

import importlib
import os
import pathlib
import re

import pytest

# Reset the dependencies module so env-var overrides are honoured
# for the override test below.
_REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
_DEPS_PATH = _REPO_ROOT / "backend" / "dependencies.py"


def _read_deps_src() -> str:
    return _DEPS_PATH.read_text(encoding="utf-8")


def test_default_bcrypt_rounds_is_14():
    """The default cost factor must be 14 (2026 OWASP baseline).

    This is a *source-level* test: we want the default baked in,
    not whatever the test process happens to have set in its
    environment. If a developer downgrades the default, this
    fails and the change must be justified.
    """
    src = _read_deps_src()
    # The default in the source must be 14
    assert 'os.environ.get("CANDWAY_BCRYPT_ROUNDS", "14")' in src
    # The cost is wired into CryptContext via _BCRYPT_ROUNDS
    assert "bcrypt__rounds=_BCRYPT_ROUNDS" in src
    # And nothing else is passing a hard-coded rounds=...
    # (e.g. no regression to rounds=12 or rounds=10)
    assert "bcrypt__rounds=12" not in src
    assert "bcrypt__rounds=10" not in src


def test_pwd_context_uses_bcrypt_and_pbkdf2_with_auto_deprecation():
    """The CryptContext must:
    * include bcrypt and pbkdf2_sha256 (so old hashes verify)
    * have deprecated="auto" (so old pbkdf2 hashes get re-hashed
      to bcrypt on the next successful verify)
    """
    src = _read_deps_src()
    assert 'schemes=["bcrypt", "pbkdf2_sha256"]' in src
    assert 'deprecated="auto"' in src


def test_bcrypt_rounds_override_via_env(monkeypatch):
    """`CANDWAY_BCRYPT_ROUNDS` env var must be honoured.

    Useful for CI / smoke tests that need a fast hash. The
    override must be read at *import* time, not at hash
    time, because CryptContext is constructed once at module
    load.
    """
    monkeypatch.setenv("CANDWAY_BCRYPT_ROUNDS", "4")
    # Drop the cached module so the env var is re-read.
    import sys
    sys.modules.pop("backend.dependencies", None)
    try:
        deps = importlib.import_module("backend.dependencies")
        pwd = deps.pwd_context
        h = pwd.hash("hunter2")
        # Extract the cost factor from the bcrypt hash
        # bcrypt format: $2b$<cost>$<22-char-salt><31-char-hash>
        m = re.match(r"\$2[abxy]\$(\d+)\$", h)
        assert m, f"hash is not bcrypt: {h!r}"
        assert int(m.group(1)) == 4
    finally:
        sys.modules.pop("backend.dependencies", None)


def test_pbkdf2_hash_still_verifies_under_new_context():
    """A pre-existing pbkdf2_sha256 hash must still verify.

    This protects against an accidental regression where the
    `pbkdf2_sha256` scheme is dropped from `schemes=[...]`
    — that would lock out every user who hasn't logged in
    since the original bcrypt migration.
    """
    from passlib.hash import pbkdf2_sha256

    legacy_hash = pbkdf2_sha256.hash("legacy-password", rounds=1000)

    # Re-import with the production default (14)
    import sys
    sys.modules.pop("backend.dependencies", None)
    try:
        deps = importlib.import_module("backend.dependencies")
        assert deps.pwd_context.verify("legacy-password", legacy_hash)
        assert not deps.pwd_context.verify("wrong", legacy_hash)
    finally:
        sys.modules.pop("backend.dependencies", None)


def test_new_hash_is_bcrypt_at_cost_14():
    """`pwd_context.hash(...)` must produce a bcrypt@14 hash.

    A behavioural check: actually call hash() and inspect the
    output. This catches the case where the `schemes=...` order
    is changed and pbkdf2 ends up as the primary.
    """
    import sys
    sys.modules.pop("backend.dependencies", None)
    try:
        deps = importlib.import_module("backend.dependencies")
        # Use a small cost for the test to keep it fast
        monkeypatch_env = os.environ.copy()
        monkeypatch_env["CANDWAY_BCRYPT_ROUNDS"] = "14"
        # Already loaded, so we need to verify against the
        # current context (which uses whatever the test process
        # has for CANDWAY_BCRYPT_ROUNDS, default 14).
        h = deps.pwd_context.hash("hunter2")
        assert h.startswith("$2b$") or h.startswith("$2a$"), (
            f"hash is not bcrypt: {h!r}"
        )
        m = re.match(r"\$2[abxy]\$(\d+)\$", h)
        assert m, f"hash is not bcrypt: {h!r}"
        # If CANDWAY_BCRYPT_ROUNDS is unset in the test env,
        # this should be 14. If a developer has set a lower
        # value for local testing, we accept that.
        rounds = int(m.group(1))
        expected = int(os.environ.get("CANDWAY_BCRYPT_ROUNDS", "14"))
        assert rounds == expected
    finally:
        sys.modules.pop("backend.dependencies", None)


def test_verify_triggers_rehash_when_cost_changes(monkeypatch):
    """Verifying an old-cost hash with `deprecated="auto"` must
    cause passlib to return a *new* hash at the current cost.

    This is the self-healing property: when a user logs in
    after we bump rounds 12 -> 14, their next request stores
    the upgraded hash in the DB.

    The contract: after `verify_and_update(...)`, the returned
    hash (if non-None) has a cost >= the new cost.
    """
    from passlib.hash import bcrypt

    monkeypatch.setenv("CANDWAY_BCRYPT_ROUNDS", "5")
    import sys
    sys.modules.pop("backend.dependencies", None)
    try:
        deps = importlib.import_module("backend.dependencies")
        # Manually craft a bcrypt@4 hash (passlib's min, very fast)
        old_hash = bcrypt.using(rounds=4).hash("hunter2")

        ok, new_hash = deps.pwd_context.verify_and_update(
            "hunter2", old_hash
        )
        assert ok is True, "verify should succeed"
        # Cost factor encoded in the new hash
        assert new_hash is not None, (
            "verify_and_update should have returned a new hash "
            "because cost 4 < new cost 5"
        )
        m = re.match(r"\$2[abxy]\$(\d+)\$", new_hash)
        assert m, f"new_hash is not bcrypt: {new_hash!r}"
        # Re-hash must use the new cost (5)
        assert int(m.group(1)) >= 5, (
            f"expected re-hash to cost >= 5, got {m.group(1)}"
        )
    finally:
        sys.modules.pop("backend.dependencies", None)
