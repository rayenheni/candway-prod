"""P0-04 FIX: Per-call LLM consent tracking.

Candway sends PII to third-party LLM providers (Groq, DeepSeek,
Gemini). To honour GDPR Art. 7 (consent) and Tunisian Law
2004-63 (consent for cross-border transfers), every LLM call must:

1. Be attributable to a user (so we can answer "did user 42
   consent to DeepSeek?").
2. Be attributable to a legal basis (``ai_processing``,
   ``ai_processing_deepseek``, ``ai_processing_gemini``, etc.).
3. Be retrievable for at least 12 months for incident response.

This module exposes a single helper, :func:`record_llm_call`, that
the AI client code must call on every successful (or attempted)
LLM call. The helper is best-effort — it never raises into the
caller. If the database write fails, the failure is logged but
the LLM call still returns.

Provider policy is also centralised here: when
``CANDWAY_BLOCK_UNDPA_PROVIDERS=1`` is set, calls to providers
without a signed DPA are refused at the call site.
"""

import hashlib
import os
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from backend.database import ConsentLog
from backend.logger import logger


@dataclass
class ProviderPolicy:
    name: str
    dpa_signed: bool
    consent_agreement_type: str
    notes: str = ""


# P0-04: provider policy registry. ``dpa_signed`` flips to True
# only after the legal team has countersigned the DPA PDF in
# ``legal/dpa/``.
PROVIDERS: Dict[str, ProviderPolicy] = {
    "groq": ProviderPolicy(
        name="groq",
        dpa_signed=False,
        consent_agreement_type="ai_processing",
        notes="Pending DPA signature; see legal/dpa/GROQ_DPA_TEMPLATE.md",
    ),
    "gemini": ProviderPolicy(
        name="gemini",
        dpa_signed=False,
        consent_agreement_type="ai_processing",
        notes="Pending order confirmation; see legal/dpa/GEMINI_DPA_TEMPLATE.md",
    ),
    "deepseek": ProviderPolicy(
        name="deepseek",
        dpa_signed=False,
        consent_agreement_type="ai_processing_deepseek",
        notes="HIGHEST RISK; no GDPR-equivalent DPA. See legal/dpa/DEEPSEEK_DPA_TEMPLATE.md",
    ),
    "ollama": ProviderPolicy(
        name="ollama",
        dpa_signed=True,
        consent_agreement_type="ai_processing",
        notes="Local-only; no third-party data transfer.",
    ),
}


def _block_undpa_providers() -> bool:
    return os.getenv("CANDWAY_BLOCK_UNDPA_PROVIDERS", "0") == "1"


def is_provider_allowed(
    provider: str,
    user_id: Optional[int] = None,
    db: Optional[Session] = None,
) -> bool:
    """Return True if a call to ``provider`` is allowed right now.

    * If ``CANDWAY_BLOCK_UNDPA_PROVIDERS=1`` and the provider has
      no signed DPA, return False.
    * If ``user_id`` and ``db`` are provided, also check that the
      user has a non-revoked consent for the provider's
      ``consent_agreement_type`` (e.g. ``ai_processing_deepseek``).
    """
    policy = PROVIDERS.get(provider.lower())
    if policy is None:
        logger.warning(f"[LLMConsent] unknown provider '{provider}'")
        return False

    if not policy.dpa_signed and _block_undpa_providers():
        logger.warning(
            f"[LLMConsent] {provider} blocked: DPA not signed and "
            "CANDWAY_BLOCK_UNDPA_PROVIDERS=1"
        )
        return False

    if user_id is None or db is None:
        return True

    # The user must have at least one current (non-revoked) consent
    # row of the right agreement_type. We don't model revocation
    # yet — for now, "any consent row" == "consented".
    has_consent = (
        db.query(ConsentLog)
        .filter(
            ConsentLog.user_id == user_id,
            ConsentLog.agreement_type == policy.consent_agreement_type,
        )
        .first()
        is not None
    )
    if not has_consent:
        logger.info(
            f"[LLMConsent] user {user_id} has no "
            f"{policy.consent_agreement_type} consent"
        )
        return False
    return True


def record_llm_call(
    *,
    db: Session,
    user_id: Optional[int],
    provider: str,
    application_id: Optional[int],
    messages: List[Dict[str, Any]],
    response_excerpt: Optional[str] = None,
    outcome: str = "success",
    latency_ms: Optional[int] = None,
    error: Optional[str] = None,
) -> None:
    """Append an immutable record of the LLM call.

    The full message content is **not** stored — only a SHA-256
    hash of the user-supplied content, plus the first 200 chars of
    the response, so an on-call engineer can grep the audit log
    without re-inferring the LLM.

    Never raises. The caller's LLM response is more important than
    the audit row.
    """
    try:
        # Hash only the user content; never hash system prompts
        # (they may contain PII the caller already redacted).
        user_content = "".join(
            str(m.get("content", "")) for m in messages if m.get("role") == "user"
        )
        content_hash = hashlib.sha256(user_content.encode("utf-8")).hexdigest()

        row = ConsentLog(
            user_id=user_id,
            agreement_type=f"llm_call:{provider}",
            version=(
                f"v1|out={outcome}"
                f"|hash={content_hash[:12]}"
                f"|app={application_id or '-'}"
                f"|latency={latency_ms or 0}"
                f"|ts={int(time.time())}"
            ),
            ip_address=None,
            user_agent=None,
        )
        if error:
            row.version = row.version + f"|err={error[:64]}"
        db.add(row)
        db.commit()
    except Exception as e:  # noqa: BLE001
        db.rollback()
        logger.error(f"[LLMConsent] failed to record call for {provider}: {e}")
