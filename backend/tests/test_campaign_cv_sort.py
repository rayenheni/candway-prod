"""Campaign candidate list: ``sort_by=cv_score`` must order rows by exactly the
value the response displays.

The displayed ``cv_score`` is the canonical ``EvaluationResult.cv_score`` of
the latest EvaluationSession, falling back to the legacy
``Application.analysis_score``.  The sort key previously ignored the legacy
fallback, so legacy rows were shown with a score but sorted as unscored.
"""

import pytest

from backend.database import (
    Application,
    BatchJob,
    EvaluationResult,
    EvaluationSession,
    Job,
)

# name -> (legacy analysis_score, [cv_score per session, oldest first])
# ``None`` in the session list means a session whose result has no cv_score.
ROWS = {
    "canonical_beats_legacy": (10.0, [90.0]),
    "legacy_only": (80.0, []),
    "canonical_only": (None, [70.0]),
    "null_canonical_uses_legacy": (60.0, [None]),
    "latest_session_wins": (None, [99.0, 50.0]),
    "no_score": (None, []),
}
EXPECTED_DESC = [
    ("canonical_beats_legacy", 90.0),
    ("legacy_only", 80.0),
    ("canonical_only", 70.0),
    ("null_canonical_uses_legacy", 60.0),
    ("latest_session_wins", 50.0),
    ("no_score", None),
]
# Unscored rows stay last in both directions.
EXPECTED_ASC = list(reversed(EXPECTED_DESC[:-1])) + [EXPECTED_DESC[-1]]


@pytest.fixture
def batch_id(db_session, test_company, test_recruiter):
    job = Job(
        title="CV Sort Role",
        recruiter_id=test_recruiter.id,
        company_id=test_company.id,
        company_name=test_company.name,
        location="Remote",
    )
    db_session.add(job)
    db_session.flush()
    batch = BatchJob(
        recruiter_id=test_recruiter.id,
        job_id=job.id,
        company_id=test_company.id,
        title="CV Sort Batch",
        status="active",
        worker_status="completed",
    )
    db_session.add(batch)
    db_session.flush()

    for name, (legacy, session_scores) in ROWS.items():
        app = Application(
            batch_id=batch.id,
            job_id=job.id,
            company_id=test_company.id,
            full_name=name,
            email=f"{name}@cvsort.test",
            status="screening",
            analysis_score=legacy,
        )
        db_session.add(app)
        db_session.flush()
        for cv in session_scores:
            es = EvaluationSession(
                application_id=app.id,
                company_id=test_company.id,
                status="completed",
                interview_state="not_started",
            )
            db_session.add(es)
            db_session.flush()
            db_session.add(
                EvaluationResult(
                    evaluation_session_id=es.id,
                    company_id=test_company.id,
                    scoring_status="PENDING",
                    cv_score=cv,
                )
            )
            db_session.flush()
    db_session.commit()
    return batch.id


def _get(client, headers, batch_id, sort_dir, page=1, page_size=50):
    resp = client.get(
        f"/api/v1/recruiter/campaigns/{batch_id}/candidates",
        params={
            "sort_by": "cv_score",
            "sort_dir": sort_dir,
            "page": page,
            "page_size": page_size,
        },
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def _pairs(items):
    return [(c["full_name"], c["cv_score"]) for c in items]


def test_cv_sort_desc_mixes_canonical_and_legacy(client, recruiter_headers, batch_id):
    data = _get(client, recruiter_headers, batch_id, "desc")
    assert data["total"] == len(ROWS)
    assert _pairs(data["items"]) == EXPECTED_DESC


def test_cv_sort_asc_keeps_unscored_last(client, recruiter_headers, batch_id):
    data = _get(client, recruiter_headers, batch_id, "asc")
    assert _pairs(data["items"]) == EXPECTED_ASC


@pytest.mark.parametrize(
    ("sort_dir", "expected"), [("desc", EXPECTED_DESC), ("asc", EXPECTED_ASC)]
)
def test_cv_sort_is_stable_across_page_boundaries(
    client, recruiter_headers, batch_id, sort_dir, expected
):
    seen = []
    for page in (1, 2, 3):
        data = _get(client, recruiter_headers, batch_id, sort_dir, page, page_size=2)
        assert len(data["items"]) == 2
        seen.extend(_pairs(data["items"]))
    assert seen == expected
    # Past the end: empty page, not a wrap-around or duplicate.
    assert (
        _get(client, recruiter_headers, batch_id, sort_dir, 4, page_size=2)["items"]
        == []
    )
