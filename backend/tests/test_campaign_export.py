"""Campaign shortlist + CSV/PDF export: security and robustness cases.

Happy paths are covered in test_campaign_p1_features.py; this file checks
tenant isolation, authentication/role checks, CSV formula-injection
neutralisation, the CSV UTF-8 BOM, latin-1-unsafe names in the PDF (FPDF core
fonts; rendered as "?" - known limitation) and tier grouping.
"""

import csv
import io

import pytest

from backend.database import (
    Application,
    BatchJob,
    EvaluationResult,
    EvaluationSession,
    User,
)
from backend.dependencies import require_recruiter
from backend.main import app as fastapi_app
from backend.models.ats.pipeline import ApplicationStageHistory

UTF8_BOM = b"\xef\xbb\xbf"


def _csv_rows(resp):
    """Parse an export CSV, asserting it starts with exactly one UTF-8 BOM."""
    assert resp.content.startswith(UTF8_BOM), resp.content[:10]
    text = resp.content.decode("utf-8-sig")
    assert not text.startswith("\ufeff")
    return list(csv.DictReader(io.StringIO(text)))


@pytest.fixture
def campaign(db_session, test_recruiter, test_company):
    batch = BatchJob(
        recruiter_id=test_recruiter.id,
        company_id=test_company.id,
        title="Export Campaign",
        status="active",
    )
    db_session.add(batch)
    db_session.flush()

    def add(name, email, status="pending", cv=None, interview=None, state=None):
        app = Application(
            batch_id=batch.id,
            company_id=test_company.id,
            full_name=name,
            email=email,
            status=status,
        )
        db_session.add(app)
        db_session.flush()
        if cv is not None or interview is not None:
            es = EvaluationSession(
                application_id=app.id,
                company_id=test_company.id,
                status="completed" if state == "completed" else "created",
                interview_state=state or "not_started",
            )
            db_session.add(es)
            db_session.flush()
            db_session.add(
                EvaluationResult(
                    evaluation_session_id=es.id,
                    company_id=test_company.id,
                    # CV-only rows are PENDING (final_score NULL) per
                    # ck_eval_result_state_machine.
                    scoring_status="SCORED" if interview is not None else "PENDING",
                    cv_score=cv,
                    final_score=interview,
                )
            )
        return app

    apps = {
        "evil": add('=HYPERLINK("http://x")', "evil@x.tn", cv=40.0),
        "arabic": add("سارة بن علي", "sara@x.tn", "shortlisted", cv=80.0),
        "strong": add(
            "Strong One", "strong@x.tn", cv=60.0, interview=88.0, state="completed"
        ),
        "unscored": add("No Score", "none@x.tn"),
    }
    db_session.commit()
    return batch, apps


def test_cross_company_recruiter_gets_404(client, recruiter_headers_b, campaign):
    batch, apps = campaign
    base = f"/api/v1/recruiter/campaigns/{batch.id}"
    assert (
        client.get(f"{base}/export/csv", headers=recruiter_headers_b).status_code == 404
    )
    assert (
        client.get(f"{base}/export/pdf", headers=recruiter_headers_b).status_code == 404
    )
    resp = client.patch(
        f"{base}/candidates/{apps['strong'].id}/shortlist", headers=recruiter_headers_b
    )
    assert resp.status_code == 404


def test_shortlist_rejects_app_from_another_campaign(
    client, recruiter_headers, campaign, db_session, test_recruiter, test_company
):
    batch, apps = campaign
    other = BatchJob(
        recruiter_id=test_recruiter.id, company_id=test_company.id, title="Other"
    )
    db_session.add(other)
    db_session.commit()
    resp = client.patch(
        f"/api/v1/recruiter/campaigns/{other.id}/candidates/{apps['strong'].id}/shortlist",
        headers=recruiter_headers,
    )
    assert resp.status_code == 404


def test_shortlist_is_idempotent(client, recruiter_headers, campaign):
    batch, apps = campaign
    url = f"/api/v1/recruiter/campaigns/{batch.id}/candidates/{apps['strong'].id}/shortlist"
    for _ in range(2):
        resp = client.patch(url, headers=recruiter_headers)
        assert resp.status_code == 200
        assert resp.json() == {"success": True, "status": "shortlisted"}


def test_csv_neutralises_formulas_and_orders_by_best_score(
    client, recruiter_headers, campaign
):
    batch, _ = campaign
    resp = client.get(
        f"/api/v1/recruiter/campaigns/{batch.id}/export/csv",
        params={"scope": "all"},
        headers=recruiter_headers,
    )
    assert resp.status_code == 200
    assert "attachment" in resp.headers["content-disposition"]
    rows = _csv_rows(resp)
    names = [r["name"] for r in rows]
    assert names[0] == "Strong One"  # interview 88 beats cv 80
    assert names[-1] == "No Score"
    evil = next(r for r in rows if "HYPERLINK" in r["name"])
    assert evil["name"].startswith("'=")


def test_csv_shortlisted_scope(client, recruiter_headers, campaign):
    batch, _ = campaign
    resp = client.get(
        f"/api/v1/recruiter/campaigns/{batch.id}/export/csv",
        params={"scope": "shortlisted"},
        headers=recruiter_headers,
    )
    rows = _csv_rows(resp)
    assert [r["email"] for r in rows] == ["sara@x.tn"]


@pytest.mark.parametrize("tier", [False, True])
def test_pdf_handles_non_latin_names(client, recruiter_headers, campaign, tier):
    batch, _ = campaign
    resp = client.get(
        f"/api/v1/recruiter/campaigns/{batch.id}/export/pdf",
        params={"scope": "all", "tier": str(tier).lower()},
        headers=recruiter_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.content.startswith(b"%PDF")


def test_invalid_scope_is_422(client, recruiter_headers, campaign):
    batch, _ = campaign
    resp = client.get(
        f"/api/v1/recruiter/campaigns/{batch.id}/export/csv",
        params={"scope": "everything"},
        headers=recruiter_headers,
    )
    assert resp.status_code == 422


def _endpoints(batch, apps):
    base = f"/api/v1/recruiter/campaigns/{batch.id}"
    return [
        ("get", f"{base}/export/csv"),
        ("get", f"{base}/export/pdf"),
        ("patch", f"{base}/candidates/{apps['strong'].id}/shortlist"),
    ]


def test_unauthenticated_requests_are_rejected(client, campaign):
    batch, apps = campaign
    for method, url in _endpoints(batch, apps):
        resp = getattr(client, method)(url)
        assert resp.status_code in (401, 403), (url, resp.status_code)


def test_candidate_role_is_forbidden(client, auth_headers, campaign, db_session):
    batch, apps = campaign
    for method, url in _endpoints(batch, apps):
        resp = getattr(client, method)(url, headers=auth_headers)
        assert resp.status_code == 403, (url, resp.status_code)
    db_session.expire_all()
    assert db_session.get(Application, apps["strong"].id).status == "pending"


def test_csv_has_bom_and_preserves_unicode(client, recruiter_headers, campaign):
    batch, _ = campaign
    resp = client.get(
        f"/api/v1/recruiter/campaigns/{batch.id}/export/csv",
        headers=recruiter_headers,
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")
    rows = _csv_rows(resp)
    assert list(rows[0].keys())[0] == "name"
    assert "سارة بن علي" in [r["name"] for r in rows]


def test_shortlist_persists_status_and_single_stage_entry(
    client, recruiter_headers, campaign, db_session
):
    batch, apps = campaign
    app_id = apps["strong"].id
    url = f"/api/v1/recruiter/campaigns/{batch.id}/candidates/{app_id}/shortlist"
    for _ in range(2):
        assert client.patch(url, headers=recruiter_headers).status_code == 200

    db_session.expire_all()
    assert db_session.get(Application, app_id).status == "shortlisted"
    entries = (
        db_session.query(ApplicationStageHistory)
        .filter(ApplicationStageHistory.application_id == app_id)
        .all()
    )
    assert [e.stage_slug for e in entries] == ["shortlisted"]

    rows = _csv_rows(
        client.get(
            f"/api/v1/recruiter/campaigns/{batch.id}/export/csv",
            params={"scope": "shortlisted"},
            headers=recruiter_headers,
        )
    )
    assert sorted(r["email"] for r in rows) == ["sara@x.tn", "strong@x.tn"]


def test_export_scopes_by_batch_company_not_request_attribute(
    client, campaign, db_session, test_recruiter
):
    """The tenant-checked batch is authoritative. A recruiter object without
    the request-scoped ``_company_id`` attribute must still export the
    campaign (previously it filtered on company_id IS NULL -> empty export)."""
    batch, apps = campaign
    recruiter = db_session.get(User, test_recruiter.id)
    assert getattr(recruiter, "_company_id", None) is None
    fastapi_app.dependency_overrides[require_recruiter] = lambda: recruiter
    try:
        base = f"/api/v1/recruiter/campaigns/{batch.id}"
        rows = _csv_rows(client.get(f"{base}/export/csv"))
        assert len(rows) == len(apps)
        resp = client.patch(f"{base}/candidates/{apps['strong'].id}/shortlist")
        assert resp.status_code == 200, resp.text
    finally:
        fastapi_app.dependency_overrides.pop(require_recruiter, None)
