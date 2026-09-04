import mimetypes
import os
import uuid
from typing import Optional

from fastapi import (
    Depends,
    FastAPI,
    HTTPException,
    Request,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import (
    FileResponse,
    HTMLResponse,
    JSONResponse,
    RedirectResponse,
    StreamingResponse,
)
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from starlette.middleware.trustedhost import TrustedHostMiddleware

# FIX: Ensure .js files are served with the correct MIME type on all OS
mimetypes.add_type("application/javascript", ".js")
mimetypes.add_type("application/javascript", ".mjs")

from backend.body_size_middleware import BodySizeLimitMiddleware  # noqa: E402
from backend.config import get_settings  # noqa: E402
from backend.database import User, get_db  # noqa: E402
from backend.dependencies import (  # noqa: E402
    get_current_user,
    get_optional_user,
)

# P0-01 FIX: Alembic is the single source of truth for schema. See
# backend/startup.py::startup_event for the auto-upgrade path and
# alembic/versions/ for revisions. Do NOT call Base.metadata.create_all
# at module import time; that bypasses migrations and silently
# diverges from the alembic head.
from backend.logger import logger  # noqa: E402
from backend.metrics_middleware import MetricsMiddleware  # noqa: E402
from backend.profile_helpers import get_user_is_super_admin  # noqa: E402
from backend.rate_limit_middleware import RateLimitMiddleware  # noqa: E402
from backend.realtime import manager as realtime_manager  # noqa: E402
from backend.routers import (  # noqa: E402
    achievements,
    admin,
    ai_interview,
    ai_sales,
    ai_utils,
    analytics,
    auth,
    calendar,
    candidate_management,
    candidate_portal,
    career,
    chatbot,
    consent,
    copilot,
    copilot_admin,
    courses,
    feature_flags,
    gdpr,
    hiring,
    jd_bias,
    mentor,
    messages,
    notifications,
    # onboarding router LAST to catch any unhandled routes
    onboarding,
    org,
    # pages router (HTML pages)
    pages,
    payments,
    # prompt management
    prompt_management,
    public,
    recommendations,
    recruiter_background_checks,
    recruiter_campaigns,
    recruiter_candidates,
    recruiter_collaboration,
    recruiter_dashboard,
    recruiter_desktop,
    recruiter_eeo,
    recruiter_enhancements,
    recruiter_interviews,
    recruiter_job_wizard,
    recruiter_jobs,
    recruiter_offers,
    recruiter_questions,
    recruiter_reengagement,
    recruiter_reports,
    recruiter_settings,
    recruiter_skill_trees,
    recruiter_talent_pool,
    search,
    setup,
    skill_progress,
    support,
    tracking,
    unsubscribe,
    uploads,
)
from backend.routers import monitoring as monitoring_router  # noqa: E402

# Import Routers
from backend.rubric.rubric_router import router as rubric_router  # noqa: E402
from backend.scoring_weights import router as scoring_weights_router  # noqa: E402
from backend.security import (  # noqa: E402
    CSRFMiddleware,
    RequestIDMiddleware,
    SanitizationMiddleware,
    SecurityHeadersMiddleware,
)
from backend.startup import shutdown_event, startup_event  # noqa: E402

settings = get_settings()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")  # backend/uploads to match systemd


def create_app() -> FastAPI:
    # 1. Sentry Initialization
    if settings.sentry_dsn:
        try:
            import sentry_sdk

            sentry_sdk.init(
                dsn=settings.sentry_dsn,
                environment=settings.environment,
                traces_sample_rate=0.5 if settings.debug else 0.05,
                profiles_sample_rate=0.5 if settings.debug else 0.05,
            )
            logger.info(f"Sentry initialized in {settings.environment} mode")
        except ImportError:
            logger.warning("sentry-sdk not installed. Skipping initialization.")

    # 2. App Initialization
    app = FastAPI(
        title="Candway Intelligence API",
        description="AI-Powered Recruitment & Learning Platform",
        version="1.0.0",
        docs_url="/api/docs" if not settings.is_prod else None,
        redoc_url="/api/redoc" if not settings.is_prod else None,
    )

    from fastapi.exceptions import RequestValidationError

    def _make_json_safe(obj):
        """Recursively convert non-JSON-serializable values to strings."""
        if isinstance(obj, dict):
            return {k: _make_json_safe(v) for k, v in obj.items()}
        elif isinstance(obj, (list, tuple)):
            return [_make_json_safe(v) for v in obj]
        elif isinstance(obj, bytes):
            return obj.decode("utf-8", errors="replace")
        elif isinstance(obj, (str, int, float, bool)) or obj is None:
            return obj
        else:
            return str(obj)

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ):
        from backend.logger import logger

        errors = _make_json_safe(exc.errors())
        logger.error(f"VALIDATION ERROR: {errors}")
        return JSONResponse(status_code=422, content={"detail": errors})

    # 3. Event Handlers
    app.router.add_event_handler("startup", startup_event)
    app.router.add_event_handler("shutdown", shutdown_event)

    # 3a. Database migrations are now handled via Alembic CLI (alembic upgrade head)

    # 4. CORS Configuration
    local_dev_origins = [
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "http://localhost:8001",
        "http://127.0.0.1:8001",
        "http://localhost:5500",
        "http://127.0.0.1:5500",
        "http://localhost:8002",
        "http://127.0.0.1:8002",
        # Vite dev server
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:8003",
        "http://127.0.0.1:8003",
        # Domain architecture explicit origins
        "https://candway.com",
        "https://www.candway.com",
        "https://app.candway.com",
    ]

    configured_origins = settings.allowed_origins_list

    if settings.is_prod:
        if not configured_origins:
            raise ValueError(
                "CRITICAL: ALLOWED_ORIGINS must be explicitly set in production."
            )
        origins = configured_origins
    else:
        origins = local_dev_origins[:]
        for origin in configured_origins:
            if origin not in origins:
                origins.append(origin)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
        allow_headers=[
            "Content-Type",
            "Authorization",
            "X-Request-ID",
            "X-CSRF-Token",
            "X-Forwarded-For",
            "X-Real-IP",
        ],
        expose_headers=["Content-Disposition", "X-CSRF-Token"],
    )

    if settings.is_prod:
        app.add_middleware(
            TrustedHostMiddleware,
            allowed_hosts=settings.allowed_hosts_list,
        )

    # 5. Security Middleware
    app.add_middleware(RequestIDMiddleware)
    app.add_middleware(SanitizationMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(CSRFMiddleware)
    # Body-size cap: reject oversized uploads/JSON before the route
    # handler runs. Tunable per-endpoint via env vars
    # (CANDWAY_BODY_LIMIT_<UPPER_SNAKE>).
    app.add_middleware(BodySizeLimitMiddleware)
    # P0-10 FIX: Prometheus instrumentation. The middleware must be
    # installed BEFORE RateLimitMiddleware so the rate-limit 429s
    # are still counted in `candway_http_requests_total`.
    try:
        app.add_middleware(MetricsMiddleware)
    except Exception as e:
        logger.warning(f"MetricsMiddleware not installed: {e}")
    if settings.rate_limit_enabled:
        app.add_middleware(
            RateLimitMiddleware,
            requests_per_minute=settings.rate_limit_per_minute,
            requests_per_hour=settings.rate_limit_per_hour,
        )

    # 6. Global Exception Handlers
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        import traceback

        error_id = uuid.uuid4().hex[:8]
        logger.error(f"CRITICAL ERROR {error_id}: {str(exc)}\n{traceback.format_exc()}")

        if "text/html" in request.headers.get("accept", ""):
            spa_index = os.path.join(BASE_DIR, "static", "app", "index.html")
            if os.path.exists(spa_index):
                return FileResponse(
                    spa_index,
                    status_code=500,
                    headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
                )
            return FileResponse(os.path.join(BASE_DIR, "500.html"), status_code=500)

        return JSONResponse(
            status_code=500,
            content={
                "detail": "Internal Server Error",
                "error_id": error_id,
            },
        )

    @app.exception_handler(404)
    async def not_found_handler(request: Request, exc: HTTPException):
        if "text/html" in request.headers.get("accept", ""):
            spa_index = os.path.join(BASE_DIR, "static", "app", "index.html")
            if os.path.exists(spa_index):
                return FileResponse(
                    spa_index,
                    status_code=404,
                    headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
                )
            return FileResponse(os.path.join(BASE_DIR, "404.html"), status_code=404)

        return JSONResponse(status_code=404, content={"detail": "Not Found"})

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        if exc.status_code == 401 and "text/html" in request.headers.get("accept", ""):
            # Redirect to React SPA login page
            resp = RedirectResponse(url="/auth/login")
            resp.delete_cookie("access_token", path="/")
            resp.delete_cookie("csrf_token", path="/")
            return resp
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
            headers=exc.headers,
        )

    @app.get("/favicon.ico", include_in_schema=False)
    async def favicon():
        fav_path = os.path.join(BASE_DIR, "public", "favicon.ico")
        if os.path.exists(fav_path):
            return FileResponse(fav_path)
        return JSONResponse(status_code=204, content=None)

    @app.get("/meta.json", include_in_schema=False)
    async def meta_json():
        meta_path = os.path.join(BASE_DIR, "public", "meta.json")
        if os.path.exists(meta_path):
            return FileResponse(meta_path, media_type="application/json")
        return JSONResponse(status_code=404, content={"detail": "Not found"})

    @app.get(
        "/.well-known/appspecific/com.chrome.devtools.json", include_in_schema=False
    )
    async def chrome_devtools_config():
        return {}

    # 7. Static Files
    os.makedirs(UPLOAD_DIR, exist_ok=True)

    # ── React SPA (Vite build output) ────────────────────────────
    # The React SPA is built with `npm run build` inside frontend/
    # and outputs to static/app/ (configured in frontend/vite.config.ts).
    # We serve the Vite-generated assets under /assets/ and handle
    # SPA routing with a catch-all that returns index.html.
    SPA_DIR = os.path.join(BASE_DIR, "static", "app")
    os.makedirs(SPA_DIR, exist_ok=True)

    # Serve Vite chunk assets (JS/CSS files with content hashes)
    spa_assets_dir = os.path.join(SPA_DIR, "assets")
    if os.path.isdir(spa_assets_dir):
        app.mount("/assets", StaticFiles(directory=spa_assets_dir), name="spa-assets")

    # Brand logo (also served by the frontend LogoMark via /candway_logo.png)
    logo_path = os.path.join(SPA_DIR, "candway_logo.png")
    if os.path.isfile(logo_path):
        from fastapi.responses import FileResponse

        @app.get("/candway_logo.png", include_in_schema=False)
        async def serve_candway_logo():
            return FileResponse(
                logo_path,
                media_type="image/png",
                headers={"Cache-Control": "public, max-age=86400"},
            )

    # Legacy static directories (kept for backward compatibility)
    legacy_css = os.path.join(BASE_DIR, "css")
    if os.path.isdir(legacy_css):
        app.mount("/css", StaticFiles(directory=legacy_css), name="css")
    legacy_js = os.path.join(BASE_DIR, "js")
    if os.path.isdir(legacy_js):
        app.mount("/js", StaticFiles(directory=legacy_js), name="js")
    legacy_assets = os.path.join(BASE_DIR, "assets")
    if os.path.isdir(legacy_assets):
        app.mount(
            "/legacy-assets", StaticFiles(directory=legacy_assets), name="legacy-assets"
        )
    promo_dir = os.path.join(BASE_DIR, "promo")
    if os.path.isdir(promo_dir):
        app.mount("/promo", StaticFiles(directory=promo_dir), name="promo")

    # 8. Include Routers
    api_routers = [
        auth.router,
        achievements.router,
        skill_progress.router,
        admin.router,
        recruiter_jobs.router,
        recruiter_job_wizard.router,
        recruiter_candidates.router,
        recruiter_dashboard.router,
        recruiter_desktop.router,
        recruiter_campaigns.router,
        recruiter_settings.router,
        recruiter_interviews.router,
        recruiter_collaboration.router,
        recruiter_offers.router,
        recruiter_background_checks.router,
        recruiter_enhancements.router,
        recruiter_eeo.router,
        recruiter_reengagement.router,
        recruiter_reports.router,
        recruiter_questions.router,
        recruiter_skill_trees.router,
        recruiter_talent_pool.router,
        copilot_admin.router,
        scoring_weights_router,
        feature_flags.router,
        gdpr.router,
        consent.router,
        payments.router,
        candidate_management.router,
        public.router,
        mentor.router,
        ai_interview.router,
        career.router,
        chatbot.router,
        candidate_portal.router,
        tracking.router,
        support.router,
        courses.router,
        recommendations.router,
        hiring.router,
        jd_bias.router,
        unsubscribe.router,
        copilot.router,
        search.router,
        org.router,
        analytics.router,
        calendar.router,
        ai_sales.router,
        setup.router,
        ai_utils.router,
        uploads.router,
        notifications.router,
        # onboarding router LAST to catch any unhandled routes
        onboarding.router,
        # prompt management
        prompt_management.router,
        messages.router,
        rubric_router,
    ]

    for r in api_routers:
        app.include_router(r, prefix="/api/v1")

    # Include Pages router (Root level) — legacy HTML pages
    app.include_router(pages.router)

    # ── Uploaded file serving ─────────────────────────────────────
    # Registered BEFORE the SPA catch-all below so /uploads/* requests
    # reach this handler instead of being swallowed by the SPA fallback.
    @app.get("/uploads/{filename:path}")
    async def serve_uploaded_file(
        filename: str,
        request: Request,
        current_user: Optional[User] = Depends(get_optional_user),
        db: Session = Depends(get_db),
    ):
        safe_path = os.path.normpath(os.path.join(UPLOAD_DIR, filename))
        if not safe_path.startswith(os.path.normpath(UPLOAD_DIR)):
            raise HTTPException(status_code=403, detail="Access denied")

        if not os.path.isfile(safe_path):
            raise HTTPException(status_code=404, detail="File not found")

        ext = os.path.splitext(safe_path)[1].lower().lstrip(".")
        mime_map = {
            "jpg": "image/jpeg",
            "jpeg": "image/jpeg",
            "png": "image/png",
            "gif": "image/gif",
            "webp": "image/webp",
        }

        # Public marketing images — no auth required
        is_public_image = (
            filename.startswith("blog/") or filename.startswith("company_logo/")
        )
        if filename.startswith("company_"):
            # Legacy company logos written as company_<userid>_<ts>.<ext>
            comp_parts = os.path.basename(safe_path).split("_", 2)
            if (
                len(comp_parts) >= 2
                and comp_parts[0] == "company"
                and comp_parts[1].isdigit()
                and ext in mime_map
            ):
                is_public_image = True

        if is_public_image:
            if ext not in mime_map:
                raise HTTPException(status_code=404, detail="File not found")
            content_type = mime_map.get(ext, "application/octet-stream")
            headers = {
                "Cache-Control": "public, max-age=86400",
                "X-Content-Type-Options": "nosniff",
            }

            async def public_file_stream():
                with open(safe_path, "rb") as f:
                    while chunk := f.read(65536):
                        yield chunk

            return StreamingResponse(
                public_file_stream(), media_type=content_type, headers=headers
            )

        # Every remaining file requires an authenticated user.
        if current_user is None:
            raise HTTPException(status_code=401, detail="Not authenticated")

        # Ownership enforcement. Previously the check only fired when the
        # basename matched `upload_<userid>_*`. Any other filename (e.g.
        # qualification uploads with the `{user_id}_{uuid}_{category}`
        # pattern, or company_*/avatar files) bypassed the check entirely,
        # allowing any logged-in user to fetch any file under UPLOAD_DIR.
        # The new logic tries every known owner-encoding pattern and
        # denies by default if no owner can be resolved.
        basename = os.path.basename(safe_path)
        owner_id = None

        # Pattern 1: explicit upload_<userid>_* prefix
        parts = basename.split("_", 2)
        if len(parts) >= 2 and parts[0] == "upload" and parts[1].isdigit():
            owner_id = int(parts[1])

        # Pattern 2: qualification uploads use
        # `{user_id}_{uuid12}_{category}.{ext}`.
        if owner_id is None:
            qual_parts = basename.split("_", 1)
            if qual_parts and qual_parts[0].isdigit():
                owner_id = int(qual_parts[0])

        # Pattern 3: company_<userid>_<timestamp>.ext (company logos)
        if owner_id is None:
            comp_parts = basename.split("_", 2)
            if (
                len(comp_parts) >= 2
                and comp_parts[0] == "company"
                and comp_parts[1].isdigit()
            ):
                owner_id = int(comp_parts[1])

        # Pattern 4: receipt_<userid>_<timestamp>.ext (payment receipts)
        if owner_id is None:
            rec_parts = basename.split("_", 2)
            if (
                len(rec_parts) >= 2
                and rec_parts[0] == "receipt"
                and rec_parts[1].isdigit()
            ):
                owner_id = int(rec_parts[1])

        # Pattern 5: video_<application_id>_<suffix>.webm (interview videos)
        # NOTE: resolves to application_id, not user_id — owner check uses DB query
        if owner_id is None:
            vid_parts = basename.split("_", 2)
            if (
                len(vid_parts) >= 2
                and vid_parts[0] == "video"
                and vid_parts[1].isdigit()
            ):
                from backend.database import Application

                app = (
                    db.query(Application)
                    .filter(Application.id == int(vid_parts[1]))
                    .first()
                )
                if app:
                    owner_id = app.user_id

        is_admin = current_user.role == "admin" or get_user_is_super_admin(current_user)

        # Bug B-29: signed-URL override. A recruiter who has been
        # authorised by the recruiter_candidates router can fetch
        # the candidate's CV via a short-lived HMAC token. This
        # avoids both the IDOR (recruiter guessing filenames) and
        # the need for a backdoor in the /uploads route.
        signed_token = request.query_params.get("token")
        signed_ok = False
        if owner_id is not None and signed_token:
            from backend.signed_url import verify_signed_cv_token

            signed_ok = verify_signed_cv_token(
                file_path=basename,
                token=signed_token,
                bearer_user_id=current_user.id,
            )
            if not signed_ok:
                logger.warning(
                    f"[UPLOADS] Invalid signed-URL token from user "
                    f"{current_user.id} for {basename}"
                )

        if signed_ok:
            # Skip the ownership check; the HMAC token is the
            # authorisation. Note we still require a logged-in
            # user (Depends(get_current_user) above).
            pass
        elif owner_id is None:
            # Could not resolve an owner — deny by default. Catches
            # UUID-only filenames and prevents unauthenticated guessing.
            if not is_admin:
                raise HTTPException(
                    status_code=403,
                    detail="File owner could not be verified",
                )
        elif owner_id != current_user.id:
            # Allow recruiters in the same company to access candidate avatars
            if filename.startswith("avatars/"):
                from backend.models.foundation.company import CompanyMember as _CM

                shared_company = (
                    db.query(_CM)
                    .filter(
                        _CM.user_id == owner_id,
                        _CM.is_active,
                    )
                    .first()
                )
                if shared_company:
                    is_recruiter = (
                        db.query(_CM)
                        .filter(
                            _CM.company_id == shared_company.company_id,
                            _CM.user_id == current_user.id,
                            _CM.is_active,
                        )
                        .first()
                    )
                    if is_recruiter:
                        pass
                    else:
                        raise HTTPException(status_code=403, detail="Access denied")
                else:
                    raise HTTPException(status_code=403, detail="Access denied")
            else:
                if not is_admin:
                    raise HTTPException(status_code=403, detail="Access denied")

        ext = os.path.splitext(safe_path)[1].lower().lstrip(".")
        mime_map = {
            "pdf": "application/pdf",
            "jpg": "image/jpeg",
            "jpeg": "image/jpeg",
            "png": "image/png",
            "gif": "image/gif",
            "mp4": "video/mp4",
            "webm": "video/webm",
            "txt": "text/plain",
            "zip": "application/zip",
        }
        content_type = mime_map.get(ext, "application/octet-stream")

        headers = {
            "Cache-Control": "private, max-age=3600",
            "X-Content-Type-Options": "nosniff",
            "Content-Disposition": f'inline; filename="{os.path.basename(safe_path)}"',
        }

        async def file_stream():
            with open(safe_path, "rb") as f:
                while chunk := f.read(65536):
                    yield chunk

        return StreamingResponse(
            file_stream(), media_type=content_type, headers=headers
        )

    # ── React SPA Catch-All ───────────────────────────────────────
    # Any route that is NOT matched by an API router or static mount
    # returns the React SPA index.html so that client-side routing
    # (react-router) handles the path (e.g. /dashboard, /auth/login).
    # IMPORTANT: This MUST be registered AFTER all other routers.
    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_react_spa(
        full_path: str,
        request: Request,
    ):
        # Protect admin SPA routes
        if full_path.startswith("admin/"):
            from backend.dependencies import get_current_admin, get_current_user
            from backend.database import get_db

            db_gen = get_db()
            db = next(db_gen)
            try:
                from backend.dependencies import _candidate_tokens

                # Extract the bearer token from the Authorization header
                # so SSR admin routes use the same auth path as the API.
                auth_header = request.headers.get("Authorization")
                bearer_token = None
                if auth_header:
                    scheme, _, credentials = auth_header.partition(" ")
                    if scheme.lower() == "bearer" and credentials.strip():
                        bearer_token = credentials.strip()

                candidates = _candidate_tokens(request, bearer_token)

                if not candidates:
                    # Do not disclose that an admin route exists.
                    overrides = getattr(request.app, "dependency_overrides", {})
                    if get_current_admin in overrides:
                        user = await overrides[get_current_admin]()
                    else:
                        raise HTTPException(
                            status_code=404,
                            detail="Not Found",
                        )
                else:
                    user = await get_current_user(
                        request=request,
                        token=candidates[0],
                        db=db,
                    )

                    await get_current_admin(user)

            except HTTPException:
                raise
            except Exception:
                # Do not disclose admin-route existence or authorization
                # details to unauthenticated/non-admin callers.
                raise HTTPException(
                    status_code=404,
                    detail="Not Found",
                )
            finally:
                try:
                    next(db_gen)
                except StopIteration:
                    pass

        # Never intercept API routes or WebSocket upgrades
        if full_path.startswith("api/") or full_path.startswith("ws/"):
            raise HTTPException(status_code=404, detail="Not Found")

        spa_index = os.path.join(BASE_DIR, "static", "app", "index.html")
        if os.path.isfile(spa_index):
            import secrets as _secrets

            nonce = request.scope.get("csp_nonce", "") or _secrets.token_urlsafe(16)
            try:
                with open(spa_index, encoding="utf-8") as f:
                    html = f.read()
                html = html.replace("{{ csp_nonce }}", nonce)
            except (FileNotFoundError, OSError):
                raise HTTPException(
                    status_code=503,
                    detail="React SPA not built. Run: cd frontend && npm run build",
                )
            # Never cache index.html: its hashed asset URLs change on every
            # build, so a stale cached copy references deleted chunks.
            return HTMLResponse(
                content=html,
                headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
            )

        # SPA not yet built — return a helpful dev-mode message
        return JSONResponse(
            status_code=503,
            content={
                "detail": "React SPA not built. Run: cd frontend && npm run build",
                "hint": "For development, start the Vite dev server: cd frontend && npm run dev",
            },
        )

    # P0-10 FIX: Prometheus /metrics and /breakers are exposed at
    # the ROOT (not under /api/v1) so the standard Prometheus
    # scrape config (which targets /metrics by default) Just Works
    # without a path rewrite.
    app.include_router(monitoring_router.router)

    # 9. WebSocket Endpoint (Secured with JWT or Interview HMAC)
    @app.websocket("/ws/{client_id}")
    async def websocket_endpoint(websocket: WebSocket, client_id: str):
        # Origin validation — reject unknown origins
        origin = (
            websocket.headers.get("origin") or websocket.headers.get("Origin") or ""
        )
        if origin:
            allowed_ws_origins = getattr(settings, "allowed_origins_list", [])
            # Also allow the configured frontend_url and base_url
            for url in (settings.frontend_url, settings.base_url):
                if url and url not in allowed_ws_origins:
                    allowed_ws_origins.append(url)
            # Local development origins
            for dev in (
                "http://localhost:8000",
                "http://127.0.0.1:8000",
                "http://localhost:8001",
                "http://127.0.0.1:8001",
                "http://localhost:8002",
                "http://127.0.0.1:8002",
            ):
                if dev not in allowed_ws_origins:
                    allowed_ws_origins.append(dev)
            origin_allowed = any(
                origin.rstrip("/") == o.rstrip("/") for o in allowed_ws_origins
            )
            if not origin_allowed:
                logger.warning(
                    f"WebSocket connection rejected from unknown origin: {origin}"
                )
                await websocket.close(code=4003, reason="Origin not allowed")
                return

        from typing import Optional

        from jose import JWTError
        from jose import jwt as jose_jwt

        from backend.database import Application, SessionLocal
        from backend.database import User as DBUser
        from backend.dependencies import (
            ALGORITHM,
            JWT_SECRET_KEY,
            verify_interview_token,
        )

        def _normalize_token(raw: Optional[str]) -> Optional[str]:
            if not raw:
                return None
            value = str(raw).strip()
            if value.lower().startswith("bearer "):
                value = value[7:].strip()
            if value == "cookie-auth":
                return None
            return value or None

        # Validate JWT or Interview Token from query params and/or auth cookie.
        token_candidates = []
        query_token = _normalize_token(websocket.query_params.get("token"))
        cookie_token = _normalize_token(websocket.cookies.get("access_token"))
        if query_token:
            token_candidates.append(query_token)
        if cookie_token and cookie_token not in token_candidates:
            token_candidates.append(cookie_token)

        if not token_candidates:
            await websocket.close(code=4001, reason="Missing auth token")
            return

        user_email = None
        is_interview_token = False

        # Attempt JWT Validation
        for token in token_candidates:
            try:
                payload = jose_jwt.decode(token, JWT_SECRET_KEY, algorithms=[ALGORITHM])
                user_email = payload.get("sub")
                if user_email:
                    break
            except JWTError:
                continue

        # If not JWT, attempt Interview HMAC Validation
        if not user_email:
            for token in token_candidates:
                try:
                    # In WS, we might not know if client_id is user_id or application_id yet
                    # But if it's an interview token, it MUST verify for the application_id
                    app_id = int(client_id)
                    if await verify_interview_token(app_id, token):
                        is_interview_token = True
                        break
                except (ValueError, TypeError):
                    continue

        if not user_email and not is_interview_token:
            await websocket.close(code=4003, reason="Token expired or invalid")
            return

        try:
            client_identifier = int(client_id)

            # Verification based on Auth Mode
            with SessionLocal() as db:
                if user_email:
                    auth_user = (
                        db.query(DBUser).filter(DBUser.email == user_email).first()
                    )
                    if auth_user is None:
                        await websocket.close(code=4003, reason="User not found")
                        return
                    # CRITICAL FIX: client_id must match the authenticated user's ID
                    # This prevents ID confusion attacks where a valid token for user A
                    # could be used to access resources of user B by changing client_id
                    if auth_user.id != client_identifier:
                        await websocket.close(
                            code=4003, reason="Client ID mismatch for user"
                        )
                        return
                elif is_interview_token:
                    # HMAC verified, just ensure application exists
                    # AND that the client_id matches the application_id
                    # This ensures the token is for THIS specific application
                    app = (
                        db.query(Application)
                        .filter(Application.id == client_identifier)
                        .first()
                    )
                    if not app:
                        await websocket.close(code=4004, reason="Application not found")
                        return
                    # Verify the token is actually for this application (redundant but safe)
                    if not await verify_interview_token(client_identifier, token):
                        await websocket.close(
                            code=4003, reason="Token verification failed"
                        )
                        return

            # Register connection using client_identifier (user_id OR application_id)
            await realtime_manager.connect(websocket, client_identifier)
            try:
                # FIX-7: Heartbeat-aware loop — prevents dead connections accumulating.
                # Sends a server-side ping every 30 s; closes if no activity for 60 s.
                import asyncio as _asyncio
                import time as _time

                PING_INTERVAL = 30  # seconds between server pings
                PONG_TIMEOUT = 60  # seconds to wait for client response

                last_pong = _time.time()

                async def _heartbeat_sender():
                    while True:
                        await _asyncio.sleep(PING_INTERVAL)
                        try:
                            # 1. Real WS protocol-level ping frame. The
                            #    browser/runtime auto-responds with a
                            #    pong without any application code on the
                            #    client. This is the cheap keep-alive
                            #    the WS spec is designed for (Bug B-21).
                            try:
                                await websocket.send_ping()
                            except (AttributeError, RuntimeError):
                                # Older FastAPI/Starlette versions or
                                # already-closed sockets — fall back to
                                # the JSON ping below.
                                pass

                            # 2. Application-level JSON ping for
                            #    clients that want a wall-clock
                            #    timestamp in the heartbeat payload.
                            await websocket.send_json(
                                {"type": "ping", "ts": _time.time()}
                            )
                        except Exception:
                            break  # Connection dead — exit sender

                async def _receiver():
                    nonlocal last_pong
                    while True:
                        try:
                            # receive() returns the next WS frame of
                            # *any* type (text, binary, ping, pong).
                            # This way both protocol-level pongs and
                            # application JSON pongs count as activity.
                            msg = await _asyncio.wait_for(
                                websocket.receive(), timeout=PONG_TIMEOUT
                            )
                            # Only update the liveness timestamp on
                            # actual messages, not on close frames.
                            if msg is not None and msg.get("type") not in (
                                "websocket.disconnect",
                            ):
                                last_pong = _time.time()
                                await realtime_manager.update_ping(
                                    websocket, client_identifier
                                )
                        except _asyncio.TimeoutError:
                            logger.warning(
                                f"WS client {client_identifier} timed out (no activity for {PONG_TIMEOUT}s)"
                            )
                            await websocket.close(code=1001, reason="Ping timeout")
                            break
                        except WebSocketDisconnect:
                            break

                sender_task = _asyncio.create_task(_heartbeat_sender())
                try:
                    await _receiver()
                finally:
                    sender_task.cancel()
                    try:
                        await sender_task
                    except _asyncio.CancelledError:
                        pass

            except WebSocketDisconnect:
                pass
            finally:
                await realtime_manager.disconnect(websocket, client_identifier)
        except (ValueError, TypeError):
            await websocket.close(code=4004, reason="Invalid client ID")
            return

    from sqlalchemy.exc import IntegrityError

    @app.exception_handler(IntegrityError)
    async def integrity_error_handler(request: Request, exc: IntegrityError):
        logger.warning(f"Database IntegrityError on {request.url}: {exc}")
        err_msg = str(exc).lower()
        if (
            "uq_applications_user_job" in err_msg
            or ("user_id" in err_msg and "job_id" in err_msg)
            or "duplicate" in err_msg
        ):
            return JSONResponse(
                status_code=409,
                content={"detail": "Candidate has already applied to this job."},
            )
        return JSONResponse(
            status_code=409,
            content={
                "detail": "Database integrity error. Record already exists or reference is invalid."
            },
        )

    return app


# Instantiate the global app instance for Uvicorn
app = create_app()
