"""
Candway Transparent Scoring System
===================================

A clear, explainable scoring system for AI interviews.

Formula:
  Base Score = (Technical × 0.40) + (Communication × 0.20) + (Problem Solving × 0.20) + (Adaptability × 0.10) + (Confidence × 0.10)

  Modifiers:
    + Momentum Bonus:      +0 to +5  (improving trend over last 3 answers)
    + Completeness Bonus:  +0 to +5  (finished all questions)
    - Integrity Penalty:   -0 to -50 (proctoring violations)
    - Gaming Penalty:      -10       (AI detects manipulation)
    - Timing Penalty:      -?        (suspicious response timing)

  Lazy Penalty removed per Bug 2 fix (Option B):
    Handled deterministically at chat level (score forced to 20).
    No additional -15 penalty on final score.

  Final Score = clamp(Base Score + Modifiers, 0, 100)

Author: Candway Engineering
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# =============================================================================
# PROCTORING VIOLATION NORMALIZATION
# =============================================================================
# Maps frontend display names (PascalCase) to canonical snake_case keys.
# Used when storing violations AND when computing penalties.
# Ensures existing stored violations with old PascalCase keys are still
# correctly penalized (backward compatible).
# =============================================================================

PROCTORING_KEY_MAP = {
    "DevTools opened": "devtools_opened",
    "Tab switch detected": "tab_switch",
    "Multiple faces detected": "multiple_faces",
    "Face not detected": "no_face_detected",
    "Window focus lost": "window_focus_lost",
    "Suspiciously fast answer": "suspicious_speed",
    "Right-click attempt": "right_click",
}


def normalize_violation_type(raw_type: str) -> str:
    """
    Normalize a proctoring violation type to canonical snake_case key.

    Handles three cases:
    1. Exact match in PROCTORING_KEY_MAP (PascalCase display name → canonical)
    2. Already a canonical key (pass-through)
    3. Unknown type → lowercase with underscores as fallback

    Backward compatible: old stored violations with PascalCase keys
    (e.g. "DevTools opened") are mapped to the same canonical key
    as new normalized violations (e.g. "devtools_opened").
    """
    canonical = PROCTORING_KEY_MAP.get(raw_type)
    if canonical is not None:
        return canonical
    return raw_type.lower().replace(" ", "_")


# =============================================================================
# SCORING WEIGHTS (must sum to 1.0)
# =============================================================================

DIMENSION_WEIGHTS = {
    "Technical": 0.40,
    "Communication": 0.20,
    "Problem Solving": 0.20,
    "Adaptability": 0.10,
    "Confidence": 0.10,
}

DIMENSION_ORDER = [
    "Technical",
    "Communication",
    "Problem Solving",
    "Adaptability",
    "Confidence",
]

# =============================================================================
# MODIFIER BOUNDS
# =============================================================================

MAX_MOMENTUM_BONUS = 5.0
MAX_COMPLETENESS_BONUS = 5.0
MAX_INTEGRITY_PENALTY = 50.0  # Must match ScoringConfig.MAX_TRUST_PENALTY
# LAZY_ANSWER_PENALTY removed per Option B decision:
# Lazy answers are penalized at the chat level (score forced to 20).
# Applying an additional -15 here was a double penalty.
# A 20/100 score is already a strong negative signal.
GAMING_PENALTY = 10.0

# Proctoring violation penalties by type — single source of truth.
# Penalties are calibrated proportionally to severity so that:
#   - One critical violation (DevTools, multiple faces) does NOT max out the 50-point cap
#   - Minor violations (right-click, focus loss) accumulate slowly
#   - Multiple minor violations (3-5 tab switches) are needed before meaningful impact
# Keys use canonical snake_case via normalize_violation_type().
VIOLATION_PENALTIES = {
    "devtools_opened": 20,  # Critical: deliberate cheating attempt
    "multiple_faces": 15,  # Critical: impersonation risk
    "tab_switch": 8,  # High: looking up answers elsewhere
    "no_face_detected": 6,  # Medium: candidate may have stepped away
    "window_focus_lost": 4,  # Medium: alt-tab or notification click
    "suspicious_speed": 5,  # Medium: answer too fast (GPT copy-paste)
    "right_click": 2,  # Low: could be accidental or copy attempt
    "voice_mismatch": 12,  # High: voice-based impersonation
    "screen_share_change": 8,  # High: screen-sharing manipulation
    "audio_anomaly": 5,  # Medium: unusual audio patterns
}


@dataclass
class ScoreBreakdown:
    """Transparent score breakdown for recruiter display"""

    # Dimension scores (0-100 each)
    technical: float = 0.0
    communication: float = 0.0
    problem_solving: float = 0.0
    adaptability: float = 0.0
    confidence: float = 0.0

    # Base weighted score
    base_score: float = 0.0

    # Modifiers
    momentum_bonus: float = 0.0
    completeness_bonus: float = 0.0
    integrity_penalty: float = 0.0
    lazy_penalty: float = 0.0
    gaming_penalty: float = 0.0
    timing_penalty: float = 0.0

    # Final
    final_score: float = 0.0

    # Metadata
    total_questions: int = 0
    answered_questions: int = 0
    question_scores: List[float] = field(default_factory=list)

    # Explainable scoring (NEW)
    confidence_interval: Optional[dict] = None
    why_this_score: str = ""
    strengths: List[str] = field(default_factory=list)
    weaknesses: List[str] = field(default_factory=list)
    gaps: List[dict] = field(default_factory=list)
    fastest_impact: str = ""
    evidence_summary: List[str] = field(default_factory=list)
    dimension_explanations: Dict[str, str] = field(default_factory=dict)
    risk_factors: List[str] = field(default_factory=list)
    hiring_signals: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "dimensions": {
                "Technical": round(self.technical, 1),
                "Communication": round(self.communication, 1),
                "Problem Solving": round(self.problem_solving, 1),
                "Adaptability": round(self.adaptability, 1),
                "Confidence": round(self.confidence, 1),
            },
            "base_score": round(self.base_score, 1),
            "modifiers": {
                "momentum_bonus": round(self.momentum_bonus, 1),
                "completeness_bonus": round(self.completeness_bonus, 1),
                "integrity_penalty": round(self.integrity_penalty, 1),
                "lazy_penalty": round(self.lazy_penalty, 1),
                "gaming_penalty": round(self.gaming_penalty, 1),
                "timing_penalty": round(self.timing_penalty, 1),
            },
            "final_score": round(self.final_score, 1),
            "question_count": self.answered_questions,
            "question_scores": [round(s, 1) for s in self.question_scores],
            "explainability": {
                "confidence_interval": self.confidence_interval,
                "why_this_score": self.why_this_score,
                "strengths": self.strengths,
                "weaknesses": self.weaknesses,
                "gaps": self.gaps,
                "fastest_impact": self.fastest_impact,
                "evidence_summary": self.evidence_summary,
                "dimension_explanations": self.dimension_explanations,
                "risk_factors": self.risk_factors,
                "hiring_signals": self.hiring_signals,
            },
        }


def calculate_base_score(skill_metrics: Dict[str, float]) -> float:
    """
    Calculate weighted base score from dimension scores.

    Formula: sum(dimension_score × weight) for all dimensions
    """
    if not skill_metrics:
        return 50.0

    total = 0.0
    total_weight = 0.0

    for dimension, weight in DIMENSION_WEIGHTS.items():
        score = skill_metrics.get(dimension, 50.0)
        score = max(0.0, min(100.0, float(score)))
        total += score * weight
        total_weight += weight

    if total_weight == 0:
        return 50.0

    return total / total_weight


def calculate_momentum_bonus(question_scores: List[float]) -> float:
    """
    Reward candidates who improve over time.

    Compares average of last 3 answers vs first 3 answers.
    Returns 0 to +5 bonus.
    """
    if len(question_scores) < 4:
        return 0.0

    first_three = question_scores[:3]
    last_three = question_scores[-3:]

    if not first_three or not last_three:
        return 0.0

    avg_first = sum(first_three) / len(first_three)
    avg_last = sum(last_three) / len(last_three)

    improvement = avg_last - avg_first

    if improvement <= 0:
        return 0.0

    # Scale: +5 points for 20+ point improvement, proportional below
    return min(MAX_MOMENTUM_BONUS, improvement / 20.0 * MAX_MOMENTUM_BONUS)


def calculate_completeness_bonus(answered: int, total: int) -> float:
    """
    Reward candidates who complete the full interview.

    Returns 0 to +5 bonus.
    """
    if total == 0:
        return 0.0

    completion_rate = answered / total

    if completion_rate >= 1.0:
        return MAX_COMPLETENESS_BONUS
    elif completion_rate >= 0.8:
        return MAX_COMPLETENESS_BONUS * 0.6
    elif completion_rate >= 0.5:
        return MAX_COMPLETENESS_BONUS * 0.3

    return 0.0


def calculate_integrity_penalty(violations: List[Any]) -> float:
    """
    Penalize proctoring violations.

    Each violation type has a fixed penalty.
    Total capped at MAX_INTEGRITY_PENALTY.

    Uses normalize_violation_type() to handle both old PascalCase stored keys
    and new canonical snake_case keys. Backward compatible.
    """
    if not violations:
        return 0.0

    total_penalty = 0.0

    for v in violations:
        if isinstance(v, dict):
            raw_type = v.get("type", "unknown")
        else:
            raw_type = str(v)

        vtype = normalize_violation_type(raw_type)
        penalty = VIOLATION_PENALTIES.get(vtype, 5)
        total_penalty += penalty

    return min(MAX_INTEGRITY_PENALTY, total_penalty)


def calculate_overall_score(
    skill_metrics: Dict[str, float],
    question_scores: List[float],
    answered: int = 0,
    total: int = 0,
    violations: Optional[List[Any]] = None,
    gaming_detected: bool = False,
    role: str = "Software Engineer",
    seniority: str = "Mid",
    answer_times: Optional[List[float]] = None,
    qa_pairs: Optional[List[dict]] = None,
) -> ScoreBreakdown:
    """
    Calculate the complete transparent score with explainability.

    This is the single source of truth for candidate scoring.

    Args:
        skill_metrics: Current dimension scores from AI evaluation
        question_scores: List of per-question scores (for momentum)
        answered: Number of questions answered
        total: Total questions in interview
        violations: Proctoring violation list
        was_lazy: True if last answer was too short (removed — lazy penalty handled at chat level)
        gaming_detected: True if AI detected manipulation
        role: Target role for context-aware explanations
        seniority: Seniority level for expectation calibration
        answer_times: Response times in seconds for timing analysis
        qa_pairs: Full Q&A pairs for deeper analysis

    Returns:
        ScoreBreakdown with full transparency data
    """
    breakdown = ScoreBreakdown()

    # 1. Dimension scores — check for rubric-specific skills first
    standard_dims = {"Technical", "Communication", "Problem Solving", "Adaptability", "Confidence", "Consistency", "Soft Skills"}
    rubric_skills = {k: v for k, v in skill_metrics.items() if k not in standard_dims}

    if rubric_skills:
        # Rubric-driven interview: use rubric skill scores as primary
        rubric_values = [float(v) for v in rubric_skills.values() if v is not None and v > 0]
        if rubric_values:
            rubric_avg = sum(rubric_values) / len(rubric_values)
            breakdown.technical = rubric_avg
            breakdown.communication = skill_metrics.get("Communication", rubric_avg)
            breakdown.problem_solving = skill_metrics.get("Problem Solving", rubric_avg)
            breakdown.adaptability = skill_metrics.get("Adaptability", rubric_avg)
            breakdown.confidence = skill_metrics.get("Confidence", 50.0)
            # Override base_score with rubric-weighted average
            breakdown.base_score = rubric_avg
        else:
            breakdown.technical = skill_metrics.get("Technical", 50.0)
            breakdown.communication = skill_metrics.get("Communication", 50.0)
            breakdown.problem_solving = skill_metrics.get("Problem Solving", 50.0)
            breakdown.adaptability = skill_metrics.get("Adaptability", 50.0)
            breakdown.confidence = skill_metrics.get("Confidence", 50.0)
            breakdown.base_score = calculate_base_score(skill_metrics)
    else:
        # Legacy non-rubric scoring
        breakdown.technical = skill_metrics.get("Technical", 50.0)
        breakdown.communication = skill_metrics.get("Communication", 50.0)
        breakdown.problem_solving = skill_metrics.get("Problem Solving", 50.0)
        breakdown.adaptability = skill_metrics.get("Adaptability", 50.0)
        breakdown.confidence = skill_metrics.get("Confidence", 50.0)
        breakdown.base_score = calculate_base_score(skill_metrics)

    # 3. Modifiers
    breakdown.momentum_bonus = calculate_momentum_bonus(question_scores)
    breakdown.completeness_bonus = calculate_completeness_bonus(answered, total)
    breakdown.integrity_penalty = calculate_integrity_penalty(violations or [])

    # Lazy penalty removed per Option B: handled at chat level (score forced to 20)
    # breakdown.lazy_penalty stays at 0.0 (default)

    if gaming_detected:
        breakdown.gaming_penalty = GAMING_PENALTY

    # 4. Timing penalty (NEW)
    if answer_times and len(answer_times) >= 3:
        from backend.ai.timing_analysis import (
            analyze_response_timing,
            compute_timing_penalty,
        )

        timing = analyze_response_timing(answer_times)
        breakdown.timing_penalty = compute_timing_penalty(timing)

    # 5. Final score
    # lazy_penalty is excluded by design (Option B): lazy answers are
    # penalized deterministically at chat level (score forced to 20).
    # Double-penalizing here was Bug 2 — now fixed.
    final = (
        breakdown.base_score
        + breakdown.momentum_bonus
        + breakdown.completeness_bonus
        - breakdown.integrity_penalty
        - breakdown.gaming_penalty
        - breakdown.timing_penalty
    )

    breakdown.final_score = round(max(0.0, min(100.0, final)), 1)

    # 6. Metadata
    breakdown.total_questions = total
    breakdown.answered_questions = answered
    breakdown.question_scores = list(question_scores)

    # 7. Explainable scoring (NEW)
    try:
        from backend.ai.explainable_scoring import generate_explainable_score

        explainable = generate_explainable_score(
            final_score=breakdown.final_score,
            dimension_scores=skill_metrics,
            question_scores=question_scores,
            role=role,
            seniority=seniority,
            violations=violations,
            answer_times=answer_times,
            qa_pairs=qa_pairs,
        )

        breakdown.confidence_interval = explainable.confidence_interval.to_dict()
        breakdown.why_this_score = explainable.why_this_score
        breakdown.strengths = explainable.strengths
        breakdown.weaknesses = explainable.weaknesses
        breakdown.gaps = [g.to_dict() for g in explainable.gaps]
        breakdown.fastest_impact = explainable.fastest_impact
        breakdown.evidence_summary = explainable.evidence_summary
        breakdown.dimension_explanations = explainable.dimension_explanations
        breakdown.risk_factors = explainable.risk_factors
        breakdown.hiring_signals = explainable.hiring_signals
    except Exception:
        # Graceful fallback if explainable scoring fails
        breakdown.why_this_score = (
            f"Score: {breakdown.final_score}/100 based on weighted dimension analysis."
        )
        breakdown.confidence_interval = {
            "point_estimate": breakdown.final_score,
            "margin_of_error": 10.0,
            "interpretation": "Default uncertainty (explainable scoring unavailable)",
        }

    return breakdown


def calculate_question_score(ai_eval: Dict[str, Any]) -> float:
    """
    Calculate a single question's score from AI evaluation.

    Uses the same dimension weights for consistency.
    """
    skills = ai_eval.get("skills", {})
    if not skills:
        return ai_eval.get("score", 50.0)

    total = 0.0
    total_weight = 0.0

    for dimension, weight in DIMENSION_WEIGHTS.items():
        score = skills.get(dimension, ai_eval.get("score", 50.0))
        score = max(0.0, min(100.0, float(score)))
        total += score * weight
        total_weight += weight

    if total_weight == 0:
        return ai_eval.get("score", 50.0)

    return total / total_weight


def get_score_label(score: float) -> str:
    """Human-readable score label"""
    if score >= 85:
        return "Exceptional"
    elif score >= 70:
        return "Strong"
    elif score >= 55:
        return "Competent"
    elif score >= 40:
        return "Developing"
    else:
        return "Needs Improvement"


def get_recommendation(score: float, integrity_penalty: float) -> str:
    """Hiring recommendation based on score and integrity"""
    if integrity_penalty >= 15:
        return "Manual Review Required"
    elif score >= 80:
        return "Strong Hire"
    elif score >= 65:
        return "Recommended"
    elif score >= 50:
        return "Consider"
    else:
        return "Not Recommended"


# =============================================================================
# SCORING CONFIGURATION
# =============================================================================


class ScoringConfig:
    """All scoring constants in one place."""

    DIMENSION_WEIGHTS = DIMENSION_WEIGHTS

    TRUST_PENALTIES = VIOLATION_PENALTIES
    MAX_TRUST_PENALTY: float = 50.0


class ScoringEngine:
    """Scoring engine that delegates to transparent functions."""

    def __init__(self, config: ScoringConfig = None):
        self.config = config or ScoringConfig()

    def score_interview(
        self,
        skill_metrics: Dict[str, float],
        question_scores: List[float],
        answered: int = 0,
        total: int = 15,
        violations: Optional[List[Any]] = None,
        gaming_detected: bool = False,
        answer_times: Optional[List[float]] = None,
        app: Any = None,
    ) -> ScoreBreakdown:
        if app is not None:
            _er = (
                app.evaluation_sessions[0].evaluation_result
                if app.evaluation_sessions
                and app.evaluation_sessions[0].evaluation_result
                else None
            )
            scoring_model = _er.scoring_model if _er else "legacy"
            if scoring_model in ("rubric", "backfill"):
                try:
                    from backend.database import (
                        EvaluationResult,
                        EvaluationSession,
                        SessionLocal,
                    )

                    db = SessionLocal()
                    try:
                        summary = (
                            db.query(EvaluationResult)
                            .join(
                                EvaluationSession,
                                EvaluationResult.evaluation_session_id
                                == EvaluationSession.id,
                            )
                            .filter(EvaluationSession.application_id == app.id)
                            .first()
                        )
                        if summary and summary.final_score and summary.final_score > 0:
                            return self._rubric_summary_to_breakdown(summary, app)
                    finally:
                        db.close()
                except Exception:
                    pass

        return calculate_overall_score(
            skill_metrics=skill_metrics,
            question_scores=question_scores,
            answered=answered,
            total=total,
            violations=violations,
            gaming_detected=gaming_detected,
            answer_times=answer_times,
        )

    def _rubric_summary_to_breakdown(
        self,
        summary: Any,
        app: Any,
    ) -> ScoreBreakdown:
        b = ScoreBreakdown()
        breakdown = getattr(summary, "score_breakdown", None) or {}
        if isinstance(breakdown, str):
            import json

            breakdown = json.loads(breakdown) if breakdown else {}

        final_score = float(getattr(summary, "final_score", 0) or 0)
        b.final_score = final_score
        b.base_score = final_score

        category_scores = (
            breakdown.get("category_scores", []) if isinstance(breakdown, dict) else []
        )
        skill_scores = (
            breakdown.get("skill_scores", {}) if isinstance(breakdown, dict) else {}
        )
        gaps = breakdown.get("gaps", []) if isinstance(breakdown, dict) else []
        num_answers_scored = (
            breakdown.get("num_answers_scored", 0) if isinstance(breakdown, dict) else 0
        )

        if category_scores:
            dim_map = {
                "technical": "technical",
                "communication": "communication",
                "problem solving": "problem_solving",
                "adaptability": "adaptability",
                "confidence": "confidence",
            }
            for cat in category_scores:
                if isinstance(cat, dict):
                    name = cat.get("name", "").lower().strip()
                    score = cat.get("score", 50)
                    for key, dim in dim_map.items():
                        if key in name:
                            setattr(b, dim, float(score))
                            break

        if skill_scores:
            all_evidences = []
            for sname, sinfo in skill_scores.items():
                if isinstance(sinfo, dict):
                    evidence = sinfo.get("evidence", [])
                    if isinstance(evidence, list):
                        all_evidences.extend(evidence)
            b.evidence_summary = all_evidences[:5]

        conf_lower = getattr(summary, "confidence_lower", None)
        conf_upper = getattr(summary, "confidence_upper", None)
        b.confidence_interval = {
            "point_estimate": final_score,
            "lower_bound": conf_lower,
            "upper_bound": conf_upper,
            "margin_of_error": round(
                (float(conf_upper or 0) - float(conf_lower or 0)) / 2, 1
            )
            if conf_lower is not None and conf_upper is not None
            else 0,
        }

        if gaps:
            b.gaps = gaps

        rubric_version = getattr(summary, "rubric_version", 0) or 0
        b.why_this_score = (
            f"Score computed by deterministic rubric engine v{rubric_version}. "
            f"Based on {num_answers_scored} answers across "
            f"{len(category_scores)} skill categories."
        )

        return b
