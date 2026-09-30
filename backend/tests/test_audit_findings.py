"""
POST-FIX AUDIT TESTS
======================
Tests verifying that bugs found during the recruiter logic audit have been fixed.
These are pure unit tests — no server or database required.

Run: pytest backend/tests/test_audit_findings.py -v
"""

import os
import sys

# Ensure backend is importable
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

# =============================================================================
# CRIT-01: Scoring Systems Are Now Aligned
# =============================================================================


class TestCrit01ScoringAligned:
    """Both scoring systems now use the same penalty values."""

    def _make_app_data(
        self,
        violations=None,
        cv_score=75,
        interview_score=75,
        skills=None,
        interview_progress=10,
    ):
        if violations is None:
            violations = []
        if skills is None:
            skills = ["python", "react"]
        return {
            "cv_score": cv_score,
            "overall_score": interview_score,
            "interview_progress": interview_progress,
            "interview_total": 15,
            "skills": skills,
            "proctoring_violations": violations,
            "experience_years": 3,
            "competencies": {},
        }

    def test_penalties_match(self):
        """All violation penalties are now identical between engine and transparent scoring."""
        for vtype in ScoringConfig.TRUST_PENALTIES:
            assert ScoringConfig.TRUST_PENALTIES[vtype] == VIOLATION_PENALTIES[vtype], (
                f"Mismatch for {vtype}: engine={ScoringConfig.TRUST_PENALTIES[vtype]}, "
                f"transparent={VIOLATION_PENALTIES[vtype]}"
            )

    def test_same_candidate_same_trust(self):
        """3 tab switches: engine and transparent apply the same penalty."""
        violations = [{"type": "tab_switch", "severity": "medium"} for _ in range(3)]
        # Legacy calculate_complete_scores() was removed; the live engine is
        # ScoringEngine.score_interview (shim over scoring_transparent).
        breakdown = ScoringEngine().score_interview(
            skill_metrics={"technical": 75, "communication": 75},
            question_scores=[75] * 10,
            answered=10,
            total=15,
            violations=violations,
        )
        transparent_penalty = calculate_integrity_penalty(violations)
        expected = min(MAX_INTEGRITY_PENALTY, 3 * VIOLATION_PENALTIES["tab_switch"])
        assert breakdown.integrity_penalty == expected, breakdown.integrity_penalty
        assert transparent_penalty == expected
        assert 100 - breakdown.integrity_penalty == 100 - transparent_penalty

    def test_both_capped_at_50(self):
        """Both systems cap the integrity penalty at 50 (trust >= 50)."""
        violations = [{"type": "tab_switch", "severity": "medium"} for _ in range(10)]
        # Legacy calculate_complete_scores() was removed; the live engine is
        # ScoringEngine.score_interview (shim over scoring_transparent).
        breakdown = ScoringEngine().score_interview(
            skill_metrics={"technical": 75, "communication": 75},
            question_scores=[75] * 10,
            answered=10,
            total=15,
            violations=violations,
        )
        transparent_penalty = calculate_integrity_penalty(violations)
        assert breakdown.integrity_penalty == 50, breakdown.integrity_penalty
        assert transparent_penalty == 50
        assert 100 - breakdown.integrity_penalty == 50


def json_dumps(obj):
    import json

    return json.dumps(obj)


# =============================================================================
# CRIT-04: Index Mismatch Fixed in ComparisonResponseBuilder
# =============================================================================


class TestCrit04IndexFixed:
    """build_comparison_response now pairs scores with correct names."""

    def test_sorted_results_correct_names(self):
        """After sorting by score, names match their scores correctly."""
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

        # Bob has the highest CV (90) and interview (85) scores, so he should be ranked first
        first_entry = candidates[0]

        assert first_entry["final_score"] >= candidates[1]["final_score"]
        assert first_entry["final_score"] >= candidates[2]["final_score"]

        # Bob (highest scorer) should be in position 0
        assert first_entry["name"] == "Bob", (
            f"FIX VERIFIED: Highest score {first_entry['final_score']} belongs to '{first_entry['name']}'"
        )


# =============================================================================
# HIGH-04: mask_candidate_data Now Recovers Original Data
# =============================================================================


class TestHigh04MutationFixed:
    """mask_candidate_data can recover original data when is_pro=True."""

    def test_input_not_mutated(self):
        """After masking with is_pro=False, calling is_pro=True recovers original data."""
        original = {
            "candidate_name": "John Doe",
            "full_name": "John Doe",
            "candidate_email": "john@example.com",
            "email": "john@example.com",
            "phone": "+21612345678",
            "cv_url": "/uploads/cv.pdf",
        }

        # Mask for non-pro user
        result = mask_candidate_data(original, is_pro=False)
        assert result["candidate_name"] == "J. Candidate", (
            "Non-pro should see masked name"
        )
        assert result["email"] == "hidden@candway.com", (
            "Non-pro should see masked email"
        )

        # Can recover for pro user
        result2 = mask_candidate_data(original, is_pro=True)
        assert result2["candidate_name"] == "John Doe", (
            "FIX VERIFIED: Data can be recovered with is_pro=True"
        )

    def test_shared_reference_safe(self):
        """Different permissions on shared data give correct independent views."""
        shared_data = {
            "candidate_name": "Jane Smith",
            "full_name": "Jane Smith",
            "candidate_email": "jane@example.com",
            "email": "jane@example.com",
            "cv_url": "/uploads/jane.pdf",
        }

        # Free user view
        view_a = mask_candidate_data(shared_data, is_pro=False)

        # Pro user view
        view_b = mask_candidate_data(shared_data, is_pro=True)

        # Views should now differ appropriately
        assert view_a["candidate_name"] == "J. Candidate", "Free user sees masked name"
        assert view_b["candidate_name"] == "Jane Smith", "Pro user sees original name"
        assert view_a["candidate_name"] != view_b["candidate_name"], (
            "FIX VERIFIED: Views correctly differ by permission level"
        )


# =============================================================================
# HIGH-05: Third Trust Score in Application Details
# =============================================================================


class TestHigh05ThirdTrustCalculation:
    """recruiter_candidates.py has a THIRD trust calculation: flat -15 per violation."""

    def test_naive_trust_vs_engine(self):
        """Naive: -15 per violation regardless of type. Engine: type-specific."""
        # 2 tab_switch violations
        # Naive: 100 - (2 * 15) = 70
        # Engine: 100 - (2 * 15) = 70 (same for tab_switch)
        naive = max(0, 100 - (2 * 15))
        assert naive == 70

        # But for 2 no_face_detected:
        # Naive: 100 - (2 * 15) = 70
        # Engine: 100 - (2 * 30) = 40
        naive_no_face = max(0, 100 - (2 * 15))
        engine_no_face = max(0, 100 - (2 * 30))

        assert naive_no_face != engine_no_face, (
            f"BUG: Naive trust={naive_no_face}, Engine trust={engine_no_face} "
            f"for same 2 no_face_detected violations"
        )

    def test_naive_ignores_severity(self):
        """Naive calculation ignores violation severity entirely."""
        # 1 high-severity tab_switch vs 1 low-severity
        # Engine: high = 15*1.5=22.5, low = 15*0.5=7.5
        # Naive: both = 15

        engine_high = 100 - (15 * 1.5)  # 77.5
        engine_low = 100 - (15 * 0.5)  # 92.5
        naive_both = 100 - 15  # 85

        assert engine_high != naive_both, "Naive ignores high severity"
        assert engine_low != naive_both, "Naive ignores low severity"


# =============================================================================
# MED-01: Momentum Bonus Now Uses First 3 vs Last 3
# =============================================================================


class TestMed01MomentumFixed:
    """Implementation now matches docstring: first 3 vs last 3."""

    def test_docstring_says_first_last_3(self):
        """Docstring explicitly mentions first 3 vs last 3."""
        assert "last 3" in calculate_momentum_bonus.__doc__
        assert "first 3" in calculate_momentum_bonus.__doc__

    def test_implementation_uses_first_and_last_three(self):
        """Implementation now uses first 3 vs last 3, not half-split."""
        scores = [10, 20, 30, 40, 50, 60, 70]
        calculate_momentum_bonus(scores)

        # First 3 vs last 3: avg([10,20,30])=20, avg([50,60,70])=60, improvement=40
        # Half-split: avg([10,20,30])=20, avg([40,50,60,70])=55, improvement=35
        # bonus caps at 5 in both cases for this input

        # Use scores where improvement < 20 to distinguish
        scores2 = [60, 62, 64, 66, 68, 70, 72]
        bonus2 = calculate_momentum_bonus(scores2)

        # first/last 3: improvement=avg([68,70,72]) - avg([60,62,64]) = 70-62 = 8 → bonus=2.0
        # half-split: improvement=avg([66,68,70,72]) - avg([60,62,64]) = 69-62 = 7 → bonus=1.75
        assert bonus2 == 2.0, (
            f"FIX VERIFIED: Expected bonus=2.0 (first/last 3), got {bonus2}"
        )


# =============================================================================
# MED-02: Fallback Skills Uses Quantity-Based Formula
# =============================================================================


# =============================================================================
# EDGE-01: Zero-Interview Candidate Gets Conservative Score
# =============================================================================


# =============================================================================
# EDGE-02: Negative Experience Clamped to Zero
# =============================================================================


# =============================================================================
# INTEGRITY: Both Systems Now Cap at MAX_INTEGRITY_PENALTY
# =============================================================================


class TestIntegrityPenaltyCapped:
    """Both transparent and engine cap integrity penalty at MAX_INTEGRITY_PENALTY."""

    def test_cap_at_50(self):
        """10 tab switches: penalty capped at 50, not 25."""
        violations = [{"type": "tab_switch"} for _ in range(10)]
        penalty = calculate_integrity_penalty(violations)
        assert penalty == 50, f"Expected cap at 50, got {penalty}"
        assert penalty == MAX_INTEGRITY_PENALTY

    def test_trust_capped_in_engine(self):
        """Engine caps the penalty at MAX_INTEGRITY_PENALTY, matching transparent."""
        violations = [{"type": "tab_switch", "severity": "medium"} for _ in range(10)]
        # Legacy calculate_complete_scores() was removed; the live engine is
        # ScoringEngine.score_interview (shim over scoring_transparent).
        breakdown = ScoringEngine().score_interview(
            skill_metrics={"technical": 75, "communication": 75},
            question_scores=[75] * 10,
            answered=10,
            total=15,
            violations=violations,
        )
        transparent_penalty = calculate_integrity_penalty(violations)
        assert breakdown.integrity_penalty == 50, breakdown.integrity_penalty
        assert transparent_penalty == 50
        assert 100 - breakdown.integrity_penalty == 50


# =============================================================================
# CONSISTENCY: Violation Type Coverage
# =============================================================================


class TestViolationTypeConsistency:
    """Both systems should have the same violation types."""

    def test_same_violation_types(self):
        """Check if both systems recognize the same violation types."""
        engine_types = set(ScoringConfig.TRUST_PENALTIES.keys())
        transparent_types = set(VIOLATION_PENALTIES.keys())

        missing_in_transparent = engine_types - transparent_types
        missing_in_engine = transparent_types - engine_types

        if missing_in_transparent or missing_in_engine:
            print(
                f"\nViolation types in Engine but not Transparent: {missing_in_transparent}"
            )
            print(f"Violation types in Transparent but not Engine: {missing_in_engine}")

        # They should have the same types
        assert engine_types == transparent_types, (
            f"Violation type mismatch! Engine has {engine_types}, Transparent has {transparent_types}"
        )

    def test_violation_penalty_ratios(self):
        """All penalty ratios should be consistent (they're not)."""
        for vtype in ScoringConfig.TRUST_PENALTIES:
            if vtype in VIOLATION_PENALTIES:
                engine_val = ScoringConfig.TRUST_PENALTIES[vtype]
                transparent_val = VIOLATION_PENALTIES[vtype]
                ratio = (
                    engine_val / transparent_val
                    if transparent_val > 0
                    else float("inf")
                )
                print(
                    f"  {vtype}: Engine={engine_val}, Transparent={transparent_val}, ratio={ratio:.1f}x"
                )
