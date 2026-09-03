import os
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, JSONResponse

from ..config import get_settings
from ..database import User
from ..dependencies import require_recruiter
from ..profile_helpers import get_user_tier

router = APIRouter(prefix="/recruiter", tags=["Recruiter Desktop"])


@router.get("/download/{platform}")
async def download_app(platform: str, recruiter: User = Depends(require_recruiter)):
    """
    Downloads the desktop application for the specified platform.
    Platforms: 'win', 'mac', 'linux'
    """
    if get_user_tier(recruiter) not in ["pro", "enterprise", "admin"]:
        raise HTTPException(
            status_code=403,
            detail="Desktop App is only available for Pro and Enterprise plans.",
        )

    # In a real production scenario, these would point to built binaries in an S3 bucket or /dist folder
    # For now, we return a helpful message since binaries must be built per OS

    platforms = {
        "win": "CandwayATS_Setup_1.0.4.exe",
        "mac": "CandwayATS_1.0.4.dmg",
        "linux": "CandwayATS_1.0.4.AppImage",
    }

    if platform not in platforms:
        raise HTTPException(status_code=400, detail="Invalid platform specified.")

    file_path = os.path.join(os.getcwd(), "downloads", platforms[platform])

    if not os.path.exists(file_path):
        # Fallback if file doesn't exist yet
        return JSONResponse(
            {
                "status": "building",
                "message": f"Our cloud engine is currently packaging the latest {platform.upper()} build. Please try again in 5 minutes.",
            },
            status_code=202,
        )

    return FileResponse(
        path=file_path,
        filename=platforms[platform],
        media_type="application/octet-stream",
    )


@router.get("/license")
async def get_license(recruiter: User = Depends(require_recruiter)):
    """
    Returns the recruiter's license key for the desktop app.
    """
    # Generate a license key using the configured secret
    import hashlib

    settings = get_settings()
    secret = settings.desktop_license_secret or settings.secret_key
    if not secret:
        raise RuntimeError("DESKTOP_LICENSE_SECRET not configured")
    key_base = f"CWA-{recruiter.id}-{recruiter.email}-{secret}"
    key = hashlib.sha256(key_base.encode()).hexdigest().upper()[:16]
    formatted_key = f"CWA-{key[:4]}-{key[4:8]}-{key[8:12]}-{key[12:16]}"

    # License valid for 1 year from now
    expires = (datetime.now(UTC) + timedelta(days=365)).strftime("%Y-%m-%d")

    return {
        "license_key": formatted_key,
        "tier": get_user_tier(recruiter),
        "expires": expires,
    }
