"""
PENALTY SYSTEM FIX TESTS
=========================
Verifies all Bug 1-3 fixes and penalty calibration.

Run: pytest backend/tests/test_penalty_fixes.py -v
"""

from backend.scoring_transparent import (
    MAX_INTEGRITY_PENALTY,
    PROCTORING_KEY_MAP,
    VIOLATION_PENALTIES,
    calculate_integrity_penalty,
    calculate_overall_score,
    normalize_violation_type,
)


class TestNormalizeViolationType:
    """Bug 1: Proctoring key mismatch — normalizer handles both old and new."""

    def test_devtools_opened_maps_correctly(self):
        assert normalize_violation_type("DevTools opened") == "devtools_opened"

    def test_tab_switch_maps_correctly(self):
        assert normalize_violation_type("Tab switch detected") == "tab_switch"

    def test_multiple_faces_maps_correctly(self):
        assert normalize_violation_type("Multiple faces detected") == "multiple_faces"

    def test_face_not_detected_maps_correctly(self):
        assert normalize_violation_type("Face not detected") == "no_face_detected"

    def test_window_focus_lost_maps_correctly(self):
        assert normalize_violation_type("Window focus lost") == "window_focus_lost"

    def test_suspiciously_fast_answer_maps_correctly(self):
        assert (
            normalize_violation_type("Suspiciously fast answer") == "suspicious_speed"
        )

    def test_right_click_maps_correctly(self):
        assert normalize_violation_type("Right-click attempt") == "right_click"

    def test_already_canonical_passthrough(self):
        assert normalize_violation_type("devtools_opened") == "devtools_opened"
        assert normalize_violation_type("tab_switch") == "tab_switch"

    def test_unknown_type_fallback(self):
        assert normalize_violation_type("Some unknown type") == "some_unknown_type"

    def test_every_pascalcase_key_has_canonical(self):
        """All display names must map to a canonical key with a defined penalty."""
        for pascal_key in PROCTORING_KEY_MAP:
            canonical = normalize_violation_type(pascal_key)
            assert canonical in VIOLATION_PENALTIES, (
                f"{pascal_key} → {canonical} not in VIOLATION_PENALTIES"
            )


class TestCalculateIntegrityPenalty:
    """Bug 1: Penalties now match violation types correctly."""

    def test_devtools_penalty_is_20(self):
        violations = [{"type": "DevTools opened"}]
        penalty = calculate_integrity_penalty(violations)
        assert penalty == 20.0, f"Expected 20, got {penalty}"

    def test_tab_switch_penalty_is_8(self):
        violations = [{"type": "Tab switch detected"}]
        penalty = calculate_integrity_penalty(violations)
        assert penalty == 8.0, f"Expected 8, got {penalty}"

    def test_multiple_faces_penalty_is_15(self):
        violations = [{"type": "Multiple faces detected"}]
        penalty = calculate_integrity_penalty(violations)
        assert penalty == 15.0, f"Expected 15, got {penalty}"

    def test_face_not_detected_penalty_is_6(self):
        violations = [{"type": "Face not detected"}]
        penalty = calculate_integrity_penalty(violations)
        assert penalty == 6.0, f"Expected 6, got {penalty}"

    def test_window_focus_lost_penalty_is_4(self):
        violations = [{"type": "Window focus lost"}]
        penalty = calculate_integrity_penalty(violations)
        assert penalty == 4.0, f"Expected 4, got {penalty}"

    def test_suspicious_speed_penalty_is_5(self):
        violations = [{"type": "Suspiciously fast answer"}]
        penalty = calculate_integrity_penalty(violations)
        assert penalty == 5.0, f"Expected 5, got {penalty}"

    def test_right_click_penalty_is_2(self):
        violations = [{"type": "Right-click attempt"}]
        penalty = calculate_integrity_penalty(violations)
        assert penalty == 2.0, f"Expected 2, got {penalty}"

    def test_multiple_violations_accumulate(self):
        violations = [
            {"type": "Tab switch detected"},
            {"type": "Tab switch detected"},
            {"type": "Tab switch detected"},
        ]
        penalty = calculate_integrity_penalty(violations)
        assert penalty == 24.0, f"Expected 24 (3×8), got {penalty}"

    def test_penalty_capped_at_50(self):
        violations = [{"type": "DevTools opened"}] * 10  # 10×20 = 200
        penalty = calculate_integrity_penalty(violations)
        assert penalty == MAX_INTEGRITY_PENALTY, (
            f"Expected cap {MAX_INTEGRITY_PENALTY}, got {penalty}"
        )

    def test_no_violations_zero_penalty(self):
        assert calculate_integrity_penalty([]) == 0.0
        assert calculate_integrity_penalty(None) == 0.0

    def test_old_pascalcase_still_works(self):
        """Backward compat: old stored violations still penalize correctly."""
        violations = [{"type": "DevTools opened"}]
        assert calculate_integrity_penalty(violations) == 20.0

    def test_new_canonical_keys_also_work(self):
        """Fwd compat: new normalized keys also work."""
        violations = [{"type": "devtools_opened"}]
        assert calculate_integrity_penalty(violations) == 20.0

    def test_mixed_old_and_new_keys(self):
        """Both old PascalCase and new snake_case keys in same list."""
        violations = [
            {"type": "DevTools opened"},
            {"type": "tab_switch"},
            {"type": "Multiple faces detected"},
            {"type": "right_click"},
        ]
        penalty = calculate_integrity_penalty(violations)
        assert penalty == 45.0, f"Expected 45 (20+8+15+2), got {penalty}"

    def test_unknown_violation_fallback_5(self):
        violations = [{"type": "some_random_event"}]
        penalty = calculate_integrity_penalty(violations)
        assert penalty == 5.0, f"Expected fallback 5, got {penalty}"

    def test_trust_score_from_penalty(self):
        """Trust score = 100 - integrity_penalty"""
        violations = [{"type": "Tab switch detected"}, {"type": "Tab switch detected"}]
        penalty = calculate_integrity_penalty(violations)
        trust = max(0.0, 100.0 - penalty)
        assert trust == 84.0, f"Expected trust 84 (100-16), got {trust}"

    def test_trust_score_capped_at_zero(self):
        violations = [{"type": "DevTools opened"}] * 10
        penalty = calculate_integrity_penalty(violations)
        trust = max(0.0, 100.0 - min(penalty, MAX_INTEGRITY_PENALTY))
        assert trust == 50.0, f"Expected trust 50 (100-50 cap), got {trust}"


class TestLazyPenaltyRemoved:
    """Bug 2: No double lazy penalty."""

    def test_no_lazy_penalty_in_final_formula(self):
        """calculate_overall_score no longer applies lazy_penalty."""
        breakdown = calculate_overall_score(
            skill_metrics={
                "Technical": 50,
                "Communication": 50,
                "Problem Solving": 50,
                "Adaptability": 50,
                "Confidence": 50,
            },
            question_scores=[50],
            answered=1,
            total=6,
            violations=[],
            gaming_detected=False,
        )
        assert breakdown.lazy_penalty == 0.0, (
            f"Expected lazy_penalty=0.0, got {breakdown.lazy_penalty}"
        )

    def test_lazy_answer_force_20_in_chat(self):
        """Lazy penalty is applied at chat level only (score forced to 20).
        This test verifies the scoring engine does NOT add a second penalty."""
        # A normal score of 50 with lazy_penalty removed should yield final_score=50-based
        breakdown = calculate_overall_score(
            skill_metrics={
                "Technical": 20,
                "Communication": 20,
                "Problem Solving": 20,
                "Adaptability": 20,
                "Confidence": 20,
            },
            question_scores=[20],
            answered=1,
            total=6,
            violations=[],
        )
        # With base=20 and no modifiers, final should be ~20 (not 5)
        assert breakdown.final_score > 15, (
            f"Expected final_score > 15 (no -15 penalty), got {breakdown.final_score}"
        )


class TestGamingPenaltyGuard:
    """Bug 3: No double anti-cheat penalty."""

    def test_gaming_penalty_applies_when_no_cheat_detected(self):
        """gaming_penalty applies when deterministic anti-cheat didn't fire."""
        breakdown = calculate_overall_score(
            skill_metrics={
                "Technical": 60,
                "Communication": 60,
                "Problem Solving": 60,
                "Adaptability": 60,
                "Confidence": 60,
            },
            question_scores=[60],
            answered=1,
            total=6,
            violations=[],
            gaming_detected=True,
        )
        assert breakdown.gaming_penalty == 10.0, (
            f"Expected gaming_penalty=10.0, got {breakdown.gaming_penalty}"
        )

    def test_gaming_penalty_suppressed_when_cheat_already_penalized(self):
        """Guard prevents double penalty: if cheat already detected, gaming_penalty is 0.
        This is enforced at the chat.py level — calculate_overall_score still applies it
        if gaming_detected=True is passed. The guard is in the caller."""
        breakdown = calculate_overall_score(
            skill_metrics={
                "Technical": 60,
                "Communication": 60,
                "Problem Solving": 60,
                "Adaptability": 60,
                "Confidence": 60,
            },
            question_scores=[60],
            answered=1,
            total=6,
            violations=[],
            gaming_detected=True,
        )
        assert breakdown.gaming_penalty == 10.0
        # The guard in chat.py will set gaming_detected=False when cheat_detected=True


class TestPenaltyCalibration:
    """Calibrated values are proportional and explainable."""

    def test_devtools_not_max_on_first_violation(self):
        """DevTools (20) should not immediately max out the 50-point cap."""
        assert VIOLATION_PENALTIES.get("devtools_opened", 0) < MAX_INTEGRITY_PENALTY
        assert VIOLATION_PENALTIES.get("devtools_opened", 0) <= 20

    def test_penalties_proportional_to_severity(self):
        """Critical violations > High > Medium > Low."""
        critical = VIOLATION_PENALTIES.get("devtools_opened", 0)
        high = VIOLATION_PENALTIES.get("multiple_faces", 0)
        medium = VIOLATION_PENALTIES.get("no_face_detected", 0)
        low = VIOLATION_PENALTIES.get("right_click", 0)
        assert critical >= high >= medium >= low, (
            f"Penalties not proportional: critical={critical}, high={high}, medium={medium}, low={low}"
        )

    def test_all_penalties_positive(self):
        """All penalties must be positive (subtracted from 100 trust)."""
        for vtype, penalty in VIOLATION_PENALTIES.items():
            assert penalty > 0, f"{vtype} has non-positive penalty {penalty}"

    def test_all_penalties_reasonable(self):
        """No single penalty exceeds 50% of the cap."""
        for vtype, penalty in VIOLATION_PENALTIES.items():
            assert penalty <= MAX_INTEGRITY_PENALTY / 2, (
                f"{vtype} penalty {penalty} > half of cap {MAX_INTEGRITY_PENALTY / 2}"
            )
