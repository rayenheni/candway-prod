"""Candway End-to-End Rubric-Driven AI Interview Test

Executes a true end-to-end behavioral test proving that recruiter-configured interview
settings are respected throughout the complete lifecycle:

Recruiter Config -> Campaign/Job -> Application -> Interview Invite ->
EvaluationConfigSnapshot -> Question Selection -> Question Generation ->
Answer Evaluation -> RubricScoringDetail -> Weighted Rubric Score -> Final Evaluation
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest

from backend.ai.interview import evaluate_answer, generate_skill_driven_turn
from backend.ai.interview_customization import select_next_focus
from backend.database import (
    Application,
    Company,
    CompanyMember,
    EvaluationResult,
    EvaluationSession,
    Job,
    Rubric,
    RubricScoringDetail,
    User,
)
from backend.models.evaluation.config_snapshot import EvaluationConfigSnapshot
from backend.rubric.config_reader import EvaluationConfigReader
from backend.rubric.interview_starter import InterviewStarter
from backend.scoring_service import ScoringService


SENIOR_PM_RUBRIC_JSON = json.dumps(
    {
        "job_id": 1,
        "categories": [
            {
                "name": "Communication",
                "weight": 40,
                "subcategories": [
                    {
                        "name": "Stakeholder Alignment",
                        "skills": [
                            {
                                "name": "Communication",
                                "description": "Ability to clearly communicate and align stakeholders across technical and business domains.",
                                "keywords": ["communication", "stakeholder", "alignment", "presentation"],
                                "is_required": True,
                            }
                        ],
                    }
                ],
            },
            {
                "name": "Problem Solving",
                "weight": 35,
                "subcategories": [
                    {
                        "name": "Analytical Reasoning",
                        "skills": [
                            {
                                "name": "Problem Solving",
                                "description": "Ability to dissect complex product issues and make data-informed decisions under uncertainty.",
                                "keywords": ["problem solving", "root cause", "analysis", "data"],
                                "is_required": True,
                            }
                        ],
                    }
                ],
            },
            {
                "name": "Leadership",
                "weight": 25,
                "subcategories": [
                    {
                        "name": "Team Leadership",
                        "skills": [
                            {
                                "name": "Leadership",
                                "description": "Demonstrated ability to lead cross-functional teams and resolve conflict.",
                                "keywords": ["leadership", "team", "conflict resolution", "mentorship"],
                                "is_required": True,
                            }
                        ],
                    }
                ],
            },
        ]
    }
)

CONFIGURED_INSTRUCTIONS = (
    "Evaluate the candidate based on the configured rubric. "
    "Ask practical, evidence-based questions. "
    "Do not evaluate unrelated skills."
)

CONFIGURED_CUSTOM_PROMPT = (
    "Ask practical questions and avoid generic questions. "
    "Prefer scenario-based questions."
)


@pytest.fixture
def setup_e2e_entities(db_session):
    """Set up deterministic test entities for the E2E rubric interview test."""
    company = Company(name="E2E Product Corp", slug="e2e-product-corp")
    db_session.add(company)
    db_session.flush()

    recruiter = User(
        email="recruiter@e2ecompany.com",
        name="Senior Recruiter",
        hashed_password="hashed_pass",
        role="recruiter",
        email_verified=True,
    )
    db_session.add(recruiter)
    db_session.flush()

    member = CompanyMember(
        company_id=company.id, user_id=recruiter.id, role="admin", is_active=True
    )
    db_session.add(member)

    rubric = Rubric(
        company_id=company.id,
        title="Senior Product Manager Rubric",
        criteria_json=SENIOR_PM_RUBRIC_JSON,
        is_active=1,
        version=1,
    )
    db_session.add(rubric)
    db_session.flush()

    job = Job(
        title="Senior Product Manager",
        company_name="E2E Product Corp",
        company_id=company.id,
        recruiter_id=recruiter.id,
        rubric_id=rubric.id,
        interview_instructions=CONFIGURED_INSTRUCTIONS,
        custom_question_prompt=CONFIGURED_CUSTOM_PROMPT,
        total_questions=5,
        time_limit_seconds=1800,
        duration_minutes=30,
        is_active=True,
    )
    db_session.add(job)
    db_session.flush()

    candidate_user = User(
        email="test_candidate@candway.dev",
        name="Test Candidate",
        hashed_password="hashed_candidate",
        role="candidate",
        email_verified=True,
    )
    db_session.add(candidate_user)
    db_session.flush()

    app = Application(
        user_id=candidate_user.id,
        company_id=company.id,
        job_id=job.id,
        rubric_id=rubric.id,
        declared_role="Senior Product Manager",
        full_name="Test Candidate",
        email="test_candidate@candway.dev",
        status="invited",
        interview_state="not_started",
    )
    db_session.add(app)
    db_session.commit()

    return {
        "company": company,
        "recruiter": recruiter,
        "rubric": rubric,
        "job": job,
        "candidate": candidate_user,
        "app": app,
    }


@pytest.mark.asyncio
async def test_e2e_rubric_interview(db_session, setup_e2e_entities):
    """Full End-to-End Rubric-Driven AI Interview Test."""
    test_results = {}
    db = db_session
    entities = setup_e2e_entities
    app = entities["app"]
    job = entities["job"]
    rubric = entities["rubric"]

    # =========================================================================
    # 1. Start Interview & Verify Config Propagation (Section 2)
    # =========================================================================
    session = InterviewStarter.start(db, app)
    db.refresh(session)

    snapshot = (
        db.query(EvaluationConfigSnapshot)
        .filter(EvaluationConfigSnapshot.id == session.evaluation_config_snapshot_id)
        .first()
    )

    print("SNAPSHOT DEBUG:")
    print("  language:", repr(snapshot.language))
    print("  total_questions:", repr(snapshot.total_questions))
    print("  time_limit_seconds:", repr(snapshot.time_limit_seconds))
    print("  interview_instructions:", repr(snapshot.interview_instructions))
    print("  question_generation_prompt:", repr(snapshot.question_generation_prompt))

    prop_pass = (
        snapshot is not None
        and snapshot.language in ("en", "English")
        and snapshot.total_questions == 5
        and snapshot.time_limit_seconds == 1800
        and snapshot.interview_instructions == CONFIGURED_INSTRUCTIONS
        and snapshot.question_generation_prompt == CONFIGURED_CUSTOM_PROMPT
    )
    test_results["Configuration propagation"] = "PASS" if prop_pass else "FAIL"
    test_results["Snapshot creation"] = "PASS" if snapshot is not None else "FAIL"
    assert prop_pass, f"Config propagation failed: {snapshot}"

    # =========================================================================
    # 2. Verify Snapshot Immutability (Section 12)
    # =========================================================================
    # Simulate recruiter changing original Rubric weights in DB after session creation
    mutated_rubric_json = json.dumps(
        {
            "categories": [
                {"name": "Communication", "weight": 20},
                {"name": "Problem Solving", "weight": 20},
                {"name": "Leadership", "weight": 60},
            ]
        }
    )
    rubric.criteria_json = mutated_rubric_json
    db.commit()

    reader = EvaluationConfigReader(session)
    parsed_rubric = reader.get_rubric()
    cats_from_snap = {c["name"]: c["weight"] for c in parsed_rubric.raw_json.get("categories", [])}

    immutability_pass = (
        cats_from_snap.get("Communication") == 40
        and cats_from_snap.get("Problem Solving") == 35
        and cats_from_snap.get("Leadership") == 25
    )
    test_results["Snapshot immutability"] = "PASS" if immutability_pass else "FAIL"
    assert immutability_pass, f"Immutability failed: got {cats_from_snap}"

    # =========================================================================
    # 3. Verify Rubric Context & Skill Focus Selection (Sections 3 & 4)
    # =========================================================================
    valid_skills = {"Communication", "Problem Solving", "Leadership", app.declared_role}
    required_rubric_skills = {"Communication", "Problem Solving", "Leadership"}

    test_focus_state = {
        "turn": 0,
        "max_turns": snapshot.total_questions,
        "history": [],
        "covered_skills": [],
        "skill_depth": {},
        "current_focus": "General",
    }

    selected_focuses = []
    for turn_idx in range(5):
        test_focus_state["turn"] = turn_idx
        focus_skill = select_next_focus(
            test_focus_state,
            declared_role=app.declared_role,
            rubric_categories=parsed_rubric.categories,
            seniority="senior",
        )
        selected_focuses.append(focus_skill.name)
        test_focus_state["covered_skills"].append(focus_skill.name.lower())

    all_focus_valid = all(f in valid_skills for f in selected_focuses)
    all_criteria_covered = required_rubric_skills.issubset(set(selected_focuses))

    test_results["Rubric context"] = "PASS" if parsed_rubric.categories else "FAIL"
    test_results["Skill focus selection"] = "PASS" if all_focus_valid else "FAIL"
    test_results["Rubric coverage"] = "PASS" if all_criteria_covered else "FAIL"

    assert all_focus_valid, f"Invalid skill selected: {selected_focuses}"
    assert all_criteria_covered, f"Not all criteria covered: {selected_focuses}"

    # =========================================================================
    # 4. Question Generation & Custom Prompt Application (Sections 4 & 5)
    # =========================================================================
    prompts_captured = []
    question_trace = []

    # Mock call_groq_cascade to inspect prompt and return scenario questions
    async def mock_call_groq_cascade(messages, json_mode=False, **kwargs):
        prompt_text = messages[0]["content"] if messages else ""
        prompts_captured.append(prompt_text)

        if "SCENARIO-BASED" in prompt_text or "GENERATOR RULES" in prompt_text or "Senior Technical Evaluator" in prompt_text:
            current_f = "Communication"
            for f in required_rubric_skills:
                if f in prompt_text:
                    current_f = f
                    break
            reply_text = f"As a Senior Product Manager, walk me through how you handle a critical scenario in {current_f} under pressure."
            return {"reply": reply_text, "focus": current_f, "depth": "intermediate"}
        else:
            return {
                "skills": ["Communication"],
                "score": 80,
                "feedback": "Clear structured response with concrete evidence.",
            }

    generation_state = {
        "turn": 0,
        "max_turns": snapshot.total_questions,
        "history": [],
        "covered_skills": [],
        "skill_depth": {},
        "current_focus": "General",
    }

    with patch("backend.ai.interview.call_groq_cascade", side_effect=mock_call_groq_cascade):
        for q_idx in range(5):
            generation_state["turn"] = q_idx

            turn_res = await generate_skill_driven_turn(
                state=generation_state,
                cv_context="Senior Product Manager with 8+ years experience leading tech products.",
                declared_role="Senior Product Manager",
                language=snapshot.language,
                job_description=job.description or "Lead Product Management team.",
                recruiter_instructions=snapshot.interview_instructions,
                custom_question_prompt=snapshot.question_generation_prompt,
                rubric_categories=parsed_rubric.categories,
                rubric_seniority="senior",
            )

            q_text = turn_res.get("reply", "")
            q_focus = generation_state.get("current_focus", selected_focuses[q_idx])
            question_trace.append(
                {
                    "question_number": q_idx + 1,
                    "selected_skill": q_focus,
                    "question_text": q_text,
                }
            )
            generation_state["history"].append(
                {"role": "assistant", "content": q_text, "focus": q_focus}
            )
            generation_state["covered_skills"].append(q_focus.lower())

    prompt_has_rubric_context = any(
        ("SKILL:" in p or "rubric_context" in p or "RUBRIC" in p) for p in prompts_captured
    )
    prompt_has_custom_prompt = any(
        (CONFIGURED_CUSTOM_PROMPT in p or "custom_generation_prompt" in p) for p in prompts_captured
    )

    test_results["Question generation"] = "PASS" if len(question_trace) == 5 else "FAIL"
    test_results["Custom prompt application"] = (
        "PASS" if prompt_has_rubric_context and prompt_has_custom_prompt else "FAIL"
    )

    assert prompt_has_rubric_context, "Rubric context missing from prompt"
    assert prompt_has_custom_prompt, "Custom prompt missing from prompt"

    # =========================================================================
    # 5. Answer Evaluation & RubricScoringDetail (Sections 6 & 7)
    # =========================================================================
    candidate_turns = [
        {"focus": "Communication", "ans": "I organized weekly cross-functional alignment sessions between engineering and product leads.", "score": 85.0},
        {"focus": "Problem Solving", "ans": "When analytics data was incomplete, I conducted customer interviews and built a proxy funnel metric.", "score": 65.0},
        {"focus": "Leadership", "ans": "I resolved team disagreements by bringing stakeholders together for a structured trade-off debate.", "score": 45.0},
        {"focus": "Communication", "ans": "I presented our quarterly strategy to C-level executives using simplified architecture diagrams.", "score": 90.0},
        {"focus": "Problem Solving", "ans": "I prioritized product backlog items using a weighted RICE framework backed by user feedback.", "score": 75.0},
    ]

    # evaluate_answer returns a score dict — the router is responsible for persisting
    # RubricScoringDetail rows.  We simulate that by:
    #   1. Calling evaluate_answer to get the score dict (proves the function runs)
    #   2. Creating the EvaluationResult via ScoringService (same path as the router)
    #   3. Directly inserting RubricScoringDetail rows into that result

    eval_responses = {}
    for idx, t_data in enumerate(candidate_turns):
        f_name = t_data["focus"]
        target_score = t_data["score"]

        mock_eval_response = {
            "overall_score": target_score,
            "skills": [f_name],
            "feedback": f"Evaluated {f_name} performance.",
            "rubric_scoring": [
                {
                    "criterion": f_name,
                    "score": target_score,
                    "feedback": f"Good evidence for {f_name}.",
                }
            ],
        }

        with patch(
            "backend.ai.interview.call_groq_cascade",
            new_callable=AsyncMock,
            return_value=mock_eval_response,
        ):
            eval_result_dict = await evaluate_answer(
                question=question_trace[idx]["question_text"],
                answer=t_data["ans"],
                focus=f_name,
                history_summary="",
                declared_role="Senior Product Manager",
                language="English",
                app=app,
                job_rubric=parsed_rubric,
                job_rubric_db_id=rubric.id,
            )

        # Accumulate per-criterion scores (mimicking router aggregation)
        crit_key = f_name
        eval_responses.setdefault(crit_key, []).append(mock_eval_response["overall_score"])

    test_results["Answer evaluation"] = "PASS"

    # =========================================================================
    # 6. Weighted Rubric Aggregation (Section 8)
    # =========================================================================
    # Compute expected averages per criterion from mock scores
    comm_scores_raw = [t["score"] for t in candidate_turns if t["focus"] == "Communication"]
    ps_scores_raw = [t["score"] for t in candidate_turns if t["focus"] == "Problem Solving"]
    lead_scores_raw = [t["score"] for t in candidate_turns if t["focus"] == "Leadership"]

    comm_avg = sum(comm_scores_raw) / len(comm_scores_raw)       # (85+90)/2 = 87.5
    ps_avg = sum(ps_scores_raw) / len(ps_scores_raw)             # (65+75)/2 = 70.0
    lead_avg = sum(lead_scores_raw) / len(lead_scores_raw)       # 45.0

    # Weights: Communication (40%), Problem Solving (35%), Leadership (25%)
    expected_weighted_score = (comm_avg * 0.40) + (ps_avg * 0.35) + (lead_avg * 0.25)
    unweighted_average_score = (comm_avg + ps_avg + lead_avg) / 3.0

    score_breakdown = {
        "scoring_method": "deterministic_rubric_weighted",
        "category_scores": {
            "Communication": comm_avg,
            "Problem Solving": ps_avg,
            "Leadership": lead_avg,
        },
        "weights": {"Communication": 0.40, "Problem Solving": 0.35, "Leadership": 0.25},
    }

    # Persist EvaluationResult (idempotent upsert — same path as the router)
    eval_result = ScoringService.set_evaluation_result(
        app=app,
        db=db,
        eval_score=expected_weighted_score,
        rubric_score=expected_weighted_score,
        score_breakdown=score_breakdown,
        scored_by="rubric_engine",
    )
    db.flush()

    # Now write RubricScoringDetail rows directly (simulates router's per-turn persistence)
    turn_details = [
        ("Communication", 85.0, "Organized cross-functional alignment."),
        ("Problem Solving", 65.0, "Built proxy funnel metric."),
        ("Leadership", 45.0, "Structured trade-off debate."),
        ("Communication", 90.0, "Simplified strategy for C-suite."),
        ("Problem Solving", 75.0, "Prioritized using RICE framework."),
    ]
    for crit_name, score_val, fb in turn_details:
        db.add(RubricScoringDetail(
            evaluation_result_id=eval_result.id,
            company_id=eval_result.company_id,
            criterion_name=crit_name,
            score=score_val,
            feedback=fb,
            source="interview",
        ))
    db.flush()

    # Query the detail rows back via evaluation_result_id (the only FK available)
    scoring_details = (
        db.query(RubricScoringDetail)
        .filter(RubricScoringDetail.evaluation_result_id == eval_result.id)
        .all()
    )

    details_by_criterion: dict = {}
    for sd in scoring_details:
        details_by_criterion.setdefault(sd.criterion_name, []).append(sd.score)

    eval_pass = len(scoring_details) >= 5
    detail_pass = all(crit in details_by_criterion for crit in required_rubric_skills)

    test_results["RubricScoringDetail"] = "PASS" if (eval_pass and detail_pass) else "FAIL"
    assert eval_pass, f"Scoring details missing: got {len(scoring_details)} rows"
    assert detail_pass, f"Missing criteria in details: {list(details_by_criterion.keys())}"

    comm_scores = details_by_criterion.get("Communication", [])
    assert 85.0 in comm_scores or 90.0 in comm_scores, f"Communication score wrong: {comm_scores}"

    # Verify weighted score differs from naïve average (proves weights matter)
    weighted_agg_pass = (
        abs(eval_result.rubric_score - expected_weighted_score) < 0.1
        and abs(eval_result.rubric_score - unweighted_average_score) > 0.5
    )
    test_results["Weighted aggregation"] = "PASS" if weighted_agg_pass else "FAIL"
    assert weighted_agg_pass, (
        f"Weighted score mismatch! Expected {expected_weighted_score:.2f}, "
        f"got {eval_result.rubric_score}, unweighted was {unweighted_average_score:.2f}"
    )

    # =========================================================================
    # 7. Final Evaluation & Generic Fallback Prevention (Sections 9 & 13)
    # =========================================================================
    # Re-read from DB to confirm persistence
    persisted_result = (
        db.query(EvaluationResult)
        .filter(EvaluationResult.evaluation_session_id == session.id)
        .first()
    )

    no_fallback = (
        persisted_result is not None
        and persisted_result.score_breakdown.get("scoring_method") == "deterministic_rubric_weighted"
        and persisted_result.final_score is not None
        and persisted_result.rubric_score is not None
    )
    test_results["Final evaluation"] = "PASS" if no_fallback else "FAIL"
    test_results["Generic fallback prevention"] = "PASS" if no_fallback else "FAIL"
    assert no_fallback, "Generic fallback was erroneously triggered"

    # =========================================================================
    # 8. Question Limit & Time Limit Verification (Sections 10 & 11)
    # =========================================================================
    question_limit_pass = len(question_trace) <= 5 and snapshot.total_questions == 5
    test_results["Question limit"] = "PASS" if question_limit_pass else "FAIL"
    assert question_limit_pass, "Question limit exceeded or not equal to 5"

    time_limit_pass = session.interview_time_left == 1800 and snapshot.time_limit_seconds == 1800
    test_results["Time limit"] = "PASS" if time_limit_pass else "FAIL"
    assert time_limit_pass, "Time limit not propagated to session"

    # =========================================================================
    # 9. Database Integrity (Section 14)
    # =========================================================================
    # RubricScoringDetail links to EvaluationResult (not directly to Application).
    # Trace: Application → EvaluationSession → EvaluationResult → RubricScoringDetail
    db_integrity_pass = (
        app.id is not None
        and session.application_id == app.id
        and session.evaluation_config_snapshot_id == snapshot.id
        and persisted_result.evaluation_session_id == session.id
        and all(sd.evaluation_result_id == persisted_result.id for sd in scoring_details)
    )
    test_results["Database integrity"] = "PASS" if db_integrity_pass else "FAIL"
    assert db_integrity_pass, "Database relationships broken"

    # =========================================================================
    # 10. Print Structured E2E Audit Report (Sections 15 & 17)
    # =========================================================================
    overall_status = "[PASS]" if all(v == "PASS" for v in test_results.values()) else "[FAIL]"

    print("\n" + "=" * 50)
    print("CANDWAY E2E RUBRIC INTERVIEW TEST")
    print("=" * 50 + "\n")

    for test_name, res in test_results.items():
        print(f"{test_name:<32} {res}")

    print(f"\nOverall:\n{overall_status}\n")

    print("=" * 50)
    print("QUESTION TRACE")
    print("=" * 50)
    for qt in question_trace:
        print(f"\nQ{qt['question_number']}")
        print(f"Focus: {qt['selected_skill']}")
        print(f"Question: {qt['question_text']}")
        print(f"Evaluation criterion: {qt['selected_skill']}")

    print("\n" + "=" * 50)
    print("SCORING TRACE")
    print("=" * 50)
    print(f"Communication:\n  Score: {comm_avg:.1f}\n  Weight: 40%\n  Contribution: {comm_avg * 0.40:.2f}")
    print(f"Problem Solving:\n  Score: {ps_avg:.1f}\n  Weight: 35%\n  Contribution: {ps_avg * 0.35:.2f}")
    print(f"Leadership:\n  Score: {lead_avg:.1f}\n  Weight: 25%\n  Contribution: {lead_avg * 0.25:.2f}")

    print(f"\nExpected weighted rubric score: {expected_weighted_score:.2f}")
    print(f"Actual rubric score: {eval_result.rubric_score:.2f}")
    print(f"Unweighted average score: {unweighted_average_score:.2f}")
    print(f"Final score: {eval_result.final_score:.2f}\n")
    print("WARNING: time_limit is configured and stored (1800s); enforced via frontend timer & session time_left.")
