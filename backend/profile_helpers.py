"""Profile helper functions — single source of truth for reading profile data.

Reads exclusively from role-specific profile tables (CandidateProfile /
RecruiterProfile / AdminProfile). Legacy User columns are no longer
consulted.

All field accesses use getattr() to safely handle missing columns
across different profile types.
"""

from typing import Any, Optional


def get_profile(user) -> Optional[object]:
    """Return the role-appropriate profile for *user*."""
    if user.role == "candidate":
        return getattr(user, "candidate_profile", None) or getattr(
            user, "candidateprofile", None
        )
    elif user.role in ("recruiter", "company", "organization"):
        return getattr(user, "recruiter_profile", None) or getattr(
            user, "recruiterprofile", None
        )
    return None


def _get_recruiter_profile(user) -> Optional[object]:
    return getattr(user, "recruiter_profile", None) or getattr(
        user, "recruiterprofile", None
    )


def _get_candidate_profile(user) -> Optional[object]:
    return getattr(user, "candidate_profile", None) or getattr(
        user, "candidateprofile", None
    )


def _get_admin_profile(user) -> Optional[object]:
    return getattr(user, "admin_profile", None) or getattr(user, "adminprofile", None)


def _safe_str(profile: Any, field: str, default: str = "") -> str:
    return str(getattr(profile, field, default) or default)


def _safe_int(profile: Any, field: str, default: int = 0) -> int:
    val = getattr(profile, field, None)
    return val if val is not None else default


def get_user_name(user) -> str:
    val = _safe_str(get_profile(user), "name")
    return val if val else getattr(user, "name", "") or ""


def get_user_email(user) -> str:
    val = _safe_str(get_profile(user), "email")
    return val if val else getattr(user, "email", "") or ""


def get_user_phone(user) -> str:
    return _safe_str(get_profile(user), "phone")


def get_user_headline(user) -> str:
    return _safe_str(get_profile(user), "headline")


def get_user_bio(user) -> str:
    return _safe_str(get_profile(user), "bio")


def get_user_skills(user) -> str:
    return _safe_str(get_profile(user), "skills")


def get_user_location(user) -> str:
    return _safe_str(get_profile(user), "location")


def get_user_avatar_url(user) -> str:
    return _safe_str(get_profile(user), "avatar_url")


def get_user_linkedin_url(user) -> str:
    return _safe_str(get_profile(user), "linkedin_url")


def get_user_github_url(user) -> str:
    return _safe_str(get_profile(user), "github_url")


def get_user_portfolio_url(user) -> str:
    return _safe_str(get_profile(user), "portfolio_url")


def get_user_languages(user) -> str:
    return _safe_str(get_profile(user), "languages")


def get_user_availability(user) -> str:
    return _safe_str(get_profile(user), "availability")


def get_user_work_preference(user) -> str:
    return _safe_str(get_profile(user), "work_preference")


def get_user_salary_expectation_min(user) -> int:
    return _safe_int(get_profile(user), "salary_expectation_min")


def get_user_salary_expectation_max(user) -> int:
    return _safe_int(get_profile(user), "salary_expectation_max")


def get_user_relocation_willing(user):
    profile = get_profile(user)
    if profile is None:
        return None
    return getattr(profile, "relocation_willing", None)


def get_user_profile_views(user) -> int:
    return _safe_int(get_profile(user), "profile_views")


def get_user_profile_views_growth(user) -> float:
    val = getattr(get_profile(user), "profile_views_growth", None)
    return float(val) if val is not None else 12.0


def get_user_company_name(user) -> str:
    return _safe_str(_get_recruiter_profile(user), "company_name")


def get_user_company_logo_url(user) -> str:
    return _safe_str(_get_recruiter_profile(user), "company_logo_url")


def get_user_company_description(user) -> str:
    return _safe_str(_get_recruiter_profile(user), "company_description")


def get_user_smtp_host(user) -> str:
    return _safe_str(_get_recruiter_profile(user), "smtp_host")


def get_user_smtp_port(user) -> int:
    val = getattr(_get_recruiter_profile(user), "smtp_port", None)
    return val if val is not None else 587


def get_user_smtp_user(user) -> str:
    return _safe_str(_get_recruiter_profile(user), "smtp_user")


def get_user_smtp_password(user) -> str:
    return _safe_str(_get_recruiter_profile(user), "smtp_password")


def get_user_email_settings(user) -> str:
    return _safe_str(_get_recruiter_profile(user), "email_settings")


def get_user_linkedin_settings(user) -> str:
    return _safe_str(_get_recruiter_profile(user), "linkedin_settings")


def get_user_usage_jobs(user) -> int:
    return _safe_int(_get_recruiter_profile(user), "usage_jobs")


def get_user_usage_cvs(user) -> int:
    return _safe_int(_get_recruiter_profile(user), "usage_cvs")


def get_user_usage_ai_interviews(user) -> int:
    return _safe_int(_get_recruiter_profile(user), "usage_ai_interviews")


def get_user_usage_reset_date(user):
    return getattr(_get_recruiter_profile(user), "usage_reset_date", None)


def get_user_candidate_cv_uploads(user) -> int:
    return _safe_int(_get_candidate_profile(user), "candidate_cv_uploads_this_month")


def get_user_candidate_ai_analyses(user) -> int:
    return _safe_int(_get_candidate_profile(user), "candidate_ai_analyses_this_month")


def get_user_candidate_pdf_downloads(user) -> int:
    return _safe_int(_get_candidate_profile(user), "candidate_pdf_downloads_this_month")


def get_user_candidate_usage_reset_date(user):
    return getattr(_get_candidate_profile(user), "candidate_usage_reset_date", None)


def get_user_tier(user) -> str:
    """Return the normalized access tier for the user's role.

    Candidates derive their tier from their assigned SubscriptionPlan.
    Recruiters/company accounts continue to derive their tier from the
    role-specific RecruiterProfile.
    """
    role = str(getattr(user, "role", "") or "").lower().strip()

    # Admins are not subscription-limited.
    if role == "admin":
        return "admin"

    # Candidate subscriptions are represented by SubscriptionPlan.
    if role == "candidate":
        plan = getattr(user, "current_plan", None)

        if plan is not None:
            slug = str(getattr(plan, "slug", "") or "").lower().strip()

            if slug in ("candidate-pro", "pro-candidate"):
                return "pro"

            if slug in ("candidate-enterprise", "enterprise-candidate"):
                return "enterprise"

            if slug.startswith("candidate-"):
                return "free" if "free" in slug else slug.removeprefix("candidate-")

            plan_group = str(getattr(plan, "plan_group", "") or "").lower().strip()
            if plan_group:
                return plan_group

        # No assigned candidate plan means Free.
        return "free"

    # Recruiter/company/organization accounts retain their existing
    # role-specific profile tier.
    return _safe_str(_get_recruiter_profile(user), "tier") or "free"


def get_user_subscription_status(user) -> str:
    return _safe_str(_get_recruiter_profile(user), "subscription_status")


def get_user_subscription_plan(user) -> str:
    return _safe_str(_get_recruiter_profile(user), "subscription_plan")


def get_user_subscription_end(user):
    return getattr(_get_recruiter_profile(user), "subscription_end", None)


def get_user_admin_permissions(user) -> str:
    profile = _get_admin_profile(user)

    if profile is not None:
        return _safe_str(profile, "permissions")

    return str(getattr(user, "admin_permissions", "") or "")


def get_user_is_super_admin(user) -> bool:
    profile = _get_admin_profile(user)

    if profile is not None:
        val = getattr(profile, "is_super_admin", None)
        if val is not None:
            return bool(val)

    return bool(getattr(user, "is_super_admin", False))
