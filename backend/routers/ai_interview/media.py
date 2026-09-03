import json
import os
import re
import secrets
import shutil
import tempfile
from datetime import datetime
from typing import Optional, Tuple

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.orm import Session
from starlette.background import BackgroundTask

from backend.authz import get_application_for_recruiter
from backend.config import get_settings
from backend.database import Application, User
from backend.dependencies import get_current_user, get_db, get_interview_access
from backend.entity_writer import sync_ai_interview_session, sync_cv_document
from backend.logger import logger
from backend.routers.ai_interview.utils import safe_user_role

try:
    import edge_tts

    EDGE_TTS_AVAILABLE = True
except ImportError:
    EDGE_TTS_AVAILABLE = False

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

router = APIRouter(tags=["ai-interview"])


def _sanitise_filename(filename: str) -> str:
    name = os.path.basename(filename)
    name = re.sub(r"[^\w\-\.]", "_", name)
    if not name or name.startswith("."):
        name = "upload"
    return name[:100]


@router.post("/interview/upload-video")
async def upload_interview_video(
    application_id: int = Depends(lambda application_id: application_id),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    auth: Tuple[Optional[User], Application] = Depends(get_interview_access),
    background_tasks: BackgroundTasks = BackgroundTasks(),
):
    current_user, app = auth
    if not app:
        if current_user and safe_user_role(current_user) in ["recruiter", "admin"]:
            app = get_application_for_recruiter(application_id, current_user, db)
        else:
            app = db.query(Application).filter(Application.id == application_id).first()

    if not app:
        raise HTTPException(status_code=404, detail="Application not found")

    MAX_SIZE = 50 * 1024 * 1024

    content = await file.read()

    if len(content) > MAX_SIZE:
        raise HTTPException(status_code=413, detail="Video file too large (max 50MB)")

    if len(content) == 0:
        raise HTTPException(status_code=400, detail="File is empty")

    original_filename = file.filename or ""
    if not original_filename.lower().endswith((".webm", ".mp4", ".mov", ".avi")):
        raise HTTPException(
            status_code=400, detail="Invalid file type. Only video files allowed."
        )

    if len(content) >= 4:
        first_four = content[:4]
        is_webm = first_four == b"\x1a\x45\xdf\xa3"
        is_mp4_like = b"ftyp" in first_four or content[4:8] == b"ftyp"

        if not (is_webm or is_mp4_like):
            if not (
                len(content) >= 12
                and content[:4] == b"RIFF"
                and content[8:12] == b"AVI "
            ):
                logger.warning(
                    f"Suspicious file upload for app {application_id}: magic bytes {first_four.hex()}"
                )
                raise HTTPException(
                    status_code=400, detail="File is not a valid video file"
                )

    await file.seek(0)

    upload_dir = os.path.join(_BASE_DIR, "uploads", "videos")
    if not os.path.exists(upload_dir):
        os.makedirs(upload_dir, exist_ok=True)

    random_suffix = secrets.token_hex(8)
    filename = f"video_{application_id}_{random_suffix}.webm"

    filename = os.path.basename(filename)
    file_path = os.path.join(upload_dir, filename)

    upload_dir_abs = os.path.abspath(upload_dir)
    file_path_abs = os.path.abspath(file_path)
    if not file_path_abs.startswith(upload_dir_abs):
        raise HTTPException(status_code=400, detail="Invalid file path")

    with open(file_path, "wb") as buffer:
        buffer.write(content)

    sync_ai_interview_session(db, app, video_file_path=f"uploads/videos/{filename}")
    db.commit()

    background_tasks.add_task(process_video_transcription, app.id, app.company_id)

    return {"status": "success", "message": "Video uploaded, processing started."}


@router.post("/interview/upload-segment")
async def upload_interview_video_segment(
    application_id: int = 0,
    video_segment: UploadFile = File(...),
    db: Session = Depends(get_db),
    auth: Tuple[Optional[User], Application] = Depends(get_interview_access),
):
    current_user, app = auth
    if not app:
        if current_user and safe_user_role(current_user) in ["recruiter", "admin"]:
            app = get_application_for_recruiter(application_id, current_user, db)
        else:
            app = db.query(Application).filter(Application.id == application_id).first()

    if not app:
        raise HTTPException(status_code=404, detail="Application not found")

    MAX_SEGMENT_SIZE = 10 * 1024 * 1024

    content = await video_segment.read()

    if len(content) == 0:
        raise HTTPException(status_code=400, detail="Segment is empty")

    if len(content) > MAX_SEGMENT_SIZE:
        raise HTTPException(status_code=413, detail="Segment too large (max 10MB)")

    if len(content) >= 4:
        first_four = content[:4]
        is_webm = first_four == b"\x1a\x45\xdf\xa3"
        if not is_webm:
            logger.warning(
                f"Suspicious segment upload for app {application_id}: magic bytes {first_four.hex()}"
            )
            raise HTTPException(
                status_code=400, detail="Segment is not a valid WebM video"
            )

    upload_dir = os.path.join(
        _BASE_DIR,
        "uploads",
        "video_segments",
        str(app.id),
    )
    os.makedirs(upload_dir, exist_ok=True)

    segment_filename = f"seg_{secrets.token_hex(8)}.webm"
    segment_path = os.path.join(upload_dir, segment_filename)

    upload_dir_abs = os.path.abspath(upload_dir)
    segment_path_abs = os.path.abspath(segment_path)
    if not segment_path_abs.startswith(upload_dir_abs):
        raise HTTPException(status_code=400, detail="Invalid segment path")

    with open(segment_path, "wb") as buffer:
        buffer.write(content)

    try:
        existing_segments = (
            json.loads(app.video_file_path or "[]")
            if app.video_file_path and app.video_file_path.startswith("[")
            else []
        )
    except Exception:
        existing_segments = []

    relative_path = os.path.join(
        "uploads", "video_segments", str(app.id), segment_filename
    )
    existing_segments.append(relative_path)
    sync_ai_interview_session(db, app, video_file_path=json.dumps(existing_segments))
    db.commit()

    logger.info(
        f"[SEGMENT UPLOAD] App {app.id}: segment {segment_filename} saved ({len(content)} bytes)"
    )

    return {"status": "success", "segment": segment_filename}


async def process_video_transcription(application_id: int, company_id: int = None):
    import os

    import httpx

    from backend.database import Application, SessionLocal

    settings = get_settings()
    db = SessionLocal()
    try:
        app = (
            db.query(Application)
            .filter(
                Application.id == application_id,
                Application.company_id == company_id,
            )
            .first()
        )
        if not app or not app.video_file_path:
            logger.warning(f"[STT] App {application_id} not found or has no video.")
            return
        video_path = app.video_file_path

        full_path = os.path.join(_BASE_DIR, video_path)
        if not os.path.exists(full_path):
            logger.error(f"Video file not found: {full_path}")
            return

        transcript = None
        error_msg = None
        status_code = None

        try:
            with open(full_path, "rb") as audio_file:
                files = {
                    "file": (os.path.basename(full_path), audio_file, "video/webm")
                }
                data = {"model": "whisper-large-v3", "response_format": "json"}
                async with httpx.AsyncClient(timeout=120.0) as client:
                    response = await client.post(
                        "https://api.groq.com/openai/v1/audio/transcriptions",
                        headers={"Authorization": f"Bearer {settings.groq_api_key}"},
                        files=files,
                        data=data,
                    )
                    status_code = response.status_code
                    if status_code == 200:
                        transcript = response.json().get("text", "")
                        logger.info(
                            f"Video transcription successful for app {application_id}"
                        )
                    else:
                        error_msg = response.text
                        logger.error(f"Groq STT Failed ({status_code}): {error_msg}")
        except Exception as e:
            logger.error(f"Transcription exception: {e}")
            error_msg = str(e)

        with db.begin():
            app = db.query(Application).filter(Application.id == application_id).first()
            if not app:
                return

            if transcript:
                try:
                    analysis = json.loads(app.analysis_json or "{}")
                    analysis["video_verification"] = (
                        "Transcription available for review."
                    )
                    sync_cv_document(db, app, analysis_json=analysis)
                except Exception:
                    pass
            else:
                sync_ai_interview_session(
                    db, app, interview_state="transcription_failed"
                )
    finally:
        db.close()


@router.post("/voice/stt")
async def speech_to_text(
    file: UploadFile = File(...), current_user: User = Depends(get_current_user)
):
    file_path = None
    try:
        temp_dir = tempfile.gettempdir()
        fd, file_path = tempfile.mkstemp(suffix=".webm", dir=temp_dir)
        os.close(fd)

        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        settings = get_settings()
        with open(file_path, "rb") as audio_file:
            files = {"file": (file.filename, audio_file, file.content_type)}
            data = {"model": "whisper-large-v3", "response_format": "json"}
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    "https://api.groq.com/openai/v1/audio/transcriptions",
                    headers={"Authorization": f"Bearer {settings.groq_api_key}"},
                    files=files,
                    data=data,
                )

        if response.status_code == 200:
            result = response.json()
            transcript = result.get("text", "")
            logger.info(f"STT Successful: {transcript[:50]}...")
            return {"text": transcript}
        else:
            logger.error(f"Groq STT Failed: {response.status_code} - {response.text}")
            return JSONResponse(
                status_code=503,
                content={
                    "detail": "Voice transcription failed. Please type your answer."
                },
            )
    except Exception as e:
        logger.error(f"STT Exception: {e}", exc_info=True)
        return JSONResponse(
            status_code=503,
            content={
                "detail": "Voice transcription unavailable. Please type your answer."
            },
        )
    finally:
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
            except OSError:
                pass


@router.post("/voice/tts")
async def text_to_speech(payload: dict, current_user: User = Depends(get_current_user)):
    import re

    text = payload.get("text", "")
    if not text or not text.strip():
        raise HTTPException(400, "Text is required")

    MAX_TTS_CHARS = 2000
    if len(text) > MAX_TTS_CHARS:
        raise HTTPException(
            400, f"Text too long. Maximum {MAX_TTS_CHARS} characters allowed."
        )

    text = re.sub(r"<[^>]+>", "", text).strip()
    if not text:
        raise HTTPException(400, "Text is empty after sanitization")

    if not EDGE_TTS_AVAILABLE:
        return JSONResponse(
            status_code=503,
            content={
                "detail": "Text-to-speech service unavailable. Using browser speech.",
                "fallback": "browser_speech",
                "text": text,
            },
        )

    output_file = None
    try:
        voice = "en-US-ChristopherNeural"
        output_file = os.path.join(
            tempfile.gettempdir(), f"tts_{datetime.now().timestamp()}.mp3"
        )
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(output_file)

        def cleanup():
            if output_file and os.path.exists(output_file):
                try:
                    os.remove(output_file)
                except Exception:
                    pass

        return StreamingResponse(
            open(output_file, "rb"),
            media_type="audio/mpeg",
            background=BackgroundTask(cleanup),
        )
    except Exception as e:
        logger.error(f"TTS Generation failed: {e}")
        if output_file and os.path.exists(output_file):
            os.remove(output_file)
        return JSONResponse(
            status_code=500,
            content={
                "detail": "Text-to-speech generation failed. Using browser speech.",
                "fallback": "browser_speech",
                "text": text,
            },
        )
