import os
from functools import lru_cache
from typing import Optional
from urllib.parse import urlparse

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_FILES = (
    os.path.join(PROJECT_ROOT, ".env"),
    os.path.join(PROJECT_ROOT, "backend", ".env"),
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ENV_FILES,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Candway Intelligence"

    # Security: JWT Settings
    secret_key: Optional[str] = None
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    # Dedicated keys per security context (prevent cross-context key compromise)
    # Production MUST set unique values for each. Dev falls back to secret_key.
    jwt_secret_key: Optional[str] = None
    csrf_secret_key: Optional[str] = None
    webhook_signing_secret: Optional[str] = None
    interview_hmac_key: Optional[str] = None
    signed_url_secret: Optional[str] = None
    desktop_license_secret: Optional[str] = None
    field_encryption_key: Optional[str] = None

    # Database pool settings
    db_pool_size: int = 10
    db_max_overflow: int = 20
    db_pool_timeout: int = 10
    db_pool_recycle: int = 1800

    # Cors

    # Database — must be overridden via env; default will fail in production
    database_url: str = ""

    # API Keys
    openai_api_key: Optional[str] = None
    groq_api_key: Optional[str] = None
    groq_api_url: str = "https://api.groq.com/openai/v1/chat/completions"
    deepseek_api_key: Optional[str] = None
    gemini_api_key: Optional[str] = None
    debug: bool = False
    redis_url: str = "redis://localhost:6379/0"

    # SMTP / Email — used by email_service as a fallback when the
    # SystemConfig table has no smtp_* rows (see get_smtp_config).
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from: str = ""

    # Google OAuth
    google_client_id: Optional[str] = None
    google_client_secret: Optional[str] = None
    google_redirect_uri: str = ""

    # App URLs
    base_url: str = "http://localhost:8002"
    frontend_url: str = "http://localhost:8002"

    # Operational
    environment: str = "dev"
    sentry_dsn: Optional[str] = None

    # Security
    allowed_origins: str | list = ""
    allowed_hosts: str | list = ""
    enable_registration: bool = True

    # AI PII handling — PII masking is unconditional and always enforced.
    # See backend/ai/security.py (PIIMasker) for the implementation.
    # There is no toggle. Raw PII never leaves the platform.

    # Checkr Background Check Integration
    checkr_api_key: str = ""
    checkr_webhook_secret: str = ""

    # Runtime Limits
    rate_limit_enabled: bool = True
    rate_limit_per_minute: int = 60
    rate_limit_per_hour: int = 1000
    max_upload_size: int = 10 * 1024 * 1024

    @field_validator("debug", mode="before")
    @classmethod
    def normalize_debug(cls, value):
        if isinstance(value, bool):
            return value
        if value is None:
            return False

        raw = str(value).strip().lower()
        if raw in {"1", "true", "yes", "on", "debug"}:
            return True
        if raw in {"0", "false", "no", "off", "release", "prod", "production", ""}:
            return False
        return False

    @property
    def is_prod(self):
        return str(self.environment).strip().lower() in {"prod", "production"}

    @property
    def allowed_origins_list(self) -> list[str]:
        if isinstance(self.allowed_origins, list):
            return [str(o).strip() for o in self.allowed_origins if str(o).strip()]
        if isinstance(self.allowed_origins, str):
            raw = self.allowed_origins.strip()
            if not raw or raw == "*":
                return []
            return [o.strip() for o in raw.split(",") if o.strip()]
        return []

    @property
    def allowed_hosts_list(self) -> list[str]:
        if isinstance(self.allowed_hosts, list):
            raw_hosts = [str(h).strip() for h in self.allowed_hosts if str(h).strip()]
        elif isinstance(self.allowed_hosts, str):
            raw_hosts = [h.strip() for h in self.allowed_hosts.split(",") if h.strip()]
        else:
            raw_hosts = []

        if raw_hosts:
            return raw_hosts

        hosts = []
        for origin in self.allowed_origins_list:
            hostname = urlparse(origin).hostname
            if hostname:
                hosts.append(hostname)
        # preserve order while removing duplicates
        return list(dict.fromkeys(hosts))

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if self.is_prod and not self.secret_key:
            raise ValueError(
                "CRITICAL: SECRET_KEY must be set in production environment."
            )

        # SECURITY: In production, every security key must have its own unique value.
        # This prevents cross-context key compromise (JWT, CSRF, webhooks, etc.).
        _dedicated_keys = {
            "JWT_SECRET_KEY": self.jwt_secret_key,
            "CSRF_SECRET_KEY": self.csrf_secret_key,
            "WEBHOOK_SIGNING_SECRET": self.webhook_signing_secret,
            "INTERVIEW_HMAC_KEY": self.interview_hmac_key,
            "SIGNED_URL_SECRET": self.signed_url_secret,
            "DESKTOP_LICENSE_SECRET": self.desktop_license_secret,
            "FIELD_ENCRYPTION_KEY": self.field_encryption_key,
        }
        if self.is_prod:
            for key_name, key_value in _dedicated_keys.items():
                if not key_value:
                    raise ValueError(
                        f"CRITICAL: {key_name} must be set in production environment. "
                        f"Each security context requires its own unique key."
                    )
                if key_value == self.secret_key:
                    import logging as _l

                    _l.getLogger("candway_app").warning(
                        f"WARNING: {key_name} is identical to SECRET_KEY in production. "
                        f"This defeats cross-context key separation."
                    )

        if self.is_prod and self.debug:
            raise ValueError("CRITICAL: DEBUG must be false in production environment.")
        if self.is_prod and not self.allowed_origins_list:
            raise ValueError(
                "CRITICAL: ALLOWED_ORIGINS must be explicitly set in production."
            )
        if self.is_prod and not self.allowed_hosts_list:
            raise ValueError(
                "CRITICAL: ALLOWED_HOSTS (or derivable hosts from ALLOWED_ORIGINS) must be set in production."
            )
        if self.is_prod:
            from urllib.parse import urlparse as _urlparse

            _parsed = _urlparse(self.database_url)
            _db_user = _parsed.username or ""
            if _db_user == "root":
                raise ValueError(
                    "CRITICAL: DATABASE_URL uses 'root' database user in production. "
                    "Create a dedicated MySQL user with least privilege. "
                    "Example: CREATE USER 'candway_app'@'%' IDENTIFIED BY '<password>';"
                )
            if (
                "://root:@" in self.database_url
                or "://root:password@" in self.database_url
                or "YOUR_STRONG_PASSWORD" in self.database_url
            ):
                raise ValueError(
                    "CRITICAL: DATABASE_URL uses root or insecure/default credentials in production. "
                    "Create a dedicated MySQL user with least privilege."
                )

        # Validate AI API keys — reject placeholders in ALL environments.
        _PLACEHOLDER_PATTERNS = [
            "your_new_",
            "your_key_here",
            "sk-your",
            "gsk_your",
            "AIzaSy_your",
            "_here",
            "placeholder",
            "changeme",
            "replace_me",
        ]

        def _is_placeholder(key: str) -> bool:
            if not key:
                return False
            return any(p in key.lower() for p in _PLACEHOLDER_PATTERNS)

        import logging as _logging

        _log = _logging.getLogger("candway_app")

        _AI_KEYS = [
            ("GROQ_API_KEY", self.groq_api_key),
            ("DEEPSEEK_API_KEY", self.deepseek_api_key),
            ("GEMINI_API_KEY", self.gemini_api_key),
        ]

        for _key_name, _key_value in _AI_KEYS:
            if _key_value and _is_placeholder(_key_value):
                msg = f"FATAL: {_key_name} contains a placeholder value. Set a real API key in .env before starting the server."
                if self.is_prod:
                    raise ValueError(msg)
                else:
                    _log.warning(f"WARNING: {msg}")

        # Warn (don't crash) if primary AI key is simply missing in dev.
        if not self.groq_api_key and not self.is_prod:
            _log.warning(
                "WARNING: GROQ_API_KEY is not set. AI interview features will use fallback providers only."
            )

        if not self.secret_key:
            # SECURITY FIX: Always require explicit SECRET_KEY - never generate ephemeral keys
            # Ephemeral keys invalidate all sessions on restart and are a security risk
            if self.is_prod:
                raise ValueError(
                    "CRITICAL: SECRET_KEY must be set in production environment."
                )
            else:
                # In development, still require explicit key to enforce good practices
                # and prevent accidental deployment without proper configuration
                raise ValueError(
                    "SECURITY CRITICAL: SECRET_KEY is not set in .env! "
                    "Please set a secure SECRET_KEY in your .env file. "
                    "You can generate one with: python -c 'import secrets; print(secrets.token_urlsafe(32))'"
                )


@lru_cache()
def get_settings():
    return Settings()
