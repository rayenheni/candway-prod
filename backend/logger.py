import contextvars
import json
import logging
import os
import re
import sys
import traceback
from logging.handlers import RotatingFileHandler

from backend.config import get_settings

request_id_var = contextvars.ContextVar("request_id", default=None)

settings = get_settings()

# Configurable log directory (default: current dir for dev, override in production)
LOG_DIR = os.environ.get("LOG_DIR", ".")
os.makedirs(LOG_DIR, exist_ok=True)

# PII masking patterns for logs
PII_PATTERNS = [
    # Email addresses
    (re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"), "[EMAIL]"),
    # Phone numbers. Deliberately strict: the previous catch-all pattern
    # matched any 4+ digit run (ports, line numbers, durations, IDs, dates),
    # which destroyed debugging information in every log line.
    # 1) International, explicit + or 00 prefix: +216 98 123 456, 0021698123456
    (
        re.compile(r"(?<![\w+])(?:\+|00)\d{1,3}(?:[\s.-]?\(?\d\)?){7,12}(?![\w])"),
        "[PHONE]",
    ),
    # 2) Tunisian local, grouped 2-3-3: 98 123 456, 98-123-456
    (
        re.compile(r"(?<![\w.:-])\d{2}[\s-]\d{3}[\s-]\d{3}(?![\w.:-])"),
        "[PHONE]",
    ),
    # 3) North-American style: (555) 555-0100, 555-555-0100
    (
        re.compile(
            r"(?<![\w.:-])(?:\(\d{3}\)\s?|\d{3}[\s.-])\d{3}[\s.-]\d{4}(?![\w.:-])"
        ),
        "[PHONE]",
    ),
    # JWT tokens (long base64 strings in Authorization headers)
    (
        re.compile(r"Bearer\s+[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+"),
        "Bearer [JWT]",
    ),
    # Passwords in JSON
    (re.compile(r'"password"\s*:\s*"[^"]*"'), '"password": "[REDACTED]"'),
    # API keys
    (
        re.compile(r'(api_key|apikey|secret|token)\s*[:=]\s*["\']?[A-Za-z0-9_-]{20,}'),
        "[API_KEY]",
    ),
    # Credit card numbers (basic pattern)
    (re.compile(r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b"), "[CC]"),
    # Tunisian CIN (8-digit national ID)
    (re.compile(r"\b\d{8}\b"), "[CIN]"),
    # Passport numbers
    (re.compile(r"\b[A-Z]{1,2}\d{6,7}\b"), "[PASSPORT]"),
    # Date of birth
    (
        re.compile(r"\b(0?[1-9]|[12]\d|3[01])[-/](0?[1-9]|1[0-2])[-/](19|20)\d{2}\b"),
        "[DOB]",
    ),
    # Social links
    (
        re.compile(r"(linkedin|facebook|twitter|x\.com|github|gitlab)\.com/\S+"),
        "[SOCIAL]",
    ),
    # PII audit placeholders (already masked, but ensure they are homogenized)
    (
        re.compile(
            r"\[(?:EMAIL|PHONE|CIN|PASSPORT|CARD|IBAN|DOB|SOCIAL|REFERENCE|ADDRESS|NAME|SSN)_[a-f0-9]+\]"
        ),
        "[PII]",
    ),
]


def _mask_pii(message: str) -> str:
    """Remove PII from log messages"""
    if not message:
        return message

    for pattern, replacement in PII_PATTERNS:
        message = pattern.sub(replacement, message)

    return message


# Sentry scrubbing. Sentry's LoggingIntegration captures records before any
# handler filter runs, so PIIFilter never sees them; mask events explicitly.
_SENTRY_STRUCTURAL_KEYS = frozenset(
    {
        "event_id",
        "timestamp",
        "level",
        "logger",
        "platform",
        "release",
        "environment",
        "server_name",
        "sdk",
        "type",
        "module",
        "function",
        "filename",
        "abs_path",
        "lineno",
        "colno",
        "in_app",
        "context_line",
        "pre_context",
        "post_context",
        "modules",
    }
)


def _scrub_value(value, key=None):
    if key in _SENTRY_STRUCTURAL_KEYS:
        return value
    if isinstance(value, str):
        return _mask_pii(value)
    if isinstance(value, dict):
        return {k: _scrub_value(v, k) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_scrub_value(v) for v in value]
    return value


def scrub_sentry_event(event, hint=None):
    """Sentry ``before_send``: mask PII in every free-text field of an event
    (messages, exception values, breadcrumbs, frame locals, request data)."""
    return _scrub_value(event)


def scrub_sentry_breadcrumb(crumb, hint=None):
    """Sentry ``before_breadcrumb``: same masking for breadcrumbs."""
    return _scrub_value(crumb)


# Custom filter to mask PII
class PIIFilter(logging.Filter):
    """Mask PII in the *rendered* log message.

    The message is interpolated first (``record.getMessage()``) and the final
    string is masked; ``args`` are then cleared. Masking each arg via
    ``str(arg)`` (the previous behaviour) broke every ``%d`` / ``%.2f``
    format in the codebase ("%d format: a real number is required, not str"),
    which made logging drop the record, and a non-string ``msg`` crashed the
    caller because handler filters run outside logging's error handling.
    """

    def filter(self, record):
        try:
            message = record.getMessage()
        except (TypeError, ValueError, KeyError):
            # Malformed format/args (e.g. "%d" with a str, unknown format
            # char, missing mapping key): keep the raw text instead of losing it.
            message = f"{record.msg} {record.args!r}" if record.args else record.msg
        record.msg = _mask_pii(str(message))
        record.args = None
        return True


class RequestIDFilter(logging.Filter):
    def filter(self, record):
        record.request_id = request_id_var.get()
        return True


class JSONFormatter(logging.Formatter):
    def format(self, record):
        log_entry = {
            "timestamp": self.formatTime(record, self.datefmt),
            "name": record.name,
            "level": record.levelname,
            "message": record.getMessage(),
        }
        if record.exc_info and record.exc_info[0]:
            log_entry["exception"] = traceback.format_exception(*record.exc_info)
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id
        for key, value in record.__dict__.items():
            if key not in (
                "args",
                "asctime",
                "created",
                "exc_info",
                "exc_text",
                "filename",
                "funcName",
                "levelname",
                "levelno",
                "lineno",
                "module",
                "msecs",
                "message",
                "msg",
                "name",
                "pathname",
                "process",
                "processName",
                "relativeCreated",
                "stack_info",
                "thread",
                "threadName",
                "request_id",
            ):
                log_entry[key] = value
        return json.dumps(log_entry, default=str)


# Create a custom logger
logger = logging.getLogger("candway_app")

# Set level based on debug flag
logger.setLevel(logging.DEBUG if settings.debug else logging.INFO)

# Create handlers (10MB max size, 5 backups)
c_handler = logging.StreamHandler(sys.stdout)
f_handler = RotatingFileHandler(
    os.path.join(LOG_DIR, "backend.log"),
    maxBytes=10 * 1024 * 1024,
    backupCount=5,
    encoding="utf-8",
)
s_handler = RotatingFileHandler(
    os.path.join(LOG_DIR, "security.log"),
    maxBytes=10 * 1024 * 1024,
    backupCount=5,
    encoding="utf-8",
)

c_handler.setLevel(logging.DEBUG if settings.debug else logging.INFO)
f_handler.setLevel(logging.DEBUG if settings.debug else logging.INFO)
s_handler.setLevel(logging.INFO)

# Add filters to all handlers
c_handler.addFilter(PIIFilter())
c_handler.addFilter(RequestIDFilter())
f_handler.addFilter(PIIFilter())
f_handler.addFilter(RequestIDFilter())
s_handler.addFilter(PIIFilter())
s_handler.addFilter(RequestIDFilter())

# Create JSON formatters and add to handlers
json_formatter = JSONFormatter()
c_handler.setFormatter(json_formatter)
f_handler.setFormatter(json_formatter)
s_handler.setFormatter(json_formatter)

# Add handlers to the logger
if not logger.handlers:
    logger.addHandler(c_handler)
    logger.addHandler(f_handler)

# Create a custom security logger
security_logger = logging.getLogger("candway_security")
security_logger.setLevel(logging.INFO)
if not security_logger.handlers:
    security_logger.addHandler(s_handler)
    # Also log to console for visibility
    security_logger.addHandler(c_handler)


def get_logger(name):
    return logging.getLogger(f"candway_app.{name}")
