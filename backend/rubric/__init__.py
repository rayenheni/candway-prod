"""
Candway Deterministic Skill Rubric Engine.

Replaces LLM-based scoring with a structured, rule-based system.
LLM is used ONLY for extracting skills and evidence from answers.
All scoring is deterministic, reproducible, and explainable.
"""

from backend.rubric.rubric_engine import SkillScoreResult, score_answer
from backend.rubric.rubric_schema import (
    CategoryDefinition,
    JobRubric,
    LevelDescriptor,
    SkillDefinition,
    SubcategoryDefinition,
)
from backend.rubric.scoring_aggregator import InterviewScoringSummary, aggregate_scores

__all__ = [
    "JobRubric",
    "CategoryDefinition",
    "SubcategoryDefinition",
    "SkillDefinition",
    "LevelDescriptor",
    "score_answer",
    "SkillScoreResult",
    "aggregate_scores",
    "InterviewScoringSummary",
]
