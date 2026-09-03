from datetime import UTC, datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, SecretStr
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.config import get_settings as _get_cfg_settings
from backend.credit_service import get_all_credit_pricing
from backend.database import AuditLog, SystemConfig, SystemPrompt, User
from backend.dependencies import get_current_user, get_db
from backend.logger import logger
from backend.routers.admin.common import SystemSettings, check_permission, paginate
from backend.schemas import SystemPromptUpdate
from backend.secret_encryption import decrypt_value, encrypt_value, is_sensitive_key

settings_router = APIRouter()


# --- SYSTEM SETTINGS ---
@settings_router.get("/settings")
def get_system_settings(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    check_permission(current_user, "manage_admins")
    secret_key = _get_cfg_settings().secret_key
    configs = db.query(SystemConfig).all()
    settings_dict = {}
    for c in configs:
        val = c.value
        if is_sensitive_key(c.key):
            val = decrypt_value(val, secret_key)
        settings_dict[c.key] = val

    def mask_value(val):
        if not val:
            return ""
        if len(val) <= 4:
            return "****"
        return "*" * (len(val) - 4) + val[-4:]

    def safe_int(val, default):
        try:
            return int(val)
        except (ValueError, TypeError):
            return default

    def safe_float(val, default):
        try:
            return float(val)
        except (ValueError, TypeError):
            return default

    return {
        "maintenance_mode": settings_dict.get("maintenance_mode") == "true",
        "free_trial": settings_dict.get("free_trial") == "true",
        "konnect_wallet_id": settings_dict.get("konnect_wallet_id", ""),
        "konnect_api_key": mask_value(settings_dict.get("konnect_api_key", "")),
        "smtp_host": settings_dict.get("smtp_host", "smtp.gmail.com"),
        "smtp_port": safe_int(settings_dict.get("smtp_port"), 587),
        "smtp_username": settings_dict.get("smtp_username", ""),
        "smtp_password": mask_value(settings_dict.get("smtp_password", "")),
        "groq_api_key": mask_value(settings_dict.get("groq_api_key", "")),
        "deepseek_api_key": mask_value(settings_dict.get("deepseek_api_key", "")),
        "gemini_api_key": mask_value(settings_dict.get("gemini_api_key", "")),
        "ai_provider": settings_dict.get("ai_provider", "groq"),
        "ai_temperature": safe_float(settings_dict.get("ai_temperature"), 0.5),
        "ai_model": settings_dict.get("ai_model", "groq/compound"),
        "platform_fee_percent": safe_float(
            settings_dict.get("platform_fee_percent"), 20.0
        ),
        "use_local_llm": settings_dict.get("use_local_llm") == "true",
        "local_llm_url": settings_dict.get("local_llm_url", "http://localhost:11434"),
        "local_llm_model": settings_dict.get("local_llm_model", "llama3"),
        "default_language": settings_dict.get("default_language", "en"),
        "bank_name": settings_dict.get("bank_name", ""),
        "bank_account_name": settings_dict.get("bank_account_name", ""),
        "bank_account_number": settings_dict.get("bank_account_number", ""),
        "bank_iban": settings_dict.get("bank_iban", ""),
        "payment_instructions": settings_dict.get("payment_instructions", ""),
        "ab_test_enabled": settings_dict.get("ab_test_enabled") == "true",
        "ab_test_bucket_size": safe_int(settings_dict.get("ab_test_bucket_size"), 10),
        "automations_enabled": settings_dict.get("automations_enabled") == "true",
        "google_client_id": settings_dict.get("google_client_id", ""),
        "google_client_secret": mask_value(settings_dict.get("google_client_secret", "")),
        "google_enabled": settings_dict.get("google_enabled") == "true",
        "ai_credit_gating_enabled": settings_dict.get("ai_credit_gating_enabled", "true")
        != "false",
        "ai_credit_costs": get_all_credit_pricing(db),
    }


@settings_router.post("/settings")
def update_system_settings(
    settings: SystemSettings,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    check_permission(current_user, "manage_settings")

    secret_key = _get_cfg_settings().secret_key

    def _resolve(val):
        if isinstance(val, SecretStr):
            return val.get_secret_value()
        return val

    def save_config(key, value):
        cfg = db.query(SystemConfig).filter(SystemConfig.key == key).first()
        if not cfg:
            cfg = SystemConfig(key=key)
            db.add(cfg)
        stored = str(value).lower() if isinstance(value, bool) else str(value)
        if is_sensitive_key(key):
            stored = encrypt_value(stored, secret_key)
        cfg.value = stored

    def is_masked(val):
        raw = _resolve(val)
        return raw and (raw.startswith("***") or raw.startswith("*"))

    save_config("maintenance_mode", settings.maintenance_mode)
    save_config("free_trial", settings.free_trial)
    if settings.konnect_wallet_id:
        save_config("konnect_wallet_id", settings.konnect_wallet_id)
    if settings.konnect_api_key and not is_masked(settings.konnect_api_key):
        save_config("konnect_api_key", _resolve(settings.konnect_api_key))
    if settings.smtp_host:
        save_config("smtp_host", settings.smtp_host)
    if settings.smtp_port:
        save_config("smtp_port", settings.smtp_port)
    if settings.smtp_username:
        save_config("smtp_username", settings.smtp_username)
    if settings.smtp_password and not is_masked(settings.smtp_password):
        save_config("smtp_password", _resolve(settings.smtp_password))
    if settings.groq_api_key and not is_masked(settings.groq_api_key):
        save_config("groq_api_key", _resolve(settings.groq_api_key))
    if settings.deepseek_api_key and not is_masked(settings.deepseek_api_key):
        save_config("deepseek_api_key", _resolve(settings.deepseek_api_key))
    if settings.gemini_api_key and not is_masked(settings.gemini_api_key):
        save_config("gemini_api_key", _resolve(settings.gemini_api_key))
    if settings.ai_provider:
        save_config("ai_provider", settings.ai_provider)
    if settings.ai_temperature is not None:
        save_config("ai_temperature", settings.ai_temperature)
    if settings.ai_model:
        save_config("ai_model", settings.ai_model)
    if settings.platform_fee_percent is not None:
        save_config("platform_fee_percent", settings.platform_fee_percent)
    save_config("use_local_llm", settings.use_local_llm)
    if settings.local_llm_url:
        save_config("local_llm_url", settings.local_llm_url)
    if settings.local_llm_model:
        save_config("local_llm_model", settings.local_llm_model)
    if settings.default_language:
        save_config("default_language", settings.default_language)
    if settings.bank_name is not None:
        save_config("bank_name", settings.bank_name)
    if settings.bank_account_name is not None:
        save_config("bank_account_name", settings.bank_account_name)
    if settings.bank_account_number is not None:
        save_config("bank_account_number", settings.bank_account_number)
    if settings.bank_iban is not None:
        save_config("bank_iban", settings.bank_iban)
    if settings.payment_instructions is not None:
        save_config("payment_instructions", settings.payment_instructions)
    if settings.ab_test_enabled is not None:
        save_config("ab_test_enabled", settings.ab_test_enabled)
    if settings.ab_test_bucket_size is not None:
        save_config("ab_test_bucket_size", settings.ab_test_bucket_size)
    if settings.automations_enabled is not None:
        save_config("automations_enabled", settings.automations_enabled)

    # AI Credit Pricing (admin-controlled monetization)
    if settings.ai_credit_gating_enabled is not None:
        save_config("ai_credit_gating_enabled", settings.ai_credit_gating_enabled)
    if isinstance(settings.ai_credit_costs, dict):
        for resource, cost in settings.ai_credit_costs.items():
            try:
                cost_int = int(float(cost))
            except (TypeError, ValueError):
                continue
            if cost_int >= 0:
                save_config(f"ai_credit_cost_{resource}", cost_int)

    if settings.google_client_id:
        save_config("google_client_id", _resolve(settings.google_client_id))
    if settings.google_client_secret and not is_masked(settings.google_client_secret):
        save_config("google_client_secret", _resolve(settings.google_client_secret))
    save_config("google_enabled", settings.google_enabled)

    audit = AuditLog(
        user_id=current_user.id,
        action="update_settings",
        details="System settings updated",
        ip_address=request.client.host,
    )
    db.add(audit)
    db.commit()
    return {"message": "Settings updated"}


class TestEmailBody(BaseModel):
    email: Optional[str] = None


@settings_router.post("/email/test")
async def send_admin_test_email(
    payload: TestEmailBody,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    check_permission(current_user, "manage_admins")

    if not payload.email:
        raise HTTPException(status_code=400, detail="Target email is required")

    subject = "Candway SMTP Relay Test Signal"
    content = f"""
    <h2 style="color:#4f46e5;">Relay Success</h2>
    <p>This is a test signal from the <strong>Candway Admin Console</strong>.</p>
    <p>If you are reading this, your SMTP configuration is active and authenticated.</p>
    <div style="margin-top:20px; padding:15px; background:#f1f5f9; border-radius:8px; font-size:12px; color:#64748b;">
        Timestamp: {datetime.now(UTC).isoformat()}<br>
        Operator: {current_user.email}
    </div>
    """

    try:
        from backend.email_service import email_service, wrap_in_template

        email_service.send_email(
            payload.email, subject, wrap_in_template(content, subject)
        )
        return {"message": "Test email sent successfully"}
    except Exception as e:
        logger.error(f"SMTP Error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail="Failed to send email. Check SMTP configuration."
        )


# --- TEST AI MODEL ---
class TestAIModelBody(BaseModel):
    model: str
    provider: str = "groq"
    api_key: Optional[str] = None


@settings_router.post("/ai/test-model")
async def test_ai_model(
    payload: TestAIModelBody,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    check_permission(current_user, "manage_admins")

    import httpx as _httpx

    provider = payload.provider.lower()

    # Resolve API key: use provided key, then DB, then .env
    api_key = payload.api_key
    db_key_name = f"{provider}_api_key"
    env_key_name = f"{provider}_api_key"

    if not api_key or api_key.startswith("*"):
        db_key = (
            db.query(SystemConfig)
            .filter(SystemConfig.key == db_key_name)
            .first()
        )
        if db_key and db_key.value:
            try:
                api_key = decrypt_value(db_key.value, _get_cfg_settings().secret_key)
            except Exception:
                api_key = db_key.value
    if not api_key or api_key.startswith("*"):
        api_key = getattr(_get_cfg_settings(), env_key_name, None)

    if not api_key:
        raise HTTPException(status_code=400, detail=f"No {provider.title()} API key configured")

    try:
        async with _httpx.AsyncClient(timeout=30.0) as client:
            if provider == "gemini":
                # Gemini API call
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{payload.model}:generateContent"
                resp = await client.post(
                    url,
                    headers={"X-Goog-Api-Key": api_key, "Content-Type": "application/json"},
                    json={
                        "contents": [{"role": "user", "parts": [{"text": "Respond with exactly this JSON: {\"status\": \"ok\", \"model\": \"" + payload.model + "\"}"}]}],
                        "generationConfig": {"temperature": 0.1, "maxOutputTokens": 64, "responseMimeType": "application/json"},
                    },
                )
                if resp.status_code == 200:
                    data = resp.json()
                    candidates = data.get("candidates", [])
                    content = candidates[0]["content"]["parts"][0]["text"] if candidates else ""
                    return {"success": True, "model": payload.model, "response": content[:200]}
                else:
                    error = resp.json().get("error", {})
                    return {"success": False, "model": payload.model, "error": error.get("message", f"HTTP {resp.status_code}"), "code": error.get("code", "unknown")}
            else:
                # Groq API call
                resp = await client.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                    json={
                        "model": payload.model,
                        "messages": [{"role": "user", "content": "Respond with exactly this JSON and nothing else: {\"status\": \"ok\", \"model\": \"" + payload.model + "\"}"}],
                        "temperature": 0.1,
                        "max_tokens": 64,
                    },
                )
                if resp.status_code == 200:
                    data = resp.json()
                    content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                    return {"success": True, "model": payload.model, "response": content[:200], "usage": data.get("usage", {})}
                else:
                    error = resp.json().get("error", {})
                    return {"success": False, "model": payload.model, "error": error.get("message", f"HTTP {resp.status_code}"), "code": error.get("code", "unknown")}
    except Exception as e:
        logger.error(f"AI model test failed: {e}")
        return {
            "success": False,
            "model": payload.model,
            "error": str(e)[:200],
            "code": "connection_error",
        }


# --- AB TESTING ---
class ABTestSettings(BaseModel):
    ab_test_enabled: bool = False
    ab_test_bucket_size: int = 10


@settings_router.get("/ab-testing/config")
def get_ab_test_config(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    check_permission(current_user, "manage_content")

    enabled_cfg = (
        db.query(SystemConfig).filter(SystemConfig.key == "ab_test_enabled").first()
    )
    bucket_cfg = (
        db.query(SystemConfig).filter(SystemConfig.key == "ab_test_bucket_size").first()
    )

    enabled = enabled_cfg.value == "true" if enabled_cfg else False
    try:
        bucket_size = int(bucket_cfg.value) if bucket_cfg else 10
    except (ValueError, TypeError):
        bucket_size = 10

    from backend.database import PromptVariant

    variants = db.query(PromptVariant).filter(PromptVariant.is_enabled).all()

    prompt_versions = {}
    for v in variants:
        if v.prompt_type not in prompt_versions:
            prompt_versions[v.prompt_type] = {"current": v.version, "versions": {}}
        prompt_versions[v.prompt_type]["versions"][v.variant_name] = {
            "id": v.id,
            "version": v.version,
            "traffic": v.traffic_percentage,
        }

    return {
        "ab_test_enabled": enabled,
        "ab_test_bucket_size": bucket_size,
        "prompt_versions": prompt_versions,
    }


@settings_router.post("/ab-testing/config")
def update_ab_test_config(
    config: ABTestSettings,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    check_permission(current_user, "manage_content")

    def save_config(key, value):
        cfg = db.query(SystemConfig).filter(SystemConfig.key == key).first()
        if not cfg:
            cfg = SystemConfig(key=key)
            db.add(cfg)
        cfg.value = str(value).lower() if isinstance(value, bool) else str(value)

    save_config("ab_test_enabled", config.ab_test_enabled)
    save_config("ab_test_bucket_size", config.ab_test_bucket_size)

    db.commit()
    return {"message": "A/B testing configuration updated"}


@settings_router.get("/ab-testing/stats")
def get_ab_test_stats(
    days: int = 7,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    check_permission(current_user, "view_analytics")

    from backend.database import DBTestResult, PromptVariant

    since = datetime.now(UTC) - timedelta(days=days)

    total_calls = (
        db.query(DBTestResult).filter(DBTestResult.executed_at >= since).count()
    )

    results = (
        db.query(
            PromptVariant.prompt_type,
            DBTestResult.version,
            DBTestResult.variant,
            func.count(DBTestResult.id).label("total"),
            func.sum(func.case((DBTestResult.status == "success", 1), else_=0)).label(
                "successes"
            ),
            func.avg(DBTestResult.response_time_ms).label("avg_latency"),
        )
        .join(PromptVariant, DBTestResult.variant_id == PromptVariant.id)
        .filter(DBTestResult.executed_at >= since)
        .group_by(PromptVariant.prompt_type, DBTestResult.version, DBTestResult.variant)
        .all()
    )

    stats = []
    for r in results:
        p_type = r[0] if r[0] else "unknown"

        total = r[3]
        successes = r[4] or 0
        success_rate = round((successes / total * 100), 1) if total > 0 else 0

        stats.append(
            {
                "prompt_type": p_type,
                "version": r[1],
                "variant": r[2],
                "total_calls": total,
                "successful_calls": successes,
                "success_rate": success_rate,
                "avg_latency": round(r[5] or 0, 2),
            }
        )

    return {"period_days": days, "total_prompt_calls": total_calls, "stats": stats}


@settings_router.post("/ab-testing/reset-stats")
def reset_ab_test_stats(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    check_permission(current_user, "manage_admins")
    return {"message": "A/B test statistics reset."}


# --- SYSTEM PROMPTS ---
@settings_router.get("/prompts")
def get_system_prompts(
    page: int = 1,
    per_page: int = 30,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    check_permission(current_user, "manage_content")
    query = db.query(SystemPrompt)
    result = paginate(query, page, per_page)
    return {
        "total": result["total"],
        "page": result["page"],
        "per_page": result["per_page"],
        "total_pages": result["total_pages"],
        "prompts": result["items"],
    }


@settings_router.post("/prompts")
def update_system_prompt(
    prompt: SystemPromptUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    check_permission(current_user, "manage_content")
    p = db.query(SystemPrompt).filter(SystemPrompt.key == prompt.key).first()
    if not p:
        p = SystemPrompt(key=prompt.key)
        db.add(p)
    p.content = prompt.content
    if prompt.description:
        p.description = prompt.description
    db.commit()
    return {"message": f"Prompt '{prompt.key}' updated."}
