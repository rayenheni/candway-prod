from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class AnswerEvaluation(BaseModel):
    score: float = Field(default=50.0, ge=0.0, le=100.0)
    feedback: str = ""
    extracted_skills: List[Dict[str, Any]] = Field(default_factory=list)
    skill_metrics: Optional[Dict[str, float]] = None
    current_score: float = Field(default=50.0, ge=0.0, le=100.0)
    answer_quality: str = "adequate"
    cheat_detected: bool = False
    cheat_score: float = 0.0
    details: str = ""
    hint_text: str = ""
    requires_followup: bool = False
    followup_question: Optional[str] = None


class FinalEvaluation(BaseModel):
    final_score: float = Field(default=50.0, ge=0.0, le=100.0)
    skill_metrics: Optional[Dict[str, float]] = None
    strengths: List[str] = Field(default_factory=list)
    weaknesses: List[str] = Field(default_factory=list)
    action_plan: Optional[str] = None
    explainability: Optional[Dict[str, Any]] = None
    detailed_feedback: Optional[str] = None
    recommendation: Optional[str] = None
    score_breakdown: Optional[Dict[str, Any]] = None
    _schema_error: Optional[str] = None


class CVAnalysis(BaseModel):
    overall_score: float = Field(default=50.0, ge=0.0, le=100.0)
    summary: Optional[str] = None
    skills: List[Dict[str, Any]] = Field(default_factory=list)
    experience_timeline: List[Dict[str, Any]] = Field(default_factory=list)
    strengths: List[str] = Field(default_factory=list)
    weaknesses: List[str] = Field(default_factory=list)
    key_insights: List[str] = Field(default_factory=list)
    market_positioning: Optional[str] = None
    education: Optional[List[Dict[str, Any]]] = None
    ai_analysis: Optional[Dict[str, Any]] = None
    explainability: Optional[Dict[str, Any]] = None
    role_confidence: float = Field(default=0.5, ge=0.0, le=1.0)


class CVSkillExtraction(BaseModel):
    technical: List[str] = Field(default_factory=list)
    tools: List[str] = Field(default_factory=list)
    soft: List[str] = Field(default_factory=list)
    skills_with_confidence: List[Dict[str, Any]] = Field(default_factory=list)


class QuestionGeneration(BaseModel):
    question: str = ""
    expected_answer: Optional[str] = None
    hint_text: str = ""
    skills: Optional[List[str]] = None
    difficulty: str = "medium"
    rubric_context: Optional[str] = None


class CareerRoadmap(BaseModel):
    overall_score: float = Field(default=50.0, ge=0.0, le=100.0)
    recommendations: List[str] = Field(default_factory=list)
    milestones: List[Dict[str, Any]] = Field(default_factory=list)
    courses: Optional[List[Dict[str, Any]]] = None
    summary: Optional[str] = None
    timeline_years: Optional[int] = None
