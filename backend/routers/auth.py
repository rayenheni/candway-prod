import secrets
from datetime import UTC, datetime, timedelta
from typing import Optional

import jose.jwt as jwt
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Query,
    Request,
    Response,
)
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend import schemas
from backend.client_ip import get_client_ip
from backend.config import get_settings
from backend.database import (
    Application,
    BatchJob,
    Company,
    CompanyMember,
    ConsentLog,
    EmailVerification,
    LoginAttempt,
    User,
)
from backend.dependencies import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    ALGORITHM,
    SECRET_KEY,
    create_access_token,
    generate_interview_token,
    get_current_user,
    get_db,
    oauth2_scheme,
    pwd_context,
    verify_interview_token,
)
from backend.email_service import email_service
from backend.logger import logger
from backend.password_validator import validate_email, validate_password
from backend.profile_helpers import (
    get_profile,
    get_user_admin_permissions,
    get_user_avatar_url,
    get_user_bio,
    get_user_company_logo_url,
    get_user_company_name,
    get_user_email,
    get_user_github_url,
    get_user_headline,
    get_user_is_super_admin,
    get_user_linkedin_url,
    get_user_location,
    get_user_name,
    get_user_phone,
    get_user_portfolio_url,
    get_user_skills,
    get_user_subscription_plan,
    get_user_subscription_status,
    get_user_tier,
)
from backend.redis_rate_limiter import rate_limit as rate_limit_dep
from backend.schemas import (
    GuestLogin,
    GuestLoginResponse,
    OrgSignup,
    OrgSignupResponse,
    ResendOTPRequest,
    Token,
    UserLogin,
    UserSignup,
    UserUpdate,
    VerifyOTPRequest,
)

router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()


def _utcnow():
    return datetime.now(UTC).replace(tzinfo=None)


# P1-08 FIX: exponential backoff schedule per (email, IP) pair.
# ``N`` failed attempts in the last hour forces the next attempt
# to wait ``BACKOFF_SECONDS[N]`` seconds.  Index 0 = first
# failure, no delay.  Index 5+ = saturated; caller should be
# hitting the 1-hour lockout by then.
LOGIN_BACKOFF_SECONDS = [0, 1.0, 2.0, 4.0, 8.0, 16.0, 30.0]
# Per-IP failed-attempt count that triggers an IP-wide 429
# (independent of the per-account lockout).
LOGIN_IP_FAIL_THRESHOLD = 20
# Per-account failed-attempt count that triggers a 1-hour lock.
LOGIN_ACCOUNT_FAIL_THRESHOLD = 5


def _get_client_ip(request: Request) -> str:
    """Best-effort client IP for rate limiting / audit.

    Delegates to the shared trusted-proxy-aware resolver so a spoofed
    ``X-Forwarded-For`` header cannot bypass login backoff / lockout.
    Behind nginx the real client IP is the rightmost XFF entry
    (see backend/client_ip.py). Set ``CANDWAY_TRUST_XFF=0`` to ignore the
    header entirely and use the transport-level peer.
    """
    return get_client_ip(
        request.headers.get("X-Forwarded-For"),
        request.client.host if request.client else None,
    )


def _check_login_backoff(db: Session, email: str, ip: str) -> None:
    """Raise ``HTTPException(429)`` if the next login attempt for
    this ``(email, IP)`` is too soon after a recent failure.

    The exponential backoff schedule is::

        failure # | min wait
        ----------+---------
              0   |  0  s
              1   |  0.5 s
              2   |  1  s
              3   |  2  s
              4   |  4  s
              5   |  8  s
              6+  | 16  s

    Once the per-account threshold (5) is hit the
    ``is_locked``/``lockout_until`` branch takes over and the
    user is locked out for an hour — backoff is the smooth
    ramp, lockout is the cliff.
    """
    hour_ago = _utcnow() - timedelta(hours=1)
    recent_failures = (
        db.query(LoginAttempt)
        .filter(
            LoginAttempt.email == email,
            LoginAttempt.ip_address == ip,
            not LoginAttempt.success,
            LoginAttempt.timestamp > hour_ago,
        )
        .order_by(LoginAttempt.timestamp.desc())
        .count()
    )
    if recent_failures == 0:
        return
    idx = min(recent_failures, len(LOGIN_BACKOFF_SECONDS) - 1)
    required = LOGIN_BACKOFF_SECONDS[idx]
    if required <= 0:
        return
    last_failure = (
        db.query(LoginAttempt)
        .filter(
            LoginAttempt.email == email,
            LoginAttempt.ip_address == ip,
            not LoginAttempt.success,
        )
        .order_by(LoginAttempt.timestamp.desc())
        .first()
    )
    if not last_failure:
        return
    elapsed = (_utcnow() - last_failure.timestamp).total_seconds()
    if elapsed < required:
        retry_after = max(1, int(required - elapsed + 0.999))
        raise HTTPException(
            status_code=429,
            detail=(f"Too many failed attempts. Try again in {retry_after}s."),
            headers={"Retry-After": str(retry_after)},
        )


def _can_log_consent(db: Session) -> bool:
    """Best-effort guard for environments where consent_logs table is not migrated yet."""
    try:
        return inspect(db.bind).has_table("consent_logs")
    except Exception:
        return False


def _consent_version(db: Session) -> str:
    """Read the live terms/privacy consent version from system_config.

    Bug B-5: the consent version used to be hardcoded to "v1.0" so bumping
    the legal terms required a deploy. Admins can now set
    ``terms_consent_version`` in SystemConfig (admin settings) and new
    signups record the current version. Defaults to "v1.0" for
    installations that have never configured it.
    """
    try:
        from backend.database import SystemConfig

        row = (
            db.query(SystemConfig)
            .filter(SystemConfig.key == "terms_consent_version")
            .first()
        )
        if row and row.value:
            return row.value
    except Exception as e:
        logger.warning(f"Failed to read consent version: {e}")
    return "v1.0"


def _send_interview_invite_on_claim(db: Session, user: User):
    """Send interview invitation to candidate after they claim their account."""
    try:
        # Find applications for this user that need invitations
        apps = (
            db.query(Application)
            .filter(
                Application.user_id == user.id,
                Application.status.in_(["imported", "invited", "pending"]),
            )
            .all()
        )

        if not apps:
            return

        for app in apps:
            # Get campaign info
            campaign = None
            if app.batch_id:
                campaign = (
                    db.query(BatchJob).filter(BatchJob.id == app.batch_id).first()
                )

            # Generate interview token
            token_data = generate_interview_token(app.id)
            token = token_data["token"]
            interview_url = (
                f"{settings.frontend_url}/auth/interview-access?app_id={app.id}&token={token}"
            )

            campaign_title = campaign.title if campaign else "the position"
            target_role = (
                campaign.target_role
                if campaign and campaign.target_role
                else campaign_title
            )

            subject = f"🎉 Welcome! Complete Your AI Interview for {target_role}"
            body = f"""
            <div style="font-family:'Segoe UI',Arial,sans-serif;max-width:600px;margin:0 auto;background:#fff;border-radius:16px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,0.08)">
                <div style="background:linear-gradient(135deg,#10b981,#059669);padding:36px 32px;text-align:center">
                    <h1 style="color:#fff;margin:0;font-size:26px;font-weight:800">🎉 Account Created!</h1>
                    <p style="color:rgba(255,255,255,0.8);margin:8px 0 0;font-size:15px">Ready for Your AI Interview</p>
                </div>
                <div style="padding:36px 32px">
                    <p style="font-size:16px;color:#1e293b;margin:0 0 12px">Dear <strong>{get_user_name(user) or "Candidate"}</strong>,</p>
                    <p style="font-size:15px;color:#475569;line-height:1.7;margin:0 0 24px">
                        Your account has been successfully created! You can now complete your AI interview for the
                        <strong>{target_role}</strong> position.
                    </p>
                    <p style="font-size:15px;color:#475569;line-height:1.7;margin:0 0 32px">
                        The interview takes approximately <strong>20-30 minutes</strong> and can be completed
                        at your convenience from any device.
                    </p>
                    <div style="text-align:center;margin:32px 0">
                        <a href="{interview_url}"
                           style="background:linear-gradient(135deg,#10b981,#059669);color:#fff;padding:16px 40px;
                                  text-decoration:none;border-radius:12px;font-weight:700;font-size:16px;
                                  display:inline-block;box-shadow:0 8px 24px rgba(16,185,129,0.35)">
                            Start Your AI Interview →
                        </a>
                    </div>
                    <p style="font-size:13px;color:#94a3b8;margin:0">
                        Best regards,<br><strong>The Recruiting Team</strong> via Candway Platform
                    </p>
                </div>
            </div>
            """

            email_service.send_email(user.email, subject, body)
            app.status = "invited"
            app.invited_at = _utcnow()
            logger.info(f"Auto-sent interview invite to {user.email} for app {app.id}")

        db.commit()
    except Exception as e:
        logger.error(f"Failed to send auto-invite on claim: {e}")


def _safe_send_verification_email(email: str, token: str, code: str = None) -> None:
    """Never let async background email failures break request lifecycle."""
    try:
        if code:
            email_service.send_otp_email(email, code)
        else:
            email_service.send_verification_email(email, token)
    except Exception as e:
        logger.error(f"Verification email send failed for {email}: {e}")


def _generate_otp(length: int = 6) -> str:
    import secrets

    return str(secrets.randbelow(10**length)).zfill(length)


def _set_auth_cookie(
    response: Response, access_token: str, expires_minutes: int
) -> None:
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        samesite="lax",
        secure=settings.is_prod,
        max_age=int(expires_minutes * 60),
        path="/",
    )
    # Non-httponly session marker so frontend JS can detect login state
    response.set_cookie(
        key="logged_in",
        value="true",
        httponly=False,
        samesite="lax",
        secure=settings.is_prod,
        max_age=int(expires_minutes * 60),
        path="/",
    )


def _set_csrf_cookie(response: Response) -> str:
    csrf_token = secrets.token_urlsafe(32)
    response.set_cookie(
        key="csrf_token",
        value=csrf_token,
        httponly=False,  # Needs to be readable by JS to be sent back in header
        samesite="lax",
        secure=settings.is_prod,
        path="/",
    )
    return csrf_token


def _visible_access_token(access_token: str) -> str:
    return access_token


@router.post("/signup")
def signup(
    user: UserSignup,
    request: Request,
    response: Response,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _rate_limit: None = Depends(rate_limit_dep(max_requests=5, window_seconds=3600)),
):
    if not settings.enable_registration:
        raise HTTPException(
            status_code=403, detail="Registration is currently disabled"
        )

    validate_email(user.email)
    validate_password(user.password)

    # Sanitize email
    user.email = user.email.lower().strip()
    db_user = db.query(User).filter(User.email == user.email).first()

    # Handle Shadow Users (invited by recruiter but not signed up)
    if db_user:
        if db_user.hashed_password is None:
            # Claim Account Logic
            db_user.hashed_password = pwd_context.hash(user.password)
            # Write to role-specific profile (SSOT for profile fields)
            if hasattr(db_user, "candidate_profile") and db_user.candidate_profile:
                db_user.candidate_profile.name = user.name or db_user.name
            if hasattr(db_user, "recruiter_profile") and db_user.recruiter_profile:
                db_user.recruiter_profile.name = user.name or db_user.name
            if hasattr(db_user, "candidate_profile") and db_user.candidate_profile:
                db_user.candidate_profile.phone = user.phone or db_user.phone
            if hasattr(db_user, "recruiter_profile") and db_user.recruiter_profile:
                db_user.recruiter_profile.phone = user.phone or db_user.phone
            if hasattr(db_user, "candidate_profile") and db_user.candidate_profile:
                db_user.candidate_profile.headline = user.headline or db_user.headline
            if hasattr(db_user, "recruiter_profile") and db_user.recruiter_profile:
                db_user.recruiter_profile.headline = user.headline or db_user.headline
            if hasattr(db_user, "candidate_profile") and db_user.candidate_profile:
                db_user.candidate_profile.location = user.location or db_user.location
            # SECURITY FIX (CRIT-04): NEVER accept role from client during account claim.
            # The role is permanently locked to the one assigned at invitation time.
            # Removing: `if user.role: db_user.role = user.role`

            db.commit()
            db.refresh(db_user)

            # Auto-send interview invitation to candidate
            _send_interview_invite_on_claim(db, db_user)

            # Send Verification Email for claimed account
            token = secrets.token_urlsafe(32)
            code = _generate_otp()
            verification = EmailVerification(
                user_id=db_user.id,
                token=token,
                code=code,
                expires_at=_utcnow() + timedelta(hours=24),
            )
            db.add(verification)

            # GDPR consent logging is best-effort for partially migrated databases.
            if _can_log_consent(db):
                consent = ConsentLog(
                    user_id=db_user.id,
                    agreement_type="terms_and_privacy",
                    version=_consent_version(db),
                    ip_address=request.client.host if request.client else "0.0.0.0",
                    user_agent=request.headers.get("user-agent", "signup_flow")[:255],
                )
                db.add(consent)
            db.commit()

            background_tasks.add_task(
                _safe_send_verification_email, db_user.email, token, code
            )

            access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
            access_token = create_access_token(
                data={
                    "sub": db_user.email,
                    "role": db_user.role,
                    "id": db_user.id,
                    "name": get_user_name(db_user)
                    or get_user_email(db_user).split("@")[0],
                },
                expires_delta=access_token_expires,
            )
            _set_auth_cookie(response, access_token, ACCESS_TOKEN_EXPIRE_MINUTES)
            return {
                "access_token": _visible_access_token(access_token),
                "token_type": "bearer",
                "role": db_user.role,
                "id": db_user.id,
                "name": get_user_name(db_user),
            }
        else:
            raise HTTPException(status_code=400, detail="Email already registered")

    hashed_password = pwd_context.hash(user.password)
    # SECURITY FIX: Restrict roles allowed from client input to prevent escalation
    # Only allow 'candidate' and 'recruiter'. 'admin' and 'mentor' must be assigned by system.
    allowed_roles = ["candidate", "recruiter"]
    requested_role = user.role.lower().strip() if user.role else "candidate"
    final_role = requested_role if requested_role in allowed_roles else "candidate"

    new_user = User(
        email=user.email,
        hashed_password=hashed_password,
        role=final_role,
        email_verified=False,
    )
    db.add(new_user)

    try:
        db.commit()
        db.refresh(new_user)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Email already registered")

    # Create role-specific profile (single source of truth for profile data)
    from backend.models.evaluation.profile import CandidateProfile, RecruiterProfile

    if final_role == "recruiter":
        profile = RecruiterProfile(
            user_id=new_user.id,
            name=user.name,
            phone=user.phone,
            email=user.email,
            company_name=user.company_name,
            email_settings="{}",
        )
        setattr(new_user, "_company_id", None)  # tenant set during company onboarding
    else:
        profile = CandidateProfile(
            user_id=new_user.id,
            name=user.name,
            phone=user.phone,
            email=user.email,
            location=user.location,
            headline=user.headline,
        )
    db.add(profile)
    db.commit()

    # Grant welcome starter credits (20 for candidate, 50 for recruiter)
    try:
        from backend.credit_service import grant_credits
        grant_credits(
            db,
            new_user,
            20 if final_role == "candidate" else 50,
            resource="starter_bonus",
            reference_type="signup",
            reference_id=new_user.id,
            note="Welcome starter credits",
        )
    except Exception as err:
        logger.warning(f"Failed to grant starter credits for user {new_user.id}: {err}")


    # SECURITY FIX: Generate Email Verification Token
    token = secrets.token_urlsafe(32)
    code = _generate_otp()
    verification = EmailVerification(
        user_id=new_user.id,
        token=token,
        code=code,
        expires_at=_utcnow() + timedelta(hours=24),
    )
    db.add(verification)

    # GDPR consent logging is best-effort for partially migrated databases.
    if _can_log_consent(db):
        consent = ConsentLog(
            user_id=new_user.id,
            agreement_type="terms_and_privacy",
            version=_consent_version(db),
            ip_address=request.client.host if request.client else "0.0.0.0",
            user_agent=request.headers.get("user-agent", "signup_flow")[:255],
        )
        db.add(consent)

    db.commit()

    # Send Verification Email
    background_tasks.add_task(
        _safe_send_verification_email, new_user.email, token, code
    )

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={
            "sub": new_user.email,
            "role": new_user.role,
            "id": new_user.id,
            "name": get_user_name(new_user) or get_user_email(new_user).split("@")[0],
        },
        expires_delta=access_token_expires,
    )
    _set_auth_cookie(response, access_token, ACCESS_TOKEN_EXPIRE_MINUTES)
    return {
        "access_token": _visible_access_token(access_token),
        "token_type": "bearer",
        "role": new_user.role,
        "id": new_user.id,
        "name": get_user_name(new_user),
        "email_verification_required": True,
    }


@router.post("/signup/org", response_model=OrgSignupResponse)
def signup_org(
    data: OrgSignup,
    request: Request,
    response: Response,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _rate_limit: None = Depends(rate_limit_dep(max_requests=5, window_seconds=3600)),
):
    """Self-service organization (company) signup.

    Atomically creates a Company (tier='free'), the organization admin
    user (role='company'), their RecruiterProfile, and the
    CompanyMember ('owner') that ties them together. The org admin is
    tenant-scoped and NEVER a platform admin.
    """
    if not settings.enable_registration:
        raise HTTPException(
            status_code=403, detail="Registration is currently disabled"
        )

    company_name = (data.company_name or "").strip()
    admin_name = (data.admin_name or "").strip()
    admin_email = data.admin_email.lower().strip()
    if not company_name or not admin_name or not admin_email:
        raise HTTPException(status_code=400, detail="All fields are required")
    validate_email(admin_email)
    validate_password(data.admin_password)

    # Reject any attempt to register an email already in use
    if db.query(User).filter(User.email == admin_email).first():
        raise HTTPException(status_code=400, detail="Email already registered")

    slug = (data.slug or company_name.lower().replace(" ", "-")).strip()
    if db.query(Company).filter(Company.slug == slug).first():
        # Ensure uniqueness by suffixing with a short random id
        slug = f"{slug}-{secrets.token_hex(3)}"

    hashed_password = pwd_context.hash(data.admin_password)

    # ── 1) Company ────────────────────────────────────────────────
    billing_email = (data.billing_email or "").strip() or None
    billing_address = (data.billing_address or "").strip() or None
    tax_id = (data.tax_id or "").strip() or None
    kyb_status = "pending" if (billing_email or billing_address or tax_id) else None
    company = Company(
        name=company_name,
        slug=slug,
        domain=data.domain,
        tier="free",
        subscription_status="active",
        max_users=10,
        max_jobs=50,
        max_ai_interviews=500,
        is_active=True,
        billing_email=billing_email,
        billing_address=billing_address,
        tax_id=tax_id,
        kyb_status=kyb_status,
    )
    db.add(company)
    db.flush()  # obtain company.id

    # ── 2) Org admin user (role locked to 'company') ──────────────
    org_admin = User(
        email=admin_email,
        hashed_password=hashed_password,
        role="company",
        email_verified=False,
    )
    db.add(org_admin)
    db.flush()  # obtain user.id

    from backend.models.evaluation.profile import RecruiterProfile

    profile = RecruiterProfile(
        user_id=org_admin.id,
        name=admin_name,
        email=admin_email,
        company_name=company_name,
        company_id=company.id,
        email_settings="{}",
    )
    db.add(profile)

    # ── 3) Membership: org admin owns the company ──────────────────
    membership = CompanyMember(
        company_id=company.id,
        user_id=org_admin.id,
        role="owner",
        is_active=True,
        joined_at=_utcnow(),
    )
    db.add(membership)
    setattr(org_admin, "_company_id", company.id)
    setattr(org_admin, "_company_role", "owner")

    # ── 4) Email verification ──────────────────────────────────────
    token = secrets.token_urlsafe(32)
    code = _generate_otp()
    db.add(
        EmailVerification(
            user_id=org_admin.id,
            token=token,
            code=code,
            expires_at=_utcnow() + timedelta(hours=24),
        )
    )

    try:
        db.commit()
        db.refresh(org_admin)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Registration failed. Try again.")

    # ── 5) GDPR consent logging (best-effort, AFTER commit so that
    #        inspect(db.bind) in _can_log_consent never interferes with
    #        the in-flight signup transaction) ──────────────────────
    if _can_log_consent(db):
        try:
            db.add(
                ConsentLog(
                    user_id=org_admin.id,
                    agreement_type="terms_and_privacy",
                    version=_consent_version(db),
                    ip_address=request.client.host if request.client else "0.0.0.0",
                    user_agent=request.headers.get("user-agent", "org_signup_flow")[
                        :255
                    ],
                )
            )
            db.commit()
        except Exception as _e:
            db.rollback()
            logger.warning(f"Failed to log org signup consent: {_e}")

    background_tasks.add_task(_safe_send_verification_email, admin_email, token, code)

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={
            "sub": admin_email,
            "role": org_admin.role,
            "id": org_admin.id,
            "name": admin_name,
        },
        expires_delta=access_token_expires,
    )
    _set_auth_cookie(response, access_token, ACCESS_TOKEN_EXPIRE_MINUTES)
    _set_csrf_cookie(response)
    return {
        "access_token": _visible_access_token(access_token),
        "token_type": "bearer",
        "role": org_admin.role,
        "id": org_admin.id,
        "name": admin_name,
        "email_verification_required": True,
        "company_id": company.id,
    }


@router.post("/verify-otp")
def verify_otp(request: VerifyOTPRequest, db: Session = Depends(get_db)):
    email = request.email
    code = request.code

    # Rate limit: 5 failed OTP attempts per hour per email
    from backend.database import LoginAttempt

    hour_ago = _utcnow() - timedelta(hours=1)
    recent_failures = (
        db.query(LoginAttempt)
        .filter(
            LoginAttempt.email == email.lower().strip(),
            not LoginAttempt.success,
            LoginAttempt.ip_address == "otp_failure",
            LoginAttempt.timestamp > hour_ago,
        )
        .count()
    )
    if recent_failures >= 5:
        logger.warning(f"OTP rate limit exceeded for {email}")
        raise HTTPException(
            status_code=429, detail="Too many OTP attempts. Try again later."
        )

    user = db.query(User).filter(User.email == email.lower().strip()).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    verification = (
        db.query(EmailVerification)
        .filter(EmailVerification.user_id == user.id)
        .order_by(EmailVerification.expires_at.desc())
        .first()
    )

    if not verification:
        raise HTTPException(status_code=400, detail="No verification code found")

    if verification.verified:
        raise HTTPException(status_code=409, detail="Email already verified")

    if _utcnow() > verification.expires_at:
        raise HTTPException(status_code=400, detail="Verification code expired")

    if verification.code != code:
        # Track failed OTP attempt
        attempt = LoginAttempt(
            email=email.lower().strip(),
            success=False,
            ip_address="otp_failure",
            timestamp=_utcnow(),
        )
        db.add(attempt)
        db.commit()
        logger.warning(f"Failed OTP attempt for {email}: invalid code provided")
        raise HTTPException(status_code=400, detail="Invalid verification code")

    # Success
    verification.verified = True
    user.email_verified = True
    db.commit()

    return {"message": "Email verified successfully"}


@router.post("/resend-otp")
def resend_otp(
    request: ResendOTPRequest,
    background_tasks: BackgroundTasks = None,
    db: Session = Depends(get_db),
):
    from backend.database import LoginAttempt

    email = request.email.lower().strip()
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.email_verified:
        raise HTTPException(status_code=409, detail="Email already verified")

    # Bug B-25 / U-09: /resend-otp previously had NO rate limit or
    # cooldown, letting an attacker (or a frustrated user) trigger
    # unlimited verification emails. We now enforce both a 60-second
    # cooldown on the most recent code and a 5-resends-per-hour cap
    # tracked via LoginAttempt, mirroring the /verify-otp guard.
    COOLDOWN_SECONDS = 60
    MAX_RESENDS_PER_HOUR = 5

    last_resend = (
        db.query(EmailVerification)
        .filter(EmailVerification.user_id == user.id)
        .order_by(EmailVerification.expires_at.desc())
        .first()
    )
    if last_resend and last_resend.expires_at:
        # expires_at is set 24h after creation; reverse it to a
        # created_at approx so we can compute cooldown.
        from datetime import timezone

        approx_created = last_resend.expires_at - timedelta(hours=24)
        if approx_created.tzinfo is None:
            approx_created = approx_created.replace(tzinfo=timezone.utc)
        now = _utcnow()
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        seconds_since_last = (now - approx_created).total_seconds()
        if seconds_since_last < COOLDOWN_SECONDS:
            retry_after = int(COOLDOWN_SECONDS - seconds_since_last)
            raise HTTPException(
                status_code=429,
                detail=(
                    f"Please wait {retry_after}s before requesting a "
                    f"new verification code."
                ),
                headers={"Retry-After": str(retry_after)},
            )

    hour_ago = _utcnow() - timedelta(hours=1)
    recent_resends = (
        db.query(LoginAttempt)
        .filter(
            LoginAttempt.email == email,
            not LoginAttempt.success,
            LoginAttempt.ip_address == "otp_resend",
            LoginAttempt.timestamp > hour_ago,
        )
        .count()
    )
    if recent_resends >= MAX_RESENDS_PER_HOUR:
        raise HTTPException(
            status_code=429,
            detail="Too many resend requests. Try again later.",
        )

    # Generate new code
    token = secrets.token_urlsafe(32)
    code = _generate_otp()

    verification = EmailVerification(
        user_id=user.id,
        token=token,
        code=code,
        expires_at=_utcnow() + timedelta(hours=24),
    )
    db.add(verification)

    # Track this resend against the hourly cap. Successful resends
    # are recorded as failures here only to participate in the
    # counter — the LoginAttempt.success flag is otherwise unused
    # for this codepath.
    db.add(
        LoginAttempt(
            email=email,
            success=False,
            ip_address="otp_resend",
            timestamp=_utcnow(),
        )
    )
    db.commit()

    background_tasks.add_task(_safe_send_verification_email, user.email, token, code)

    return {"message": "Verification code resent"}


@router.post("/resend-verification")
def resend_verification(
    request: ResendOTPRequest,
    background_tasks: BackgroundTasks = None,
    db: Session = Depends(get_db),
):
    """Re-send a link-based email verification (used by org-created members)."""
    from backend.database import LoginAttempt

    email = request.email.lower().strip()
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.email_verified:
        raise HTTPException(status_code=409, detail="Email already verified")

    # Mirrors the /resend-otp guard: 60s cooldown + 5 resends/hour.
    COOLDOWN_SECONDS = 60
    MAX_RESENDS_PER_HOUR = 5

    last_resend = (
        db.query(EmailVerification)
        .filter(EmailVerification.user_id == user.id)
        .order_by(EmailVerification.expires_at.desc())
        .first()
    )
    if last_resend and last_resend.expires_at:
        from datetime import timezone

        approx_created = last_resend.expires_at - timedelta(hours=24)
        if approx_created.tzinfo is None:
            approx_created = approx_created.replace(tzinfo=timezone.utc)
        now = _utcnow()
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        seconds_since_last = (now - approx_created).total_seconds()
        if seconds_since_last < COOLDOWN_SECONDS:
            retry_after = int(COOLDOWN_SECONDS - seconds_since_last)
            raise HTTPException(
                status_code=429,
                detail=(
                    f"Please wait {retry_after}s before requesting a "
                    f"new verification link."
                ),
                headers={"Retry-After": str(retry_after)},
            )

    hour_ago = _utcnow() - timedelta(hours=1)
    recent_resends = (
        db.query(LoginAttempt)
        .filter(
            LoginAttempt.email == email,
            not LoginAttempt.success,
            LoginAttempt.ip_address == "verification_resend",
            LoginAttempt.timestamp > hour_ago,
        )
        .count()
    )
    if recent_resends >= MAX_RESENDS_PER_HOUR:
        raise HTTPException(
            status_code=429,
            detail="Too many resend requests. Try again later.",
        )

    token = secrets.token_urlsafe(32)

    db.add(
        EmailVerification(
            user_id=user.id,
            token=token,
            code=None,
            expires_at=_utcnow() + timedelta(hours=24),
        )
    )
    db.add(
        LoginAttempt(
            email=email,
            success=False,
            ip_address="verification_resend",
            timestamp=_utcnow(),
        )
    )
    db.commit()

    background_tasks.add_task(_safe_send_verification_email, user.email, token)

    return {"message": "Verification link sent"}


@router.post("/guest-login", response_model=GuestLoginResponse)
async def guest_login(
    guest: GuestLogin, response: Response, db: Session = Depends(get_db)
):
    """
    Zero-Friction: Login via HMAC token for invited candidates.
    Returns a limited-time JWT without requiring a password.
    """
    if not await verify_interview_token(guest.app_id, guest.token):
        logger.warning(f"Guest login failed: Invalid token for AppID {guest.app_id}")
        raise HTTPException(status_code=401, detail="Invalid interview link")

    app = db.query(Application).filter(Application.id == guest.app_id).first()
    if not app:
        raise HTTPException(
            status_code=404, detail="Application or Candidate reference not found"
        )

    # Find candidate associated with this app (optional for guests)
    user = (
        db.query(User).filter(User.id == app.user_id).first() if app.user_id else None
    )
    if not user:
        user = db.query(User).filter(User.email == app.email).first()

    # Generate a guest session with configurable expiry
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    if user:
        # Link user to app if not linked (for existing users found by email)
        if not app.user_id:
            app.user_id = user.id
            db.commit()
        logger.info(f"Guest login successful for {user.email} (AppID {guest.app_id})")
        token_data = {
            "sub": user.email,
            "role": user.role,
            "id": user.id,
            "guest": True,
            "scope": "interview",
            "app_id": app.id,
        }
    else:
        logger.info(
            f"True Guest login successful for AppID {guest.app_id} (No User Record)"
        )
        # For non-registered guests, we use a special 'guest_ID' sub to allow lookup by ID in dependencies
        token_data = {
            "sub": f"guest_{app.id}",
            "role": "candidate",
            "id": None,
            "guest": True,
            "scope": "interview",
            "app_id": app.id,
        }

    access_token = create_access_token(
        data=token_data, expires_delta=access_token_expires
    )
    _set_auth_cookie(response, access_token, ACCESS_TOKEN_EXPIRE_MINUTES)
    _set_csrf_cookie(response)

    # Bug U-07: previously the guest-login response told the
    # candidate "you're in" but gave no hint of where to go next,
    # so the redirect-to-interview logic on the client relied on
    # fragile URL parameter detection. We now return an explicit
    # ``redirect`` URL so the client doesn't have to guess.
    #
    # Decision matrix:
    #   * Status in (invited, imported, pending) with a usable
    #     interview token -> push them straight into the interview.
    #   * Anything else -> candidate dashboard.
    if (app.interview_state or "").lower() == "completed":
        redirect = f"/candidate/interview-analysis?application_id={app.id}"
    else:
        redirect = f"/interviews/room/{app.id}"

    return {
        "access_token": _visible_access_token(access_token),
        "token_type": "bearer",
        "role": user.role if user else "candidate",
        "name": get_user_name(user) if user else "Guest Candidate",
        "email": user.email if user else app.email,
        "redirect": redirect,
        "application_id": app.id,
    }


@router.post("/login", response_model=Token)
def login(
    user: UserLogin,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    _rate_limit: None = Depends(rate_limit_dep(max_requests=10, window_seconds=60)),
):
    user.email = user.email.lower().strip()
    client_ip = _get_client_ip(request)

    # P1-08 FIX: exponential backoff. Done BEFORE the user lookup
    # so even non-existent accounts throttle, preventing the
    # attacker from spraying emails to discover valid accounts
    # (no timing difference between existing and non-existing
    # accounts on the backoff path).
    _check_login_backoff(db, user.email, client_ip)

    db_user = db.query(User).filter(User.email == user.email).first()
    logger.debug(
        f"Login attempt for {user.email}, found user: {db_user.email if db_user else 'None'}, role: {db_user.role if db_user else 'N/A'}"
    )

    # SECURITY FIX: Reject suspended/deleted accounts
    if db_user and db_user.deleted_at is not None:
        logger.warning(f"Login attempt for suspended account: {user.email}")
        raise HTTPException(
            status_code=403,
            detail="This account has been suspended. Contact support for assistance.",
        )

    # SECURITY FIX: Check for account lockout
    if db_user:
        if db_user.is_locked:
            if db_user.lockout_until and db_user.lockout_until > _utcnow():
                logger.warning(f"Failed login attempt for LOCKED account: {user.email}")
                raise HTTPException(
                    status_code=403,
                    detail="Account locked due to too many failed attempts.",
                )
            else:
                # Lock expired
                db_user.is_locked = False
                db_user.lockout_until = None
                db.commit()

    # CRITICAL: Email verification is MANDATORY for all non-admin users.
    # This prevents impersonation and spam account creation.
    if db_user and db_user.role != "admin" and not db_user.email_verified:
        raise HTTPException(
            status_code=403,
            detail="Email not verified. Please check your inbox for the verification link.",
        )

    # ROLE VERIFICATION FIX
    if db_user and user.required_role and db_user.role != user.required_role:
        logger.warning(
            f"Role mismatch: User {user.email} (role: {db_user.role}) attempted to login as {user.required_role}"
        )
        raise HTTPException(
            status_code=403,
            detail=f"Access denied. This account is registered as a {db_user.role}. Please use the correct login page.",
        )

    try:
        from passlib.exc import UnknownHashError

        password_valid = bool(
            db_user
            and db_user.hashed_password
            and pwd_context.verify(user.password, db_user.hashed_password)
        )
        logger.debug(f"Password valid for {user.email}: {password_valid}")
    except UnknownHashError:
        logger.warning(f"Legacy or unknown password hash format for user {user.email}")
        password_valid = False
    except Exception as e:
        logger.error(f"Password verification error for {user.email}: {e}")
        password_valid = False
    if not password_valid:
        # SECURITY FIX: Track failed login attempts
        attempt = LoginAttempt(
            email=user.email,
            success=False,
            timestamp=_utcnow(),
            ip_address=client_ip,
        )
        db.add(attempt)

        # Check failed attempts in last hour
        hour_ago = _utcnow() - timedelta(hours=1)
        failed_count = (
            db.query(LoginAttempt)
            .filter(
                LoginAttempt.email == user.email,
                not LoginAttempt.success,
                LoginAttempt.timestamp > hour_ago,
            )
            .count()
        )

        # Check failed attempts from IP
        failed_ip_count = (
            db.query(LoginAttempt)
            .filter(
                LoginAttempt.ip_address == client_ip,
                not LoginAttempt.success,
                LoginAttempt.timestamp > hour_ago,
            )
            .count()
        )

        if failed_ip_count >= LOGIN_IP_FAIL_THRESHOLD:
            db.commit()
            raise HTTPException(
                status_code=429,
                detail="Too many failed login attempts from this IP. Try again later.",
            )

        if failed_count >= LOGIN_ACCOUNT_FAIL_THRESHOLD and db_user:
            db_user.is_locked = True
            db_user.lockout_until = _utcnow() + timedelta(hours=1)
            db.commit()

        db.commit()
        raise HTTPException(status_code=401, detail="Invalid email or password")

    # Log successful login
    attempt = LoginAttempt(
        email=user.email,
        success=True,
        timestamp=_utcnow(),
        ip_address=client_ip,
    )
    db.add(attempt)
    db.commit()

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={
            "sub": db_user.email,
            "role": db_user.role,
            "id": db_user.id,
            "name": get_user_name(db_user) or get_user_email(db_user).split("@")[0],
        },
        expires_delta=access_token_expires,
    )
    _set_auth_cookie(response, access_token, ACCESS_TOKEN_EXPIRE_MINUTES)
    _set_csrf_cookie(response)
    return {
        "access_token": _visible_access_token(access_token),
        "token_type": "bearer",
        "role": db_user.role,
        "id": db_user.id,
        "name": get_user_name(db_user),
        "avatar": get_user_avatar_url(db_user),
    }


@router.get("/verify-email/{token}")
def verify_email(token: str, db: Session = Depends(get_db)):
    """
    SECURITY FIX: Verify candidate email address
    """
    verification = (
        db.query(EmailVerification)
        .filter(
            EmailVerification.token == token,
            EmailVerification.verified.is_(False),
            EmailVerification.expires_at > _utcnow(),
        )
        .first()
    )

    if not verification:
        raise HTTPException(
            status_code=400, detail="Invalid or expired verification link"
        )

    user = db.query(User).filter(User.id == verification.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.email_verified = True
    verification.verified = True
    db.commit()

    return {"message": "Email verified successfully. You can now login."}


@router.get("/me")
def get_me(current_user: User = Depends(get_current_user)):
    return {
        "id": current_user.id,
        "name": get_user_name(current_user),
        "email": get_user_email(current_user),
        "role": current_user.role,
        "email_verified": current_user.email_verified,
        "phone": get_user_phone(current_user),
        "location": get_user_location(current_user),
        "headline": get_user_headline(current_user),
        "bio": get_user_bio(current_user),
        "linkedin": get_user_linkedin_url(current_user),
        "github": get_user_github_url(current_user),
        "portfolio": get_user_portfolio_url(current_user),
        "avatar": get_user_avatar_url(current_user),
        "skills": get_user_skills(current_user) or "",
        "tier": get_user_tier(current_user),
        "subscription_status": get_user_subscription_status(current_user),
        "subscription_plan": get_user_subscription_plan(current_user),
        "admin_permissions": get_user_admin_permissions(current_user),
        "is_super_admin": get_user_is_super_admin(current_user),
        "company_id": getattr(current_user, "_company_id", None),
        "company_role": getattr(current_user, "_company_role", None),
        "company_logo_url": get_user_company_logo_url(current_user),
        "company_name": get_user_company_name(current_user),
    }


@router.put("/me")
def update_me(
    user_update: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Consolidated update for user profile"""
    user = db.query(User).filter(User.id == current_user.id).first()

    # SECURITY FIX: Whitelist of allowed profile fields (prevents role escalation)
    ALLOWED_FIELDS = {
        "name",
        "phone",
        "headline",
        "bio",
        "location",
        "linkedin_url",
        "github_url",
        "portfolio_url",
        "avatar_url",
    }

    update_data = user_update.model_dump(exclude_unset=True)
    if "password" in update_data:
        new_password = update_data.pop("password")
        validate_password(new_password)
        user.hashed_password = pwd_context.hash(new_password)

    profile = get_profile(user)
    for key, value in update_data.items():
        if key in ALLOWED_FIELDS:
            setattr(user, key, value)
            if profile is not None and hasattr(profile, key):
                setattr(profile, key, value)

    db.commit()
    db.refresh(user)
    return {"message": "Profile updated successfully"}


@router.get("/me/export")
def export_data(current_user: User = Depends(get_current_user)):
    """GDPR Compliance: Export all user data"""
    return {
        "profile": {
            "id": current_user.id,
            "name": get_user_name(current_user),
            "email": get_user_email(current_user),
            "role": current_user.role,
            "joined_at": current_user.created_at,
            "phone": get_user_phone(current_user),
            "location": get_user_location(current_user),
            "bio": get_user_bio(current_user),
            "skills": get_user_skills(current_user),
            "linkedin": get_user_linkedin_url(current_user),
            "github": get_user_github_url(current_user),
            "portfolio": get_user_portfolio_url(current_user),
        },
        "activity": {
            "jobs_posted": len(current_user.jobs),
            "applications": len(current_user.applications),
            "courses_enrolled": len(current_user.enrollments),
            "courses_created": len(current_user.courses),
            "payouts_requested": len(current_user.payouts),
        },
    }


@router.post("/logout")
async def logout(
    request: Request, response: Response, token: Optional[str] = Depends(oauth2_scheme)
):
    """SECURITY FIX: Invalidate token on logout"""
    raw_token = token or request.cookies.get("access_token")
    if raw_token and raw_token.lower().startswith("bearer "):
        raw_token = raw_token[7:].strip()
    if raw_token == "cookie-auth":
        raw_token = None

    try:
        if raw_token:
            from backend.token_blacklist import invalidate_token

            # Identify user if possible
            user_id = 0
            try:
                payload = jwt.decode(raw_token, SECRET_KEY, algorithms=[ALGORITHM])
                user_id = payload.get("id") or 0
            except Exception:
                pass

            await invalidate_token(raw_token, user_id, reason="logout")
    except Exception as e:
        logger.warning(f"Error during logout token invalidation: {e}")
        pass

    response.delete_cookie("access_token", path="/")
    response.delete_cookie("logged_in", path="/")

    return {"message": "Successfully logged out"}


# --- PASSWORD RESET FLOW ---

from pydantic import BaseModel as PydanticBaseModel  # noqa: E402


class ForgotPasswordRequest(PydanticBaseModel):
    email: str


class ResetPasswordRequest(PydanticBaseModel):
    token: str
    new_password: str


class ChangePasswordRequest(PydanticBaseModel):
    current_password: str
    new_password: str


@router.post("/forgot-password")
def forgot_password(
    req: ForgotPasswordRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _rate_limit: None = Depends(rate_limit_dep(max_requests=3, window_seconds=3600)),
):
    """
    Send a password reset email if the account exists.
    Always returns success to prevent email enumeration.
    """
    from backend.database import PasswordReset

    email = req.email.lower().strip()
    user = db.query(User).filter(User.email == email).first()

    # Always return success to prevent email enumeration
    if not user:
        return {
            "message": "If an account exists with that email, a reset link has been sent."
        }

    # Rate limit: max 3 reset requests per hour
    hour_ago = _utcnow() - timedelta(hours=1)
    recent_resets = (
        db.query(PasswordReset)
        .filter(PasswordReset.user_id == user.id, PasswordReset.created_at > hour_ago)
        .count()
    )

    if recent_resets >= 3:
        return {
            "message": "If an account exists with that email, a reset link has been sent."
        }

    # Generate reset token
    reset_token = secrets.token_urlsafe(48)
    reset = PasswordReset(
        user_id=user.id,
        token=reset_token,
        expires_at=_utcnow() + timedelta(hours=1),
        created_at=_utcnow(),
    )
    db.add(reset)
    db.commit()

    # Send email
    reset_url = f"{settings.frontend_url}/auth/reset-password?token={reset_token}"
    subject = "Candway — Reset Your Password"
    body = f"""
    <h2>Password Reset Request</h2>
    <p>You requested a password reset for your Candway account.</p>
    <p>Click the link below to set a new password:</p>
    <p><a href="{reset_url}" style="display:inline-block;padding:12px 24px;background:#6366f1;color:white;text-decoration:none;border-radius:8px;font-weight:bold;">Reset Password</a></p>
    <p>This link expires in <strong>1 hour</strong>.</p>
    <p>If you didn't request this, you can safely ignore this email.</p>
    <br>
    <p style="color: #999; font-size: 12px;">— The Candway Team</p>
    """

    try:
        background_tasks.add_task(email_service.send_email, email, subject, body)
    except Exception as e:
        logger.error(f"Failed to queue password reset email: {e}")

    return {
        "message": "If an account exists with that email, a reset link has been sent."
    }


@router.post("/reset-password", response_model=schemas.Message)
async def reset_password(
    request: Request, payload: ResetPasswordRequest, db: Session = Depends(get_db)
):
    """
    Final step: reset the password using the token from the email.
    """
    from backend.database import PasswordReset
    from backend.redis_rate_limiter import check_rate_limit

    # Rate limiting
    client_ip = request.client.host if request.client else "0.0.0.0"
    is_allowed, metadata = await check_rate_limit(
        identifier=f"reset_pw_final:{client_ip}", max_requests=5, window_seconds=3600
    )
    if not is_allowed:
        retry_after = metadata.get("retry_after", 3600)
        raise HTTPException(
            status_code=429,
            detail=f"Too many reset attempts. Try again in {retry_after} seconds.",
            headers={"Retry-After": str(retry_after)},
        )

    # CRITICAL FIX: Use row-level locking to prevent race condition
    # SELECT ... FOR UPDATE ensures only one request can process this token at a time

    # Lock the password reset row to prevent concurrent processing
    reset = (
        db.query(PasswordReset)
        .filter(
            PasswordReset.token == payload.token,
            PasswordReset.used.is_(False),
            PasswordReset.expires_at > _utcnow(),
        )
        .with_for_update()
        .first()
    )

    if not reset:
        # Double-check if token was already used (race condition protection)
        used_reset = (
            db.query(PasswordReset)
            .filter(PasswordReset.token == payload.token, PasswordReset.used)
            .first()
        )
        if used_reset:
            raise HTTPException(
                status_code=400,
                detail="This reset link has already been used. Please request a new one.",
            )
        raise HTTPException(
            status_code=400,
            detail="Invalid or expired reset link. Please request a new one.",
        )

    user = db.query(User).filter(User.id == reset.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Validate new password — raises HTTPException directly on failure
    validate_password(payload.new_password)

    # Update password
    user.hashed_password = pwd_context.hash(payload.new_password)

    # Unlock account if locked
    user.is_locked = False
    user.lockout_until = None

    # Mark token as used - atomically with the row lock held
    reset.used = True
    db.commit()

    # Invalidate all existing tokens - CRITICAL for security
    try:
        from backend.token_blacklist import invalidate_all_user_tokens

        # Directly await the async function in this async route
        await invalidate_all_user_tokens(user.id, reason="password_reset")
    except Exception as e:
        logger.error(f"Failed to invalidate tokens on password reset: {e}")

    logger.info(f"Password reset successful for user {user.email}")
    return {
        "message": "Password updated successfully. You can now login with your new password."
    }


@router.post("/change-password", response_model=schemas.Message)
async def change_password(
    req: ChangePasswordRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Change the authenticated user's password (requires current password).
    Invalidates all existing tokens after a successful change.
    """
    from backend.redis_rate_limiter import check_rate_limit

    client_ip = request.client.host if request.client else "0.0.0.0"
    is_allowed, metadata = await check_rate_limit(
        identifier=f"change_pw:{current_user.id}:{client_ip}",
        max_requests=5,
        window_seconds=3600,
    )
    if not is_allowed:
        retry_after = metadata.get("retry_after", 3600)
        raise HTTPException(
            status_code=429,
            detail=f"Too many change attempts. Try again in {retry_after} seconds.",
            headers={"Retry-After": str(retry_after)},
        )

    user = db.query(User).filter(User.id == current_user.id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if not user.hashed_password or not pwd_context.verify(
        req.current_password, user.hashed_password
    ):
        raise HTTPException(status_code=400, detail="Current password is incorrect")

    validate_password(req.new_password)

    user.hashed_password = pwd_context.hash(req.new_password)
    user.is_locked = False
    user.lockout_until = None
    db.commit()

    try:
        from backend.token_blacklist import invalidate_all_user_tokens

        await invalidate_all_user_tokens(user.id, reason="password_changed")
    except Exception as e:
        logger.error(f"Failed to invalidate tokens on password change: {e}")

    logger.info(f"Password changed for user {user.email}")
    return {"message": "Password changed successfully."}


# === GOOGLE OAUTH ===
@router.get("/google/login")
async def google_login(
    response: Response,
    db: Session = Depends(get_db),
):
    """Redirect to Google OAuth with CSRF-protected state parameter"""
    from backend.database import SystemConfig

    google_enabled = (
        db.query(SystemConfig).filter(SystemConfig.key == "google_enabled").first()
    )
    if not google_enabled or google_enabled.value.lower() != "true":
        raise HTTPException(status_code=400, detail="Google login is not enabled")

    client_id = (
        db.query(SystemConfig).filter(SystemConfig.key == "google_client_id").first()
    )
    if not client_id:
        raise HTTPException(status_code=400, detail="Google OAuth not configured")

    import urllib.parse

    redirect_uri = f"{settings.frontend_url}/auth/google/callback"
    scope = "email profile openid"

    # CSRF: generate random state nonce, store in httponly cookie
    state_nonce = secrets.token_urlsafe(32)
    response.set_cookie(
        key="google_oauth_state",
        value=state_nonce,
        httponly=True,
        samesite="lax",
        secure=settings.is_prod,
        max_age=600,
        path="/",
    )

    auth_url = f"https://accounts.google.com/o/oauth2/v2/auth?client_id={client_id.value}&redirect_uri={urllib.parse.quote(redirect_uri)}&response_type=code&scope={urllib.parse.quote(scope)}&state={state_nonce}"

    return {"auth_url": auth_url}


@router.get("/google/callback")
async def google_callback(
    request: Request,
    response: Response,
    code: str = Query(None),
    state: str = Query(None),
    db: Session = Depends(get_db),
):
    """Handle Google OAuth callback with CSRF state validation"""
    if not code:
        raise HTTPException(status_code=400, detail="No code provided")

    # Validate CSRF state nonce
    stored_state = request.cookies.get("google_oauth_state")
    if not stored_state or not state or stored_state != state:
        logger.warning(
            f"Google OAuth state mismatch: stored={stored_state}, received={state}"
        )
        raise HTTPException(
            status_code=403,
            detail="CSRF validation failed. Please try logging in again.",
        )
    # Clear the state cookie immediately
    response.delete_cookie("google_oauth_state", path="/")

    from backend.database import SystemConfig, User
    from backend.secret_encryption import decrypt_value

    client_id = (
        db.query(SystemConfig).filter(SystemConfig.key == "google_client_id").first()
    )
    client_secret = (
        db.query(SystemConfig)
        .filter(SystemConfig.key == "google_client_secret")
        .first()
    )

    if not client_id or not client_secret:
        raise HTTPException(status_code=400, detail="OAuth not configured")

    import json
    import urllib.parse
    import urllib.request

    token_url = "https://oauth2.googleapis.com/token"
    secret_key = settings.secret_key
    decrypted_client_secret = decrypt_value(client_secret.value, secret_key)

    if not decrypted_client_secret:
        logger.error("Google OAuth client secret decryption failed")
        raise HTTPException(status_code=500, detail="OAuth configuration error")

    token_data = {
        "client_id": client_id.value,
        "client_secret": decrypted_client_secret,
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": f"{settings.frontend_url}/auth/google/callback",
    }

    req = urllib.request.Request(
        token_url, data=urllib.parse.urlencode(token_data).encode()
    )
    req.add_header("Content-Type", "application/x-www-form-urlencoded")

    with urllib.request.urlopen(req) as token_response:
        tokens = json.loads(token_response.read())

        userinfo_url = "https://www.googleapis.com/oauth2/v2/userinfo"
        req = urllib.request.Request(userinfo_url)
        req.add_header("Authorization", f"Bearer {tokens['access_token']}")

        with urllib.request.urlopen(req) as userinfo_response:
            google_user = json.loads(userinfo_response.read())

        user = db.query(User).filter(User.email == google_user["email"]).first()

        if not user:
            user = User(
                email=google_user["email"],
                name=google_user.get("name", "Google User"),
                role="candidate",
                email_verified=True,
            )
            db.add(user)
            db.commit()
            db.refresh(user)

        access_token = create_access_token(
            data={
                "sub": user.email,
                "role": user.role,
                "id": user.id,
                "name": get_user_name(user) or get_user_email(user).split("@")[0],
            }
        )
        _set_auth_cookie(response, access_token, ACCESS_TOKEN_EXPIRE_MINUTES)

        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user": {
                "id": user.id,
                "email": user.email,
                "name": get_user_name(user),
                "role": user.role,
            },
        }


@router.post("/refresh")
async def refresh_token(
    request: Request,
    response: Response,
    current_user: User = Depends(get_current_user),
):
    """Refresh the access token with a new expiry."""
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={
            "sub": current_user.email,
            "role": current_user.role,
            "id": current_user.id,
            "name": get_user_name(current_user)
            or get_user_email(current_user).split("@")[0],
        },
        expires_delta=access_token_expires,
    )
    _set_auth_cookie(response, access_token, ACCESS_TOKEN_EXPIRE_MINUTES)
    return {"access_token": access_token, "token_type": "bearer"}
