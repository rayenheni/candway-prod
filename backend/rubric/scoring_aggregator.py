from typing import Dict, List, Optional

from backend.rubric.rubric_engine import SkillScoreResult


class AggregatedScore:
    def __init__(
        self,
        name: str,
        score: int,
        weight: float,
        confidence_lower: int,
        confidence_upper: int,
        children: Optional[List["AggregatedScore"]] = None,
        skills_scored: int = 0,
        skills_total: int = 0,
    ):
        self.name = name
        self.score = score
        self.weight = weight
        self.confidence_lower = confidence_lower
        self.confidence_upper = confidence_upper
        self.children = children or []
        self.skills_scored = skills_scored
        self.skills_total = skills_total

    @property
    def coverage_pct(self) -> int:
        if self.skills_total == 0:
            return 0
        return round((self.skills_scored / self.skills_total) * 100)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "score": self.score,
            "weight": self.weight,
            "confidence_range": [self.confidence_lower, self.confidence_upper],
            "coverage_pct": self.coverage_pct,
            "skills_scored": self.skills_scored,
            "skills_total": self.skills_total,
            "children": [c.to_dict() for c in self.children] if self.children else None,
        }


class InterviewScoringSummary:
    def __init__(
        self,
        application_id: int,
        rubric_version: int,
        overall_score: int,
        confidence_lower: int,
        confidence_upper: int,
        categories: List[AggregatedScore],
        skill_scores: Dict[str, dict],
        gaps: List[dict],
        num_answers_scored: int = 0,
    ):
        self.application_id = application_id
        self.rubric_version = rubric_version
        self.overall_score = overall_score
        self.confidence_lower = confidence_lower
        self.confidence_upper = confidence_upper
        self.categories = categories
        self.skill_scores = skill_scores
        self.gaps = gaps
        self.num_answers_scored = num_answers_scored
        self.overall_coverage_pct = 0

    def to_dict(self) -> dict:
        # overall_score here is deliberately the pure rubric-derived
        # score. Global rewards/penalties are applied later by the
        # interview scoring layer.
        return {
            "application_id": self.application_id,
            "rubric_version": self.rubric_version,
            "overall_score": self.overall_score,
            "rubric_base_score": self.overall_score,
            "confidence_range": [self.confidence_lower, self.confidence_upper],
            "categories": [c.to_dict() for c in self.categories],
            "skill_scores": self.skill_scores,
            "gaps": self.gaps,
            "num_answers_scored": self.num_answers_scored,
            "overall_coverage_pct": self.overall_coverage_pct,
            "adjustments": [],
            "penalty_total": 0.0,
            "reward_total": 0.0,
            "adjusted_score": self.overall_score,
        }


def aggregate_scores(
    application_id: int,
    rubric,
    all_answer_results: Dict[int, Dict[str, SkillScoreResult]],
    seniority: str = "mid",
) -> InterviewScoringSummary:
    # Normalize skill names because persisted rubric details may use
    # different casing/whitespace from the rubric definition.
    best_skill_scores: Dict[str, SkillScoreResult] = {}

    for turn_results in all_answer_results.values():
        for skill_name, result in turn_results.items():
            normalized_name = str(skill_name).strip().lower()

            current = best_skill_scores.get(normalized_name)
            if current is None or result.final_score > current.final_score:
                best_skill_scores[normalized_name] = result

    category_scores = []
    all_skill_dicts = {}
    gaps = []
    total_answers = sum(
        len(turn_results)
        for turn_results in all_answer_results.values()
    )

    for cat in rubric.categories:
        subcategory_scores = []

        for sub in cat.subcategories:
            skill_scores_list = []
            for skill in sub.skills:
                result = best_skill_scores.get(skill.name.lower())

                if result:
                    skill_score = result.final_score
                    cl = result.confidence_lower
                    cu = result.confidence_upper
                    explanation = result.explanation
                    evidence = result.evidence_sentences
                else:
                    skill_score = 0
                    cl = 0
                    cu = 0
                    explanation = "Not assessed"
                    evidence = []

                skill_scores_list.append(
                    {
                        "name": skill.name,
                        "score": skill_score,
                        "weight": skill.weight,
                        "confidence_lower": cl,
                        "confidence_upper": cu,
                        "explanation": explanation,
                        "evidence": evidence,
                    }
                )

            scored_skills = [s for s in skill_scores_list if s["score"] > 0]
            if scored_skills:
                sub_cl = min(s["confidence_lower"] for s in scored_skills)
                sub_cu = max(s["confidence_upper"] for s in scored_skills)
            else:
                sub_cl = 0
                sub_cu = 0

            total_weight = sum(s["weight"] for s in skill_scores_list)
            weighted_sum = sum(s["score"] * s["weight"] for s in skill_scores_list)

            sub_score_value = (
                round(weighted_sum / total_weight) if total_weight > 0 else 0
            )

            subcategory_scores.append(
                AggregatedScore(
                    name=sub.name,
                    score=sub_score_value,
                    weight=sub.weight,
                    confidence_lower=sub_cl,
                    confidence_upper=sub_cu,
                    children=[],
                    skills_scored=len(scored_skills),
                    skills_total=len(sub.skills),
                )
            )

        scored_subs = [s for s in subcategory_scores if s.score > 0]
        if scored_subs:
            cat_cl = min(s.confidence_lower for s in scored_subs)
            cat_cu = max(s.confidence_upper for s in scored_subs)
        else:
            cat_cl = 0
            cat_cu = 0

        cat_total_weight = sum(s.weight for s in subcategory_scores)
        cat_weighted_sum = sum(s.score * s.weight for s in subcategory_scores)

        cat_score_value = (
            round(cat_weighted_sum / cat_total_weight) if cat_total_weight > 0 else 0
        )
        cat_skills_scored = sum(s.skills_scored for s in subcategory_scores)
        cat_skills_total = sum(s.skills_total for s in subcategory_scores)

        category_scores.append(
            AggregatedScore(
                name=cat.name,
                score=cat_score_value,
                weight=cat.weight,
                confidence_lower=cat_cl,
                confidence_upper=cat_cu,
                children=subcategory_scores,
                skills_scored=cat_skills_scored,
                skills_total=cat_skills_total,
            )
        )

        _check_category_gaps(cat, cat_score_value, gaps)

    scored_cats = [c for c in category_scores if c.score > 0]
    if scored_cats:
        overall_cl = min(c.confidence_lower for c in scored_cats)
        overall_cu = max(c.confidence_upper for c in scored_cats)
    else:
        overall_cl = 0
        overall_cu = 0

    total_cat_weight = sum(c.weight for c in category_scores)
    overall_weighted = sum(c.score * c.weight for c in category_scores)

    overall_score = (
        round(overall_weighted / total_cat_weight) if total_cat_weight > 0 else 0
    )

    for skill_name, result in best_skill_scores.items():
        if result.final_score > 0:
            all_skill_dicts[skill_name] = result.to_dict()

    total_scored = sum(c.skills_scored for c in category_scores)
    total_all = sum(c.skills_total for c in category_scores)
    overall_coverage_pct = (
        round((total_scored / total_all) * 100) if total_all > 0 else 0
    )

    summary = InterviewScoringSummary(
        application_id=application_id,
        rubric_version=rubric.version,
        overall_score=overall_score,
        confidence_lower=overall_cl,
        confidence_upper=overall_cu,
        categories=category_scores,
        skill_scores=all_skill_dicts,
        gaps=gaps,
        num_answers_scored=total_answers,
    )
    summary.overall_coverage_pct = overall_coverage_pct
    return summary


def _check_category_gaps(category, actual_score: int, gaps: List[dict]):
    expected = 55
    if actual_score < expected:
        gap_pct = round(((expected - actual_score) / expected) * 100)
        gaps.append(
            {
                "category": category.name,
                "score": actual_score,
                "expected": expected,
                "gap_pct": gap_pct,
                "severity": "critical"
                if gap_pct > 30
                else "moderate"
                if gap_pct > 15
                else "minor",
            }
        )


def apply_rubric_adjustments(
    rubric_score: float,
    adjustments: Optional[List[dict]] = None,
) -> dict:
    """
    Apply explicit interview performance adjustments to the rubric score.

    The rubric score remains the source of truth. Adjustments are additive,
    bounded, and fully auditable.
    """
    base = max(0.0, min(100.0, float(rubric_score)))

    reward_total = 0.0
    penalty_total = 0.0
    normalized = []

    for item in adjustments or []:
        if not isinstance(item, dict):
            continue

        try:
            points = float(item.get("points", 0))
        except (TypeError, ValueError):
            continue

        if points == 0:
            continue

        points = max(-20.0, min(10.0, points))

        adjustment = {
            "type": "reward" if points > 0 else "penalty",
            "points": round(points, 2),
            "reason": str(item.get("reason", "Interview performance")),
            "skill": item.get("skill"),
            "category": item.get("category"),
        }

        normalized.append(adjustment)

        if points > 0:
            reward_total += points
        else:
            penalty_total += points

    adjusted = base + reward_total + penalty_total
    adjusted = max(0.0, min(100.0, adjusted))

    return {
        "rubric_base_score": round(base, 2),
        "reward_total": round(reward_total, 2),
        "penalty_total": round(penalty_total, 2),
        "adjusted_score": round(adjusted, 2),
        "adjustments": normalized,
    }


def apply_rubric_adjustments(
    rubric_score: float,
    adjustments: Optional[List[dict]] = None,
) -> dict:
    """
    Apply explicit interview performance adjustments to the rubric score.

    The rubric score remains the source of truth. Adjustments are additive,
    bounded, and fully auditable.
    """
    base = max(0.0, min(100.0, float(rubric_score)))

    reward_total = 0.0
    penalty_total = 0.0
    normalized = []

    for item in adjustments or []:
        if not isinstance(item, dict):
            continue

        try:
            points = float(item.get("points", 0))
        except (TypeError, ValueError):
            continue

        if points == 0:
            continue

        points = max(-20.0, min(10.0, points))

        adjustment = {
            "type": "reward" if points > 0 else "penalty",
            "points": round(points, 2),
            "reason": str(item.get("reason", "Interview performance")),
            "skill": item.get("skill"),
            "category": item.get("category"),
        }

        normalized.append(adjustment)

        if points > 0:
            reward_total += points
        else:
            penalty_total += points

    adjusted = base + reward_total + penalty_total
    adjusted = max(0.0, min(100.0, adjusted))

    return {
        "rubric_base_score": round(base, 2),
        "reward_total": round(reward_total, 2),
        "penalty_total": round(penalty_total, 2),
        "adjusted_score": round(adjusted, 2),
        "adjustments": normalized,
    }
