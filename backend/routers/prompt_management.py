"""
Prompt Management & Statistics Module

Provides comprehensive tools for managing, testing, and analyzing prompt performance.
Separate from settings to avoid clutter and provide focused functionality.
"""

import json
import logging
from datetime import UTC, datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy import case, desc, func, text
from sqlalchemy.orm import Session

from backend.ai.cv_analysis import analyze_cv
from backend.ai.prompts import (
    PROMPT_VERSIONS,
)
from backend.database import (
    AuditLog,
    DBTestResult,
    PromptTest,
    PromptVariant,
    User,
)
from backend.dependencies import get_current_user, get_db
from backend.profile_helpers import get_user_email
from backend.routers.admin.common import check_permission

router = APIRouter(prefix="/admin/prompts", tags=["prompt-management"])

logger = logging.getLogger(__name__)

# ============================================================================
# DATABASE MODELS FOR PROMPT MANAGEMENT
# ============================================================================

# Note: These models should be added to backend/database.py
# I'm including them here for reference:

"""
class PromptTest(Base):
    __tablename__ = "prompt_tests"

    id = Column(Integer, primary_key=True, index=True)
    prompt_type = Column(String(100), index=True)
    version = Column(String(20))
    variant = Column(String(20))
    test_name = Column(String(255))
    description = Column(Text)
    prompt_content = Column(Text)
    expected_output = Column(Text)

    # Test configuration
    test_cases_count = Column(Integer, default=0)

    # Results
    total_runs = Column(Integer, default=0)
    successful_runs = Column(Integer, default=0)
    avg_latency_ms = Column(Float, default=0)
    avg_score = Column(Float, default=0)

    # Metadata
    created_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)
    is_active = Column(Boolean, default=True)

    creator = relationship("User")

class PromptVariant(Base):
    __tablename__ = "prompt_variants"

    id = Column(Integer, primary_key=True, index=True)
    prompt_type = Column(String(100), index=True)
    version = Column(String(20))
    variant_name = Column(String(100))
    content = Column(Text)
    description = Column(Text)

    # Performance metrics
    times_used = Column(Integer, default=0)
    success_rate = Column(Float, default=0)
    avg_latency = Column(Float, default=0)

    # Configuration
    is_enabled = Column(Boolean, default=True)
    traffic_percentage = Column(Float, default=0)  # For A/B testing

    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

class DBTestResult(Base):
    __tablename__ = "prompt_test_results"

    id = Column(Integer, primary_key=True, index=True)
    test_id = Column(Integer, ForeignKey("prompt_tests.id"))
    variant_id = Column(Integer, ForeignKey("prompt_variants.id"), nullable=True)

    # Test execution
    status = Column(String(50))  # success, failure, error
    response_time_ms = Column(Float)

    # Output quality metrics
    output_score = Column(Float, nullable=True)
    quality_metrics = Column(Text)  # JSON

    # Actual vs expected
    actual_output = Column(Text)
    similarity_score = Column(Float, nullable=True)

    # Metadata
    executed_at = Column(DateTime, default=utcnow)

    test = relationship("PromptTest")
    variant = relationship("PromptVariant")
"""

# ============================================================================
# PROMPT CATALOG & VERSIONS
# ============================================================================


@router.get("/catalog", summary="Get all available prompts and versions")
def get_prompt_catalog(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """
    Get comprehensive catalog of all prompts, their versions, and variants.
    Includes performance statistics and configuration options.
    """
    check_permission(current_user, "manage_ai")

    catalog = []

    for prompt_type, info in PROMPT_VERSIONS.items():
        # Get variants from database if they exist
        variants = (
            db.query(PromptVariant)
            .filter(
                PromptVariant.prompt_type == prompt_type,
                PromptVariant.is_enabled,
            )
            .all()
        )

        # Get recent test results
        recent_tests = (
            db.query(PromptTest)
            .filter(PromptTest.prompt_type == prompt_type, PromptTest.is_active)
            .order_by(desc(PromptTest.updated_at))
            .limit(5)
            .all()
        )

        catalog.append(
            {
                "type": prompt_type,
                "current_version": info["current"],
                "versions": info["versions"],
                "variants": [
                    {
                        "name": v.variant_name,
                        "version": v.version,
                        "description": v.description,
                        "traffic_percentage": v.traffic_percentage,
                        "times_used": v.times_used,
                        "success_rate": v.success_rate,
                        "avg_latency": v.avg_latency,
                        "is_enabled": v.is_enabled,
                    }
                    for v in variants
                ],
                "recent_tests": [
                    {
                        "id": t.id,
                        "test_name": t.test_name,
                        "version": t.version,
                        "variant": t.variant,
                        "total_runs": t.total_runs,
                        "success_rate": (t.successful_runs / t.total_runs * 100)
                        if t.total_runs > 0
                        else 0,
                        "avg_latency": t.avg_latency_ms,
                        "avg_score": t.avg_score,
                        "updated_at": t.updated_at.isoformat(),
                    }
                    for t in recent_tests
                ],
            }
        )

    return {
        "catalog": catalog,
        "total_prompt_types": len(catalog),
        "total_variants": sum(len(c["variants"]) for c in catalog),
        "last_updated": datetime.now(UTC).isoformat(),
    }


@router.get("/versions/{prompt_type}", summary="Get all versions of a specific prompt")
def get_prompt_versions(
    prompt_type: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get all versions and variants for a specific prompt type.
    """
    check_permission(current_user, "manage_ai")

    if prompt_type not in PROMPT_VERSIONS:
        raise HTTPException(status_code=404, detail="Prompt type not found")

    info = PROMPT_VERSIONS[prompt_type]

    # Get all variants from database
    variants = (
        db.query(PromptVariant)
        .filter(PromptVariant.prompt_type == prompt_type)
        .order_by(desc(PromptVariant.updated_at))
        .all()
    )

    # Get test results grouped by version
    test_results = (
        db.query(
            PromptTest.version,
            PromptTest.variant,
            func.count(PromptTest.id).label("total_tests"),
            func.avg(PromptTest.avg_latency_ms).label("avg_latency"),
            func.avg(PromptTest.avg_score).label("avg_score"),
        )
        .filter(PromptTest.prompt_type == prompt_type, PromptTest.is_active)
        .group_by(PromptTest.version, PromptTest.variant)
        .all()
    )

    return {
        "prompt_type": prompt_type,
        "current_version": info["current"],
        "versions": info["versions"],
        "variants": [
            {
                "id": v.id,
                "variant_name": v.variant_name,
                "version": v.version,
                "description": v.description,
                "content_preview": v.content[:200] + "..."
                if len(v.content) > 200
                else v.content,
                "traffic_percentage": v.traffic_percentage,
                "times_used": v.times_used,
                "success_rate": v.success_rate,
                "avg_latency": v.avg_latency,
                "is_enabled": v.is_enabled,
                "created_at": v.created_at.isoformat(),
                "updated_at": v.updated_at.isoformat(),
            }
            for v in variants
        ],
        "test_results": [
            {
                "version": r.version,
                "variant": r.variant,
                "total_tests": r.total_tests,
                "avg_latency": float(r.avg_latency) if r.avg_latency else 0,
                "avg_score": float(r.avg_score) if r.avg_score else 0,
            }
            for r in test_results
        ],
    }


# ============================================================================
# PROMPT TESTING & COMPARISON
# ============================================================================


@router.post("/test", summary="Create a new prompt test")
async def create_prompt_test(
    test_data: Dict[str, Any],
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Create a new prompt test to compare different versions/variants.
    """
    check_permission(current_user, "manage_ai")

    prompt_type = test_data.get("prompt_type")
    versions_to_test = test_data.get("versions", [])
    test_name = test_data.get("test_name", f"Test {datetime.now(UTC).isoformat()}")
    description = test_data.get("description", "")
    test_cases = test_data.get("test_cases", [])

    if not prompt_type or not versions_to_test:
        raise HTTPException(
            status_code=400, detail="prompt_type and versions are required"
        )

    # Create test record
    test = PromptTest(
        prompt_type=prompt_type,
        test_name=test_name,
        description=description,
        test_cases_count=len(test_cases),
        created_by=current_user.id,
        is_active=True,
    )
    db.add(test)
    db.commit()
    db.refresh(test)

    # Queue test execution in background
    background_tasks.add_task(
        execute_prompt_test,
        test_id=test.id,
        versions=versions_to_test,
        test_cases=test_cases,
        db=db,
    )

    return {
        "test_id": test.id,
        "status": "queued",
        "message": "Test created and queued for execution",
    }


async def execute_prompt_test(
    test_id: int, versions: List[str], test_cases: List[Dict], db: Session
):
    """
    Execute a prompt test across multiple versions/variants.
    """
    test = db.query(PromptTest).filter(PromptTest.id == test_id).first()
    if not test:
        return

    results = []

    for version_info in versions:
        version = version_info.get("version")
        variant = version_info.get("variant", "control")

        for test_case in test_cases:
            try:
                start_time = datetime.now(UTC)

                # Execute test based on prompt type
                if test.prompt_type == "cv_analysis":
                    result = await execute_cv_analysis_test(test_case, version, variant)
                elif test.prompt_type == "calibration_questions":
                    result = await execute_calibration_test(test_case, version, variant)
                else:
                    result = await execute_generic_test(
                        test.prompt_type, test_case, version, variant
                    )

                execution_time = (datetime.now(UTC) - start_time).total_seconds() * 1000

                # Calculate quality metrics
                quality_score = calculate_quality_score(
                    result, test_case.get("expected_output")
                )

                test_result = DBTestResult(
                    test_id=test_id,
                    status="success",
                    response_time_ms=execution_time,
                    output_score=quality_score,
                    actual_output=json.dumps(result),
                    similarity_score=calculate_similarity(
                        result, test_case.get("expected_output")
                    ),
                )
                results.append(test_result)

            except Exception as e:
                test_result = DBTestResult(
                    test_id=test_id,
                    status="error",
                    response_time_ms=0,
                    actual_output=str(e),
                )
                results.append(test_result)

    # Save results
    db.add_all(results)

    # Update test summary
    successful = sum(1 for r in results if r.status == "success")
    test.total_runs = len(results)
    test.successful_runs = successful
    test.avg_latency_ms = (
        sum(r.response_time_ms for r in results) / len(results) if results else 0
    )
    test.avg_score = (
        sum(r.output_score for r in results if r.output_score)
        / len([r for r in results if r.output_score])
        if any(r.output_score for r in results)
        else 0
    )

    db.commit()

    logger.info(
        f"Prompt test {test_id} completed: {successful}/{len(results)} successful"
    )


async def execute_cv_analysis_test(test_case: Dict, version: str, variant: str) -> Dict:
    """Execute a CV analysis test case."""
    # Mock CV text for testing
    cv_text = test_case.get("cv_text", "Sample CV content for testing purposes.")
    declared_role = test_case.get("declared_role", "Software Engineer")

    # Execute analysis
    result = await analyze_cv(cv_text, declared_role)
    return result


async def execute_calibration_test(test_case: Dict, version: str, variant: str) -> Dict:
    """Execute a calibration questions test case."""
    from backend.ai.prompts import get_calibration_questions_prompt

    role = test_case.get("role", "Software Engineer")
    skills = test_case.get("skills", [])
    level = test_case.get("level", "Mid")
    cv_context = test_case.get("cv_context", "")
    intelligence = test_case.get("intelligence_layer", {})

    prompt, prompt_info = get_calibration_questions_prompt(
        role=role,
        skills=skills,
        level=level,
        cv_context=cv_context,
        intelligence_layer=intelligence,
        user_id="test_user",
    )

    return {
        "prompt": prompt[:500] + "...",
        "prompt_info": prompt_info,
        "test_case": test_case,
    }


async def execute_generic_test(
    prompt_type: str, test_case: Dict, version: str, variant: str
) -> Dict:
    """Execute a generic prompt test."""
    return {
        "prompt_type": prompt_type,
        "version": version,
        "variant": variant,
        "test_case": test_case,
        "executed_at": datetime.now(UTC).isoformat(),
    }


def calculate_quality_score(actual: Dict, expected: Dict) -> float:
    """Calculate quality score based on expected vs actual output."""
    if not expected:
        return 50.0  # Neutral score if no expected output

    # Simple scoring based on key field presence
    expected_keys = set(expected.keys()) if isinstance(expected, dict) else set()
    actual_keys = set(actual.keys()) if isinstance(actual, dict) else set()

    if not expected_keys:
        return 50.0

    matching_keys = expected_keys.intersection(actual_keys)
    return (len(matching_keys) / len(expected_keys)) * 100


def calculate_similarity(actual: Dict, expected: Dict) -> float:
    """Calculate similarity between actual and expected outputs."""
    if not expected or not actual:
        return 0.0

    # Simple text similarity for demonstration
    actual_str = json.dumps(actual, sort_keys=True)
    expected_str = json.dumps(expected, sort_keys=True)

    # Levenshtein distance approximation
    if actual_str == expected_str:
        return 100.0

    # Rough similarity calculation
    max_len = max(len(actual_str), len(expected_str))
    if max_len == 0:
        return 100.0

    # Count matching characters (simplified)
    matches = sum(1 for a, e in zip(actual_str, expected_str) if a == e)
    return (matches / max_len) * 100


@router.get("/tests", summary="Get all prompt tests")
def get_prompt_tests(
    prompt_type: Optional[str] = None,
    version: Optional[str] = None,
    is_active: bool = True,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get prompt tests with optional filtering.
    """
    check_permission(current_user, "manage_ai")

    query = db.query(PromptTest).filter(PromptTest.is_active == is_active)

    if prompt_type:
        query = query.filter(PromptTest.prompt_type == prompt_type)
    if version:
        query = query.filter(PromptTest.version == version)

    tests = query.order_by(desc(PromptTest.updated_at)).all()

    return {
        "tests": [
            {
                "id": t.id,
                "prompt_type": t.prompt_type,
                "test_name": t.test_name,
                "description": t.description,
                "version": t.version,
                "variant": t.variant,
                "test_cases_count": t.test_cases_count,
                "total_runs": t.total_runs,
                "successful_runs": t.successful_runs,
                "success_rate": (t.successful_runs / t.total_runs * 100)
                if t.total_runs > 0
                else 0,
                "avg_latency_ms": t.avg_latency_ms,
                "avg_score": t.avg_score,
                "created_at": t.created_at.isoformat(),
                "updated_at": t.updated_at.isoformat(),
                "is_active": t.is_active,
            }
            for t in tests
        ],
        "total": len(tests),
    }


@router.get("/tests/{test_id}", summary="Get detailed test results")
def get_test_details(
    test_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get detailed results for a specific test.
    """
    check_permission(current_user, "manage_ai")

    test = db.query(PromptTest).filter(PromptTest.id == test_id).first()
    if not test:
        raise HTTPException(status_code=404, detail="Test not found")

    results = db.query(DBTestResult).filter(DBTestResult.test_id == test_id).all()

    # Group by version/variant
    grouped = {}
    for r in results:
        key = f"{r.version}_{r.variant}"
        if key not in grouped:
            grouped[key] = {
                "version": r.version,
                "variant": r.variant,
                "total_runs": 0,
                "successful_runs": 0,
                "failed_runs": 0,
                "avg_latency_ms": 0,
                "avg_score": 0,
                "avg_similarity": 0,
            }

        grouped[key]["total_runs"] += 1
        if r.status == "success":
            grouped[key]["successful_runs"] += 1
        else:
            grouped[key]["failed_runs"] += 1

        if r.response_time_ms:
            grouped[key]["avg_latency_ms"] += r.response_time_ms
        if r.output_score:
            grouped[key]["avg_score"] += r.output_score
        if r.similarity_score:
            grouped[key]["avg_similarity"] += r.similarity_score

    # Calculate averages
    for key in grouped:
        total = grouped[key]["total_runs"]
        if total > 0:
            grouped[key]["avg_latency_ms"] /= total
            grouped[key]["avg_score"] /= total
            grouped[key]["avg_similarity"] /= total

    return {
        "test": {
            "id": test.id,
            "prompt_type": test.prompt_type,
            "test_name": test.test_name,
            "description": test.description,
            "test_cases_count": test.test_cases_count,
            "created_at": test.created_at.isoformat(),
            "updated_at": test.updated_at.isoformat(),
        },
        "results_summary": list(grouped.values()),
        "total_results": len(results),
        "best_performer": max(grouped.values(), key=lambda x: x["avg_score"])
        if grouped
        else None,
        "results": [
            {
                "id": r.id,
                "version": r.version,
                "variant": r.variant,
                "actual_output": r.actual_output,
                "response_time_ms": r.response_time_ms,
                "output_score": r.output_score,
                "similarity_score": r.similarity_score,
                "status": r.status,
                "executed_at": r.executed_at.isoformat(),
            }
            for r in results
        ],
    }


@router.patch(
    "/results/{result_id}/score", summary="Set manual score for a test result"
)
def set_result_score(
    result_id: int,
    score_data: Dict[str, Any],
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Set a manual quality score for a specific AI output."""
    check_permission(current_user, "manage_ai")

    result = db.query(DBTestResult).filter(DBTestResult.id == result_id).first()
    if not result:
        raise HTTPException(status_code=404, detail="Result not found")

    score = score_data.get("score")
    if score is None or not (0 <= score <= 100):
        raise HTTPException(status_code=400, detail="Invalid score (must be 0-100)")

    result.output_score = float(score)
    result.status = (
        "success" if score >= 50 else "failed"
    )  # Update status based on score
    db.commit()

    # Update the parent test's average score (async would be better but this is simple)
    test = db.query(PromptTest).filter(PromptTest.id == result.test_id).first()
    if test:
        all_results = (
            db.query(DBTestResult).filter(DBTestResult.test_id == test.id).all()
        )
        valid_scores = [
            r.output_score for r in all_results if r.output_score is not None
        ]
        if valid_scores:
            test.avg_score = sum(valid_scores) / len(valid_scores)
            test.successful_runs = sum(1 for r in all_results if r.status == "success")
            db.commit()

    return {"message": "Score updated", "new_score": result.output_score}


# ============================================================================
# PROMPT VARIANT MANAGEMENT
# ============================================================================


@router.post("/variants", summary="Create or update a prompt variant")
def create_prompt_variant(
    variant_data: Dict[str, Any],
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Create or update a prompt variant for A/B testing.
    """
    check_permission(current_user, "manage_ai")

    prompt_type = variant_data.get("prompt_type")
    version = variant_data.get("version")
    variant_name = variant_data.get("variant_name")
    content = variant_data.get("content")

    if not all([prompt_type, version, variant_name, content]):
        raise HTTPException(status_code=400, detail="Missing required fields")

    # Check if variant exists
    existing = (
        db.query(PromptVariant)
        .filter(
            PromptVariant.prompt_type == prompt_type,
            PromptVariant.version == version,
            PromptVariant.variant_name == variant_name,
        )
        .first()
    )

    if existing:
        # Update existing
        existing.content = content
        existing.description = variant_data.get("description", existing.description)
        existing.traffic_percentage = variant_data.get(
            "traffic_percentage", existing.traffic_percentage
        )
        existing.is_enabled = variant_data.get("is_enabled", existing.is_enabled)
        existing.updated_at = datetime.now(UTC)
        variant = existing
        message = "Variant updated"
    else:
        # Create new
        variant = PromptVariant(
            prompt_type=prompt_type,
            version=version,
            variant_name=variant_name,
            content=content,
            description=variant_data.get("description", ""),
            traffic_percentage=variant_data.get("traffic_percentage", 0),
            is_enabled=variant_data.get("is_enabled", True),
        )
        db.add(variant)
        message = "Variant created"

    db.commit()
    db.refresh(variant)

    # Audit log
    audit = AuditLog(
        user_id=current_user.id,
        action="variant_update",
        details=f"User {get_user_email(current_user)} {message}: {prompt_type} v{version} ({variant_name})",
        ip_address="system",
    )
    db.add(audit)
    db.commit()

    return {
        "message": message,
        "variant": {
            "id": variant.id,
            "prompt_type": variant.prompt_type,
            "version": variant.version,
            "variant_name": variant.variant_name,
            "description": variant.description,
            "traffic_percentage": variant.traffic_percentage,
            "is_enabled": variant.is_enabled,
            "created_at": variant.created_at.isoformat(),
            "updated_at": variant.updated_at.isoformat(),
        },
    }


@router.get("/variants", summary="Get all prompt variants")
def get_prompt_variants(
    prompt_type: Optional[str] = None,
    is_enabled: Optional[bool] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get all prompt variants with filtering options.
    """
    check_permission(current_user, "manage_ai")

    query = db.query(PromptVariant)

    if prompt_type:
        query = query.filter(PromptVariant.prompt_type == prompt_type)
    if is_enabled is not None:
        query = query.filter(PromptVariant.is_enabled == is_enabled)

    variants = query.order_by(desc(PromptVariant.updated_at)).all()

    return {
        "variants": [
            {
                "id": v.id,
                "prompt_type": v.prompt_type,
                "version": v.version,
                "variant_name": v.variant_name,
                "description": v.description,
                "content_preview": v.content[:200] + "..."
                if len(v.content) > 200
                else v.content,
                "traffic_percentage": v.traffic_percentage,
                "times_used": v.times_used,
                "success_rate": v.success_rate,
                "avg_latency": v.avg_latency,
                "is_enabled": v.is_enabled,
                "created_at": v.created_at.isoformat(),
                "updated_at": v.updated_at.isoformat(),
            }
            for v in variants
        ],
        "total": len(variants),
    }


# ============================================================================
# DELETE & PATCH ENDPOINTS (missing — JS calls these)
# ============================================================================


@router.delete("/tests/{test_id}", summary="Delete a prompt test")
def delete_prompt_test(
    test_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    check_permission(current_user, "manage_ai")
    test = db.query(PromptTest).filter(PromptTest.id == test_id).first()
    if not test:
        raise HTTPException(status_code=404, detail="Test not found")
    db.delete(test)
    db.commit()
    return {"success": True, "message": f"Test {test_id} deleted"}


@router.delete("/variants/{variant_id}", summary="Delete a prompt variant")
def delete_prompt_variant(
    variant_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    check_permission(current_user, "manage_ai")
    v = db.query(PromptVariant).filter(PromptVariant.id == variant_id).first()
    if not v:
        raise HTTPException(status_code=404, detail="Variant not found")
    db.delete(v)
    db.commit()
    return {"success": True, "message": f"Variant {variant_id} deleted"}


@router.patch(
    "/variants/{variant_id}", summary="Patch a prompt variant (enable/disable)"
)
def patch_prompt_variant(
    variant_id: int,
    patch_data: Dict[str, Any],
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    check_permission(current_user, "manage_ai")
    v = db.query(PromptVariant).filter(PromptVariant.id == variant_id).first()
    if not v:
        raise HTTPException(status_code=404, detail="Variant not found")
    if "is_enabled" in patch_data:
        v.is_enabled = bool(patch_data["is_enabled"])
    if "traffic_percentage" in patch_data:
        v.traffic_percentage = float(patch_data["traffic_percentage"])
    db.commit()
    return {"success": True, "variant_id": variant_id, "is_enabled": v.is_enabled}


# ============================================================================
# STATISTICS & ANALYTICS
# ============================================================================


@router.get("/statistics", summary="Get comprehensive prompt statistics")
def get_prompt_statistics(
    days: int = Query(7, ge=1, le=365),
    prompt_type: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get comprehensive statistics for prompt performance.
    """
    check_permission(current_user, "manage_ai")

    cutoff_date = datetime.now(UTC) - timedelta(days=days)

    # Base query
    query = db.query(DBTestResult).filter(DBTestResult.executed_at >= cutoff_date)

    if prompt_type:
        query = query.join(PromptTest).filter(PromptTest.prompt_type == prompt_type)

    results = query.all()

    # Calculate statistics
    total_runs = len(results)
    successful_runs = sum(1 for r in results if r.status == "success")
    failed_runs = total_runs - successful_runs

    avg_latency = (
        sum(r.response_time_ms for r in results if r.response_time_ms) / total_runs
        if total_runs > 0
        else 0
    )
    avg_score = (
        sum(r.output_score for r in results if r.output_score)
        / len([r for r in results if r.output_score])
        if any(r.output_score for r in results)
        else 0
    )
    avg_similarity = (
        sum(r.similarity_score for r in results if r.similarity_score)
        / len([r for r in results if r.similarity_score])
        if any(r.similarity_score for r in results)
        else 0
    )

    # Group by prompt type
    type_stats = {}
    for r in results:
        if r.test and r.test.prompt_type:
            pt = r.test.prompt_type
            if pt not in type_stats:
                type_stats[pt] = {
                    "total_runs": 0,
                    "successful_runs": 0,
                    "avg_latency": 0,
                    "avg_score": 0,
                }
            type_stats[pt]["total_runs"] += 1
            if r.status == "success":
                type_stats[pt]["successful_runs"] += 1
            if r.response_time_ms:
                type_stats[pt]["avg_latency"] += r.response_time_ms
            if r.output_score:
                type_stats[pt]["avg_score"] += r.output_score

    # Calculate averages per type
    for pt in type_stats:
        total = type_stats[pt]["total_runs"]
        if total > 0:
            type_stats[pt]["avg_latency"] /= total
            type_stats[pt]["avg_score"] /= total
            type_stats[pt]["success_rate"] = (
                type_stats[pt]["successful_runs"] / total
            ) * 100

    # Daily trend — use TEXT aggregate to avoid MySQL func.date() type issues
    try:
        daily = (
            db.query(
                func.date(DBTestResult.executed_at).label("date"),
                func.count(DBTestResult.id).label("total"),
                func.sum(case((DBTestResult.status == "success", 1), else_=0)).label(
                    "successful"
                ),
            )
            .filter(DBTestResult.executed_at >= cutoff_date)
            .group_by(func.date(DBTestResult.executed_at))
            .order_by(func.date(DBTestResult.executed_at))
            .all()
        )
    except Exception as e:
        logger.warning(f"[PM] Daily trend query failed: {e}")
        daily = []

    return {
        "period_days": days,
        "cutoff_date": cutoff_date.isoformat(),
        "total_runs": total_runs,
        "successful_runs": successful_runs,
        "failed_runs": failed_runs,
        "success_rate": (successful_runs / total_runs * 100) if total_runs > 0 else 0,
        "avg_latency_ms": avg_latency,
        "avg_score": avg_score,
        "avg_similarity": avg_similarity,
        "by_prompt_type": type_stats,
        "daily_trend": [
            {
                "date": str(d.date),  # MySQL func.date() returns str, not date obj
                "total": d.total,
                "successful": d.successful or 0,
                "success_rate": ((d.successful or 0) / d.total * 100)
                if d.total > 0
                else 0,
            }
            for d in daily
        ],
    }


@router.get("/performance", summary="Get prompt performance comparison")
def get_performance_comparison(
    prompt_type: str,
    metric: str = Query("success_rate", enum=["success_rate", "latency", "score"]),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Compare performance across different prompt versions and variants.
    """
    check_permission(current_user, "manage_ai")

    # Get test results grouped by version and variant
    results = (
        db.query(
            PromptTest.version,
            PromptTest.variant,
            func.count(PromptTest.id).label("total_tests"),
            func.sum(case([(PromptTest.successful_runs > 0, 1)], else_=0)).label(
                "successful_tests"
            ),
            func.avg(PromptTest.avg_latency_ms).label("avg_latency"),
            func.avg(PromptTest.avg_score).label("avg_score"),
        )
        .filter(PromptTest.prompt_type == prompt_type, PromptTest.is_active)
        .group_by(PromptTest.version, PromptTest.variant)
        .all()
    )

    # Sort by metric
    comparison = []
    for r in results:
        item = {
            "version": r.version,
            "variant": r.variant,
            "total_tests": r.total_tests,
            "success_rate": (r.successful_tests / r.total_tests * 100)
            if r.total_tests > 0
            else 0,
            "avg_latency": float(r.avg_latency) if r.avg_latency else 0,
            "avg_score": float(r.avg_score) if r.avg_score else 0,
        }
        comparison.append(item)

    # Sort by selected metric
    reverse = metric in ["success_rate", "score"]  # Higher is better
    comparison.sort(key=lambda x: x[metric], reverse=reverse)

    return {
        "prompt_type": prompt_type,
        "metric": metric,
        "comparison": comparison,
        "best": comparison[0] if comparison else None,
        "worst": comparison[-1] if comparison else None,
    }


@router.post("/recommendations", summary="Get prompt recommendations")
def get_prompt_recommendations(
    recommendation_data: Dict[str, Any],
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get AI-powered recommendations for prompt optimization.
    """
    check_permission(current_user, "manage_ai")

    prompt_type = recommendation_data.get("prompt_type")
    use_case = recommendation_data.get("use_case")
    performance_threshold = recommendation_data.get("performance_threshold", 90)

    # Get historical performance
    stats = (
        db.query(
            PromptTest.version,
            PromptTest.variant,
            func.avg(PromptTest.avg_score).label("avg_score"),
            func.avg(PromptTest.avg_latency_ms).label("avg_latency"),
            func.count(PromptTest.id).label("test_count"),
        )
        .filter(PromptTest.prompt_type == prompt_type, PromptTest.is_active)
        .group_by(PromptTest.version, PromptTest.variant)
        .all()
    )

    recommendations = []

    for s in stats:
        if s.test_count < 5:
            recommendation = "Insufficient test data - run more tests"
            confidence = "low"
        elif float(s.avg_score or 0) >= performance_threshold:
            recommendation = "Recommended for production use"
            confidence = "high"
        elif float(s.avg_score or 0) >= performance_threshold * 0.8:
            recommendation = "Acceptable with monitoring"
            confidence = "medium"
        else:
            recommendation = "Needs improvement - consider optimization"
            confidence = "low"

        recommendations.append(
            {
                "version": s.version,
                "variant": s.variant,
                "avg_score": float(s.avg_score or 0),
                "avg_latency": float(s.avg_latency or 0),
                "test_count": s.test_count,
                "recommendation": recommendation,
                "confidence": confidence,
            }
        )

    # Sort by score
    recommendations.sort(key=lambda x: x["avg_score"], reverse=True)

    return {
        "prompt_type": prompt_type,
        "use_case": use_case,
        "performance_threshold": performance_threshold,
        "recommendations": recommendations,
        "best_option": recommendations[0] if recommendations else None,
    }


# ============================================================================
# REAL-TIME MONITORING
# ============================================================================


@router.get("/monitoring/live", summary="Get real-time prompt monitoring data")
def get_live_monitoring(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """
    Get real-time monitoring data for prompt execution.
    """
    check_permission(current_user, "manage_ai")

    # Get recent executions (last hour)
    cutoff = datetime.now(UTC) - timedelta(hours=1)
    recent = (
        db.query(DBTestResult)
        .filter(DBTestResult.executed_at >= cutoff)
        .order_by(desc(DBTestResult.executed_at))
        .limit(100)
        .all()
    )

    # Calculate current status
    total_recent = len(recent)
    successful_recent = sum(1 for r in recent if r.status == "success")

    # Get system health
    audit_count = db.query(AuditLog).filter(AuditLog.timestamp >= cutoff).count()

    return {
        "timestamp": datetime.now(UTC).isoformat(),
        "recent_executions": {
            "total": total_recent,
            "successful": successful_recent,
            "failed": total_recent - successful_recent,
            "success_rate": (successful_recent / total_recent * 100)
            if total_recent > 0
            else 0,
        },
        "system_health": {
            "audit_events_last_hour": audit_count,
            "status": "healthy"
            if total_recent > 0 and successful_recent / total_recent > 0.9
            else "degraded"
            if total_recent > 0
            else "unknown",
        },
        "recent_events": [
            {
                "id": r.id,
                "status": r.status,
                "response_time_ms": r.response_time_ms,
                "output_score": r.output_score,
                "executed_at": r.executed_at.isoformat(),
            }
            for r in recent[:20]
        ],  # Last 20 events
    }


@router.get("/monitoring/alerts", summary="Get active alerts")
def get_active_alerts(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """
    Get active alerts for prompt performance issues.
    """
    check_permission(current_user, "manage_ai")

    alerts = []

    # Check for low success rates
    cutoff = datetime.now(UTC) - timedelta(hours=24)
    recent_tests = (
        db.query(PromptTest)
        .filter(PromptTest.updated_at >= cutoff, PromptTest.total_runs > 10)
        .all()
    )

    for test in recent_tests:
        success_rate = (
            (test.successful_runs / test.total_runs) * 100 if test.total_runs > 0 else 0
        )

        if success_rate < 80:
            alerts.append(
                {
                    "type": "low_success_rate",
                    "severity": "high" if success_rate < 50 else "medium",
                    "message": f"Prompt test '{test.test_name}' has low success rate: {success_rate:.1f}%",
                    "details": {
                        "test_id": test.id,
                        "prompt_type": test.prompt_type,
                        "version": test.version,
                        "success_rate": success_rate,
                        "total_runs": test.total_runs,
                    },
                }
            )

        if test.avg_latency_ms and test.avg_latency_ms > 2000:
            alerts.append(
                {
                    "type": "high_latency",
                    "severity": "medium",
                    "message": f"Prompt test '{test.test_name}' has high latency: {test.avg_latency_ms:.0f}ms",
                    "details": {
                        "test_id": test.id,
                        "prompt_type": test.prompt_type,
                        "latency_ms": test.avg_latency_ms,
                    },
                }
            )

    # Check for disabled variants with high traffic
    variants = (
        db.query(PromptVariant)
        .filter(not PromptVariant.is_enabled, PromptVariant.traffic_percentage > 0)
        .all()
    )

    for variant in variants:
        alerts.append(
            {
                "type": "disabled_variant_traffic",
                "severity": "low",
                "message": f"Disabled variant '{variant.variant_name}' still receiving {variant.traffic_percentage}% traffic",
                "details": {
                    "variant_id": variant.id,
                    "prompt_type": variant.prompt_type,
                    "traffic_percentage": variant.traffic_percentage,
                },
            }
        )

    return {
        "alerts": alerts,
        "total_active": len(alerts),
        "high_severity": len([a for a in alerts if a["severity"] == "high"]),
        "medium_severity": len([a for a in alerts if a["severity"] == "medium"]),
        "low_severity": len([a for a in alerts if a["severity"] == "low"]),
    }


# ============================================================================
# EXPORT & IMPORT
# ============================================================================


@router.get("/export", summary="Export prompt configurations")
def export_prompt_configurations(
    prompt_type: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Export prompt configurations for backup or sharing.
    """
    check_permission(current_user, "manage_ai")

    query = db.query(PromptVariant)

    if prompt_type:
        query = query.filter(PromptVariant.prompt_type == prompt_type)

    variants = query.all()

    export_data = {
        "exported_at": datetime.now(UTC).isoformat(),
        "exported_by": get_user_email(current_user),
        "prompt_variants": [
            {
                "prompt_type": v.prompt_type,
                "version": v.version,
                "variant_name": v.variant_name,
                "content": v.content,
                "description": v.description,
                "traffic_percentage": v.traffic_percentage,
                "is_enabled": v.is_enabled,
            }
            for v in variants
        ],
    }

    return export_data


@router.post("/import", summary="Import prompt configurations")
def import_prompt_configurations(
    import_data: Dict[str, Any],
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Import prompt configurations from export.
    """
    check_permission(current_user, "manage_ai")

    imported_count = 0

    for variant_data in import_data.get("prompt_variants", []):
        # Check if variant exists
        existing = (
            db.query(PromptVariant)
            .filter(
                PromptVariant.prompt_type == variant_data["prompt_type"],
                PromptVariant.version == variant_data["version"],
                PromptVariant.variant_name == variant_data["variant_name"],
            )
            .first()
        )

        if existing:
            # Update
            existing.content = variant_data["content"]
            existing.description = variant_data["description"]
            existing.traffic_percentage = variant_data["traffic_percentage"]
            existing.is_enabled = variant_data["is_enabled"]
            existing.updated_at = datetime.now(UTC)
        else:
            # Create
            variant = PromptVariant(
                prompt_type=variant_data["prompt_type"],
                version=variant_data["version"],
                variant_name=variant_data["variant_name"],
                content=variant_data["content"],
                description=variant_data["description"],
                traffic_percentage=variant_data["traffic_percentage"],
                is_enabled=variant_data["is_enabled"],
            )
            db.add(variant)

        imported_count += 1

    # Audit log
    audit = AuditLog(
        user_id=current_user.id,
        action="import_prompts",
        details=f"User {get_user_email(current_user)} imported {imported_count} prompt variants",
        ip_address="system",
    )
    db.add(audit)
    db.commit()

    return {
        "message": f"Successfully imported {imported_count} prompt variants",
        "imported_count": imported_count,
    }


# ============================================================================
# HEALTH CHECK
# ============================================================================


@router.get("/health", summary="Health check for prompt management system")
def health_check(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """
    Health check for prompt management system.
    """
    check_permission(current_user, "manage_ai")

    # Check database connectivity
    try:
        db.execute(text("SELECT 1"))
        db_healthy = True
    except Exception:
        db_healthy = False

    # Check prompt variants
    variant_count = db.query(PromptVariant).filter(PromptVariant.is_enabled).count()

    # Check recent tests
    recent_tests = (
        db.query(PromptTest)
        .filter(PromptTest.updated_at >= datetime.now(UTC) - timedelta(hours=24))
        .count()
    )

    return {
        "status": "healthy" if db_healthy else "unhealthy",
        "timestamp": datetime.now(UTC).isoformat(),
        "checks": {
            "database": "OK" if db_healthy else "FAILED",
            "prompt_variants": f"{variant_count} active variants",
            "recent_tests": f"{recent_tests} tests in last 24h",
        },
        "version": "1.0",
    }
