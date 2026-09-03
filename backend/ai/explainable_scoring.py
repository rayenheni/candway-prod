"""
Explainable Scoring Layer
==========================

Provides human-readable explanations for every score, including:
- Why this score was given
- Gap analysis (what's missing)
- Fastest path to improvement
- Confidence intervals
- Evidence-based reasoning

Author: Candway Engineering
"""

import math
import statistics
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


@dataclass
class ConfidenceInterval:
    """Statistical confidence bounds around a score"""

    point_estimate: float
    lower_bound: float
    upper_bound: float
    confidence_level: float  # e.g., 0.95 for 95%
    margin_of_error: float
    sample_size: int
    std_dev: float
    per_dimension: Dict[str, dict] = field(default_factory=dict)

    def to_dict(self) -> dict:
        result = {
            "point_estimate": round(self.point_estimate, 1),
            "lower_bound": round(self.lower_bound, 1),
            "upper_bound": round(self.upper_bound, 1),
            "confidence_level": self.confidence_level,
            "margin_of_error": round(self.margin_of_error, 1),
            "sample_size": self.sample_size,
            "std_dev": round(self.std_dev, 1),
            "interpretation": self._interpret(),
        }
        if self.per_dimension:
            result["per_dimension"] = self.per_dimension
        return result

    def _interpret(self) -> str:
        if self.margin_of_error <= 3:
            return "Score is reliable across all questions"
        elif self.margin_of_error <= 7:
            return "Performance varied — review per-question scores"
        else:
            return "Answers were inconsistent — recommend manual review"


@dataclass
class GapAnalysis:
    """Specific areas where candidate underperformed"""

    skill: str
    expected_level: str
    actual_score: float
    gap_size: float
    evidence: List[str] = field(default_factory=list)
    improvement_action: str = ""

    def to_dict(self) -> dict:
        return {
            "skill": self.skill,
            "expected_level": self.expected_level,
            "actual_score": round(self.actual_score, 1),
            "gap_size": round(self.gap_size, 1),
            "evidence": self.evidence,
            "improvement_action": self.improvement_action,
        }


@dataclass
class ExplainableScore:
    """Complete explainable score with reasoning"""

    final_score: float
    confidence_interval: ConfidenceInterval
    why_this_score: str
    strengths: List[str] = field(default_factory=list)
    weaknesses: List[str] = field(default_factory=list)
    gaps: List[GapAnalysis] = field(default_factory=list)
    fastest_impact: str = ""
    evidence_summary: List[str] = field(default_factory=list)
    dimension_explanations: Dict[str, str] = field(default_factory=dict)
    risk_factors: List[str] = field(default_factory=list)
    hiring_signals: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "final_score": round(self.final_score, 1),
            "confidence_interval": self.confidence_interval.to_dict(),
            "why_this_score": self.why_this_score,
            "strengths": self.strengths,
            "weaknesses": self.weaknesses,
            "gaps": [g.to_dict() for g in self.gaps],
            "fastest_impact": self.fastest_impact,
            "evidence_summary": self.evidence_summary,
            "dimension_explanations": self.dimension_explanations,
            "risk_factors": self.risk_factors,
            "hiring_signals": self.hiring_signals,
        }


def compute_confidence_interval(
    question_scores: List[float],
    confidence_level: float = 0.95,
    dimension_scores: Dict[str, List[float]] = None,
) -> ConfidenceInterval:
    """
    Compute statistical confidence interval for the score.

    Uses t-distribution for small samples (n < 30),
    normal distribution for larger samples.
    When dimension_scores are provided, computes per-dimension CIs.
    """
    if not question_scores or len(question_scores) < 2:
        return ConfidenceInterval(
            point_estimate=question_scores[0] if question_scores else 50.0,
            lower_bound=0.0,
            upper_bound=100.0,
            confidence_level=confidence_level,
            margin_of_error=50.0,
            sample_size=len(question_scores),
            std_dev=0.0,
        )

    n = len(question_scores)
    mean = statistics.mean(question_scores)
    std_dev = statistics.stdev(question_scores) if n > 1 else 0.0

    std_error = std_dev / math.sqrt(n) if n > 1 else std_dev

    if n >= 30:
        critical_value = 1.96
    elif n >= 10:
        critical_value = 2.0
    elif n >= 5:
        critical_value = 2.5
    else:
        critical_value = 3.0

    margin_of_error = critical_value * std_error

    lower = max(0.0, mean - margin_of_error)
    upper = min(100.0, mean + margin_of_error)

    per_dim = {}
    if dimension_scores:
        for dim, scores in dimension_scores.items():
            if len(scores) >= 2:
                dim_mean = statistics.mean(scores)
                dim_std = statistics.stdev(scores)
                dim_se = dim_std / math.sqrt(len(scores))
                dim_moe = critical_value * dim_se
                per_dim[dim] = {
                    "score": round(dim_mean, 1),
                    "margin_of_error": round(dim_moe, 1),
                    "lower_bound": round(max(0.0, dim_mean - dim_moe), 1),
                    "upper_bound": round(min(100.0, dim_mean + dim_moe), 1),
                    "samples": len(scores),
                }

    return ConfidenceInterval(
        point_estimate=mean,
        lower_bound=lower,
        upper_bound=upper,
        confidence_level=confidence_level,
        margin_of_error=margin_of_error,
        sample_size=n,
        std_dev=std_dev,
        per_dimension=per_dim,
    )


def analyze_dimension_performance(
    dimension: str,
    score: float,
    question_scores: List[float],
    role: str,
    seniority: str = "Mid",
) -> Tuple[str, List[str], float]:
    """
    Analyze a single dimension's performance.
    Returns: (explanation, evidence, expected_score)
    """
    # Expected scores by seniority
    expectations = {
        "Junior": {
            "Technical": 60,
            "Communication": 65,
            "Problem Solving": 55,
            "Adaptability": 60,
            "Confidence": 60,
        },
        "Mid": {
            "Technical": 75,
            "Communication": 75,
            "Problem Solving": 70,
            "Adaptability": 70,
            "Confidence": 70,
        },
        "Senior": {
            "Technical": 85,
            "Communication": 80,
            "Problem Solving": 85,
            "Adaptability": 80,
            "Confidence": 80,
        },
        "Lead": {
            "Technical": 90,
            "Communication": 85,
            "Problem Solving": 90,
            "Adaptability": 85,
            "Confidence": 85,
        },
    }

    expected = expectations.get(seniority, expectations["Mid"]).get(dimension, 70)
    gap = score - expected

    evidence = []
    if question_scores:
        trend = (
            "improving"
            if len(question_scores) >= 3 and question_scores[-1] > question_scores[0]
            else "declining"
            if len(question_scores) >= 3 and question_scores[-1] < question_scores[0]
            else "stable"
        )
        evidence.append(f"Performance trend: {trend}")
        evidence.append(
            f"Score range: {min(question_scores):.0f}-{max(question_scores):.0f}"
        )

    if gap >= 10:
        explanation = f"Exceeds {seniority} expectations by {gap:.0f} points. Demonstrates advanced proficiency."
    elif gap >= 0:
        explanation = f"Meets {seniority} expectations. Solid foundational capability."
    elif gap >= -10:
        explanation = f"Slightly below {seniority} expectations ({abs(gap):.0f} point gap). Areas for development identified."
    else:
        explanation = f"Significantly below {seniority} expectations ({abs(gap):.0f} point gap). Requires targeted improvement."

    return explanation, evidence, expected


def _extract_per_dimension_scores(
    qa_pairs: Optional[List[dict]],
) -> Dict[str, List[float]]:
    """Extract per-dimension scores from QA pairs for per-dimension confidence intervals."""
    dim_scores: Dict[str, List[float]] = {}
    if not qa_pairs:
        return dim_scores
    for qa in qa_pairs:
        if isinstance(qa, dict):
            scores = qa.get("scores") or qa.get("skills") or {}
            if isinstance(scores, dict):
                for dim, val in scores.items():
                    if dim not in dim_scores:
                        dim_scores[dim] = []
                    try:
                        dim_scores[dim].append(float(val))
                    except (ValueError, TypeError):
                        pass
    return dim_scores


def generate_explainable_score(
    final_score: float,
    dimension_scores: Dict[str, float],
    question_scores: List[float],
    role: str,
    seniority: str = "Mid",
    violations: Optional[List[dict]] = None,
    answer_times: Optional[List[float]] = None,
    cheat_signals: Optional[List[str]] = None,
    qa_pairs: Optional[List[dict]] = None,
) -> ExplainableScore:
    """
    Generate a fully explainable score with reasoning, gaps, and recommendations.
    """
    # 1. Confidence interval (with per-dimension if QA data available)
    per_dim = _extract_per_dimension_scores(qa_pairs)
    ci = compute_confidence_interval(
        question_scores, dimension_scores=per_dim if per_dim else None
    )

    # 2. Dimension explanations
    dimension_explanations = {}
    gaps = []
    strengths = []
    weaknesses = []
    evidence_summary = []

    for dim, score in dimension_scores.items():
        explanation, evidence, expected = analyze_dimension_performance(
            dim, score, question_scores, role, seniority
        )
        dimension_explanations[dim] = explanation
        evidence_summary.extend(evidence)

        gap_size = score - expected
        if gap_size >= 5:
            strengths.append(f"{dim}: {score:.0f}/100 (exceeds expectations)")
        elif gap_size <= -10:
            weaknesses.append(f"{dim}: {score:.0f}/100 (below expectations)")
            gaps.append(
                GapAnalysis(
                    skill=dim,
                    expected_level=seniority,
                    actual_score=score,
                    gap_size=abs(gap_size),
                    evidence=evidence,
                    improvement_action=_get_improvement_action(dim, score, seniority),
                )
            )

    # 3. Why this score
    why = _generate_score_explanation(
        final_score, dimension_scores, ci, role, seniority
    )

    # 4. Fastest impact
    fastest = _compute_fastest_impact(gaps, dimension_scores, seniority)

    # 5. Risk factors
    risks = []
    if violations and len(violations) >= 3:
        risks.append(
            f"Multiple proctoring violations ({len(violations)}) suggest integrity concerns"
        )
    if cheat_signals:
        risks.extend([f"Anti-cheat flag: {signal}" for signal in cheat_signals[:3]])
    if answer_times:
        fast_answers = sum(1 for t in answer_times if t < 10)
        if fast_answers >= 3:
            risks.append(
                f"{fast_answers} answers submitted in under 10 seconds — possible pre-written responses"
            )
    if ci.margin_of_error > 10:
        risks.append(
            f"High score uncertainty (±{ci.margin_of_error:.0f} points) — recommend additional assessment"
        )

    # 6. Hiring signals
    signals = {
        "technical_readiness": _assess_technical_readiness(dimension_scores, seniority),
        "growth_trajectory": _assess_growth_trajectory(question_scores),
        "culture_fit_indicator": _assess_communication_fit(dimension_scores),
        "risk_level": "Low"
        if len(risks) == 0
        else "Medium"
        if len(risks) <= 2
        else "High",
    }

    return ExplainableScore(
        final_score=final_score,
        confidence_interval=ci,
        why_this_score=why,
        strengths=strengths,
        weaknesses=weaknesses,
        gaps=gaps,
        fastest_impact=fastest,
        evidence_summary=evidence_summary[:5],
        dimension_explanations=dimension_explanations,
        risk_factors=risks,
        hiring_signals=signals,
    )


def _generate_score_explanation(
    score: float,
    dimensions: Dict[str, float],
    ci: ConfidenceInterval,
    role: str,
    seniority: str,
) -> str:
    """Generate natural language explanation for the score"""
    sorted_dims = sorted(dimensions.items(), key=lambda x: x[1], reverse=True)
    best_dim = sorted_dims[0]
    worst_dim = sorted_dims[-1]

    if score >= 85:
        base = f"This candidate scored {score:.0f}/100, placing them in the top tier for {role} positions at {seniority} level. "
    elif score >= 70:
        base = f"This candidate scored {score:.0f}/100, demonstrating solid competence for {role} positions. "
    elif score >= 55:
        base = f"This candidate scored {score:.0f}/100, showing foundational capability with room for growth. "
    else:
        base = f"This candidate scored {score:.0f}/100, indicating significant development needs for this role. "

    base += f"Strongest area: {best_dim[0]} ({best_dim[1]:.0f}/100). "
    base += f"Weakest area: {worst_dim[0]} ({worst_dim[1]:.0f}/100). "

    if ci.margin_of_error <= 5:
        base += f"Score is precise (±{ci.margin_of_error:.0f} points, {ci.sample_size} data points)."
    else:
        base += f"Score has moderate uncertainty (±{ci.margin_of_error:.0f} points) — consider additional assessment."

    return base


def _get_improvement_action(skill: str, score: float, seniority: str) -> str:
    """Get specific improvement recommendation"""
    actions = {
        "Technical": {
            "Junior": "Focus on core fundamentals: data structures, basic algorithms, and language syntax. Build 2-3 small projects.",
            "Mid": "Deepen expertise in system design, architecture patterns, and advanced language features. Contribute to open source.",
            "Senior": "Master distributed systems, performance optimization, and mentoring. Lead technical design reviews.",
        },
        "Communication": {
            "Junior": "Practice explaining technical concepts to non-technical audiences. Use the STAR method for structured answers.",
            "Mid": "Develop stakeholder communication skills. Practice presenting technical trade-offs to business audiences.",
            "Senior": "Focus on executive communication, technical writing, and cross-team alignment strategies.",
        },
        "Problem Solving": {
            "Junior": "Practice algorithmic thinking with coding challenges. Learn debugging methodologies.",
            "Mid": "Work on complex system debugging, root cause analysis, and creative solution design.",
            "Senior": "Develop strategic problem-solving: architecture decisions, risk assessment, and trade-off analysis.",
        },
        "Adaptability": {
            "Junior": "Expose yourself to new technologies through side projects. Practice learning unfamiliar codebases.",
            "Mid": "Work on cross-functional projects. Practice switching between different tech stacks.",
            "Senior": "Lead technology evaluations and migrations. Develop frameworks for assessing new tools.",
        },
        "Confidence": {
            "Junior": "Build a portfolio of completed projects. Practice mock interviews to build comfort.",
            "Mid": "Take ownership of technical decisions. Present at team meetings or tech talks.",
            "Senior": "Develop thought leadership: write articles, speak at conferences, mentor others.",
        },
    }

    return actions.get(skill, {}).get(
        seniority, f"Seek mentorship and focused practice in {skill.lower()}."
    )


def _compute_fastest_impact(
    gaps: List[GapAnalysis], dimensions: Dict[str, float], seniority: str
) -> str:
    """Compute the single fastest way to improve the score"""
    if not gaps:
        return (
            "Score is strong across all dimensions. Focus on maintaining consistency."
        )

    # Find the dimension with the largest gap that's easiest to improve
    priority_order = [
        "Technical",
        "Communication",
        "Problem Solving",
        "Adaptability",
        "Confidence",
    ]

    for dim in priority_order:
        gap = next((g for g in gaps if g.skill == dim), None)
        if gap and gap.gap_size >= 10:
            return f"Priority: Improve {dim} (currently {gap.actual_score:.0f}, target {seniority} level). {gap.improvement_action}"

    # If no major gaps, suggest consistency
    lowest_dim = min(dimensions.items(), key=lambda x: x[1])
    return f"Focus on {lowest_dim[0]} (currently {lowest_dim[1]:.0f}/100) to raise overall score. Small improvements here will have the largest impact."


def _assess_technical_readiness(dimensions: Dict[str, float], seniority: str) -> str:
    """Assess if candidate is technically ready for the role"""
    tech_score = dimensions.get("Technical", 50)
    problem_score = dimensions.get("Problem Solving", 50)
    avg = (tech_score + problem_score) / 2

    thresholds = {"Junior": 55, "Mid": 70, "Senior": 80, "Lead": 85}
    threshold = thresholds.get(seniority, 70)

    if avg >= threshold + 10:
        return "Ready — exceeds technical bar"
    elif avg >= threshold:
        return "Ready — meets technical bar"
    elif avg >= threshold - 10:
        return "Conditional — needs mentoring support"
    else:
        return "Not ready — significant skill gaps"


def _assess_growth_trajectory(question_scores: List[float]) -> str:
    """Assess if candidate is improving or declining"""
    if len(question_scores) < 3:
        return "Insufficient data"

    first_third = statistics.mean(question_scores[: len(question_scores) // 3])
    last_third = statistics.mean(question_scores[-(len(question_scores) // 3) :])
    change = last_third - first_third

    if change >= 10:
        return "Strong upward trajectory — quick learner"
    elif change >= 3:
        return "Moderate improvement — receptive to feedback"
    elif change >= -3:
        return "Stable performance — consistent but not growing"
    elif change >= -10:
        return "Slight decline — may be fatigued or struggling"
    else:
        return "Significant decline — concerning pattern"


def _assess_communication_fit(dimensions: Dict[str, float]) -> str:
    """Assess cultural fit based on communication patterns"""
    comm = dimensions.get("Communication", 50)
    confidence = dimensions.get("Confidence", 50)
    adaptability = dimensions.get("Adaptability", 50)

    avg = (comm + confidence + adaptability) / 3

    if avg >= 80:
        return "Strong collaborator — would thrive in team environments"
    elif avg >= 65:
        return "Good team player — may need support in high-pressure situations"
    elif avg >= 50:
        return "Developing interpersonal skills — consider team fit carefully"
    else:
        return "Communication concerns — may struggle in collaborative settings"
