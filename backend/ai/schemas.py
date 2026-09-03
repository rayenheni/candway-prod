from typing import Optional

from pydantic import BaseModel, Field


class EvaluationResponse(BaseModel):
    """Validated schema for AI interview evaluation output.

    ``final_score`` is the only required field — if the AI omits it,
    the response is rejected.  All other fields have safe defaults so
    that minor schema drift does not cause a hard failure.
    """

    final_score: float = Field(..., ge=0, le=100)
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    skill_metrics: dict[str, float] = Field(default_factory=dict)
    recommendation: str = Field(default="Error")
    detailed_feedback: str = Field(default="")
    explainability: Optional[dict] = Field(default=None)
    question_scores: list[float] = Field(default_factory=list)
    role_fit_score: float = Field(default=0, ge=0, le=100)
