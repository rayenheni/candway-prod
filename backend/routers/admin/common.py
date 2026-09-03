import math
from typing import Optional

from fastapi import HTTPException
from pydantic import BaseModel, SecretStr
from sqlalchemy.orm import Query

from backend.database import User
from backend.dependencies import check_admin
from backend.profile_helpers import get_user_admin_permissions, get_user_is_super_admin


class SystemSettings(BaseModel):
    maintenance_mode: Optional[bool] = False
    free_trial: Optional[bool] = True
    platform_fee_percent: Optional[float] = 20.0
    default_language: Optional[str] = "en"

    # SMTP
    smtp_host: Optional[str] = None
    smtp_port: Optional[int] = None
    smtp_username: Optional[str] = None
    smtp_password: Optional[SecretStr] = None

    # AI
    groq_api_key: Optional[SecretStr] = None
    deepseek_api_key: Optional[SecretStr] = None
    gemini_api_key: Optional[SecretStr] = None
    ai_provider: Optional[str] = "groq"
    ai_model: Optional[str] = "groq/compound"
    ai_temperature: Optional[float] = 0.5

    # Local LLM (Ollama)
    use_local_llm: Optional[bool] = False
    local_llm_url: Optional[str] = "http://localhost:11434"
    local_llm_model: Optional[str] = "llama3"

    # Konnect (Payment)
    konnect_wallet_id: Optional[str] = None
    konnect_api_key: Optional[SecretStr] = None

    # Manual Payment Settings
    bank_name: Optional[str] = None
    bank_account_name: Optional[str] = None
    bank_account_number: Optional[str] = None
    bank_iban: Optional[str] = None
    payment_instructions: Optional[str] = None

    # A/B Testing
    ab_test_enabled: Optional[bool] = False
    ab_test_bucket_size: Optional[int] = 10

    # Automation
    automations_enabled: Optional[bool] = True

    # P0-07 FIX: Marketing permissions. Sending bulk email, creating
    # coupons, and managing marketing campaigns are sensitive
    # actions that should NOT be reachable by a "manage_content"
    # admin. Add this permission to any admin role that is allowed
    # to push campaigns to the userbase.
    manage_marketing: Optional[bool] = False

    # Google OAuth
    google_client_id: Optional[SecretStr] = None
    google_client_secret: Optional[SecretStr] = None
    google_enabled: Optional[bool] = False

    # AI Credit Pricing (admin-controlled monetization)
    ai_credit_gating_enabled: Optional[bool] = True
    ai_credit_costs: Optional[dict] = None

    # LinkedIn OAuth


def paginate(
    query: Query,
    page: int = 1,
    per_page: int = 30,
    max_per_page: int = 100,
):
    if per_page > max_per_page:
        per_page = max_per_page
    if page < 1:
        page = 1
    total = query.count()
    items = query.offset((page - 1) * per_page).limit(per_page).all()
    total_pages = max(1, math.ceil(total / per_page))
    return {
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": total_pages,
        "items": items,
    }


def check_permission(user: User, required_perm: str):
    check_admin(user)
    if get_user_is_super_admin(user):
        return True
    admin_perms = get_user_admin_permissions(user)
    if not admin_perms or not admin_perms.strip():
        raise HTTPException(
            status_code=403,
            detail=f"Missing permission: {required_perm}. This admin has no granted permissions.",
        )
    if admin_perms.strip().lower() == "all":
        return True
    perms = [p.strip() for p in admin_perms.split(",")]
    if required_perm not in perms:
        raise HTTPException(
            status_code=403, detail=f"Missing permission: {required_perm}"
        )
    return True
