"""Page serving router -- legacy HTML pages removed.

All page routes now serve the React SPA (static/app/index.html) so that
client-side react-router handles them. Only a few redirect helpers and
cookie-clearing actions remain.

CSP nonce is injected into the inline theme script via {{ csp_nonce }}
placeholder in index.html.
"""

import os
import secrets

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from backend.database import User
from backend.dependencies import require_candidate, require_recruiter

router = APIRouter(tags=["pages"])

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SPA_INDEX = os.path.join(BASE_DIR, "static", "app", "index.html")

# Cache the SPA HTML template at import time
_spa_html_template: str | None = None


def _load_spa_template() -> str:
    with open(SPA_INDEX, encoding="utf-8") as f:
        return f.read()


def _spa(request: Request) -> HTMLResponse:
    """Serve the SPA index.html with CSP nonce injected.

    index.html must never be cached by the browser: its hashed asset URLs
    change on every build, so a stale cached copy references deleted chunks
    and breaks the SPA ("Failed to fetch dynamically imported module").
    """
    nonce = request.scope.get("csp_nonce", "") or secrets.token_urlsafe(16)
    try:
        html = _load_spa_template().replace("{{ csp_nonce }}", nonce)
    except (FileNotFoundError, OSError):
        return HTMLResponse(
            status_code=503,
            content="<h1>React SPA not built. Run: cd frontend && npm run build</h1>",
        )
    return HTMLResponse(
        content=html,
        headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
    )


@router.get("/")
async def read_root(request: Request):
    if os.path.isfile(SPA_INDEX):
        return _spa(request)
    return JSONResponse(
        status_code=503,
        content={
            "detail": "React SPA not built. Run: cd frontend && npm run build",
            "hint": "For development, start the Vite dev server: cd frontend && npm run dev",
        },
    )


@router.get("/logout")
async def logout_page(response: Response):
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("csrf_token", path="/")
    return RedirectResponse(url="/auth/login", status_code=302)


@router.get("/recruiter")
async def recruiter_root():
    return RedirectResponse(url="/recruiter/dashboard", status_code=302)


@router.get("/admin")
async def admin_root(request: Request):
    if request.cookies.get("access_token"):
        return RedirectResponse(url="/admin/dashboard", status_code=302)
    return RedirectResponse(url="/auth/login", status_code=302)


@router.get("/candidate/applications/{app_id}")
async def candidate_application_detail(
    app_id: int, user: User = Depends(require_candidate)
):
    return RedirectResponse(url="/candidate/applications", status_code=302)


@router.get("/candidate/offers/{offer_id}/accept")
async def candidate_offer_accept(offer_id: int):
    return RedirectResponse(
        url=f"/candidate/esign-view?offer_id={offer_id}&action=accept",
        status_code=302,
    )


@router.get("/candidate/offers/{offer_id}/decline")
async def candidate_offer_decline(offer_id: int):
    return RedirectResponse(
        url=f"/candidate/esign-view?offer_id={offer_id}&action=decline",
        status_code=302,
    )


@router.get("/recruiter/candidate/{app_id}/report")
async def recruiter_ghost_report(app_id: int, user: User = Depends(require_recruiter)):
    return RedirectResponse(
        url=f"/recruiter/ghost-report?app_id={app_id}", status_code=302
    )


@router.get("/recruiter/jobs/{job_id}")
async def recruiter_job_detail(job_id: int):
    return RedirectResponse(url=f"/recruiter/jobs?highlight={job_id}", status_code=302)


@router.get("/recruiter/scoring-preview")
async def recruiter_scoring_preview(request: Request):
    return _spa(request)


@router.get("/test-pm-direct")
async def test_pm_direct():
    return JSONResponse({"status": "ok", "route": "test-pm-direct working"})


@router.get("/{page_name}.html")
async def read_html(page_name: str, request: Request):
    if not page_name or not all(c.isalnum() or c in "-_" for c in page_name):
        raise HTTPException(status_code=400, detail="Invalid page name")
    if os.path.isfile(SPA_INDEX):
        return _spa(request)
    raise HTTPException(status_code=404, detail="Page not found")
