"""
Candway Scoring Engine — Pure Compatibility Shim
=================================================

Imports everything from scoring_transparent (single source of truth).
Kept for backward compatibility. No duplicate logic.

Architecture (defined in scoring_transparent.py):
  1. Interview Dimension Scoring (per-question, live)
  2. Interview Modifiers (momentum, completeness, integrity, etc.)
  3. Composite Score (CV + Interview + Skills + Trust)
  4. 7D Talent Radar
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from backend.scoring_transparent import (
    ScoreBreakdown as TransparentScoreBreakdown,
)
from backend.scoring_transparent import (
    ScoringConfig as TransparentScoringConfig,
)
from backend.scoring_transparent import (
    ScoringEngine as TransparentScoringEngine,
)
from backend.scoring_transparent import (
    calculate_base_score as _transparent_calculate_base_score,
)
from backend.scoring_transparent import (
    calculate_completeness_bonus as _transparent_calculate_completeness_bonus,
)
from backend.scoring_transparent import (
    calculate_integrity_penalty as _transparent_calculate_integrity_penalty,
)
from backend.scoring_transparent import (
    calculate_momentum_bonus as _transparent_calculate_momentum_bonus,
)
from backend.scoring_transparent import (
    calculate_overall_score as _transparent_calculate_overall_score,
)

ScoringConfig = TransparentScoringConfig


class ComparisonResponseBuilder:
    """Simple builder used in audit tests.

    Takes a list of application dicts (as produced by the API) and returns a
    response structure containing a ``candidates`` list sorted by ``final_score``
    descending. Only the fields needed by the tests are included.
    """

    def build_comparison_response(self, applications: list) -> dict:
        candidates = []
        for app in applications:
            # Prefer explicit name fields; fall back to ``full_name`` or a placeholder.
            name = (
                app.get("candidate_name")
                or app.get("full_name")
                or app.get("name")
                or "Unknown"
            )
            # ``overall_score`` is the canonical final score; fall back to ``cv_score``.
            final_score = app.get("overall_score") or app.get("cv_score") or 0
            candidates.append({"name": name, "final_score": final_score})
        # Sort highest score first (descending).
        candidates.sort(key=lambda x: x["final_score"], reverse=True)
        return {"candidates": candidates}


@dataclass
class LegacyScoreBreakdown:
    """Wraps TransparentScoreBreakdown for backward compatibility."""

    technical: float = 50.0
    communication: float = 50.0
    problem_solving: float = 50.0
    adaptability: float = 50.0
    confidence: float = 50.0
    base_score: float = 50.0
    momentum_bonus: float = 0.0
    completeness_bonus: float = 0.0
    integrity_penalty: float = 0.0
    lazy_penalty: float = 0.0
    gaming_penalty: float = 0.0
    timing_penalty: float = 0.0
    final_score: float = 0.0
    total_questions: int = 0
    answered_questions: int = 0
    question_scores: List[float] = field(default_factory=list)
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

    @classmethod
    def from_transparent(cls, b: TransparentScoreBreakdown) -> "LegacyScoreBreakdown":
        return cls(
            technical=b.technical,
            communication=b.communication,
            problem_solving=b.problem_solving,
            adaptability=b.adaptability,
            confidence=b.confidence,
            base_score=b.base_score,
            momentum_bonus=b.momentum_bonus,
            completeness_bonus=b.completeness_bonus,
            integrity_penalty=b.integrity_penalty,
            lazy_penalty=b.lazy_penalty,
            gaming_penalty=b.gaming_penalty,
            timing_penalty=b.timing_penalty,
            final_score=b.final_score,
            total_questions=b.total_questions,
            answered_questions=b.answered_questions,
            question_scores=b.question_scores,
            confidence_interval=b.confidence_interval,
            why_this_score=b.why_this_score,
            strengths=b.strengths,
            weaknesses=b.weaknesses,
            gaps=b.gaps,
            fastest_impact=b.fastest_impact,
            evidence_summary=b.evidence_summary,
            dimension_explanations=b.dimension_explanations,
            risk_factors=b.risk_factors,
            hiring_signals=b.hiring_signals,
        )

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
) -> LegacyScoreBreakdown:
    transparent = _transparent_calculate_overall_score(
        skill_metrics=skill_metrics,
        question_scores=question_scores,
        answered=answered,
        total=total,
        violations=violations,
        gaming_detected=gaming_detected,
        role=role,
        seniority=seniority,
        answer_times=answer_times,
        qa_pairs=qa_pairs,
    )
    return LegacyScoreBreakdown.from_transparent(transparent)


def calculate_base_score(skill_metrics: Dict[str, float]) -> float:
    return _transparent_calculate_base_score(skill_metrics)


def calculate_momentum_bonus(question_scores: List[float]) -> float:
    return _transparent_calculate_momentum_bonus(question_scores)


def calculate_completeness_bonus(answered: int, total: int) -> float:
    return _transparent_calculate_completeness_bonus(answered, total)


def calculate_integrity_penalty(violations: List[Any]) -> float:
    return _transparent_calculate_integrity_penalty(violations)


class ScoringEngine(TransparentScoringEngine):
    """Delegates to TransparentScoringEngine. Returns LegacyScoreBreakdown from score_interview."""

    def score_interview(
        self,
        skill_metrics: Dict[str, float],
        question_scores: List[float],
        answered: int = 0,
        total: int = 15,
        violations: Optional[List[Any]] = None,
        gaming_detected: bool = False,
        answer_times: Optional[List[float]] = None,
    ) -> LegacyScoreBreakdown:
        transparent = super().score_interview(
            skill_metrics=skill_metrics,
            question_scores=question_scores,
            answered=answered,
            total=total,
            violations=violations,
            gaming_detected=gaming_detected,
            answer_times=answer_times,
        )
        return LegacyScoreBreakdown.from_transparent(transparent)


ScoreBreakdown = TransparentScoreBreakdown
