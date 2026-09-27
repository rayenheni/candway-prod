"""Regression tests for backend.logger.PIIFilter.

The filter used to ``str()`` every log argument before interpolation, which
broke all numeric formats (``%d``, ``%.2f``) — Python's logging then printed
"--- Logging error ---" and dropped the record.
"""

import logging

from backend.logger import PIIFilter


def _record(msg, *args):
    return logging.LogRecord("t", logging.INFO, __file__, 1, msg, args, None)


def test_numeric_formats_survive_masking():
    rec = _record("score=%d ratio=%.2f focus=%s", 42, 0.5, "Problem Solving")
    assert PIIFilter().filter(rec) is True
    assert rec.getMessage() == "score=42 ratio=0.50 focus=Problem Solving"


def test_pii_in_args_is_masked_after_interpolation():
    rec = _record("login for %s", "jane.doe@example.com")
    PIIFilter().filter(rec)
    assert rec.getMessage() == "login for [EMAIL]"


def test_non_string_message_does_not_raise():
    rec = _record(ValueError("contact jane.doe@example.com"))
    PIIFilter().filter(rec)
    assert rec.getMessage() == "contact [EMAIL]"


def test_filter_is_idempotent_across_handlers():
    # The same record passes through several handlers' filters.
    rec = _record("n=%d email=%s", 7, "a@b.io")
    PIIFilter().filter(rec)
    PIIFilter().filter(rec)
    assert rec.getMessage() == "n=7 email=[EMAIL]"


def test_malformed_args_are_kept_not_dropped():
    rec = _record("value=%d", "not-a-number")
    PIIFilter().filter(rec)
    assert "value=%d" in rec.getMessage()
    assert "not-a-number" in rec.getMessage()


# --- phone masking ---------------------------------------------------------
# The old catch-all phone pattern matched any 4+ digit run, so ports, line
# numbers, durations and timestamps all became "[PHONE]" in production logs.

import pytest  # noqa: E402

from backend.logger import _mask_pii  # noqa: E402


@pytest.mark.parametrize(
    "text",
    [
        "call +216 98 123 456 now",
        "call 0021698123456 now",
        "call +21698123456 now",
        "call 98 123 456 now",
        "call 98-123-456 now",
        "call (555) 555-0100 now",
        "call 555-555-0100 now",
        "call +1 555 555 0100 now",
    ],
)
def test_real_phone_numbers_are_masked(text):
    masked = _mask_pii(text)
    assert "[PHONE]" in masked, masked
    assert masked.startswith("call ") and masked.endswith(" now")


@pytest.mark.parametrize(
    "text",
    [
        "connect localhost:6379 failed",
        'File "x.py", line 1165, in run',
        "took 1234 ms",
        "2026-09-26 15:36:12,980 WARNING started",
        "peer 127.0.0.1 port 8000",
        "app_id=4521 score=87.5",
        "version 3.11.2",
    ],
)
def test_technical_numbers_are_not_masked_as_phones(text):
    assert "[PHONE]" not in _mask_pii(text)


# --- Sentry scrubbing ------------------------------------------------------

from backend.logger import scrub_sentry_breadcrumb, scrub_sentry_event  # noqa: E402


def test_sentry_event_free_text_is_scrubbed_structure_kept():
    event = {
        "event_id": "abc123",
        "level": "error",
        "logentry": {"message": "login failed for jane@x.io", "params": []},
        "exception": {
            "values": [
                {
                    "type": "ValueError",
                    "value": "bad phone +216 98 123 456",
                    "stacktrace": {
                        "frames": [
                            {
                                "filename": "backend/auth.py",
                                "lineno": 12345678,
                                "function": "login",
                                "vars": {"email": "'jane@x.io'", "attempt": 3},
                            }
                        ]
                    },
                }
            ]
        },
        "breadcrumbs": {"values": [{"message": "user bob@y.tn clicked"}]},
        "request": {"data": {"email": "bob@y.tn"}, "url": "https://candway.tn/x"},
    }
    out = scrub_sentry_event(event, None)
    flat = repr(out)
    assert "jane@x.io" not in flat and "bob@y.tn" not in flat
    assert "98 123 456" not in flat
    frame = out["exception"]["values"][0]["stacktrace"]["frames"][0]
    assert frame["filename"] == "backend/auth.py"
    assert frame["lineno"] == 12345678
    assert frame["vars"]["attempt"] == 3
    assert out["exception"]["values"][0]["type"] == "ValueError"
    assert out["event_id"] == "abc123"


def test_sentry_breadcrumb_is_scrubbed():
    crumb = {"category": "log", "message": "sent to a@b.io", "data": {"to": "a@b.io"}}
    assert "a@b.io" not in repr(scrub_sentry_breadcrumb(crumb, None))
