import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta
from typing import Optional, Tuple

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from backend.authz import get_application_for_recruiter
from backend.config import get_settings
from backend.database import Application, CompanyMember, SessionLocal, User
from backend.logger import logger
from backend.client_ip import get_client_ip
from backend.profile_helpers import get_user_is_super_admin, get_user_tier

settings = get_settings()
logger.debug("backend/dependencies.py MODULE LOADED")

# Use dedicated context-specific keys with SECRET_KEY as dev fallback
JWT_SECRET_KEY = settings.jwt_secret_key or settings.secret_key
INTERVIEW_HMAC_KEY = settings.interview_hmac_key or settings.secret_key
CSRF_SECRET_KEY = settings.csrf_secret_key or settings.secret_key
SECRET_KEY = settings.secret_key
ALGORITHM = settings.algorithm
ACCESS_TOKEN_EXPIRE_MINUTES = settings.access_token_expire_minutes

from backend.redis_manager import redis_manager  # noqa: E402


async def _get_redis():
    return await redis_manager.get_client()


# Password Hashing
#
# bcrypt cost factor history (OWASP / 2026 baseline):
#   * 10 = 2010-era default
#   * 12 = 2017-era default  <-- candway through this audit
#   * 14 = 2026 baseline      <-- P1-07 fix
#
# Old pbkdf2_sha256 hashes are auto-marked deprecated by passlib
# `deprecated="auto"` and silently re-hashed to bcrypt on next
# successful verify. Old bcrypt@12 hashes continue to verify
# (the cost factor is encoded in the hash itself) and will be
# re-hashed to bcrypt@14 on next successful verify.
#
# Bcrypt cost 14 on a modern x86 CPU: ~250ms per hash. P1-08
# rate-limits login to 20 attempts/min/IP and 5 attempts per
# account, so the worst-case login page latency is bounded
# and the cost is amortised.
#
# If you need to override for a CI / smoke test environment,
# set CANDWAY_BCRYPT_ROUNDS=4 at process start.
import os  # noqa: E402

_BCRYPT_ROUNDS = int(os.environ.get("CANDWAY_BCRYPT_ROUNDS", "14"))

pwd_context = CryptContext(
    schemes=["bcrypt", "pbkdf2_sha256"],
    deprecated="auto",
    bcrypt__rounds=_BCRYPT_ROUNDS,
)

# OAuth2 Scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login", auto_error=False)


def _normalize_token(raw_token: Optional[str]) -> Optional[str]:
    if not raw_token:
        return None
    token = str(raw_token).strip()
    if token.lower().startswith("bearer "):
        token = token[7:].strip()
    return token or None


def _candidate_tokens(request: Request, bearer_token: Optional[str]) -> list[str]:
    logger.debug(
        "_candidate_tokens called with bearer_token=%s",
        "Present" if bearer_token else "None",
    )
    tokens = []
    header_token = _normalize_token(bearer_token)
    cookie_token = _normalize_token(request.cookies.get("access_token"))

    if header_token:
        logger.debug("Found header token (truncated): %s...", header_token[:10])
        tokens.append(header_token)
    if cookie_token and cookie_token not in tokens:
        logger.debug("Found cookie token (truncated): %s...", cookie_token[:10])
        tokens.append(cookie_token)

    # Placeholder used by browser clients in production cookie-auth mode.
    valid_tokens = [t for t in tokens if t != "cookie-auth"]
    logger.debug("Returning %s valid candidate tokens", len(valid_tokens))
    return valid_tokens


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    now = datetime.now(UTC).replace(tzinfo=None)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=15)
    import time as _time

    to_encode.update({"exp": expire, "iat": int(_time.time())})
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def generate_interview_token(app_id: int) -> dict:
    """
    Generate a time-limited HMAC signature for an application ID.
    Includes:
    - Day bucket for expiration (24h validity)
    - Unique nonce for single-use enforcement
    - App ID binding to prevent token reuse across candidates
    """
    from datetime import UTC, datetime

    now = datetime.now(UTC)
    days_since_epoch = int(now.timestamp() / 86400)
    nonce = secrets.token_urlsafe(8)  # Unique per generation

    # Include app_id, day, and nonce in the HMAC
    message = f"{app_id}:{days_since_epoch}:{nonce}".encode()
    token = hmac.new(INTERVIEW_HMAC_KEY.encode(), message, hashlib.sha256).hexdigest()

    # Calculate expiry (current day end in UTC)
    expiry = now.replace(hour=23, minute=59, second=59)

    return {
        "token": f"{nonce}:{token}",  # nonce:signature format
        "app_id": app_id,
        "expires_at": int(expiry.timestamp()),
        "nonce": nonce,
    }


async def verify_interview_token(app_id: int, raw_token: str) -> bool:
    """
    Verify interview token with:
    - Time expiry check
    - Single-use via nonce (stored in Redis after use)
    - Bound to specific app_id
    """
    if not raw_token:
        return False

    # Parse nonce:signature format
    if ":" not in raw_token:
        return False

    parts = raw_token.split(":", 1)
    if len(parts) != 2:
        return False

    nonce, received_sig = parts

    # Check day and app_id in signature
    days_since_epoch = int(datetime.now(UTC).timestamp() / 86400)

    for day_offset in [0, -1]:
        check_day = days_since_epoch + day_offset
        msg = f"{app_id}:{check_day}:{nonce}".encode()
        expected_sig = hmac.new(
            INTERVIEW_HMAC_KEY.encode(), msg, hashlib.sha256
        ).hexdigest()

        if hmac.compare_digest(expected_sig, received_sig):
            # Signature valid - now enforce single-use
            used_key = f"interview_token_used:{app_id}:{nonce}"
            redis = await _get_redis()
            if redis:
                if await redis.exists(used_key):
                    logger.warning(
                        f"Interview token REUSED: app={app_id}, nonce={nonce[:8]}"
                    )
                    return False
                await redis.setex(used_key, 86400 * 7, f"used:{app_id}")
                logger.info(
                    f"Interview token validated & consumed via Redis: app={app_id}"
                )
            else:
                # Fallback: database-backed single-use enforcement when Redis is down
                # NOTE: user_id stays NULL since this is an interview token
                # nonce, not a real user token. Using app_id here would cause
                # spurious blacklist matches for real users.
                try:
                    from backend.database import SessionLocal
                    from backend.database import TokenBlacklist as TBModel

                    db_fb = SessionLocal()
                    try:
                        existing = (
                            db_fb.query(TBModel)
                            .filter(TBModel.token_hash == used_key)
                            .first()
                        )
                        if existing:
                            logger.warning(
                                f"Interview token REUSED (DB fallback): app={app_id}, nonce={nonce[:8]}"
                            )
                            return False
                        entry = TBModel(
                            token_hash=used_key,
                            user_id=None,  # Interview nonce, not a real user
                            reason=f"interview_nonce:{nonce[:8]}",
                            expires_at=datetime.now(UTC) + timedelta(days=7),
                            invalidated_at=datetime.now(UTC),
                        )
                        db_fb.add(entry)
                        db_fb.commit()
                        logger.info(
                            f"Interview token validated & consumed via DB fallback: app={app_id}"
                        )
                    finally:
                        db_fb.close()
                except Exception as e:
                    logger.error(f"DB fallback for interview token failed: {e}")
                    return False
            return True

    logger.warning(f"HMAC verify FAILED or EXPIRED: app={app_id}, nonce={nonce[:8]}")
    return False


async def get_current_user(
    request: Request,
    token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    decoded_payload = None
    active_token = None
    for candidate in _candidate_tokens(request, token):
        try:
            decoded_payload = jwt.decode(
                candidate, JWT_SECRET_KEY, algorithms=[ALGORITHM]
            )
            active_token = candidate
            break
        except JWTError:
            continue

    if decoded_payload is None or active_token is None:
        logger.debug("No valid bearer/cookie token presented.")
        raise credentials_exception

    try:
        email: str = decoded_payload.get("sub")
        decoded_payload.get("role")
        if email is None:
            logger.warning("Token decode success but email is None.")
            raise credentials_exception
    except JWTError as e:
        logger.debug(f"JWT decode error: {e}")
        raise credentials_exception

    # SECURITY (H-2): guest / interview-scoped tokens are NOT valid normal
    # user sessions. They may only be used on interview endpoints via
    # get_current_interview_user. Reject them here so a leaked interview
    # link can never be promoted to a full account session.
    if (
        decoded_payload.get("scope") == "interview"
        or decoded_payload.get("guest") is True
    ):
        logger.warning("Rejected guest-scoped token on a normal user endpoint.")
        raise credentials_exception

    user = db.query(User).filter(User.email == email).first()
    if user is None:
        logger.warning("User not found in DB for the provided email.")
        raise credentials_exception

    from backend.token_blacklist import token_blacklist

    # Check if token is blacklisted (SECURITY: fail-closed in production)
    try:
        is_blacklisted = await token_blacklist.is_blacklisted(active_token)
    except Exception:
        # In production, reject on any Redis failure (fail-closed)
        if settings.is_prod:
            logger.critical(
                "SECURITY: Token blacklist check failed in production — rejecting token."
            )
            raise credentials_exception
        is_blacklisted = False  # Dev: fail open for convenience

    if is_blacklisted:
        logger.warning(f"Rejected blacklisted token for email: {email}")
        raise credentials_exception

    # Check for bulk invalidation (password reset, account lock)
    iat = decoded_payload.get("iat")
    if iat:
        issued_at = datetime.fromtimestamp(iat, tz=UTC)
        try:
            if await token_blacklist.is_user_invalidated(user.id, issued_at):
                logger.warning(
                    f"Rejected token issued before security event for: {email}"
                )
                raise credentials_exception
        except Exception as e:
            if settings.is_prod:
                logger.critical(f"SECURITY: User invalidation check failed: {e}")
                raise credentials_exception

    # SECURITY FIX: Check if account is locked
    if getattr(user, "is_locked", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is locked. Please contact support.",
        )

    # SECURITY FIX: Check if account is soft-deleted
    if user.deleted_at is not None:
        logger.warning(f"Rejecting soft-deleted user: {email}")
        raise credentials_exception

    # TENANT ISOLATION: Attach company context to user object.
    # Lazy lookup from CompanyMember — cached on the user for the request lifetime.
    # Available as current_user.company_id and current_user.company_role.
    try:
        membership = (
            db.query(CompanyMember)
            .filter(
                CompanyMember.user_id == user.id,
                CompanyMember.is_active,
            )
            .first()
        )
        if membership:
            user._company_id = membership.company_id
            user._company_role = membership.role
    except Exception:
        logger.exception(
            "[TENANT] Failed to attach company context for user %s", user.id
        )

    # AI SECURITY CONTEXT:
    # Propagate authenticated identity to centralized AI guardrails so
    # rate limiting can enforce per-company, per-user and per-IP limits.
    try:
        from backend.ai.llm import set_ai_security_context

        client_ip = get_client_ip(
            request.headers.get("X-Forwarded-For"),
            request.client.host if request.client else None,
        )
        set_ai_security_context(
            company_id=getattr(user, "_company_id", None),
            user_id=user.id,
            ip=client_ip,
        )
    except Exception:
        # Do not break authentication if optional AI context propagation fails.
        logger.exception(
            "[AI SECURITY] Failed to propagate request security context "
            "for user %s",
            user.id,
        )

    return user


# Admin guard — uses is_super_admin flag, NOT the role string "super_admin"
async def get_current_admin(user: User = Depends(get_current_user)) -> User:
    if not user:
        logger.warning("Admin Guard: No user found in session.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired or invalid",
        )
    if not is_admin_user(user):
        logger.warning(
            f"Admin Guard: User {user.email} role={user.role} user.is_super_admin={getattr(user, 'is_super_admin', False)} profile.is_super_admin={getattr(getattr(user, 'admin_profile', None), 'is_super_admin', None)} — not an admin"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized as admin"
        )
    logger.info(f"Admin Guard: Access granted for {user.email}")
    return user


async def get_current_interview_user(
    request: Request,
    db: Session = Depends(get_db),
    token: Optional[str] = Depends(oauth2_scheme),
) -> Tuple[Optional[User], Application]:
    """Authenticate users/guests for interview-scoped endpoints.

    Accepts:
      * normal user JWTs (recruiter / logged-in candidate),
      * true-guest JWTs (``sub = guest_<app_id>``, ``scope=interview``),
      * existing-user guest JWTs (``scope=interview`` + ``app_id`` claim)
        bound to the application the interview link was minted for.

    Rejects guest-scoped tokens everywhere else (``get_current_user``), so
    an interview link can only ever reach interview endpoints.
    """
    return await _get_interview_access_impl(request, db, token)


async def get_interview_access(
    request: Request,
    db: Session = Depends(get_db),
    token: Optional[str] = Depends(oauth2_scheme),
) -> Tuple[Optional[User], Application]:
    """Backward-compatible alias for get_current_interview_user."""
    logger.debug(f"get_interview_access: path={request.url.path}")
    try:
        return await _get_interview_access_impl(request, db, token)
    except Exception as e:
        logger.error(f"get_interview_access failed: {e}", exc_info=True)
        raise e


async def _get_interview_access_impl(
    request: Request,
    db: Session = Depends(get_db),
    token: Optional[str] = Depends(oauth2_scheme),
) -> Tuple[Optional[User], Application]:
    """
    Reconciles JWT and HMAC authentication for interviews.
    Allows recruiters (JWT) and guest candidates (HMAC) to access interview endpoints.
    Returns (User or None, Application).
    """
    logger.debug("get_interview_access called for %s", request.url.path)
    # 1. Try JWT Auth first (Recruiters or Logged-in Candidates)
    current_user = None
    try:
        current_user = await get_current_user(request, token, db)
        logger.debug("get_current_user succeeded: %s", current_user.email)
    except HTTPException as e:
        logger.debug("get_current_user failed with status %s", e.status_code)
        # Check if it's a guest JWT
        candidates = _candidate_tokens(request, token)
        logger.debug("Checking %s token candidates", len(candidates))
        for tk in candidates:
            try:
                payload = jwt.decode(tk, JWT_SECRET_KEY, algorithms=[ALGORITHM])
                sub = payload.get("sub")
                logger.debug("Decoded token successfully for guest check")
                if not sub:
                    continue

                from backend.token_blacklist import token_blacklist

                # Common guest-token blacklist / invalidation checks.
                async def _guest_token_blocked() -> bool:
                    iat = payload.get("iat")
                    if iat:
                        issued_at = datetime.fromtimestamp(iat, tz=UTC)
                        guest_key = payload.get("app_id") or int(str(sub).split("_")[1])
                        try:
                            if await token_blacklist.is_user_invalidated(
                                guest_key, issued_at
                            ):
                                logger.warning(
                                    f"AUTH: Guest token for {sub} was invalidated"
                                )
                                return True
                        except Exception:
                            if settings.is_prod:
                                return True
                    try:
                        if await token_blacklist.is_blacklisted(tk):
                            logger.warning(
                                f"AUTH: Guest token for {sub} is blacklisted"
                            )
                            return True
                    except Exception:
                        if settings.is_prod:
                            return True
                    return False

                # True guest: sub = guest_<app_id> (no account record).
                if str(sub).startswith("guest_"):
                    try:
                        if await _guest_token_blocked():
                            continue
                        guest_app_id = int(sub.split("_")[1])
                        application = (
                            db.query(Application)
                            .filter(Application.id == guest_app_id)
                            .first()
                        )
                        if application and application.user_id is None:
                            logger.info(
                                f"AUTH: Guest access via JWT confirmed for app {guest_app_id}"
                            )
                            return None, application
                    except (IndexError, ValueError):
                        logger.warning(f"AUTH: Invalid guest sub format: {sub}")
                        continue

                # Existing-user guest: scope=interview + app_id claim.
                # Carries the candidate's email sub but is NOT a normal
                # session (get_current_user rejects scope=interview), so it
                # may only reach interview endpoints. Bound to the specific
                # application the interview link was minted for.
                if payload.get("scope") == "interview" and payload.get("app_id"):
                    try:
                        if await _guest_token_blocked():
                            continue
                        app_id_claim = int(payload["app_id"])
                        user_id = payload.get("id")
                        application = (
                            db.query(Application)
                            .filter(Application.id == app_id_claim)
                            .first()
                        )
                        if not application:
                            continue
                        if user_id is not None and application.user_id == user_id:
                            user = db.query(User).filter(User.id == user_id).first()
                            if user:
                                logger.info(
                                    f"AUTH: Guest interview access for user "
                                    f"{user.id} on app {app_id_claim}"
                                )
                                return user, application
                    except (IndexError, ValueError, TypeError):
                        logger.warning(f"AUTH: Invalid interview guest token: {sub}")
                        continue
            except JWTError as jwt_err:
                logger.debug(
                    f"JWT Decode failed during interview access check: {jwt_err}"
                )
                continue

    # 2. Try HMAC Auth (Guest Candidates - first time link access)
    app_id = None
    hmac_token = None

    # Check path, query and body params for application identifying ID
    path_params = request.path_params
    query_params = request.query_params

    app_id = (
        path_params.get("app_id")
        or path_params.get("application_id")
        or query_params.get("application_id")
        or query_params.get("id")
        or query_params.get("app_id")
        or query_params.get("candidate_id")
    )

    # ADVANCED FALLBACK: If path_params is empty (can happen in some dependency contexts)
    # try extracting ID from URL path manually
    if not app_id:
        import re

        path = request.url.path
        # Match patterns like /applications/123 or /interview/chat?candidate_id=123
        match = re.search(r"/applications/(\d+)", path)
        if match:
            app_id = match.group(1)

    hmac_token = query_params.get("token")

    # Check JSON body safely
    if not app_id or not hmac_token:
        try:
            # Check if request has a JSON content type before attempting to parse
            content_type = request.headers.get("content-type", "")
            if "application/json" in content_type:
                body = await request.json()
                if isinstance(body, dict):
                    app_id = (
                        app_id
                        or body.get("application_id")
                        or body.get("id")
                        or body.get("app_id")
                        or body.get("candidate_id")
                    )
                    hmac_token = hmac_token or body.get("token")
        except Exception as e:
            logger.debug(f"Could not parse JSON body for interview access: {e}")
            pass

    if app_id and hmac_token:
        try:
            app_id_int = int(app_id)
            is_valid = await verify_interview_token(app_id_int, hmac_token)
            if is_valid:
                application = (
                    db.query(Application).filter(Application.id == app_id_int).first()
                )
                if application:
                    # If we have a valid HMAC token, they ARE authorized to
                    # access the application resource. Logged-in recruiters and
                    # admins still require company-aware application ownership.
                    if current_user:
                        if current_user.role in ["recruiter", "admin"]:
                            get_application_for_recruiter(
                                application.id, current_user, db
                            )
                            return current_user, application
                        if (
                            application.user_id
                            and application.user_id == current_user.id
                        ):
                            return current_user, application
                        logger.warning(
                            f"AUTH: Token for app {application.id} used by "
                            f"non-owner {current_user.email} — denied"
                        )
                        raise HTTPException(
                            status_code=status.HTTP_403_FORBIDDEN,
                            detail="Token does not belong to the logged-in user",
                        )

                    # Guest or public candidate with valid token
                    if application.user_id:
                        user = (
                            db.query(User)
                            .filter(User.id == application.user_id)
                            .first()
                        )
                        return user, application

                    return None, application  # Public/Guest candidate
        except HTTPException:
            raise
        except (ValueError, TypeError):
            pass

    if current_user:
        # Fallback for recruiter checking applications anonymously
        app_id_val = app_id or (getattr(request, "path_params", {}).get("app_id"))
        if app_id_val:
            try:
                a_id = int(app_id_val)
                application = (
                    db.query(Application).filter(Application.id == a_id).first()
                )
                if application and current_user.role in ["recruiter", "admin"]:
                    get_application_for_recruiter(application.id, current_user, db)
                    return current_user, application
                if (
                    application
                    and current_user.role == "candidate"
                    and application.user_id == current_user.id
                ):
                    return current_user, application
            except Exception as _e:
                logger.debug(
                    "get_interview_access recruiter fallback lookup failed: %s", _e
                )
        return current_user, None

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required (JWT or valid Interview Token)",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_optional_user(request: Request, db: Session = Depends(get_db)):
    auth_header = request.headers.get("Authorization")
    bearer_token = None
    if auth_header and auth_header.startswith("Bearer "):
        bearer_token = auth_header.split(" ", 1)[1]

    for candidate in _candidate_tokens(request, bearer_token):
        try:
            payload = jwt.decode(candidate, JWT_SECRET_KEY, algorithms=[ALGORITHM])
            email: str = payload.get("sub")
            if not email:
                continue
            user = db.query(User).filter(User.email == email).first()
            if not user:
                continue

            from backend.token_blacklist import token_blacklist

            try:
                if await token_blacklist.is_blacklisted(candidate):
                    continue
            except Exception:
                if settings.is_prod:
                    continue

            iat = payload.get("iat")
            if iat:
                issued_at = datetime.fromtimestamp(iat, tz=UTC)
                try:
                    if await token_blacklist.is_user_invalidated(user.id, issued_at):
                        continue
                except Exception:
                    if settings.is_prod:
                        continue

            if getattr(user, "is_locked", False):
                continue

            if user.deleted_at is not None:
                continue

            return user
        except JWTError:
            continue
    return None


# ============================================
# ROLE-BASED ACCESS CONTROL
# ============================================


def require_recruiter(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role not in ["recruiter", "admin", "company"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Recruiter access required"
        )
    # Propagate company_id to AI security context
    company_id = getattr(current_user, "_company_id", None)
    if company_id:
        try:
            from backend.ai.llm import set_ai_company_id

            set_ai_company_id(company_id)
        except ImportError:
            pass
    return current_user


def is_admin_user(user: User) -> bool:
    """Determine whether the user has admin privileges.

    Checks AdminProfile.is_super_admin (SSOT after migration)
    and allows regular admin users with role == "admin".
    """
    try:
        if get_user_is_super_admin(user):
            return True
    except Exception:
        pass
    return user.role == "admin"


def require_company_admin(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> User:
    """Guard for organization (company) admin actions.

    Requires the user to be a member of an active company with the
    CompanyMember role 'owner' or 'admin'. Platform admins (role
    'admin') are explicitly NOT granted org-admin powers here — the
    org portal is a distinct surface. Raises 403 otherwise.
    """
    from backend.tenant import _resolve_company_id

    company_id = _resolve_company_id(current_user, db)
    if company_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No active company membership. Contact your admin.",
        )
    membership = (
        db.query(CompanyMember)
        .filter(
            CompanyMember.company_id == company_id,
            CompanyMember.user_id == current_user.id,
            CompanyMember.is_active,
        )
        .first()
    )
    if not membership or membership.role not in ("owner", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Company admin access required.",
        )
    current_user._company_id = company_id
    current_user._company_role = membership.role
    return current_user


def require_org_admin(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> User:
    """Organization portal guard — requires the 'company' role too.

    Self-contained (does not nest `require_company_admin`) so every
    access failure on the org portal surface yields the consistent
    "Organization portal access required." message. Ensures only
    company-owned accounts (created via /auth/signup/org) can drive the
    org portal, while platform admins use /admin/*.

    Accepts both the canonical 'company' role (assigned to new org
    signups) and the legacy 'organization' role for accounts created
    before the rename. New accounts always use 'company'.
    """
    if current_user.role not in ("company", "organization"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Organization portal access required.",
        )
    from backend.tenant import _resolve_company_id

    company_id = _resolve_company_id(current_user, db)
    if company_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Organization portal access required.",
        )
    membership = (
        db.query(CompanyMember)
        .filter(
            CompanyMember.company_id == company_id,
            CompanyMember.user_id == current_user.id,
            CompanyMember.is_active,
        )
        .first()
    )
    if not membership or membership.role not in ("owner", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Organization portal access required.",
        )
    current_user._company_id = company_id
    current_user._company_role = membership.role
    return current_user


def check_admin(user: User):
    if not is_admin_user(user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required"
        )


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if not is_admin_user(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required"
        )
    return current_user


def require_candidate(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role not in ["candidate", "admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Candidate access required"
        )
    return current_user


def require_mentor(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role not in ["mentor", "admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Mentor access required"
        )
    return current_user


def require_tier(required_tier: str):
    """
    Dependency factory to require a specific subscription tier.
    """

    def tier_dependency(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role == "admin":
            return current_user

        tier = (get_user_tier(current_user) or "").lower()
        # Enterprise/pro+ tiers satisfy any lower tier requirement
        hierarchy = {"free": 0, "starter": 1, "pro": 2, "pro_plus": 3, "enterprise": 4}
        if hierarchy.get(tier, 0) < hierarchy.get(required_tier, 0):
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail=f"This feature requires a {required_tier.upper()} subscription tier.",
            )
        return current_user

    return tier_dependency


def require_pro_tier(current_user: User = Depends(get_current_user)) -> User:
    """
    Shorthand dependency for Pro tier access.
    Pro_plus and enterprise tiers also satisfy this requirement.
    """
    if current_user.role == "admin":
        return current_user

    tier = (get_user_tier(current_user) or "").lower()
    if tier not in ("pro", "pro_plus", "enterprise"):
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="This feature requires a PRO subscription tier.",
        )
    return current_user


def require_credits(resource: str, credits: int = 1, ref_resolver=None):
    """
    Dependency factory: reserve ``credits`` from the user's credit wallet
    before the endpoint runs. Server-side single choke point for all AI /
    paid features. Raises 402 with upgrade guidance on insufficient funds.

    ``ref_resolver(request, db, current_user)`` returns an optional stable
    reference id (e.g. application id) used to build the idempotency key so
    a retried HTTP request cannot double-debit.
    """

    async def credit_dependency(
        request: Request,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ):
        from backend.credit_service import consume_credits

        ref = None
        if ref_resolver is not None:
            try:
                ref = ref_resolver(request, db, current_user)
            except Exception as e:
                logger.warning(f"require_credits ref_resolver failed: {e}")

        try:
            from backend.credit_service import consume_credits, effective_credit_cost

            # Admin-configured price may override the caller's default — show
            # the real cost in the 402 payload. When gating is off or cost 0,
            # consume_credits returns a free no-op tx (no ValueError raised).
            real_cost = effective_credit_cost(db, resource, credits)
            tx = consume_credits(
                db,
                current_user,
                credits,
                resource,
                reference_type=resource,
                reference_id=ref,
            )
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail={
                    "error": "insufficient_credits",
                    "message": f"This feature costs {real_cost} credit(s) and you don't have enough.",
                    "cost": real_cost,
                    "upgrade_url": "/subscription",
                },
            )
        except Exception as e:
            logger.error(
                f"require_credits consume failed for user {current_user.id}: {e}"
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Could not process credits at this time.",
            )

        request.state.credit_tx = tx
        return tx

    return credit_dependency


# ============================================
# PAGINATION HELPER
# ============================================


def paginate(query, page: int = 1, per_page: int = 20):
    """
    Paginate a SQLAlchemy query.

    Args:
        query: SQLAlchemy query object
        page: Page number (1-indexed)
        per_page: Items per page

    Returns:
        Paginated query with offset and limit applied
    """
    if page < 1:
        page = 1
    if per_page < 1:
        per_page = 20
    if per_page > 100:  # Max 100 items per page
        per_page = 100

    offset = (page - 1) * per_page
    return query.offset(offset).limit(per_page)


def get_pagination_meta(total_count: int, page: int, per_page: int):
    """
    Generate pagination metadata.

    Returns:
        Dictionary with pagination info (total, page, per_page, total_pages, has_next, has_prev)
    """
    total_pages = (total_count + per_page - 1) // per_page  # Ceiling division

    return {
        "total": total_count,
        "page": page,
        "per_page": per_page,
        "total_pages": total_pages,
        "has_next": page < total_pages,
        "has_prev": page > 1,
    }
