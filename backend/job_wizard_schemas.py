from typing import Any, List, Optional

from pydantic import BaseModel, Field, model_validator


class Step1BasicInfo(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    category_id: Optional[int] = None
    employment_type: str = "full-time"
    workplace_type: str = "hybrid"
    location: Optional[str] = None
    num_openings: int = 1
    hiring_manager_id: Optional[int] = None
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    salary_currency: str = "USD"
    internal_reference: Optional[str] = None


class RoleOverviewItem(BaseModel):
    question_key: str
    question: str
    answer: Optional[str] = None


class Step2RoleOutcomes(BaseModel):
    items: List[RoleOverviewItem]
    role_summary: Optional[str] = None


class SkillDef(BaseModel):
    skill_name: str = Field(..., max_length=100)
    required_level: str = "intermediate"
    weight: int = Field(..., ge=1, le=100)
    is_mandatory: bool = True
    notes: Optional[str] = None
    sort_order: int = 0


class Step3SkillTree(BaseModel):
    skills: List[SkillDef]
    skill_tree_id: Optional[int] = None

    @model_validator(mode="after")
    def validate_weights_sum(cls, values):
        skills = values.skills
        if skills:
            total = sum(s.weight for s in skills)
            if total != 100:
                raise ValueError(f"Total skill weight must be 100%, got {total}%")
        return values


class EvalCategory(BaseModel):
    name: str
    weight: int = Field(..., ge=1, le=100)
    sort_order: int = 0


class AIConfigData(BaseModel):
    ai_scoring_enabled: bool = True
    minimum_recommended_score: float = 0.0
    auto_shortlist_threshold: Optional[float] = None
    auto_reject_threshold: Optional[float] = None
    explain_ai_decisions: bool = True
    evidence_based_scoring: bool = True
    ignore_missing_cv: bool = False
    prioritize_verified_skills: bool = True
    custom_instructions: Optional[str] = None
    duration_minutes: Optional[int] = None
    total_questions: Optional[int] = None


class Step4EvaluationConfig(BaseModel):
    categories: List[EvalCategory]
    ai_config: Optional[AIConfigData] = None

    @model_validator(mode="after")
    def validate_category_weights(cls, values):
        cats = values.categories
        if cats:
            total = sum(c.weight for c in cats)
            if total != 100:
                raise ValueError(
                    f"Total evaluation category weight must be 100%, got {total}%"
                )
        return values


class ScreeningQuestionDef(BaseModel):
    question: str
    type: str = "text"
    options: Optional[List[str]] = None
    is_required: bool = True
    sort_order: int = 0


class PipelineStageDef(BaseModel):
    name: str
    slug: str
    sort_order: int = 0
    color: Optional[str] = None
    icon: Optional[str] = None


class Step5ScreeningPipeline(BaseModel):
    screening_questions: List[ScreeningQuestionDef] = []
    pipeline_stages: List[PipelineStageDef]


class Step6ReviewPublish(BaseModel):
    publish: bool = True


# Response models
class WizardProgress(BaseModel):
    job_id: int
    current_step: int
    completed_steps: List[int]
    is_published: bool


class SuggestionResult(BaseModel):
    suggestions: List[Any]
    source: str = "ai"
