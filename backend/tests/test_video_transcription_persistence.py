"""process_video_transcription must persist its outcome.

It used to wrap the write in ``with db.begin():`` on a session whose earlier
lookup had already autobegun a transaction, so SQLAlchemy raised
InvalidRequestError and neither ``transcription_failed`` nor the transcript
was ever stored.
"""

import asyncio
from unittest.mock import MagicMock, patch

import pytest

import backend.database
from backend.database import Application
from backend.models.evaluation.evaluation import EvaluationSession
from backend.routers.ai_interview.media import process_video_transcription


class _FakeClient:
    def __init__(self, response):
        self._response = response

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def post(self, *args, **kwargs):
        return self._response


@pytest.fixture
def video_app(db_session, test_company, tmp_path):
    video = tmp_path / "interview.webm"
    video.write_bytes(b"\x1a\x45\xdf\xa3 fake webm")
    app = Application(
        full_name="Video Candidate",
        email="video_candidate@test.com",
        declared_role="Engineer",
        status="applied",
        company_id=test_company.id,
        interview_state="completed",
    )
    db_session.add(app)
    db_session.commit()
    db_session.refresh(app)
    from backend.entity_writer import sync_ai_interview_session

    sync_ai_interview_session(db_session, app, video_file_path=str(video))
    db_session.commit()
    return app.id, test_company.id


def _run(app_id, company_id, status_code, payload=None):
    response = MagicMock(status_code=status_code, text="upstream error")
    response.json.return_value = payload or {}
    with patch("httpx.AsyncClient", return_value=_FakeClient(response)):
        asyncio.run(process_video_transcription(app_id, company_id))


def _session(app_id):
    db = backend.database.SessionLocal()
    try:
        app = db.query(Application).filter(Application.id == app_id).one()
        sess = (
            db.query(EvaluationSession)
            .filter(EvaluationSession.application_id == app_id)
            .order_by(EvaluationSession.id.desc())
            .first()
        )
        return app.interview_state, sess.video_transcript if sess else None
    finally:
        db.close()


def test_failed_transcription_is_persisted(video_app):
    app_id, company_id = video_app
    _run(app_id, company_id, 500)
    state, transcript = _session(app_id)
    assert state == "transcription_failed"
    assert transcript is None


def test_successful_transcription_stores_transcript(video_app):
    app_id, company_id = video_app
    _run(app_id, company_id, 200, {"text": "I led the migration to Postgres."})
    state, transcript = _session(app_id)
    assert state != "transcription_failed"
    assert transcript == "I led the migration to Postgres."
