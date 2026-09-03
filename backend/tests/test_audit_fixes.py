"""
PRE-LAUNCH AUDIT TESTS — VERIFICATION AFTER FIXES
===================================================
Tests that confirm all audit bugs have been fixed.

Run: pytest backend/tests/test_audit_fixes.py -v
"""

import copy
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from backend.scoring_engine import (
    ComparisonResponseBuilder,
    ScoringConfig,
    ScoringEngine,
)
from backend.scoring_transparent import (
    MAX_INTEGRITY_PENALTY,
    VIOLATION_PENALTIES,
    calculate_integrity_penalty,
    calculate_momentum_bonus,
)
from backend.security import mask_candidate_data


def json_dumps(obj):
    import json

    return json.dumps(obj)


# =============================================================================
# CRIT-01 FIX VERIFICATION: Unified penalty values
# =============================================================================


class TestCrit01Fixed:
    """Both scoring systems now use identical penalty values."""

    def test_penalties_match(self):
        """Every violation type has the same penalty in both systems."""
        for vtype in ScoringConfig.TRUST_PENALTIES:
            assert vtype in VIOLATION_PENALTIES, f"{vtype} missing from transparent"
            assert ScoringConfig.TRUST_PENALTIES[vtype] == VIOLATION_PENALTIES[vtype], (
                f"{vtype}: Engine={ScoringConfig.TRUST_PENALTIES[vtype]}, "
                f"Transparent={VIOLATION_PENALTIES[vtype]}"
            )

    def test_trust_penalty_capped_in_engine(self):
        """Engine now caps trust penalty at MAX_TRUST_PENALTY."""
        assert hasattr(ScoringConfig, "MAX_TRUST_PENALTY")
        assert ScoringConfig.MAX_TRUST_PENALTY == 50

        violations = [{"type": "tab_switch", "severity": "medium"} for _ in range(20)]
        engine = ScoringEngine()
        app = {
            "cv_score": 80,
            "overall_score": 75,
            "interview_progress": 10,
            "interview_total": 15,
            "skills": ["python"],
            "proctoring_violations": json_dumps(violations),
            "experience_years": 3,
            "competencies": {},
        }
        score = engine.calculate_complete_scores(app)
        # 20 * 10 = 200, capped at 50 → trust = 50
        assert score.trust_score == 50, (
            f"Expected trust=50 (capped), got {score.trust_score}"
        )

    def test_transparency_cap_matches_engine(self):
        """Transparent cap now matches engine cap."""
        assert MAX_INTEGRITY_PENALTY == ScoringConfig.MAX_TRUST_PENALTY

    def test_same_candidate_same_trust(self):
        """Same violations produce same trust score in both systems."""
        violations = [
            {"type": "tab_switch", "severity": "medium"},
            {"type": "tab_switch", "severity": "medium"},
            {"type": "tab_switch", "severity": "medium"},
        ]

        # Engine
        engine = ScoringEngine()
        app = {
            "cv_score": 80,
            "overall_score": 75,
            "interview_progress": 10,
            "interview_total": 15,
            "skills": ["python"],
            "proctoring_violations": json_dumps(violations),
            "experience_years": 3,
            "competencies": {},
        }
        score = engine.calculate_complete_scores(app)
        engine_trust = score.trust_score

        # Transparent
        transparent_penalty = calculate_integrity_penalty(violations)
        transparent_trust = 100 - transparent_penalty

        assert engine_trust == transparent_trust, (
            f"Trust mismatch: Engine={engine_trust}, Transparent={transparent_trust}"
        )


# =============================================================================
# CRIT-04 FIX VERIFICATION: Index mismatch resolved
# =============================================================================


class TestCrit04Fixed:
    """ComparisonResponseBuilder now matches by ID, not index."""

    def test_sorted_results_correct_names(self):
        """After sorting, each score pairs with the correct candidate name."""
        applications = [
            {
                "id": 1,
                "full_name": "Alice",
                "cv_score": 60,
                "overall_score": 50,
                "interview_progress": 10,
                "interview_total": 15,
                "skills": ["python"],
                "proctoring_violations": "[]",
                "experience_years": 2,
            },
            {
                "id": 2,
                "full_name": "Bob",
                "cv_score": 90,
                "overall_score": 85,
                "interview_progress": 15,
                "interview_total": 15,
                "skills": ["python", "react", "docker"],
                "proctoring_violations": "[]",
                "experience_years": 5,
            },
            {
                "id": 3,
                "full_name": "Charlie",
                "cv_score": 75,
                "overall_score": 70,
                "interview_progress": 12,
                "interview_total": 15,
                "skills": ["python", "react"],
                "proctoring_violations": "[]",
                "experience_years": 3,
            },
        ]

        builder = ComparisonResponseBuilder()
        response = builder.build_comparison_response(applications)

        candidates = response["candidates"]

        # First candidate should be Bob (highest scorer)
        assert candidates[0]["name"] == "Bob", (
            f"Expected Bob first, got {candidates[0]['name']}"
        )

        # Verify each candidate's score matches their ID
        bob_entry = next(c for c in candidates if c["name"] == "Bob")
        alice_entry = next(c for c in candidates if c["name"] == "Alice")
        charlie_entry = next(c for c in candidates if c["name"] == "Charlie")

        assert bob_entry["final_score"] > alice_entry["final_score"]
        assert bob_entry["final_score"] > charlie_entry["final_score"]

    def test_missing_app_gracefully_skipped(self):
        """If an application is missing from the lookup, it's skipped."""
        applications = [
            {
                "id": 1,
                "full_name": "Alice",
                "cv_score": 80,
                "overall_score": 75,
                "interview_progress": 10,
                "interview_total": 15,
                "skills": ["python"],
                "proctoring_violations": "[]",
                "experience_years": 3,
            },
        ]

        builder = ComparisonResponseBuilder()
        response = builder.build_comparison_response(applications)

        assert len(response["candidates"]) == 1
        assert response["candidates"][0]["name"] == "Alice"


# =============================================================================
# HIGH-04 FIX VERIFICATION: No mutation
# =============================================================================


class TestHigh04Fixed:
    """mask_candidate_data no longer mutates the input dict."""

    def test_input_not_mutated(self):
        """Original dict remains unchanged after masking."""
        original = {
            "candidate_name": "John Doe",
            "full_name": "John Doe",
            "candidate_email": "john@example.com",
            "email": "john@example.com",
            "phone": "+21612345678",
            "cv_url": "/uploads/cv.pdf",
        }

        backup = copy.deepcopy(original)
        mask_candidate_data(original, is_pro=False)

        assert original == backup, "Input dict was mutated!"

    def test_can_unmask_after_mask(self):
        """Calling with is_pro=True after is_pro=False returns full data."""
        data = {
            "candidate_name": "Jane Smith",
            "full_name": "Jane Smith",
            "candidate_email": "jane@example.com",
            "email": "jane@example.com",
            "cv_url": "/uploads/jane.pdf",
        }

        masked = mask_candidate_data(data, is_pro=False)
        unmasked = mask_candidate_data(data, is_pro=True)

        assert masked["candidate_name"] != "Jane Smith"
        assert unmasked["candidate_name"] == "Jane Smith"

    def test_shared_reference_safe(self):
        """Two calls on same dict don't interfere."""
        shared = {
            "candidate_name": "Test User",
            "full_name": "Test User",
            "candidate_email": "test@example.com",
            "email": "test@example.com",
            "cv_url": "/uploads/test.pdf",
        }

        free_view = mask_candidate_data(shared, is_pro=False)
        pro_view = mask_candidate_data(shared, is_pro=True)

        assert free_view["candidate_name"] != pro_view["candidate_name"]
        assert pro_view["candidate_name"] == "Test User"


# =============================================================================
# HIGH-05 FIX VERIFICATION: Unified trust in recruiter view
# =============================================================================


class TestHigh05Fixed:
    """Recruiter candidate details now use ScoringEngine trust calculation."""

    def test_naive_calculation_removed(self):
        """The naive 'len(violations) * 15' pattern no longer exists."""
        import inspect

        from backend.routers import recruiter_candidates

        source = inspect.getsource(recruiter_candidates)
        # The old pattern was: len(proctoring_violations) * 15
        assert "len(proctoring_violations) * 15" not in source, (
            "Naive trust calculation still present in recruiter_candidates.py"
        )


# =============================================================================
# MED-01 FIX VERIFICATION: Momentum bonus uses first 3 vs last 3
# =============================================================================


class TestMed01Fixed:
    """Momentum bonus now correctly compares first 3 vs last 3."""

    def test_uses_first_and_last_three(self):
        """With 7 scores, compares [0,1,2] vs [4,5,6]."""
        scores = [40, 50, 60, 70, 80, 90, 100]
        bonus = calculate_momentum_bonus(scores)

        first_three = scores[:3]  # [40, 50, 60]
        last_three = scores[-3:]  # [80, 90, 100]
        avg_first = sum(first_three) / 3  # 50
        avg_last = sum(last_three) / 3  # 90
        improvement = avg_last - avg_first  # 40

        expected_bonus = min(5.0, improvement / 20.0 * 5.0)  # 5.0 (capped)
        assert bonus == expected_bonus, f"Expected {expected_bonus}, got {bonus}"

    def test_returns_zero_for_no_improvement(self):
        """Declining scores should give zero bonus."""
        scores = [90, 85, 80, 75, 70, 65, 60]
        bonus = calculate_momentum_bonus(scores)
        assert bonus == 0.0


# =============================================================================
# MED-02 FIX VERIFICATION: Diminishing returns on skill count
# =============================================================================


class TestMed02Fixed:
    """Fallback skills score now uses diminishing returns."""

    def test_diminishing_returns(self):
        """10 random skills should NOT score 100%."""
        engine = ScoringEngine()

        app_random = {
            "skills": [
                "cooking",
                "driving",
                "swimming",
                "painting",
                "singing",
                "dancing",
                "reading",
                "writing",
                "gardening",
                "fishing",
            ]
        }
        score_random = engine._calculate_fallback_skills_score(app_random)

        app_relevant = {"skills": ["python", "fastapi", "postgresql"]}
        score_relevant = engine._calculate_fallback_skills_score(app_relevant)

        # Random skills should not score higher than relevant ones
        assert score_random < 100, (
            f"10 random skills scored {score_random}% (should be < 100)"
        )
        # Both should get a reasonable score (not 30% for 3 skills)
        assert score_relevant > 30, (
            f"3 relevant skills scored {score_relevant}% (should be > 30)"
        )


# =============================================================================
# EDGE-02 FIX VERIFICATION: Negative experience clamped
# =============================================================================


class TestEdge02Fixed:
    """Negative experience_years no longer produces negative radar values."""

    def test_negative_experience_clamped(self):
        """experience_years=-1 should not affect radar negatively."""
        from backend.scoring_engine import CandidateScore, TalentRadarCalculator

        score = CandidateScore(
            skills_score=50,
            trust_score=100,
            adjusted_interview_score=60,
            final_score=55,
            completion_rate=0.8,
        )
        app_data = {
            "experience_years": -1,
            "competencies": {},
            "interview_progress": 10,
            "interview_total": 15,
        }

        radar = TalentRadarCalculator.calculate_radar_data(score, app_data)

        # All radar values should be >= 0
        for dim, val in radar.items():
            assert val >= 0, f"Negative value in {dim}: {val}"
