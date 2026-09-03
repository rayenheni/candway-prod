import base64
from hashlib import sha256

from cryptography.fernet import Fernet

from backend.logger import logger

_SENSITIVE_KEYS = {
    "smtp_password",
    "groq_api_key",
    "deepseek_api_key",
    "gemini_api_key",
    "konnect_api_key",
    "google_client_secret",
}


def _resolve_encryption_key() -> str:
    """Resolve the encryption key: FIELD_ENCRYPTION_KEY > secret_key."""
    from backend.config import get_settings

    s = get_settings()
    return s.field_encryption_key or s.secret_key


def _derive_key(secret_key: str = None) -> bytes:
    if secret_key is None:
        secret_key = _resolve_encryption_key()
    raw = sha256(secret_key.encode()).digest()
    return base64.urlsafe_b64encode(raw)


def is_sensitive_key(key: str) -> bool:
    return key in _SENSITIVE_KEYS


def encrypt_value(plaintext: str, secret_key: str) -> str:
    if not plaintext:
        return ""
    try:
        f = Fernet(_derive_key(secret_key))
        return f.encrypt(plaintext.encode()).decode()
    except Exception as e:
        logger.error(f"Encryption failed: {e}")
        raise


def decrypt_value(ciphertext: str, secret_key: str) -> str:
    if not ciphertext:
        return ""
    try:
        f = Fernet(_derive_key(secret_key))
        return f.decrypt(ciphertext.encode()).decode()
    except Exception as e:
        logger.error(f"Decryption failed: {e}")
        return ""
