"""
Monitoring and Observability Router
Provides health checks, metrics, and system status endpoints
"""

import json
import os
from datetime import datetime

import psutil
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.database import User
from backend.dependencies import get_current_user, get_db
from backend.logger import logger
from backend.metrics import get_metrics_summary

router = APIRouter(prefix="/monitoring", tags=["monitoring"])


@router.post("/csp-report")
async def csp_report(request: Request):
    """
    CSP violation report endpoint.
    Logs CSP violations without blocking the request.
    """
    try:
        body = await request.json()
        logger.warning(f"CSP violation: {json.dumps(body, indent=2)}")
    except Exception:
        pass
    return {"status": "ok"}


@router.get("/health")
async def health_check(db: Session = Depends(get_db)):
    """
    Health check endpoint for load balancers and monitoring systems.
    Returns 200 if system is healthy, 503 if unhealthy.
    """
    health_status = {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "checks": {},
    }

    # Check database connectivity
    try:
        db.execute(text("SELECT 1"))
        health_status["checks"]["database"] = "healthy"
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        health_status["checks"]["database"] = "unhealthy"
        health_status["status"] = "unhealthy"

    # Tunable warning thresholds (defaults are less noisy for dev/test environments)
    disk_warn_threshold = int(os.getenv("HEALTH_DISK_WARN_PERCENT", "95"))
    memory_warn_threshold = int(os.getenv("HEALTH_MEMORY_WARN_PERCENT", "95"))

    # Check disk space
    try:
        disk_root = os.path.abspath(os.sep)
        disk = psutil.disk_usage(disk_root)
        if disk.percent > disk_warn_threshold:
            health_status["checks"]["disk"] = "warning"
            health_status["status"] = "degraded"
        else:
            health_status["checks"]["disk"] = "healthy"
    except Exception:
        health_status["checks"]["disk"] = "unknown"

    # Check memory
    try:
        memory = psutil.virtual_memory()
        if memory.percent > memory_warn_threshold:
            health_status["checks"]["memory"] = "warning"
            health_status["status"] = "degraded"
        else:
            health_status["checks"]["memory"] = "healthy"
    except Exception:
        health_status["checks"]["memory"] = "unknown"

    if health_status["status"] == "unhealthy":
        raise HTTPException(status_code=503, detail=health_status)

    return health_status


@router.get("/metrics")
async def get_metrics(current_user: User = Depends(get_current_user)):
    """
    Get system metrics (requires authentication).
    Returns interview performance, AI API stats, and error rates.
    """
    # Only allow admin or recruiter to view metrics
    if current_user.role not in ["admin", "recruiter"]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    metrics = get_metrics_summary()

    # Add system metrics
    try:
        metrics["system"] = {
            "cpu_percent": psutil.cpu_percent(interval=0.1),
            "memory_percent": psutil.virtual_memory().percent,
            "disk_percent": psutil.disk_usage("/").percent,
            "uptime_seconds": (
                datetime.now() - datetime.fromtimestamp(psutil.boot_time())
            ).total_seconds(),
        }
    except Exception:
        metrics["system"] = {"error": "Unable to collect system metrics"}

    return metrics


@router.get("/metrics/prometheus")
async def prometheus_metrics():
    """
    Prometheus-compatible metrics endpoint (no auth required for scraping).
    Uses prometheus_client generate_latest() when available,
    falls back to hand-rolled format for backward compatibility.
    """
    from backend.metrics import _PROMETHEUS_AVAILABLE

    if _PROMETHEUS_AVAILABLE:
        try:
            from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
            from starlette.responses import Response

            return Response(
                content=generate_latest(),
                media_type=CONTENT_TYPE_LATEST,
            )
        except Exception:
            pass

    # Fallback: hand-rolled Prometheus format
    from backend.metrics import interview_metrics

    lines = []
    lines.append("# HELP interview_starts_total Total number of interviews started")
    lines.append("# TYPE interview_starts_total counter")
    lines.append(f"interview_starts_total {interview_metrics.interviews_started}")
    lines.append(
        "# HELP interview_completions_total Total number of interviews completed"
    )
    lines.append("# TYPE interview_completions_total counter")
    lines.append(
        f"interview_completions_total {interview_metrics.interviews_completed}"
    )
    lines.append("# HELP interview_failures_total Total number of interviews failed")
    lines.append("# TYPE interview_failures_total counter")
    lines.append(f"interview_failures_total {interview_metrics.interviews_failed}")
    lines.append("# HELP ai_calls_total Total number of AI API calls")
    lines.append("# TYPE ai_calls_total counter")
    lines.append(f"ai_calls_total {interview_metrics.ai_calls_total}")
    lines.append(
        "# HELP ai_calls_success_total Total number of successful AI API calls"
    )
    lines.append("# TYPE ai_calls_success_total counter")
    lines.append(f"ai_calls_success_total {interview_metrics.ai_calls_success}")
    lines.append("# HELP ai_calls_failed_total Total number of failed AI API calls")
    lines.append("# TYPE ai_calls_failed_total counter")
    lines.append(f"ai_calls_failed_total {interview_metrics.ai_calls_failed}")
    lines.append("# HELP ai_timeouts_total Total number of AI API timeouts")
    lines.append("# TYPE ai_timeouts_total counter")
    lines.append(f"ai_timeouts_total {interview_metrics.ai_timeouts}")
    if interview_metrics.ai_response_times:
        avg_response_time = sum(interview_metrics.ai_response_times) / len(
            interview_metrics.ai_response_times
        )
        lines.append("# HELP ai_response_time_seconds AI API response time")
        lines.append("# TYPE ai_response_time_seconds gauge")
        lines.append(f"ai_response_time_seconds {avg_response_time:.3f}")
    if interview_metrics.interview_durations:
        avg_duration = sum(interview_metrics.interview_durations) / len(
            interview_metrics.interview_durations
        )
        lines.append("# HELP interview_duration_seconds Average interview duration")
        lines.append("# TYPE interview_duration_seconds gauge")
        lines.append(f"interview_duration_seconds {avg_duration:.1f}")
    try:
        lines.append("# HELP system_cpu_percent CPU usage percentage")
        lines.append("# TYPE system_cpu_percent gauge")
        lines.append(f"system_cpu_percent {psutil.cpu_percent(interval=0.1)}")
        lines.append("# HELP system_memory_percent Memory usage percentage")
        lines.append("# TYPE system_memory_percent gauge")
        lines.append(f"system_memory_percent {psutil.virtual_memory().percent}")
    except Exception:
        pass
    return "\n".join(lines)


@router.get("/readyz")
async def readiness_probe(db: Session = Depends(get_db)):
    """Readiness probe - checks if app can serve traffic"""
    try:
        db.execute(text("SELECT 1"))
        return {"status": "ok"}
    except Exception:
        raise HTTPException(status_code=503, detail="Not ready")


@router.get("/livez")
async def liveness_probe():
    """Liveness probe - checks if app is alive"""
    return {"status": "ok"}


@router.get("/status")
async def system_status():
    """
    Public system status endpoint (no auth required).
    Shows high-level system health without sensitive details.
    """
    from backend.metrics import interview_metrics

    # Calculate uptime
    try:
        uptime = (
            datetime.now() - datetime.fromtimestamp(psutil.boot_time())
        ).total_seconds()
        uptime_hours = uptime / 3600
    except Exception:
        uptime_hours = 0

    # Calculate success rates
    completion_rate = 0
    if interview_metrics.interviews_started > 0:
        completion_rate = (
            interview_metrics.interviews_completed
            / interview_metrics.interviews_started
        ) * 100

    ai_success_rate = 0
    if interview_metrics.ai_calls_total > 0:
        ai_success_rate = (
            interview_metrics.ai_calls_success / interview_metrics.ai_calls_total
        ) * 100

    return {
        "status": "operational",
        "uptime_hours": round(uptime_hours, 1),
        "interviews_today": interview_metrics.interviews_started,
        "completion_rate": round(completion_rate, 1),
        "ai_availability": round(ai_success_rate, 1),
        "last_updated": datetime.now().isoformat(),
    }


@router.post("/metrics/reset")
async def reset_metrics(current_user: User = Depends(get_current_user)):
    """
    Reset all metrics (admin only).
    Useful for testing or periodic resets.
    """
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")

    from backend.metrics import interview_metrics

    interview_metrics.reset()

    logger.info(f"Metrics reset by admin user_id={current_user.id}")

    return {"message": "Metrics reset successfully"}
