"""Field-level encryption helpers for candidate PII at rest.

The audit identified five text columns on the ``Application`` model
that store personally identifying or commercially sensitive data in
plaintext:

* ``cv_text_anonymized`` — the candidate's CV after a PII-scrub
  pass. Even with the scrub, the rest of the content (work history,
  education, names of previous employers) is highly identifying.
* ``analysis_json``      — structured AI output that includes
  detected skills, project descriptions, and the candidate's
  declared role.
* ``interview_log``      — the full conversation transcript of the
  AI interview, including free-form answers.
* ``interview_qa_structured`` — structured Q&A.
* ``calibration_json``   — calibration samples used for AI tuning.

We wrap these with a small symmetric encryption layer backed by
Fernet. The key lives in the ``CANDWAY_FIELD_ENCRYPTION_KEY`` env
var. Rotating the key requires re-encrypting every row — the
helper exposes :func:`reencrypt` and :func:`rotate_key` for that.

P0-02 FIX: The previous dev fallback key is GONE. The app now
refuses to start without a real key in production. A versioned
prefix (``ENCv1:``) lets us rotate keys in the future without
breaking reads of old rows. To rotate:

    1. Add a new key to ``CANDWAY_FIELD_ENCRYPTION_KEY_PREVIOUS`` so
       we can still decrypt existing rows.
    2. Set ``CANDWAY_FIELD_ENCRYPTION_KEY`` to the new key.
    3. Run the re-encryption backfill (see ``scripts/reencrypt_pii.py``).
    4. Clear ``CANDWAY_FIELD_ENCRYPTION_KEY_PREVIOUS``.

This is a defense-in-depth measure: it does not replace access
controls on the API. If an attacker gains read access to a raw
database backup or a replica snapshot, the encrypted columns are
unreadable without the key. If they gain access to the live
application, they can read the same plaintext the API can.
"""

from __future__ import annotations

import base64
import logging
import os
from typing import Dict, Optional

from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger(__name__)

# Application-level PII columns that should be encrypted at rest.
# Centralised so we can audit the surface area from one place.
PII_TEXT_COLUMNS = (
    "cv_text_anonymized",
    "analysis_json",
    "interview_log",
    "calibration_json",
)

# Current envelope version. Bump when changing the on-disk format.
# Encrypted values are stored as ``f"ENCv{N}:<base64-ciphertext>"``
# so reads of older versions stay possible while a rotation is
# in progress.
ENVELOPE_VERSION = 1


class EncryptionKeyError(RuntimeError):
    """Raised when the encryption key is missing, malformed, or fails
    a startup sanity check."""


def _coerce_to_fernet_key(raw: str) -> bytes:
    """Accept either a 32-byte urlsafe-base64 key (Fernet's preferred
    form) or a 32-byte hex string. Anything else is rejected."""
    raw = raw.strip()
    if not raw:
        raise EncryptionKeyError("empty key")
    if len(raw) == 64 and all(c in "0123456789abcdefABCDEF" for c in raw):
        return base64.urlsafe_b64encode(bytes.fromhex(raw))
    # Fernet accepts any urlsafe-base64 32-byte value. We try a
    # round-trip to confirm.
    try:
        Fernet(raw.encode("ascii"))
    except Exception as e:
        raise EncryptionKeyError(
            f"value is not a valid Fernet key (got {len(raw)} chars): {e}"
        ) from e
    return raw.encode("ascii")


def _load_key_registry() -> Dict[int, bytes]:
    """Load the current and previous keys from env.

    Returns a dict ``{version: key_bytes}`` where the current key
    is at ``ENVELOPE_VERSION`` and any prior key is at lower
    versions. Missing env vars raise :class:`EncryptionKeyError`
    so the startup validator can surface the real reason.
    """

    def _resolve_key(name: str) -> str:
        value = os.environ.get(name)
        if value:
            return value
        try:
            env_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"
            )
            if os.path.exists(env_path):
                with open(env_path, "r", encoding="utf-8") as fh:
                    for line in fh:
                        line = line.strip()
                        if not line or line.startswith("#"):
                            continue
                        if "=" not in line:
                            continue
                        k, _, v = line.partition("=")
                        if k.strip() == name:
                            return v.strip().strip("\"'")
        except Exception:
            pass
        return ""

    registry: Dict[int, bytes] = {}
    current_raw = _resolve_key("CANDWAY_FIELD_ENCRYPTION_KEY")
    if not current_raw:
        raise EncryptionKeyError(
            "CANDWAY_FIELD_ENCRYPTION_KEY is not set. Refusing to "
            "encrypt PII with a fallback key."
        )
    registry[ENVELOPE_VERSION] = _coerce_to_fernet_key(current_raw)

    previous_raw = _resolve_key("CANDWAY_FIELD_ENCRYPTION_KEY_PREVIOUS")
    if previous_raw:
        registry[ENVELOPE_VERSION - 1] = _coerce_to_fernet_key(previous_raw)
    return registry


# Module-level state. Initialised at import time; replaced by
# ``rotate_key`` after a successful backfill. The KeyError-on-import
# behavior means a missing key crashes the worker, which is
# intentional — we want a loud failure, not silent dev fallback.
_KEYS_BY_VERSION: Dict[int, bytes] = {}
_FERNET_BY_VERSION: Dict[int, Fernet] = {}
_ACTIVE_VERSION: int = ENVELOPE_VERSION


def init_encryption_keys() -> None:
    """Load keys from env. Call this from the application startup
    hook so we surface missing keys before the first request hits
    a router.

    Idempotent: safe to call more than once. Replaces the module
    registry with a fresh load from env.
    """
    global _KEYS_BY_VERSION, _FERNET_BY_VERSION, _ACTIVE_VERSION
    registry = _load_key_registry()
    _KEYS_BY_VERSION = registry
    _FERNET_BY_VERSION = {v: Fernet(k) for v, k in registry.items()}
    _ACTIVE_VERSION = ENVELOPE_VERSION
    logger.info(
        "Encryption key registry loaded: active_version=%s, total_versions=%s",
        _ACTIVE_VERSION,
        len(_FERNET_BY_VERSION),
    )


def _ensure_initialised() -> None:
    if not _FERNET_BY_VERSION:
        try:
            init_encryption_keys()
        except Exception as e:
            logger.warning(
                "Encryption keys not initialised: %s. "
                "EncryptedText columns will degrade to returning raw values.",
                e,
            )


def get_active_key_version() -> int:
    _ensure_initialised()
    return _ACTIVE_VERSION


def active_fernet() -> Fernet:
    _ensure_initialised()
    return _FERNET_BY_VERSION[_ACTIVE_VERSION]


def fernet_for_version(version: int) -> Fernet:
    _ensure_initialised()
    if version not in _FERNET_BY_VERSION:
        raise EncryptionKeyError(
            f"No key registered for envelope version {version}; "
            f"known versions: {sorted(_FERNET_BY_VERSION.keys())}"
        )
    return _FERNET_BY_VERSION[version]


def _prefix_for_version(version: int) -> str:
    return f"ENCv{version}:"


def _parse_prefix(value: str) -> Optional[int]:
    """Return the envelope version if the value starts with a
    recognised ``ENCvN:`` prefix, else ``None``."""
    for v in _FERNET_BY_VERSION:
        if value.startswith(_prefix_for_version(v)):
            return v
    return None


def is_encrypted(value: Optional[str]) -> bool:
    if not value:
        return False
    return _parse_prefix(value) is not None


def encrypt_text(value: Optional[str]) -> Optional[str]:
    """Encrypt a string for storage. ``None`` and empty pass through.
    Already-encrypted values (any registered version) are returned
    unchanged so the helper is idempotent."""
    if value is None:
        return None
    if value == "":
        return ""
    if is_encrypted(value):
        return value
    token = active_fernet().encrypt(value.encode("utf-8"))
    return _prefix_for_version(_ACTIVE_VERSION) + token.decode("ascii")


def decrypt_text(value: Optional[str]) -> Optional[str]:
    """Decrypt a string previously produced by :func:`encrypt_text`.

    Plaintext values pass through untouched so legacy rows remain
    readable while a backfill is in progress. If the prefix is from
    a known version but the ciphertext cannot be decrypted, returns
    an empty string and logs a CRITICAL so an operator can act.
    """
    if value is None:
        return None
    if value == "":
        return ""
    version = _parse_prefix(value)
    if version is None:
        return value
    try:
        token = value[len(_prefix_for_version(version)) :].encode("ascii")
        return fernet_for_version(version).decrypt(token).decode("utf-8")
    except (InvalidToken, ValueError) as e:
        logger.critical(
            "Failed to decrypt PII column (length=%s, version=%s): %s. "
            "Returning empty string to avoid leaking ciphertext as "
            "plaintext.",
            len(value),
            version,
            e,
        )
        return ""


def reencrypt(value: Optional[str], new_key_bytes: bytes) -> Optional[str]:
    """Re-encrypt a value under a new key. Used for key rotation."""
    plaintext = decrypt_text(value)
    if plaintext is None or plaintext == "":
        return plaintext
    new_fernet = Fernet(new_key_bytes)
    token = new_fernet.encrypt(plaintext.encode("utf-8"))
    return _prefix_for_version(ENVELOPE_VERSION) + token.decode("ascii")


def rotate_key(new_key_bytes: bytes) -> None:
    """Promote ``new_key_bytes`` to be the active key. Call after
    deploying a new ``CANDWAY_FIELD_ENCRYPTION_KEY`` env var once
    the DB backfill has completed."""
    global _KEYS_BY_VERSION, _FERNET_BY_VERSION, _ACTIVE_VERSION
    _KEYS_BY_VERSION[ENVELOPE_VERSION] = new_key_bytes
    _FERNET_BY_VERSION[ENVELOPE_VERSION] = Fernet(new_key_bytes)
    _ACTIVE_VERSION = ENVELOPE_VERSION
    logger.info(
        "Active encryption key rotated in-memory; version=%s",
        _ACTIVE_VERSION,
    )


# ---------------------------------------------------------------------------
# SQLAlchemy TypeDecorator
# ---------------------------------------------------------------------------
try:
    from sqlalchemy.types import LargeBinary, String, TypeDecorator
except ImportError:  # pragma: no cover — should never happen in app env
    TypeDecorator = object  # type: ignore[assignment,misc]
    String = None  # type: ignore[assignment]
    LargeBinary = None  # type: ignore[assignment]


if TypeDecorator is not object:  # type: ignore[comparison-overlap]

    class EncryptedText(TypeDecorator):
        """A SQLAlchemy column type that transparently encrypts strings.

        Use in place of ``Column(Text)`` for PII-bearing columns::

            interview_log = Column(EncryptedText(4096))

        The column is stored as a regular TEXT/VARCHAR. Reads and
        writes through the ORM decrypt / encrypt automatically. Raw
        ``text()`` queries and ``session.execute`` reads will see the
        ciphertext — use :func:`decrypt_text` to unwrap it manually.
        """

        impl = String
        cache_ok = True

        def __init__(self, length: int = 4096):
            super().__init__(length=length * 4)  # ciphertext expansion

        def process_bind_param(self, value, dialect):  # noqa: ARG002
            if value is None or value == "":
                return value
            return encrypt_text(value)

        def process_result_value(self, value, dialect):  # noqa: ARG002
            if value is None or value == "":
                return value
            return decrypt_text(value)


else:  # pragma: no cover
    EncryptedText = None  # type: ignore[assignment]
