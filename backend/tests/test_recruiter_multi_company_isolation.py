"""P0-4 regression: recruiter list / search / ranking never cross companies.

Setup
  company A, company B
  recruiter A (member of A), recruiter B (member of B)
  recruiter M: member of A (earliest membership) AND of B, owns a job in each
  applications in both companies (incl. one in B assigned to M)

Before the fix ``GET /recruiter/applications`` scoped rows by "job created
by ANY member of my company", so recruiter M's company-B job leaked into
company A's list (and vice versa), and applications assigned to M in B
showed up while M acted for A. The active company was also resolved with an
unordered ``.first()`` over memberships.
"""

import pytest

from backend.authz import _user_company_id
from backend.database import (
    Application,
    CompanyMember,
    EvaluationResult,
    EvaluationSession,
    Job,
    User,
)
from backend.dependencies import pwd_context
from backend.models.ats.candidate import Candidate
from backend.tenant import _resolve_company_id
from backend.tests.conftest import _fetch_csrf_token

PASSWORD = "multipass123"


def _login(client, email):
    csrf = _fetch_csrf_token(client)
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": PASSWORD},
        headers={"X-CSRF-Token": csrf},
    )
    assert resp.status_code == 200, resp.text
    return {
        "Authorization": f"Bearer {resp.json()['access_token']}",
        "X-CSRF-Token": csrf,
    }


def _recruiter(db, email, companies):
    user = User(
        email=email,
        name=email.split("@")[0],
        hashed_password=pwd_context.hash(PASSWORD),
        role="recruiter",
        email_verified=True,
    )
    db.add(user)
    db.flush()
    for company in companies:  # insertion order == membership id order
        db.add(
            CompanyMember(
                company_id=company.id, user_id=user.id, role="admin", is_active=True
            )
        )
        db.flush()
    db.commit()
    return user


def _job(db, recruiter, company, title):
    job = Job(
        recruiter_id=recruiter.id,
        company_id=company.id,
        title=title,
        description=title,
        is_active=True,
    )
    db.add(job)
    db.commit()
    return job


def _app(db, job, company, name, score, assigned_to=None):
    email = f"{name.lower().replace(' ', '.')}@example.com"
    candidate = Candidate(company_id=company.id, email=email, full_name=name)
    db.add(candidate)
    db.flush()
    app = Application(
        company_id=company.id,
        job_id=job.id,
        candidate_id=candidate.id,
        full_name=name,
        email=email,
        status="applied",
        assigned_to=assigned_to,
    )
    db.add(app)
    db.flush()
    es = EvaluationSession(
        application_id=app.id, company_id=company.id, status="completed"
    )
    db.add(es)
    db.flush()
    db.add(
        EvaluationResult(
            evaluation_session_id=es.id,
            company_id=company.id,
            cv_score=score,
            final_score=score,
            scoring_status="SCORED",
        )
    )
    db.commit()
    return app


@pytest.fixture
def tenants(db_session, test_company, test_company_b):
    a, b = test_company, test_company_b
    rec_a = _recruiter(db_session, "rec.a@alpha-example.com", [a])
    rec_b = _recruiter(db_session, "rec.b@beta-example.com", [b])
    rec_m = _recruiter(db_session, "rec.m@both-example.com", [a, b])

    job_m_a = _job(db_session, rec_m, a, "M job in A")
    job_m_b = _job(db_session, rec_m, b, "M job in B")
    job_a = _job(db_session, rec_a, a, "A job")
    job_b = _job(db_session, rec_b, b, "B job")

    apps = {
        "A_m": _app(db_session, job_m_a, a, "Alice MA", 70),
        "A_a": _app(db_session, job_a, a, "Adam AA", 60),
        "B_m": _app(db_session, job_m_b, b, "Bob MB", 90),
        "B_b": _app(db_session, job_b, b, "Bella BB", 80),
        "B_assigned_m": _app(
            db_session, job_b, b, "Boris BX", 85, assigned_to=rec_m.id
        ),
    }
    return {
        "a": a,
        "b": b,
        "rec_a": rec_a,
        "rec_b": rec_b,
        "rec_m": rec_m,
        "jobs": {"m_a": job_m_a, "m_b": job_m_b, "a": job_a, "b": job_b},
        "apps": {k: v.id for k, v in apps.items()},
    }


def _ids(apps, *keys):
    return {apps[k] for k in keys}


A_KEYS = ("A_m", "A_a")
B_KEYS = ("B_m", "B_b", "B_assigned_m")


def _list_ids(client, headers):
    resp = client.get("/api/v1/recruiter/applications?per_page=100", headers=headers)
    assert resp.status_code == 200, resp.text
    return {item["id"] for item in resp.json()["items"]}


def _search_ids(client, headers):
    resp = client.get(
        "/api/v1/recruiter/candidates/search?per_page=100", headers=headers
    )
    assert resp.status_code == 200, resp.text
    return {item["id"] for item in resp.json()["items"]}


def _ranked(client, headers, job_id):
    return client.get(
        f"/api/v1/recruiter/jobs/{job_id}/candidates/ranked", headers=headers
    )


# ── Active company resolution ─────────────────────────────────────────────
def test_multi_company_recruiter_has_one_deterministic_active_company(
    db_session, tenants
):
    rec_m = tenants["rec_m"]
    assert _user_company_id(db_session, rec_m.id) == tenants["a"].id
    fresh = db_session.get(User, rec_m.id)
    fresh.__dict__.pop("_company_id", None)
    assert _resolve_company_id(fresh, db_session) == tenants["a"].id

    # Earliest ACTIVE membership wins: deactivate A -> B.
    db_session.query(CompanyMember).filter(
        CompanyMember.user_id == rec_m.id,
        CompanyMember.company_id == tenants["a"].id,
    ).update({"is_active": False})
    db_session.commit()
    assert _user_company_id(db_session, rec_m.id) == tenants["b"].id


# ── List ──────────────────────────────────────────────────────────────────
def test_application_list_is_scoped_to_the_active_company(client, tenants):
    apps = tenants["apps"]
    assert _list_ids(client, _login(client, "rec.a@alpha-example.com")) == _ids(
        apps, *A_KEYS
    )
    assert _list_ids(client, _login(client, "rec.b@beta-example.com")) == _ids(
        apps, *B_KEYS
    )
    # M acts for company A: none of the B apps (own B job, assigned B app).
    assert _list_ids(client, _login(client, "rec.m@both-example.com")) == _ids(
        apps, *A_KEYS
    )


# ── Search ────────────────────────────────────────────────────────────────
def test_candidate_search_is_scoped_to_the_active_company(client, tenants):
    apps = tenants["apps"]
    assert _search_ids(client, _login(client, "rec.a@alpha-example.com")) == _ids(
        apps, *A_KEYS
    )
    assert _search_ids(client, _login(client, "rec.b@beta-example.com")) == _ids(
        apps, *B_KEYS
    )
    assert _search_ids(client, _login(client, "rec.m@both-example.com")) == _ids(
        apps, *A_KEYS
    )


# ── Ranking ───────────────────────────────────────────────────────────────
def test_ranking_is_scoped_to_the_active_company(client, tenants):
    apps, jobs = tenants["apps"], tenants["jobs"]
    h_a = _login(client, "rec.a@alpha-example.com")
    h_b = _login(client, "rec.b@beta-example.com")
    h_m = _login(client, "rec.m@both-example.com")

    # Another company's job: 404, never its candidates.
    assert _ranked(client, h_a, jobs["b"].id).status_code == 404
    assert _ranked(client, h_a, jobs["m_b"].id).status_code == 404
    assert _ranked(client, h_b, jobs["m_a"].id).status_code == 404
    assert _ranked(client, h_m, jobs["m_b"].id).status_code == 404

    resp = _ranked(client, h_m, jobs["m_a"].id)
    assert resp.status_code == 200, resp.text
    assert {c["id"] for c in resp.json()["candidates"]} == {apps["A_m"]}

    resp = _ranked(client, h_b, jobs["b"].id)
    assert resp.status_code == 200, resp.text
    ranked = resp.json()["candidates"]
    assert [c["id"] for c in ranked] == [apps["B_assigned_m"], apps["B_b"]]


def test_ranking_displays_the_score_it_sorts_by(db_session, client, tenants):
    """Ranking sorts by the latest computed result; the displayed composite
    must be that same result, not an arbitrary (e.g. oldest) session's."""
    apps, jobs, b = tenants["apps"], tenants["jobs"], tenants["b"]
    # Newer interview result for "Bella BB" (was 80 from the CV session).
    es = EvaluationSession(
        application_id=apps["B_b"], company_id=b.id, status="completed"
    )
    db_session.add(es)
    db_session.flush()
    db_session.add(
        EvaluationResult(
            evaluation_session_id=es.id,
            company_id=b.id,
            cv_score=80,
            final_score=95,
            scoring_status="SCORED",
        )
    )
    db_session.commit()

    resp = _ranked(client, _login(client, "rec.b@beta-example.com"), jobs["b"].id)
    assert resp.status_code == 200, resp.text
    ranked = resp.json()["candidates"]
    assert ranked[0]["id"] == apps["B_b"]
    assert ranked[0]["final_score"] == 95


def test_unfinished_interview_does_not_hide_prior_score(db_session, client, tenants):
    """An in-progress/abandoned interview (PENDING result, no final yet) must
    not drop the candidate to 0 in ranking; the prior score stays canonical."""
    from backend.scoring_service import ScoringService

    apps, jobs, b = tenants["apps"], tenants["jobs"], tenants["b"]
    es = EvaluationSession(
        application_id=apps["B_b"], company_id=b.id, status="in_progress"
    )
    db_session.add(es)
    db_session.flush()
    db_session.add(
        EvaluationResult(
            evaluation_session_id=es.id,
            company_id=b.id,
            scoring_status="PENDING",
            final_score=None,
        )
    )
    db_session.commit()

    canonical = ScoringService.get_canonical_score(apps["B_b"], db_session)
    assert canonical.final_score == 80

    resp = _ranked(client, _login(client, "rec.b@beta-example.com"), jobs["b"].id)
    ranked = {c["id"]: c for c in resp.json()["candidates"]}
    assert ranked[apps["B_b"]]["final_score"] == 80
    order = [c["id"] for c in resp.json()["candidates"]]
    assert order == [apps["B_assigned_m"], apps["B_b"]]
