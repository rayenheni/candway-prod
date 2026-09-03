import json
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple, Type

from pydantic import BaseModel, ValidationError

from backend.ai.output_schema import (
    AnswerEvaluation,
    CareerRoadmap,
    CVAnalysis,
    CVSkillExtraction,
    FinalEvaluation,
    QuestionGeneration,
)
from backend.ai_audit import log_ai_call
from backend.logger import logger


class _FallbackSchema(BaseModel):
    model_config = {"extra": "allow"}


VALIDATION_SCHEMA_REGISTRY: Dict[str, Type[BaseModel]] = {
    "answer_evaluation": AnswerEvaluation,
    "final_evaluation": FinalEvaluation,
    "cv_analysis": CVAnalysis,
    "skill_extraction": CVSkillExtraction,
    "question_generation": QuestionGeneration,
    "career_roadmap": CareerRoadmap,
    "fallback": _FallbackSchema,
}


@dataclass
class AIValidationFailure(Exception):
    action: str
    application_id: int
    schema_name: str
    errors: List[str]
    raw_response: Optional[str] = None
    turn_number: Optional[int] = None
    company_id: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action": self.action,
            "application_id": self.application_id,
            "schema_name": self.schema_name,
            "errors": self.errors,
            "raw_response_preview": (self.raw_response or "")[:500],
        }


@dataclass
class AIValidationContext:
    application_id: int
    db: Any
    action: str = "llm_call"
    turn_number: Optional[int] = None
    company_id: Optional[int] = None
    model_version: Optional[str] = None


@dataclass
class ValidationResult:
    valid: bool
    model: Optional[BaseModel] = None
    errors: List[str] = field(default_factory=list)
    raw_response: Optional[str] = None


class AIOutputValidator:
    """Validates AI response dicts against predefined Pydantic schemas.

    Usage:
        validator = AIOutputValidator(context)
        result = validator.validate("answer_evaluation", raw_dict)
        if result is None:
            # validation failed, handle_failure was already called
            safe_result = get_default_safe("answer_evaluation")
    """

    def __init__(self, context: AIValidationContext):
        self.context = context

    def validate(
        self,
        schema_name: str,
        data: Any,
        raise_on_failure: bool = False,
    ) -> Optional[BaseModel]:
        if not isinstance(data, dict):
            self._fail(schema_name, [f"Expected dict, got {type(data).__name__}"])
            if raise_on_failure:
                raise AIValidationFailure(
                    action=self.context.action,
                    application_id=self.context.application_id,
                    schema_name=schema_name,
                    errors=[f"Expected dict, got {type(data).__name__}"],
                    raw_response=str(data),
                    turn_number=self.context.turn_number,
                    company_id=self.context.company_id,
                )
            return None

        schema_cls = VALIDATION_SCHEMA_REGISTRY.get(schema_name)
        if schema_cls is None:
            logger.warning(
                f"[VALIDATION] Unknown schema '{schema_name}', rejecting validation"
            )
            self._fail(schema_name, [f"Unknown schema '{schema_name}'"])
            return None

        try:
            return schema_cls(**data)
        except ValidationError as e:
            errors = [
                f"{'.'.join(map(str, err['loc']))}: {err['msg']}" for err in e.errors()
            ]
            logger.warning(
                f"[VALIDATION] Schema '{schema_name}' validation failed for "
                f"app {self.context.application_id}: {'; '.join(errors)}"
            )
            self._fail(schema_name, errors)
            if raise_on_failure:
                raise AIValidationFailure(
                    action=self.context.action,
                    application_id=self.context.application_id,
                    schema_name=schema_name,
                    errors=errors,
                    raw_response=json.dumps(data),
                    turn_number=self.context.turn_number,
                    company_id=self.context.company_id,
                )
            return None

    def _fail(self, schema_name: str, errors: List[str]) -> None:
        try:
            error_msg = "; ".join(errors)
            _mark_needs_review(
                db=self.context.db,
                application_id=self.context.application_id,
                reason=f"[{schema_name}] {error_msg}",
            )
            log_ai_call(
                application_id=self.context.application_id,
                company_id=self.context.company_id,
                turn_number=self.context.turn_number,
                action=f"validation_failure:{schema_name}",
                model_version=self.context.model_version,
                response_content=error_msg,
                success=False,
                error_message=error_msg,
            )
            logger.warning(
                f"[VALIDATION] App {self.context.application_id}: "
                f"marked needs_review due to failed '{schema_name}' validation: {error_msg}"
            )
        except Exception as e:
            logger.error(f"[VALIDATION] Error handling validation failure: {e}")


def _mark_needs_review(
    db: Any,
    application_id: int,
    reason: str,
) -> None:
    from backend.database import Application, EvaluationResult, EvaluationSession

    evaluation_session = (
        db.query(EvaluationSession)
        .filter(EvaluationSession.application_id == application_id)
        .first()
    )

    if evaluation_session is None:
        application = (
            db.query(Application)
            .filter(Application.id == application_id)
            .first()
        )

        evaluation_session = EvaluationSession(
            application_id=application_id,
            company_id=application.company_id if application else None,
            rubric_id=application.rubric_id if application else None,
            status="needs_review",
        )
        db.add(evaluation_session)
        db.flush()

    evaluation_result = (
        db.query(EvaluationResult)
        .filter(
            EvaluationResult.evaluation_session_id
            == evaluation_session.id
        )
        .first()
    )

    if evaluation_result is None:
        # No score exists yet: create a review-state result.
        evaluation_result = EvaluationResult(
            evaluation_session_id=evaluation_session.id,
            company_id=evaluation_session.company_id,
            rubric_id=evaluation_session.rubric_id,
            scoring_status="NEEDS_REVIEW",
            final_score=None,
            scoring_model="rubric",
        )
        db.add(evaluation_result)
    else:
        # Review flag is orthogonal to scoring state.
        # NEVER destroy or invalidate an existing canonical score.
        #
        # SCORED + final_score is valid even when needs_review=True.
        pass

    evaluation_result.needs_review = True
    evaluation_result.needs_review_reason = reason[:500]

    db.flush()


def validate_ai_response(
    context: AIValidationContext,
    schema_name: str,
    data: Any,
) -> Optional[BaseModel]:
    """Convenience wrapper around AIOutputValidator."""
    return AIOutputValidator(context).validate(schema_name, data)


def validate_ai_response_strict(
    content: Any,
    schema_name: str,
    max_content_chars: int = 100000,
) -> Tuple[Optional[BaseModel], Optional[str]]:
    """Parse and validate LLM response content against the requested schema.
    Handles str or dict input, JSON parsing, regex extraction, and size limits.
    Returns (parsed_model, error) — never raises.
    """
    data: Any = None

    if isinstance(content, dict):
        data = content
    elif isinstance(content, str):
        if len(content) > max_content_chars:
            return None, f"Response content exceeds {max_content_chars} character limit"
        try:
            data = json.loads(content)
        except (json.JSONDecodeError, ValueError):
            match = re.search(r"(\{.*\})", content[:10000], re.DOTALL)
            if match:
                try:
                    data = json.loads(match.group())
                except (json.JSONDecodeError, ValueError):
                    return None, "Could not parse extracted JSON content"
            else:
                return None, "Could not extract JSON from response"
    else:
        return None, f"Expected str or dict, got {type(content).__name__}"

    schema_cls = VALIDATION_SCHEMA_REGISTRY.get(schema_name)
    if schema_cls is None:
        return None, f"Unknown schema '{schema_name}'"

    try:
        model = schema_cls(**data)
        return model, None
    except ValidationError as e:
        errors = [
            f"{'.'.join(map(str, err['loc']))}: {err['msg']}" for err in e.errors()
        ]
        return None, "; ".join(errors)


def extract_and_validate_json(
    content: str,
    schema_name: str,
    max_content_chars: int = 50000,
) -> ValidationResult:
    """Extract JSON from LLM response text and validate against schema.
    Handles markdown-wrapped JSON, partial JSON, etc.
    """
    if len(content) > max_content_chars:
        return ValidationResult(
            valid=False,
            errors=[f"Response content exceeds {max_content_chars} character limit"],
            raw_response=content[:500],
        )

    data: Any = None
    try:
        data = json.loads(content)
    except (json.JSONDecodeError, ValueError):
        match = re.search(r"(\{.*\})", content[:10000], re.DOTALL)
        if match:
            try:
                data = json.loads(match.group())
            except (json.JSONDecodeError, ValueError):
                return ValidationResult(
                    valid=False,
                    errors=["Could not parse extracted JSON content"],
                    raw_response=content[:500],
                )
        else:
            return ValidationResult(
                valid=False,
                errors=["No JSON object found in response"],
                raw_response=content[:500],
            )

    schema_cls = VALIDATION_SCHEMA_REGISTRY.get(schema_name)
    if schema_cls is None:
        return ValidationResult(
            valid=False,
            errors=[f"Unknown schema '{schema_name}'"],
            raw_response=content[:500],
        )

    try:
        model = schema_cls(**data)
        return ValidationResult(valid=True, model=model, raw_response=content[:500])
    except ValidationError as e:
        errors = [
            f"{'.'.join(map(str, err['loc']))}: {err['msg']}" for err in e.errors()
        ]
        return ValidationResult(
            valid=False,
            errors=errors,
            raw_response=content[:500],
        )


def get_default_safe(schema_name: str) -> Dict[str, Any]:
    """Return a safe fallback dict for the given schema."""
    schema_cls = VALIDATION_SCHEMA_REGISTRY.get(schema_name)
    if schema_cls is None:
        return {}
    return schema_cls().model_dump()
