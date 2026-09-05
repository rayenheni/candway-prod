import asyncio
import json
import re
from contextvars import ContextVar
from datetime import datetime
from typing import Optional

import httpx

from backend.ai.cost_controller import (
    check_ai_budget,
    estimate_gemini_cost,
    estimate_groq_cost,
    record_ai_usage,
)

# P0-09 FIX: Import the per-provider breaker registry instead of the
# single shared one. Each provider call below now picks the breaker
# matching its own name so a Groq outage cannot block Gemini.
from backend.ai.resilience import get_breaker
from backend.ai.security import AISecurity, PIIMasker
from backend.ai.token_tracker import (
    count_tokens_in_messages,
    enforce_budget,
    get_model_context_window,
    truncate_messages_to_budget,
)
from backend.ai.validation import AIOutputValidator, AIValidationContext
from backend.config import get_settings
from backend.llm_cost import record_cost
from backend.logger import logger
from backend.rate_limiter import groq_rate_limiter

# Context variable for automatic company_id propagation through AI calls.
# Set at router level, read inside call_groq_cascade for security enforcement.
current_company_id_var: ContextVar[Optional[int]] = ContextVar(
    "current_company_id", default=None
)
current_user_id_var: ContextVar[Optional[int]] = ContextVar(
    "current_user_id", default=None
)
current_ip_var: ContextVar[Optional[str]] = ContextVar(
    "current_ip", default=None
)


def set_ai_company_id(company_id: Optional[int]) -> None:
    """Set company_id for AI security enforcement in the current request."""
    current_company_id_var.set(company_id)


def set_ai_security_context(
    company_id: Optional[int],
    user_id: Optional[int],
    ip: Optional[str],
) -> None:
    """Set request identity used by AI security controls."""
    current_company_id_var.set(company_id)
    current_user_id_var.set(user_id)
    current_ip_var.set(ip)


def get_ai_context_company_id() -> Optional[int]:
    return current_company_id_var.get()


def get_ai_context_user_id() -> Optional[int]:
    return current_user_id_var.get()


def get_ai_context_ip() -> Optional[str]:
    return current_ip_var.get()


class SecurityException(Exception):
    """Custom exception for security violations in AI calls"""

    pass


class OutputSizeExceededError(Exception):
    """Raised when AI response exceeds the maximum allowed size."""

    pass


# Maximum allowed response size in characters (~100KB text)
MAX_RESPONSE_SIZE = 100_000


def _validate_output_size(content: str) -> str:
    """Reject AI responses that exceed MAX_RESPONSE_SIZE to prevent
    denial-of-service through abnormally large LLM output."""
    if isinstance(content, str) and len(content) > MAX_RESPONSE_SIZE:
        raise OutputSizeExceededError(
            f"AI response too large ({len(content)} chars, max {MAX_RESPONSE_SIZE})"
        )
    return content


# Global persistent client for connection pooling
# Initialized lazily to ensure it's created in the correct event loop
_http_client: httpx.AsyncClient = None


def get_http_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(60.0, connect=10.0),
            limits=httpx.Limits(max_connections=100, max_keepalive_connections=50),
        )
    return _http_client


# --- MODEL CASCADE STRATEGY ---
# BUG-10 FIX: mixtral-8x7b-32768 was deprecated by Groq in Oct 2024.
# UPDATE Apr 2026: gemma2-9b-it is also now decommissioned.
# UPDATE Apr 2026: llama-3.1-70b-versatile is also now decommissioned.
# UPDATE Aug 2026: llama-3.3-70b-versatile + llama-3.1-8b-instant no longer available.
# Using models confirmed available on current Groq account (Aug 2026).
MODELS_CASCADE = [
    "groq/compound",  # Best Quality — routes to best available model, json_mode supported
    "openai/gpt-oss-20b",  # Fallback — reasoning model, json_mode supported
    "groq/compound-mini",  # Fast Fallback — lighter compound, json_mode supported
]

GEMINI_MODELS = ["gemini-3.6-flash", "gemini-2.0-flash", "gemini-1.5-flash"]

# --- SYSTEM CONFIG CACHE ---
# Uses Redis-backed shared cache across all workers.
# See backend/system_config_cache.py for implementation.


async def _get_cached_system_config() -> dict:
    """Return SystemConfig values from Redis-backed shared cache."""
    try:
        from backend.system_config_cache import get_system_config

        return await get_system_config()
    except Exception as e:
        logger.warning(f"[AI] SystemConfig cache refresh failed: {e}")
        return {}


async def call_ollama_local(
    messages, url="http://localhost:11434/api/chat", model="llama3", temperature=0.6
):
    """
    Communicates with a local Ollama instance.
    """
    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "options": {"temperature": temperature},
    }

    client = get_http_client()
    try:
        response = await client.post(url, json=payload, timeout=120.0)
        if response.status_code == 200:
            content = response.json()["message"]["content"]
            logger.info(f"[AI] Local Ollama ({model}) succeeded.")
            return content
    except Exception as e:
        logger.error(f"[AI] Local LLM (Ollama) failed: {e}")
        return None


async def get_embedding(text: str):
    """
    Generates a vector embedding for the given text.
    Prioritizes Local Ollama embeddings if enabled.
    """
    if not text:
        return None

    # 1. Check Admin Settings
    try:
        from backend.database import SessionLocal, SystemConfig

        with SessionLocal() as db:
            configs = (
                db.query(SystemConfig)
                .filter(
                    SystemConfig.key.in_(
                        ["use_local_llm", "local_llm_url", "local_llm_model"]
                    )
                )
                .all()
            )
            settings_map = {c.key: c.value for c in configs}

            if settings_map.get("use_local_llm") == "true":
                local_url = settings_map.get("local_llm_url", "http://localhost:11434")
                # Ollama embeddings endpoint is /api/embeddings
                emb_url = local_url.rstrip("/") + "/api/embeddings"
                local_model = settings_map.get(
                    "local_llm_model", "llama3"
                )  # Or a dedicated embedding model

                payload = {
                    "model": local_model,
                    "prompt": text[:4000],
                }  # Truncate for safety

                async with httpx.AsyncClient(timeout=30.0) as client:
                    resp = await client.post(emb_url, json=payload)
                    if resp.status_code == 200:
                        embedding = resp.json().get("embedding")
                        if embedding:
                            logger.info(
                                f"[AI] Generated embedding ({len(embedding)} dimensions) using Ollama."
                            )
                            return embedding
    except Exception as e:
        logger.warning(f"[AI] Embedding generation failed/skipped: {e}")

    # Fallback: No embedding (None) indicating feature is inactive or failed.
    # The search router will handle filtering out candidates without embeddings.
    return None


async def _check_ai_security_rate_limit(company_id=None) -> tuple[bool, str]:
    """Apply request-level AI rate limiting once per public AI call.

    The identity is propagated by get_current_user() through ContextVars.
    Explicit company_id is preferred when supplied.

    Returns:
        (True, "") when allowed or when no complete authenticated context
        is available for legacy/internal callers.
        (False, message) when the request must be blocked.
    """
    security_company_id = company_id or current_company_id_var.get()
    security_user_id = current_user_id_var.get()
    security_ip = current_ip_var.get()

    # Legacy/background/internal callers may not have HTTP identity.
    # Do not break those callers merely because they have no request context.
    if not security_company_id or not security_user_id or not security_ip:
        logger.debug(
            "[AI SECURITY] Incomplete rate-limit context "
            "(company=%s, user=%s, ip=%s); skipping identity limiter",
            security_company_id,
            security_user_id,
            security_ip,
        )
        return True, ""

    try:
        allowed, message = await AISecurity.check_rate_limit(
            company_id=security_company_id,
            user_id=security_user_id,
            ip=security_ip,
        )

        if not allowed:
            logger.warning(
                "[AI SECURITY] AI rate limit blocked: company=%s user=%s ip=%s reason=%s",
                security_company_id,
                security_user_id,
                security_ip,
                message,
            )
            return False, message or "AI rate limit exceeded. Try again later."

        return True, ""

    except Exception as e:
        # AISecurityRateLimiter itself is fail-closed when Redis errors.
        # This guard must therefore NOT silently turn a limiter exception
        # into an unlimited AI request in production.
        logger.exception("[AI SECURITY] Rate-limit check failed: %s", e)

        if settings.is_prod:
            return False, "AI security check unavailable. Please try again later."

        return True, ""


async def call_groq_cascade(
    messages,
    temperature=0.1,
    max_tokens=1024,
    json_mode=True,
    application_id=None,
    company_id=None,
):
    """
    Public entry point for AI calls with full security enforcement.

    Provider routing: reads ``ai_provider`` from SystemConfig (admin panel).
    - ``groq`` (default): tries MODELS_CASCADE, falls back to Gemini on failure.
    - ``gemini``: tries GEMINI_MODELS with retries, falls back to Groq on failure.

    Security layers (applied in order):
    1. Token budget enforcement    (token_tracker.enforce_budget)
    2. Prompt injection scanning   (AISecurity.detect_prompt_injection)
    3. PII masking                 (PIIMasker.mask_pii)
    4. Cost budget check           (cost_controller.check_ai_budget)
    5. Circuit breaker protection  (resilience.get_breaker)
    6. Output size validation      (_validate_output_size)
    7. Cost usage recording        (record_ai_usage)
    """
    # Resolve company_id from context if not explicitly provided
    if not company_id:
        company_id = current_company_id_var.get()

    # AI SECURITY: one identity rate-limit check for this public AI call.
    # Provider fallback below must NOT perform another check.
    rate_allowed, rate_message = await _check_ai_security_rate_limit(company_id)
    if not rate_allowed:
        if json_mode:
            return {
                "error": rate_message,
                "score": 0,
            }
        return rate_message

    # Read provider preference from admin settings
    settings_map = await _get_cached_system_config()
    provider = settings_map.get("ai_provider", "groq")

    # Token budget enforcement (90% safety margin on context window)
    try:
        primary_model = (
            GEMINI_MODELS[0] if provider == "gemini" else MODELS_CASCADE[0]
        )
        context_window = get_model_context_window(primary_model)
        budget = int(context_window * 0.9)
        total_tokens = count_tokens_in_messages(messages, primary_model)
        if total_tokens > budget:
            messages = truncate_messages_to_budget(messages, budget, primary_model)
            logger.info(
                f"[AI TOKEN] Truncated messages from {total_tokens} to {budget} tokens"
            )
    except Exception as e:
        logger.warning(f"[AI TOKEN] Budget enforcement failed: {e}")

    # Cost budget check
    if company_id:
        try:
            input_tokens = count_tokens_in_messages(messages)
            cost_estimator = (
                estimate_gemini_cost if provider == "gemini" else estimate_groq_cost
            )
            estimated_cost = cost_estimator(input_tokens, max_tokens, primary_model)
            if not check_ai_budget(company_id, estimated_cost):
                logger.warning(f"[AI COST] Budget exceeded for company {company_id}")
                if json_mode:
                    return {"error": "AI budget exceeded", "score": 0}
                return "AI budget exceeded for your company. Contact your admin."
        except Exception as e:
            logger.warning(f"[AI COST] Budget check failed: {e}")

    # --- Provider routing ---
    result = None

    if provider == "gemini":
        # Gemini-first: try Gemini cascade, fall back to Groq
        try:
            result = await get_breaker("gemini").call(
                _call_gemini_cascade_impl,
                messages,
                temperature,
                max_tokens,
                json_mode,
                application_id,
            )
        except Exception as gemini_error:
            logger.warning(
                f"[AI FALLBACK] Gemini failed, trying Groq: {gemini_error}"
            )
            try:
                result = await get_breaker("groq").call(
                    _call_groq_cascade_impl,
                    messages,
                    temperature,
                    max_tokens,
                    json_mode,
                    application_id,
                )
            except Exception as groq_error:
                logger.error(f"[AI FALLBACK] Groq also failed: {groq_error}")
                result = None
    else:
        # Groq-first (default): try Groq cascade, fall back to Gemini
        try:
            result = await get_breaker("groq").call(
                _call_groq_cascade_impl,
                messages,
                temperature,
                max_tokens,
                json_mode,
                application_id,
            )
        except Exception as groq_error:
            logger.warning(
                f"[AI FALLBACK] Groq failed, trying Gemini: {groq_error}"
            )
            try:
                result = await get_breaker("gemini").call(
                    _call_gemini_ai_impl,
                    messages,
                    temperature,
                    max_tokens,
                    json_mode,
                    application_id,
                )
            except Exception as gemini_error:
                logger.error(f"[AI FALLBACK] Gemini also failed: {gemini_error}")
                result = None

    # Record usage
    if company_id and result is not None:
        try:
            output_tokens = max(1, len(str(result)) // 4)
            input_tokens = count_tokens_in_messages(messages)
            if provider == "gemini":
                cost = estimate_gemini_cost(
                    input_tokens, output_tokens, GEMINI_MODELS[0]
                )
                record_ai_usage(
                    company_id=company_id,
                    provider="gemini",
                    model=GEMINI_MODELS[0],
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    cost=cost,
                )
            else:
                cost = estimate_groq_cost(
                    input_tokens, output_tokens, MODELS_CASCADE[0]
                )
                record_ai_usage(
                    company_id=company_id,
                    provider="groq",
                    model=MODELS_CASCADE[0],
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    cost=cost,
                )
        except Exception as e:
            logger.debug(f"[AI COST] Usage recording failed: {e}")

    # Output validation (validate size and structure)
    if result is not None and isinstance(result, str):
        try:
            trimmed = result[:10000]
            parsed = json.loads(trimmed)
            if not isinstance(parsed, dict) and not isinstance(parsed, list):
                logger.warning("[AI OUTPUT] Unexpected structure, returning raw")
            else:
                result = parsed
        except (json.JSONDecodeError, TypeError):
            pass
    elif result is not None and isinstance(result, dict):
        max_size = 100000
        if len(json.dumps(result, default=str)) > max_size:
            logger.warning(
                f"[AI OUTPUT] Output too large ({len(str(result))} chars), truncating keys"
            )
            for key in list(result.keys()):
                if isinstance(result[key], str) and len(result[key]) > 50000:
                    result[key] = result[key][:50000]

    return result


# Central trailing-role normalization for the Groq cascade.
#
# Groq's compound-family models ("groq/compound", "groq/compound-mini")
# reject payloads whose FINAL message role is "system" (or that contain no
# user role at all). Many callers build single-system prompt lists
# (extraction / analysis / generation prompts), so this module enforces the
# invariant centrally: every message list that reaches the Groq transport
# ends with a "user" turn. Existing messages are never reordered or mutated
# (system content passes through byte-for-byte) — a minimal constant user
# instruction is appended only when the list does not already end in user.
#
# NOTE: Bare-string entries are NOT part of the supported message contract
# (see call_groq_cascade's handling of non-dict entries). They are left
# untouched here — no coercion is invented for them.
_TRAILING_USER_INSTRUCTION = (
    "Please respond based on the context provided above."
)


def _normalize_trailing_user(messages):
    """Return ``messages`` guaranteed to end with a ``role == "user"`` dict.

    - Lists already ending in a ``user`` dict are returned as the SAME
      list object (and same message dicts) — byte-for-byte unchanged.
    - All other dict-based lists get a new list with a constant minimal
      user instruction appended; no existing entry is modified.
    - Empty / non-list inputs and lists whose last entry is not a dict
      are returned untouched.
    """
    if not isinstance(messages, list) or not messages:
        return messages
    last = messages[-1]
    if isinstance(last, dict) and last.get("role") == "user":
        return messages
    if not isinstance(last, dict):
        return messages
    return messages + [{"role": "user", "content": _TRAILING_USER_INSTRUCTION}]


async def _call_groq_cascade_impl(
    messages, temperature=0.1, max_tokens=1024, json_mode=True, application_id=None
):
    """
    Internal implementation of Groq cascade (called via circuit breaker).
    """
    # BUG-FIX: Deep copy messages to prevent mutating caller's list
    messages = [dict(m) if isinstance(m, dict) else m for m in messages]

    # CENTRAL FIX (Groq trailing-role invariant): normalize BEFORE any
    # payload is built, so every Groq model, the retry-without-json path,
    # and the self-heal path all receive a list whose last message role is
    # "user". Existing messages are preserved untouched.
    messages = _normalize_trailing_user(messages)

    # Scan user messages for injection. System messages are app-generated and trusted.
    for i, msg in enumerate(messages):
        if not isinstance(msg, dict):
            continue
        if msg.get("role") != "user":
            continue
        content = msg.get("content", "")
        if not content:
            continue
        is_safe, reason = AISecurity.detect_prompt_injection(content)
        if not is_safe:
            logger.warning(f"AI SECURITY BLOCKED (user input at index {i}): {reason}")
            raise ValueError(
                f"Security Alert: Your input was flagged as potentially harmful. Reason: {reason}"
            )
        messages[i]["content"] = AISecurity.sanitize_input(content)

    # PII ANONYMIZATION: Mask personal data before sending to external AI (GDPR)
    # Only mask user messages — system messages contain trusted app-authored content
    # (rubric skill names, prompts, etc.) that must NOT be altered.
    pii_detected = 0
    for msg in messages:
        if not isinstance(msg, dict):
            continue
        if msg.get("role") == "system":
            continue
        if msg.get("content"):
            masked_content = PIIMasker.mask_pii(msg["content"])
            if masked_content != msg["content"]:
                pii_detected += 1
            msg["content"] = masked_content
    if pii_detected:
        logger.info(
            f"[PII-GUARD] Masked PII in {pii_detected} message(s) "
            f"before sending to external LLM"
        )

    settings = get_settings()
    start_time = datetime.now()

    # ISSUE-12 FIX: Use cached SystemConfig (60s TTL) instead of 3 separate DB queries.
    settings_map = await _get_cached_system_config()

    # 1. OPTIONAL: Local LLM Activation (Admin Toggle)
    if settings_map.get("use_local_llm") == "true":
        try:
            local_messages = [
                {"role": m["role"], "content": PIIMasker.mask_pii(m.get("content", "")) if m.get("role") != "system" else m.get("content", "")}
                for m in messages
                if isinstance(m, dict)
            ]
            local_url = settings_map.get(
                "local_llm_url", "http://localhost:11434/api/chat"
            )
            if "/api/chat" not in local_url:
                local_url = local_url.rstrip("/") + "/api/chat"
            local_model = settings_map.get("local_llm_model", "llama3")
            local_result = await call_ollama_local(
                local_messages,
                url=local_url,
                model=local_model,
                temperature=temperature,
            )
            if local_result:
                if json_mode:
                    try:
                        return json.loads(local_result)
                    except Exception:
                        match = re.search(r"(\{.*\})", local_result[:10000], re.DOTALL)
                        if match:
                            return json.loads(match.group())
                return local_result
        except Exception as e:
            logger.warning(f"Local LLM failed, falling back to cloud: {e}")

    # PRIORITIZE DB CONFIG: Admin Panel settings should override .env
    db_api_key = settings_map.get("groq_api_key")
    db_ai_model = settings_map.get("ai_model")
    env_api_key = settings.groq_api_key
    api_key = db_api_key or env_api_key
    using_db_key = bool(db_api_key)

    # Prepend user-selected model to cascade
    active_cascade = list(MODELS_CASCADE)
    user_selected_model = db_ai_model or getattr(settings, "ai_model", None)

    if user_selected_model:
        if user_selected_model in active_cascade:
            active_cascade.remove(user_selected_model)
        active_cascade.insert(0, user_selected_model)

    # Validate API key
    placeholder_keys = ["YOUR_NEW_GROQ_API_KEY_HERE", "", None]
    if api_key in placeholder_keys:
        logger.warning("⚠️ No valid Groq API key - using fallback response")
        if json_mode:
            return {
                "error": "AI service not configured. Please add Groq API key in .env file.",
                "score": 0,
                "verdict": "pending",
            }
        return "AI service not configured. Please add Groq API key in .env file."

    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    client = get_http_client()
    for model in active_cascade:
        # RELIABILITY FIX: Retry each model up to 3 times with exponential backoff
        max_retries = 3
        base_delay = 1
        response = None
        succeeded = False

        logger.info(f"[AI CASCADE] Trying model: {model}")

        for attempt in range(max_retries):
            try:
                if attempt > 0:
                    delay = base_delay * (2 ** (attempt - 1))  # 1s, 2s, 4s
                    logger.info(
                        f"[AI] Retry {attempt}/{max_retries} for {model} after {delay}s delay..."
                    )
                    await asyncio.sleep(delay)

                logger.info(
                    f"[AI] Attempting {model} (attempt {attempt + 1}/{max_retries}), json_mode={json_mode}"
                )

                payload = {
                    "model": model,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                }
                if json_mode:
                    payload["response_format"] = {"type": "json_object"}
                    # Groq requirement: "json" must be in messages when using response_format json_object
                    # Add "json" hint to last user message or system message if no user exists
                    target_idx = None
                    for i, msg in enumerate(messages):
                        if msg.get("role") == "user":
                            target_idx = i

                    # Fallback to system message if no user message found
                    if target_idx is None:
                        for i, msg in enumerate(messages):
                            if msg.get("role") == "system":
                                target_idx = i
                                break

                    if target_idx is not None:
                        content = messages[target_idx].get("content", "")
                        if content and "json" not in content.lower():
                            messages[target_idx]["content"] = (
                                content + "\nOutput your response as valid JSON."
                            )
                            payload["messages"] = messages

                # RATE LIMITING (Apply only before cloud call)
                await groq_rate_limiter.acquire()

                response = await client.post(
                    url, headers=headers, json=payload, timeout=120.0
                )

                logger.debug(f"[AI] {model} response status: {response.status_code}")

                # AUTH FALLBACK: If DB key failed with 401, immediately try matching ENV key if it exists
                if (
                    response.status_code == 401
                    and using_db_key
                    and env_api_key
                    and env_api_key != api_key
                ):
                    logger.warning(
                        f"[AI] 401 Auth Error with DB key. Falling back to ENV key for {model}..."
                    )
                    api_key = env_api_key
                    using_db_key = False
                    headers["Authorization"] = f"Bearer {api_key}"
                    # Retry this exact attempt with the new key
                    response = await client.post(url, headers=headers, json=payload)
                    logger.info(
                        f"[AI] Auth fallback response status: {response.status_code}"
                    )

                # If successful, break retry loop
                if response.status_code == 200:
                    logger.info(f"[AI] SUCCESS: {model} succeeded")
                    succeeded = True
                    break

                # Handle 400 errors - retry with exponential backoff
                if response.status_code == 400:
                    error_detail = (
                        response.text[:200] if hasattr(response, "text") else "Unknown"
                    )
                    logger.warning(
                        f"[AI] {model} returned 400 (Bad Request): {error_detail}"
                    )
                    # Apply backoff before retrying 400 errors
                    if attempt < max_retries - 1:
                        delay = base_delay * (2**attempt)
                        logger.info(
                            f"[AI] {model} 400 error - retrying after {delay}s delay..."
                        )
                        await asyncio.sleep(delay)
                    continue

            except Exception as e:
                logger.error(
                    f"[AI] {model} Error (attempt {attempt + 1}): {type(e).__name__}: {str(e)}"
                )
                if attempt == max_retries - 1:
                    # Last attempt failed, move to next model
                    logger.warning(
                        f"[AI] {model} failed all {max_retries} attempts, moving to next model"
                    )
                    continue
                # Otherwise, retry with backoff
                continue

            # Handle any other non-200 status codes (429, 500, etc)
            if response.status_code != 200 and response.status_code != 401:
                logger.warning(
                    f"[AI] {model} returned status {response.status_code}, will retry..."
                )
                if attempt < max_retries - 1:
                    delay = base_delay * (2**attempt)
                    await asyncio.sleep(delay)
                continue

        if not succeeded:
            logger.warning(
                f"[AI] Model {model} failed after all retries or returned non-200. Moving to next model."
            )
            continue

        if response.status_code == 400 and json_mode:
            logger.warning(
                f"[AI] {model} returned 400 with json_mode={json_mode}. Attempting retry without JSON mode..."
            )
            try:
                del payload["response_format"]
                response = await client.post(url, headers=headers, json=payload)
                if response.status_code == 200:
                    logger.info(f"[AI] SUCCESS: {model} succeeded without json_mode")
                    content = response.json()["choices"][0]["message"]["content"]
                    try:
                        parsed = json.loads(content)
                        logger.info(f"[AI] Parsed JSON successfully from {model}")
                        return parsed
                    except Exception as json_err:
                        logger.warning(
                            f"[AI] Could not parse response as JSON: {json_err}"
                        )
                        match = re.search(r"(\{.*\})", content[:10000], re.DOTALL)
                        if match:
                            try:
                                return json.loads(match.group())
                            except Exception:
                                logger.warning("[AI] Could not parse extracted JSON")
            except Exception as retry_e:
                logger.error(
                    f"[AI] Retry without json_mode failed: {type(retry_e).__name__}: {retry_e}"
                )

        if response.status_code != 200:
            logger.warning(
                f"[AI] ERROR: {model} returned status {response.status_code}, moving to next model"
            )
            try:
                error_detail = (
                    response.text[:200]
                    if hasattr(response, "text")
                    else str(response)[:200]
                )
                logger.warning(f"[AI] {model} error detail: {error_detail}")
            except Exception:
                pass
            continue

        result = response.json()
        content = _validate_output_size(result["choices"][0]["message"]["content"])

        # P1-10 FIX: Record per-call cost. ``record_cost`` is
        # best-effort — it never raises — and emits a structured
        # log line plus Prometheus counter updates.
        try:
            record_cost(
                provider="groq",
                model=model,
                response_json=result,
                outcome="success",
            )
        except Exception as e:  # noqa: BLE001
            logger.debug(f"[LLM-COST] record failed: {e}")

        if json_mode:
            try:
                return json.loads(content)
            except Exception:
                # AUTO-REPAIR: Try to extract JSON from text if it's not pure JSON
                match = re.search(r"(\{.*\})", content[:10000], re.DOTALL)
                if match:
                    try:
                        return json.loads(match.group())
                    except Exception:
                        pass
                logger.warning(f"[AI] JSON failed for {model}, trying next...")
                continue

        # TRAKIN LOGGING (SUCCESS)
        try:
            duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
            from backend.trakin.ai_monitor import log_ai_interaction

            asyncio.create_task(
                log_ai_interaction(
                    model=model,
                    messages=messages,
                    response_content=content[:1000]
                    if isinstance(content, str)
                    else "JSON_RESPONSE",
                    duration_ms=duration_ms,
                    status="success" if response.status_code == 200 else "error",
                )
            )
        except Exception as e:
            logger.error(f"[TRAKIN] Log failed: {e}")

        # AUDIT TRAIL LOGGING
        try:
            from backend.ai_audit import log_ai_call

            log_ai_call(
                action="groq_cascade",
                model_version=model,
                application_id=application_id,
                prompt=messages[-1].get("content", "")[:2000] if messages else None,
                response_content=content[:1000]
                if isinstance(content, str)
                else json.dumps(content)[:1000],
                duration_ms=duration_ms,
                success=True,
                prompt_injection_blocked=False,
            )
        except Exception as e:
            logger.error(f"[AUDIT] Log failed: {e}")

        return content

    # FINAL SELF-HEALING: One last try with a smaller model, NO JSON MODE, and manual parsing
    logger.warning("[AI] Self-Healing Protocol triggered...")
    try:
        heal_model = "groq/compound-mini"
        # FIX: Ensure we don't violate Groq's single-system-message rule
        heal_messages = list(messages)
        # Defensive: the self-heal POST must never be system-last, even if a
        # future path feeds it a non-normalized list. Idempotent when the
        # invoker already normalized (message lists arrive user-last here).
        heal_messages = _normalize_trailing_user(heal_messages)
        if heal_messages and heal_messages[0].get("role") == "system":
            # Append instruction to existing system message
            heal_messages[0] = heal_messages[0].copy()
            heal_messages[0]["content"] += (
                "\nIMPORTANT: Return ONLY raw JSON. No markdown."
            )
        else:
            # Insert as the first message
            heal_messages.insert(
                0,
                {
                    "role": "system",
                    "content": "IMPORTANT: Return ONLY raw JSON. No markdown.",
                },
            )

        heal_payload = {
            "model": heal_model,
            "messages": heal_messages,
            "temperature": 0.2,  # Low temp for consistency
            "max_tokens": max_tokens,
        }
        client = get_http_client()
        resp = await client.post(url, headers=headers, json=heal_payload, timeout=45.0)
        if resp.status_code == 200:
            raw_content = resp.json()["choices"][0]["message"]["content"]
            match = re.search(r"(\{.*\})", raw_content[:10000], re.DOTALL)
            if match:
                try:
                    return json.loads(match.group())
                except json.JSONDecodeError:
                    logger.warning(
                        "[AI] Self-healing returned invalid JSON despite regex match"
                    )
    except Exception:
        pass

    # SAFETY NET: Mock Fallback if ALL AI fails (Prevent 500 Error)
    logger.critical(
        "[AI] SYSTEM FAILURE: All models and self-healing failed. Using Mock Fallback."
    )

    # TRAKIN LOGGING (FAILURE)
    duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
    try:
        from backend.trakin.ai_monitor import log_ai_interaction

        asyncio.create_task(
            log_ai_interaction(
                model="ALL_FAILED",
                messages=messages,
                response_content="Mock Fallback Triggered",
                duration_ms=duration_ms,
                status="failed",
            )
        )
    except Exception as e:
        logger.error(f"[TRAKIN] Log failed: {e}")

    # AUDIT TRAIL LOGGING (FAILURE)
    try:
        from backend.ai_audit import log_ai_call

        log_ai_call(
            action="groq_cascade",
            model_version="ALL_FAILED",
            application_id=application_id,
            prompt=messages[-1].get("content", "")[:2000] if messages else None,
            response_content=None,
            duration_ms=duration_ms,
            success=False,
            error_message="All models and self-healing failed. Mock fallback returned.",
            prompt_injection_blocked=False,
        )
    except Exception as e:
        logger.error(f"[AUDIT] Log failed: {e}")

    # CRITICAL: Return None so the caller handles "AI unavailable" explicitly.
    return None


async def _call_gemini_cascade_impl(
    messages, temperature=0.5, max_tokens=1024, json_mode=True, application_id=None
):
    """Gemini cascade with retries — mirrors Groq cascade structure."""
    import asyncio

    from backend.ai.security import AISecurity, PIIMasker
    from backend.ai.token_tracker import enforce_budget

    start_time = datetime.now()

    # Deep copy to avoid mutating caller's list
    messages = [dict(m) if isinstance(m, dict) else m for m in messages]

    # Injection scan
    for msg in messages:
        if not isinstance(msg, dict):
            continue
        content = msg.get("content", "")
        if content and msg.get("role") == "user":
            is_safe, reason = AISecurity.detect_prompt_injection(content)
            if not is_safe:
                logger.warning(f"[AI SECURITY] Blocking Gemini input: {reason}")
                raise SecurityException(f"Security Alert: {reason}")
            msg["content"] = AISecurity.sanitize_input(content)

    # PII masking
    pii_detected = 0
    for msg in messages:
        if not isinstance(msg, dict):
            continue
        content = msg.get("content", "")
        if content:
            masked, count = PIIMasker.mask_pii(content)
            if count > 0:
                msg["content"] = masked
                pii_detected += count
    if pii_detected:
        logger.info(
            f"[PII-GUARD] Masked PII in {pii_detected} Gemini message(s)"
        )

    settings = get_settings()
    settings_map = await _get_cached_system_config()
    api_key = settings_map.get("gemini_api_key") or settings.gemini_api_key

    if not api_key:
        logger.warning("[AI] Gemini API key is missing. Skipping Gemini call.")
        return None

    # Build Gemini payload
    contents = []
    system_prompt = ""
    for msg in messages:
        role = msg.get("role")
        content = msg.get("content", "")
        if role == "system":
            system_prompt = content
        elif role == "user":
            contents.append({"role": "user", "parts": [{"text": content}]})
        elif role in ["assistant", "ai"]:
            contents.append({"role": "model", "parts": [{"text": content}]})

    base_url = (
        getattr(settings, "gemini_api_url", None)
        or "https://generativelanguage.googleapis.com/v1beta"
    )
    headers = {"X-Goog-Api-Key": api_key, "Content-Type": "application/json"}
    client = get_http_client()

    # Cascade through Gemini models with retries
    for model in GEMINI_MODELS:
        max_retries = 3
        base_delay = 1

        for attempt in range(max_retries):
            if attempt > 0:
                delay = base_delay * (2 ** (attempt - 1))
                logger.info(f"[AI] Gemini retry {attempt}/{max_retries} for {model} after {delay}s")
                await asyncio.sleep(delay)

            payload = {
                "contents": contents,
                "generationConfig": {
                    "temperature": temperature,
                    "maxOutputTokens": max_tokens,
                },
            }
            if system_prompt:
                payload["system_instruction"] = {"parts": [{"text": system_prompt}]}
            if json_mode:
                payload["generationConfig"]["responseMimeType"] = "application/json"

            url = f"{base_url}/models/{model}:generateContent"
            logger.info(f"[AI CASCADE] Trying Gemini model: {model} (attempt {attempt + 1})")

            try:
                response = await client.post(url, headers=headers, json=payload, timeout=60.0)
                if response.status_code == 200:
                    result = response.json()
                    if "candidates" in result and len(result["candidates"]) > 0:
                        candidate = result["candidates"][0]
                        # Extract text from parts — handle both text and inlineData
                        parts = candidate.get("content", {}).get("parts", [])
                        text_chunks = []
                        for part in parts:
                            if "text" in part:
                                text_chunks.append(part["text"])
                            elif "inlineData" in part:
                                continue  # skip non-text parts
                        content = _validate_output_size("".join(text_chunks)) if text_chunks else ""

                        if not content:
                            logger.warning(f"[AI] Gemini {model} returned empty text content")
                            break

                        logger.info(f"[AI] SUCCESS: Gemini {model} succeeded")

                        # Parse JSON if json_mode
                        if json_mode:
                            try:
                                return json.loads(content)
                            except Exception:
                                match = re.search(r"(\{.*\})", content[:10000], re.DOTALL)
                                if match:
                                    try:
                                        return json.loads(match.group())
                                    except Exception:
                                        pass
                                logger.warning(f"[AI] Gemini {model} JSON parse failed, trying next model")
                                break  # move to next model
                        return content
                    else:
                        logger.warning(f"[AI] Gemini {model} returned empty candidates")
                else:
                    error_detail = response.text[:200] if hasattr(response, "text") else "Unknown"
                    logger.warning(f"[AI] Gemini {model} returned {response.status_code}: {error_detail}")
                    if response.status_code == 429:
                        continue
                    elif response.status_code >= 500:
                        continue
                    else:
                        break  # client error — try next model
            except Exception as e:
                logger.warning(f"[AI] Gemini {model} error: {type(e).__name__}: {e}")
                if attempt == max_retries - 1:
                    break

    # All Gemini models failed
    logger.error("[AI] All Gemini models failed")
    return None


async def call_gemini_ai(
    messages,
    temperature=0.5,
    max_tokens=1024,
    json_mode=True,
    application_id=None,
    company_id=None,
):
    """
    Public entry point for Gemini AI with full security enforcement.

    Security layers (applied in order):
    1. Token budget enforcement
    2. Cost budget check
    3. Circuit breaker protection
    4. PII masking + injection scanning (inside _call_gemini_ai_impl)
    5. Output size validation
    """

    # Resolve company from the request context when the caller did not
    # explicitly provide one.
    if not company_id:
        company_id = current_company_id_var.get()

    # AI SECURITY: one identity rate-limit check for this public AI call.
    rate_allowed, rate_message = await _check_ai_security_rate_limit(company_id)
    if not rate_allowed:
        if json_mode:
            return {
                "error": rate_message,
                "score": 0,
            }
        return rate_message

    # Token budget enforcement
    try:
        model_name = GEMINI_MODELS[0]
        context_window = get_model_context_window(model_name)
        budget = int(context_window * 0.9)
        total_tokens = count_tokens_in_messages(messages, model_name)
        if total_tokens > budget:
            messages = truncate_messages_to_budget(messages, budget, model_name)
    except Exception as e:
        logger.warning(f"[AI TOKEN] Gemini budget enforcement failed: {e}")

    # Cost budget check
    if company_id:
        try:
            input_tokens = count_tokens_in_messages(messages)
            estimated_cost = estimate_gemini_cost(
                input_tokens, max_tokens, GEMINI_MODELS[0]
            )
            if not check_ai_budget(company_id, estimated_cost):
                logger.warning(
                    f"[AI COST] Gemini budget exceeded for company {company_id}"
                )
                if json_mode:
                    return {"error": "AI budget exceeded", "score": 0}
                return "AI budget exceeded. Contact your admin."
        except Exception as e:
            logger.warning(f"[AI COST] Gemini budget check failed: {e}")

    result = await get_breaker("gemini").call(
        _call_gemini_ai_impl,
        messages,
        temperature,
        max_tokens,
        json_mode,
        application_id,
    )

    # Record usage
    if company_id and result is not None:
        try:
            output_tokens = max(1, len(str(result)) // 4)
            input_tokens = count_tokens_in_messages(messages)
            cost = estimate_gemini_cost(input_tokens, output_tokens, GEMINI_MODELS[0])
            record_ai_usage(
                company_id=company_id,
                provider="gemini",
                model=GEMINI_MODELS[0],
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost=cost,
            )
        except Exception as e:
            logger.debug(f"[AI COST] Gemini usage recording failed: {e}")

    return result


async def _call_gemini_ai_impl(
    messages, temperature=0.5, max_tokens=1024, json_mode=True, application_id=None
):
    """
    Internal implementation of Gemini AI (called via circuit breaker).
    """
    # BUG-FIX: Deep copy messages to prevent mutating caller's list
    messages = [dict(m) if isinstance(m, dict) else m for m in messages]

    # SECURITY: Sanitize all user-controllable content
    for msg in messages:
        if not isinstance(msg, dict):
            continue
        content = msg.get("content", "")
        if content and msg.get("role") == "user":
            # Check for injection
            is_safe, reason = AISecurity.detect_prompt_injection(content)
            if not is_safe:
                logger.warning(f"[AI SECURITY] Blocking Gemini input: {reason}")
                raise SecurityException(f"Security Alert: {reason}")
            # Sanitize content
            msg["content"] = AISecurity.sanitize_input(content)

    # PII ANONYMIZATION: Mask personal data before sending to external AI (GDPR)
    # Only mask user messages — system messages contain trusted app-authored content
    # (rubric skill names, prompts, etc.) that must NOT be altered.
    pii_detected = 0
    for msg in messages:
        if not isinstance(msg, dict):
            continue
        if msg.get("role") == "system":
            continue
        if msg.get("content"):
            masked_content = PIIMasker.mask_pii(msg["content"])
            if masked_content != msg["content"]:
                pii_detected += 1
            msg["content"] = masked_content
    if pii_detected:
        logger.info(
            f"[PII-GUARD] Masked PII in {pii_detected} Gemini message(s) "
            f"before sending to external LLM"
        )

    settings = get_settings()
    settings_map = await _get_cached_system_config()

    api_key = settings_map.get("gemini_api_key") or settings.gemini_api_key

    if not api_key:
        logger.warning("[AI] Gemini API key is missing. Skipping Gemini call.")
        return None

    # Build prompt from messages
    # Gemini uses a different format, but we'll try to adapt common OpenAI-style messages
    contents = []
    system_prompt = ""

    for msg in messages:
        role = msg.get("role")
        content = msg.get("content", "")
        if role == "system":
            system_prompt = content
        elif role == "user":
            contents.append({"role": "user", "parts": [{"text": content}]})
        elif role in ["assistant", "ai"]:
            contents.append({"role": "model", "parts": [{"text": content}]})

    # Gemini 2.0 system instruction handling
    payload = {
        "contents": contents,
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": max_tokens,
        },
    }

    if system_prompt:
        payload["system_instruction"] = {"parts": [{"text": system_prompt}]}

    if json_mode:
        payload["generationConfig"]["responseMimeType"] = "application/json"

    model = "gemini-3.6-flash"  # Default high-performance model
    base_url = (
        getattr(settings, "gemini_api_url", None)
        or "https://generativelanguage.googleapis.com/v1beta"
    )
    url = f"{base_url}/models/{model}:generateContent"
    headers = {"X-Goog-Api-Key": api_key, "Content-Type": "application/json"}

    start_time = datetime.now()
    client = get_http_client()
    try:
        response = await client.post(url, headers=headers, json=payload, timeout=60.0)

        if response.status_code == 200:
            result = response.json()
            if "candidates" in result and len(result["candidates"]) > 0:
                candidate = result["candidates"][0]
                parts = candidate.get("content", {}).get("parts", [])
                text_chunks = [p["text"] for p in parts if "text" in p]
                content = _validate_output_size("".join(text_chunks)) if text_chunks else ""

                # Log success to Trakin
                duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
                try:
                    from backend.trakin.ai_monitor import log_ai_interaction

                    asyncio.create_task(
                        log_ai_interaction(
                            model=model,
                            messages=messages,
                            response_content=content[:1000],
                            duration_ms=duration_ms,
                            status="success",
                        )
                    )
                except Exception:
                    pass

                # AUDIT TRAIL LOGGING
                try:
                    from backend.ai_audit import log_ai_call

                    log_ai_call(
                        action="gemini_call",
                        model_version=model,
                        application_id=application_id,
                        prompt=messages[-1].get("content", "")[:2000]
                        if messages
                        else None,
                        response_content=content[:1000],
                        duration_ms=duration_ms,
                        success=True,
                        prompt_injection_blocked=False,
                    )
                except Exception:
                    pass

                if json_mode:
                    try:
                        return json.loads(content)
                    except Exception:
                        match = re.search(r"(\{.*\})", content[:10000], re.DOTALL)
                        if match:
                            return json.loads(match.group())
                # P1-10 FIX: Gemini cost recording.
                try:
                    record_cost(
                        provider="gemini",
                        model=model,
                        response_json=result,
                        outcome="success",
                    )
                except Exception as e:  # noqa: BLE001
                    logger.debug(f"[LLM-COST] record failed: {e}")
                return content
        else:
            logger.error(
                f"[AI] Gemini Error {response.status_code}: {response.text[:200]}"
            )
    except Exception as e:
        logger.error(f"[AI] Gemini Exception: {type(e).__name__}: {str(e)}")

    return None


# ---------------------------------------------------------------------------
# validated_ai_call — unified wrapper with token/cost/enforcement + validation
# ---------------------------------------------------------------------------

_DEFAULT_MODEL = "groq/compound"


async def validated_ai_call(
    messages: list,
    *,
    application_id: int = 0,
    company_id: int = 0,
    schema_name: str = "fallback",
    temperature: float = 0.1,
    max_tokens: int = 1024,
    json_mode: bool = True,
    provider: str = "groq",
) -> tuple:
    """Unified AI call wrapper with full security enforcement.

    1. Token budget enforcement   (token_tracker.enforce_budget)
    2. Cost budget check          (cost_controller.check_ai_budget)
    3. LLM call                   (call_groq_cascade / call_gemini_ai)
    4. Output validation           (AIOutputValidator)
    5. Usage recording            (cost_controller.record_ai_usage)

    Returns (parsed_result: dict | str | None, error: str | None).
    """
    model = _DEFAULT_MODEL

    # 0. Security rate limiting is enforced centrally by the public
    # call_groq_cascade()/call_gemini_ai() wrappers. Keeping it there
    # prevents double-counting during provider fallback.
    # 1. Token budget enforcement (90% safety margin)
    try:
        context_window = get_model_context_window(model)
        messages = enforce_budget(messages, context_window, safety_margin=0.9)
    except Exception as e:
        logger.warning(f"[validated_ai_call] Token budget enforcement failed: {e}")

    # 2. Estimate cost for budget check
    input_tokens = count_tokens_in_messages(messages, model)
    estimated_cost = estimate_groq_cost(input_tokens, max_tokens, model)

    # 3. Check cost budget
    if company_id:
        try:
            if not check_ai_budget(company_id, estimated_cost):
                logger.warning(
                    f"[validated_ai_call] AI budget exceeded for company {company_id}"
                )
                return None, "AI budget exceeded for your company. Contact your admin."
        except Exception as e:
            logger.warning(f"[validated_ai_call] Budget check failed: {e}")

    # 4. Call the provider
    raw_result = None
    if provider == "groq":
        raw_result = await call_groq_cascade(
            messages,
            temperature=temperature,
            max_tokens=max_tokens,
            json_mode=json_mode,
            application_id=application_id,
        )
    else:
        raw_result = await call_gemini_ai(
            messages,
            temperature=temperature,
            max_tokens=max_tokens,
            json_mode=json_mode,
            application_id=application_id,
        )

    if raw_result is None:
        return None, "AI service unavailable. All providers failed."

    # 5. Record usage (rough token estimate)
    if company_id:
        output_tokens = max(1, len(str(raw_result)) // 4)
        try:
            record_ai_usage(
                company_id=company_id,
                provider=provider,
                model=model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost=estimated_cost,
            )
        except Exception as e:
            logger.debug(f"[validated_ai_call] Usage recording failed: {e}")

    # 6. Validate output against schema
    if schema_name and schema_name != "fallback":
        try:
            context = AIValidationContext(
                application_id=application_id,
                db=None,
                action="validated_ai_call",
                company_id=company_id,
            )
            validator = AIOutputValidator(context)
            validated = validator.validate(schema_name, raw_result)
            if validated is not None:
                return validated.model_dump(), None
            logger.warning(
                f"[validated_ai_call] Schema validation failed for {schema_name}"
            )
            # Return raw result anyway — caller can fall back
        except Exception as e:
            logger.warning(f"[validated_ai_call] Schema validation error: {e}")

    if json_mode and isinstance(raw_result, dict):
        return raw_result, None
    if isinstance(raw_result, str):
        # Try to parse as JSON for consistency
        try:
            return json.loads(raw_result), None
        except (json.JSONDecodeError, TypeError):
            pass
    return raw_result, None
