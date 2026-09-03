import io
import os
import uuid
import zipfile
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile

from backend.config import get_settings
from backend.database import User
from backend.dependencies import get_current_user
from backend.security import secure_filename

router = APIRouter(tags=["uploads"])

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
settings = get_settings()
MAX_UPLOAD_SIZE_BYTES = settings.max_upload_size
MAX_UPLOAD_SIZE_MB = max(1, MAX_UPLOAD_SIZE_BYTES // (1024 * 1024))

MAGIC_BYTES = {
    b"\xff\xd8\xff": "image/jpeg",
    b"\x89PNG\r\n\x1a\n": "image/png",
    b"GIF87a": "image/gif",
    b"GIF89a": "image/gif",
    b"%PDF": "application/pdf",
    b"PK\x03\x04": "application/zip",
}

MAX_ZIP_RATIO = 100  # Maximum decompression ratio (100:1)


@router.post("/upload")
async def upload_file(
    request: Request,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    allowed_extensions = {
        "jpg",
        "jpeg",
        "png",
        "gif",
        "mp4",
        "webm",
        "pdf",
        "txt",
        "zip",
    }

    # Sanitize filename first, then extract extension
    safe_original = secure_filename(file.filename or "")
    file_ext = os.path.splitext(safe_original)[1].lower().lstrip(".")
    if not file_ext or file_ext not in allowed_extensions:
        raise HTTPException(status_code=400, detail="Invalid file extension")

    os.makedirs(UPLOAD_DIR, exist_ok=True)
    filename = f"upload_{current_user.id}_{int(datetime.now(UTC).timestamp())}_{uuid.uuid4().hex[:8]}.{file_ext}"
    file_path = os.path.join(UPLOAD_DIR, filename)

    bytes_written = 0
    entire_content = b""
    try:
        while True:
            chunk = await file.read(65536)
            if not chunk:
                break
            entire_content += chunk
            bytes_written += len(chunk)
            if bytes_written > MAX_UPLOAD_SIZE_BYTES:
                raise HTTPException(
                    status_code=400,
                    detail=f"File too large. Maximum size is {MAX_UPLOAD_SIZE_MB}MB.",
                )

        # Read all content before validation
        if not entire_content:
            raise HTTPException(status_code=400, detail="Empty file")

        # Magic byte validation on full content header
        matched = False
        for magic, _mime in MAGIC_BYTES.items():
            if entire_content.startswith(magic):
                matched = True
                break
        if not matched and file_ext != "txt":
            raise HTTPException(
                status_code=400, detail="File content does not match expected format"
            )

        # ZIP bomb protection: check decompression ratio
        if file_ext == "zip":
            compressed_size = len(entire_content)
            try:
                with zipfile.ZipFile(io.BytesIO(entire_content)) as zf:
                    for info in zf.infolist():
                        if info.file_size > compressed_size * MAX_ZIP_RATIO:
                            # Clean up partial file
                            raise HTTPException(
                                status_code=400,
                                detail="File rejected: decompression ratio exceeds safe limit (potential zip bomb).",
                            )
            except zipfile.BadZipFile:
                raise HTTPException(status_code=400, detail="Invalid ZIP file")

        # Write validated content to disk
        with open(file_path, "wb") as buffer:
            buffer.write(entire_content)

    except HTTPException:
        if os.path.exists(file_path):
            os.remove(file_path)
        raise

    base_url = str(request.base_url).rstrip("/")
    return {"url": f"{base_url}/uploads/{filename}", "filename": filename}
