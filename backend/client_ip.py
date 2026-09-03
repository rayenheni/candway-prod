"""Trusted client-IP extraction.

The app sits behind nginx (the edge proxy in docker-compose). A client can
send an arbitrary ``X-Forwarded-For`` header, so we must NEVER trust the
*first* value for rate limiting, audit, or lockout decisions — the first
entry is client-controlled and trivially spoofable.

nginx ``$proxy_add_x_forwarded_for`` *appends* the real peer IP after any
client-supplied values, so the *rightmost* non-empty entry is the value
written by our trusted proxy and is the real client IP.

Deployment contract (must hold for the default ``CANDWAY_TRUST_XFF=1``):
  * All inbound traffic goes through nginx (no direct app exposure).
  * nginx forwards ``$proxy_add_x_forwarded_for`` unchanged.

Operators that cannot guarantee this (e.g. the app is directly reachable)
MUST set ``CANDWAY_TRUST_XFF=0``, which ignores the header entirely and
uses the transport-level peer.
"""

import os



def get_client_ip(
    forwarded_for: str | None,
    client_host: str | None,
    *,
    trust_xff: bool | None = None,
) -> str:
    """Return the real client IP for a request.

    Args:
        forwarded_for: raw ``X-Forwarded-For`` header value (or None).
        client_host: ``request.client.host`` (transport-level peer).
        trust_xff: override for ``CANDWAY_TRUST_XFF`` (tests use this).

    Returns:
        The real client IP string, or ``"unknown"`` as a last resort.
    """
    trust = (os.getenv("CANDWAY_TRUST_XFF", "1") == "1") if trust_xff is None else trust_xff

    if trust and forwarded_for:
        entries = [e.strip() for e in forwarded_for.split(",") if e.strip()]
        if entries:
            # Rightmost entry is appended by the trusted reverse proxy and
            # therefore reflects the real client, not a spoofed header.
            return entries[-1]

    if client_host:
        return client_host

    return "unknown"
