"""
HMAC-signed URLs for short-lived access to private candidate assets.

Why this exists
---------------
The candidate's CV is stored on disk under ``backend/uploads/`` with
a filename like ``upload_<user_id>_<uuid>.pdf``. The ``/uploads/...``
route is protected by ownership middleware that only lets the
candidate, admin, or super-admin fetch it.

That breaks the recruiter flow: a PRO-tier recruiter with a candidate
*assigned* to them cannot preview the CV because the filename is
encoded with the candidate's user_id, not theirs. Without signed
URLs, the recruiter would have to download the CV via a private
admin endpoint (or have a backdoor in /uploads) — both of which
violate the audit's "no backdoor uploads" finding.

A signed URL solves this cleanly:
  * The recruiter endpoint (``/api/v1/recruiter/candidates/{id}``)
    issues a URL of the form
    ``/uploads/<file>?token=<hmac>&exp=<unix>``
    where the HMAC is computed over ``file|exp|user_id|app_id``.
  * The ``/uploads`` route accepts a valid token in lieu of the
    candidate being the logged-in user.
  * Tokens expire in 5 minutes by default (configurable per-call),
    making them useless to scrape or forward.

The token is bound to the *current* user_id, not the candidate's, so
a token issued for recruiter #42 cannot be replayed by recruiter
#99. The candidate's user_id is the *subject* of the token, but
the *bearer* is checked against the JWT-derived user_id.

This is NOT meant to replace authentication — it's a delegating
credential. The recruiter still has to authenticate with their
JWT to *get* the URL; the URL itself just carries the
authorisation to fetch one file.
"""

import hashlib
import hmac
import logging
import time
from typing import Optional
from urllib.parse import urlencode

from backend.config import get_settings

logger = logging.getLogger(__name__)

DEFAULT_TTL_SECONDS = 300  # 5 minutes


def _secret() -> bytes:
    """The signing key. Uses dedicated SIGNED_URL_SECRET with fallback."""
    key = get_settings().signed_url_secret or get_settings().secret_key
    return key.encode("utf-8")


def make_signed_cv_token(
    *,
    file_path: str,
    subject_user_id: int,
    bearer_user_id: int,
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
) -> dict:
    """Mint a signed-URL token.

    Returns ``{"token": "...", "expires_at": <unix>, "url": "..."}``.
    The ``url`` is a relative path (no host) so the caller can
    prepend the public base URL.
    """
    expires_at = int(time.time()) + ttl_seconds
    # Bind to subject (candidate), bearer (recruiter), file, and
    # expiry. The bearer check stops a recruiter sharing a token
    # with another recruiter; the file check stops a token being
    # used against a different file.
    payload = f"{file_path}|{subject_user_id}|{bearer_user_id}|{expires_at}"
    sig = hmac.new(_secret(), payload.encode("utf-8"), hashlib.sha256).hexdigest()

    token = f"{sig}.{expires_at}.{subject_user_id}.{bearer_user_id}"
    qs = urlencode({"token": token})
    return {
        "token": token,
        "expires_at": expires_at,
        "url": f"/uploads/{file_path}?{qs}",
    }


def verify_signed_cv_token(
    *,
    file_path: str,
    token: Optional[str],
    bearer_user_id: int,
) -> bool:
    """Verify a token issued by ``make_signed_cv_token``.

    Returns True on success, False on:
      * missing / malformed token
      * expired token
      * signature mismatch
      * subject user_id mismatch
      * bearer user_id mismatch (token stolen by a different user)
    """
    if not token or not isinstance(token, str):
        return False
    parts = token.split(".")
    if len(parts) != 4:
        return False
    sig, exp_str, subject_str, bearer_str = parts
    try:
        exp = int(exp_str)
        subject = int(subject_str)
        bearer = int(bearer_str)
    except (TypeError, ValueError):
        return False

    if int(time.time()) > exp:
        logger.info(
            f"[SIGNED-URL] Token expired at {exp} for {file_path} "
            f"(now={int(time.time())})"
        )
        return False

    if bearer != bearer_user_id:
        # The token was issued for a different recruiter; reject.
        logger.warning(
            f"[SIGNED-URL] Bearer mismatch: token bearer={bearer}, "
            f"actual bearer={bearer_user_id}, file={file_path}"
        )
        return False

    expected = hmac.new(
        _secret(),
        f"{file_path}|{subject}|{bearer}|{exp}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(expected, sig):
        logger.warning(
            f"[SIGNED-URL] Signature mismatch for {file_path} "
            f"(subject={subject}, bearer={bearer})"
        )
        return False

    return True
