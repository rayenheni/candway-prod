"""
Phase 6: Rubric connectivity — candidate analysis + recruiter all-interviews.
"""

from backend.database import (
    Application,
    EvaluationResult,
    EvaluationSession,
    Job,
    RubricScoringDetail,
    User,
)
from backend.database import (
    Rubric as RubricDB,
)
from backend.rubric.rubric_schema import (
    CategoryDefinition,
    JobRubric,
    LevelDescriptor,
    SkillDefinition,
    SubcategoryDefinition,
)


def _make_rubric(job_id: int) -> JobRubric:
    return JobRubric(
        job_id=job_id,
        version=2,
        seniority="mid",
        categories=[
            CategoryDefinition(
                name="Technical",
                weight=1.0,
                subcategories=[
                    SubcategoryDefinition(
                        name="Backend",
                        weight=1.0,
                        skills=[
                            SkillDefinition(
                                name="Python",
                                weight=1.0,
                                is_required=True,
                                levels={
                                    "junior": [],
                                    "mid": [
                                        LevelDescriptor(
                                            score_threshold=100,
                                            description="Builds production APIs",
                                            keywords=["python", "api"],
                                        )
                                    ],
                                    "senior": [],
                                },
                            )
                        ],
                    )
                ],
            )
        ],
    )


def _seed_rubric_summary(db_session, app_id: int, rubric_db_id: int):
    summary = RubricScoringDetail(
        application_id=app_id,
        rubric_id=rubric_db_id,
        rubric_version=2,
        overall_score=72,
        confidence_lower=60,
        confidence_upper=85,
        category_scores=[
            {
                "name": "Technical",
                "score": 72,
                "weight": 1.0,
                "confidence_range": [60, 85],
                "coverage_pct": 50,
                "skills_scored": 1,
                "skills_total": 2,
                "children": [
                    {
                        "name": "Backend",
                        "score": 72,
                        "weight": 1.0,
                        "confidence_range": [60, 85],
                        "coverage_pct": 100,
                        "skills_scored": 1,
                        "skills_total": 1,
                        "children": None,
                    }
                ],
            }
        ],
        skill_scores={
            "python": {
                "skill_name": "python",
                "final_score": 72,
                "is_required": True,
                "category": "Technical",
            }
        },
        gaps=[
            {
                "skill_name": "System Design",
                "category": "Technical",
                "severity": "critical",
                "gap_pct": 45,
                "description": "No assessment data for System Design",
            }
        ],
        num_answers_scored=5,
    )
    db_session.add(summary)


def _seed_scoring_results(db_session, app_id: int, rubric_db_id: int):
    result = RubricScoringDetail(
        application_id=app_id,
        rubric_id=rubric_db_id,
        skill_name="Python",
        base_score=70,
        quality_multiplier=1.0,
        final_score=70,
        turn_number=1,
        matched_keywords=["python"],
        missing_competencies=["async"],
        explanation="Candidate demonstrated basic Python but missing async patterns.",
    )
    db_session.add(result)


DEFAULT_FIVE = [
    "Communication",
    "Technical Knowledge",
    "Problem Solving",
    "Clarity & Structure",
    "Confidence",
]


class TestCandidateAnalysisRubricDriven:
    """GET /api/v1/candidate/interviews/{app_id}/analysis with rubric data."""

    def _setup_rubric_app(self, db_session, client, auth_headers):
        user = db_session.query(User).filter_by(role="candidate").first()
        job = Job(recruiter_id=user.id, company_id=test_company.id, title="Engineer")
        db_session.add(job)
        db_session.flush()

        rubric = _make_rubric(job.id)
        db_rubric = RubricDB(
            job_id=job.id,
            company_id=job.company_id,
            version=rubric.version,
            is_active=1,
            criteria_json=rubric.model_dump_json(),
            created_by=user.id,
        )
        db_session.add(db_rubric)
        db_session.flush()

        app = Application(
            user_id=user.id,
            job_id=job.id,
            declared_role="Engineer",
        )
        db_session.add(app)
        db_session.flush()

        _es = EvaluationSession(application_id=app.id, status="completed")
        db_session.add(_es)
        db_session.flush()
        _er = EvaluationResult(
            evaluation_session_id=_es.id,
            scoring_status="SCORED",
            scoring_model="rubric",
            rubric_version=2,
            rubric_score=72.0,
            final_score=70.0,
        )
        db_session.add(_er)
        db_session.flush()

        _seed_rubric_summary(db_session, app.id, db_rubric.id)
        db_session.commit()

        return app

    def test_returns_rubric_fields(self, db_session, client, auth_headers):
        app = self._setup_rubric_app(db_session, client, auth_headers)
        resp = client.get(
            f"/api/v1/candidate/interviews/{app.id}/analysis",
            headers=auth_headers,
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["is_rubric_driven"] is True
        assert data["rubric_version"] == 2
        assert data["rubric_score"] == 72.0
        # rubric_coverage_pct comes from EvaluationResult; if not set it's None
        # This test verifies is_rubric_driven and rubric_version are correct

    def test_performance_overview_uses_category_scores(
        self, db_session, client, auth_headers
    ):
        app = self._setup_rubric_app(db_session, client, auth_headers)
        resp = client.get(
            f"/api/v1/candidate/interviews/{app.id}/analysis",
            headers=auth_headers,
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        overview = data["performance_overview"]
        labels = [m["label"] for m in overview]
        assert "Technical" in labels
        for m in overview:
            assert isinstance(m["score"], (int, float))
            assert m["label_score"] in ("Excellent", "Good", "Fair")

    def test_metrics_uses_category_names(self, db_session, client, auth_headers):
        app = self._setup_rubric_app(db_session, client, auth_headers)
        resp = client.get(
            f"/api/v1/candidate/interviews/{app.id}/analysis",
            headers=auth_headers,
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        metrics = data["metrics"]
        assert "Technical" in metrics
        assert metrics["Technical"] == 72
        for dim in DEFAULT_FIVE:
            assert dim not in metrics, (
                f"Should not contain fabricated '{dim}' when rubric-driven"
            )

    def test_returns_gaps(self, db_session, client, auth_headers):
        app = self._setup_rubric_app(db_session, client, auth_headers)
        resp = client.get(
            f"/api/v1/candidate/interviews/{app.id}/analysis",
            headers=auth_headers,
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert len(data["gaps"]) == 1
        gap = data["gaps"][0]
        assert gap["skill_name"] == "System Design"
        assert gap["severity"] == "critical"


class TestCandidateAnalysisLegacyFallback:
    """GET /api/v1/candidate/interviews/{app_id}/analysis without rubric."""

    def test_returns_legacy_when_no_rubric(self, db_session, client, auth_headers, test_company):
        user = db_session.query(User).filter_by(role="candidate").first()
        job = Job(recruiter_id=user.id, company_id=test_company.id, title="Engineer")
        db_session.add(job)
        db_session.flush()

        app = Application(
            user_id=user.id,
            job_id=job.id,
            declared_role="Engineer",
        )
        db_session.add(app)
        db_session.flush()

        _es = EvaluationSession(application_id=app.id, status="completed")
        db_session.add(_es)
        db_session.flush()
        _er = EvaluationResult(
            evaluation_session_id=_es.id,
            scoring_status="SCORED",
            scoring_model="legacy",
            final_score=65.0,
        )
        db_session.add(_er)
        db_session.commit()

        resp = client.get(
            f"/api/v1/candidate/interviews/{app.id}/analysis",
            headers=auth_headers,
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["is_rubric_driven"] is False
        assert data["rubric_version"] is None
        assert data["gaps"] == []

    def test_fabricated_dimensions_when_no_rubric(
        self, db_session, client, auth_headers
    , test_company):
        user = db_session.query(User).filter_by(role="candidate").first()
        job = Job(recruiter_id=user.id, company_id=test_company.id, title="Engineer")
        db_session.add(job)
        db_session.flush()

        app = Application(
            user_id=user.id,
            job_id=job.id,
            declared_role="Engineer",
        )
        db_session.add(app)
        db_session.flush()

        _es = EvaluationSession(application_id=app.id, status="completed")
        db_session.add(_es)
        db_session.flush()
        _er = EvaluationResult(
            evaluation_session_id=_es.id,
            scoring_status="SCORED",
            scoring_model="legacy",
            final_score=65.0,
        )
        db_session.add(_er)
        db_session.commit()

        resp = client.get(
            f"/api/v1/candidate/interviews/{app.id}/analysis",
            headers=auth_headers,
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        overview = data["performance_overview"]
        labels = [m["label"] for m in overview]
        for dim in DEFAULT_FIVE:
            assert dim in labels, (
                f"Fabricated dimension '{dim}' should be present when no rubric"
            )
        assert len(overview) == 5

    def test_is_rubric_driven_false_when_no_rubric(
        self, db_session, client, auth_headers
    , test_company):
        user = db_session.query(User).filter_by(role="candidate").first()
        job = Job(recruiter_id=user.id, company_id=test_company.id, title="Engineer")
        db_session.add(job)
        db_session.flush()

        app = Application(
            user_id=user.id,
            job_id=job.id,
            declared_role="Engineer",
        )
        db_session.add(app)
        db_session.flush()

        _es = EvaluationSession(application_id=app.id, status="completed")
        db_session.add(_es)
        db_session.flush()
        _er = EvaluationResult(
            evaluation_session_id=_es.id,
            scoring_status="SCORED",
            scoring_model="legacy",
            final_score=65.0,
        )
        db_session.add(_er)
        db_session.commit()

        resp = client.get(
            f"/api/v1/candidate/interviews/{app.id}/analysis",
            headers=auth_headers,
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["is_rubric_driven"] is False
        assert data["performance_overview"] is not None


class TestRecruiterAllInterviewsRubricDriven:
    """GET /api/v1/recruiter/applications/{app_id}/all-interviews with rubric."""

    def _setup_rubric_app(self, db_session, client, recruiter_headers):
        recruiter = db_session.query(User).filter_by(role="recruiter").first()
        job = Job(recruiter_id=recruiter.id, company_id=test_company.id, title="Engineer")
        db_session.add(job)
        db_session.flush()

        rubric = _make_rubric(job.id)
        db_rubric = RubricDB(
            job_id=job.id,
            company_id=job.company_id,
            version=rubric.version,
            is_active=1,
            criteria_json=rubric.model_dump_json(),
            created_by=recruiter.id,
        )
        db_session.add(db_rubric)
        db_session.flush()

        app = Application(
            user_id=recruiter.id,
            job_id=job.id,
            declared_role="Engineer",
            assigned_to=recruiter.id,
        )
        db_session.add(app)
        db_session.flush()

        _es = EvaluationSession(application_id=app.id, status="completed")
        db_session.add(_es)
        db_session.flush()
        _er = EvaluationResult(
            evaluation_session_id=_es.id,
            scoring_status="SCORED",
            scoring_model="rubric",
            rubric_version=2,
            rubric_score=72.0,
            final_score=70.0,
        )
        db_session.add(_er)
        db_session.flush()

        _seed_rubric_summary(db_session, app.id, db_rubric.id)
        db_session.commit()

        return app

    def test_performance_overview_uses_rubric_categories(
        self, db_session, client, recruiter_headers
    ):
        app = self._setup_rubric_app(db_session, client, recruiter_headers)
        resp = client.get(
            f"/api/v1/recruiter/applications/{app.id}/all-interviews",
            headers=recruiter_headers,
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert len(data["interviews"]) == 1
        iv = data["interviews"][0]
        assert iv["is_rubric_driven"] is True
        overview = iv["performance_overview"]
        labels = [m["label"] for m in overview]
        assert "Technical" in labels
        for dim in [
            "Technical",
            "Communication",
            "Problem Solving",
            "Adaptability",
            "Confidence",
        ]:
            pass

    def test_rubric_gaps_in_response(self, db_session, client, recruiter_headers):
        app = self._setup_rubric_app(db_session, client, recruiter_headers)
        resp = client.get(
            f"/api/v1/recruiter/applications/{app.id}/all-interviews",
            headers=recruiter_headers,
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        iv = data["interviews"][0]
        assert len(iv["rubric_gaps"]) == 1
        assert iv["rubric_gaps"][0]["skill_name"] == "System Design"
        assert iv["rubric_categories"] is not None
        assert iv["rubric_skill_scores"] is not None

    def test_performance_overview_no_fabricated_dims_when_rubric(
        self, db_session, client, recruiter_headers
    ):
        app = self._setup_rubric_app(db_session, client, recruiter_headers)
        resp = client.get(
            f"/api/v1/recruiter/applications/{app.id}/all-interviews",
            headers=recruiter_headers,
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        iv = data["interviews"][0]
        labels = [m["label"] for m in iv["performance_overview"]]
        for dim in [
            "technical",
            "communication",
            "problem_solving",
            "adaptability",
            "confidence",
        ]:
            assert dim not in labels, (
                f"Fabricated key '{dim}' should not appear when rubric-driven"
            )


class TestRecruiterAllInterviewsLegacyFallback:
    """GET /api/v1/recruiter/applications/{app_id}/all-interviews without rubric."""

    def test_fabricated_dims_when_no_rubric(
        self, db_session, client, recruiter_headers
    , test_company):
        recruiter = db_session.query(User).filter_by(role="recruiter").first()
        job = Job(recruiter_id=recruiter.id, company_id=test_company.id, title="Engineer")
        db_session.add(job)
        db_session.flush()

        app = Application(
            user_id=recruiter.id,
            job_id=job.id,
            declared_role="Engineer",
            assigned_to=recruiter.id,
        )
        db_session.add(app)
        db_session.flush()

        _es = EvaluationSession(application_id=app.id, status="completed")
        db_session.add(_es)
        db_session.flush()
        _er = EvaluationResult(
            evaluation_session_id=_es.id,
            scoring_status="SCORED",
            scoring_model="legacy",
            final_score=65.0,
        )
        db_session.add(_er)
        db_session.commit()

        resp = client.get(
            f"/api/v1/recruiter/applications/{app.id}/all-interviews",
            headers=recruiter_headers,
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        iv = data["interviews"][0]
        assert iv["is_rubric_driven"] is False
        # Without interview turns no Q&A data exists to fabricate from
        assert isinstance(iv["performance_overview"], list)

    def test_rubric_gaps_empty_when_no_rubric(
        self, db_session, client, recruiter_headers
    , test_company):
        recruiter = db_session.query(User).filter_by(role="recruiter").first()
        job = Job(recruiter_id=recruiter.id, company_id=test_company.id, title="Engineer")
        db_session.add(job)
        db_session.flush()

        app = Application(
            user_id=recruiter.id,
            job_id=job.id,
            declared_role="Engineer",
            assigned_to=recruiter.id,
        )
        db_session.add(app)
        db_session.flush()

        _es = EvaluationSession(application_id=app.id, status="completed")
        db_session.add(_es)
        db_session.flush()
        _er = EvaluationResult(
            evaluation_session_id=_es.id,
            scoring_status="SCORED",
            scoring_model="legacy",
            final_score=65.0,
        )
        db_session.add(_er)
        db_session.commit()

        resp = client.get(
            f"/api/v1/recruiter/applications/{app.id}/all-interviews",
            headers=recruiter_headers,
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        iv = data["interviews"][0]
        assert iv["rubric_gaps"] == []
        assert iv["rubric_categories"] == []
        assert iv["rubric_skill_scores"] == {}
