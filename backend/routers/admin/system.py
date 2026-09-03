import os
import subprocess
from datetime import UTC, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.database import DATABASE_URL, AuditLog, BatchJob, User
from backend.dependencies import check_admin, get_current_user, get_db
from backend.logger import logger
from backend.routers.admin.common import check_permission

router = APIRouter(tags=["admin"])


@router.get("/backup/db")
def backup_database(current_user: User = Depends(get_current_user)):
    check_permission(current_user, "manage_admins")
    url = DATABASE_URL or ""
    if url.startswith("sqlite"):
        path = url.replace("sqlite:///", "")
        if not os.path.exists(path):
            raise HTTPException(status_code=404, detail="Database file not found")
        return FileResponse(
            path,
            media_type="application/octet-stream",
            filename=f"candway_backup_{datetime.now(UTC).strftime('%Y-%m-%d')}.db",
        )
    try:
        from urllib.parse import urlparse

        parsed = urlparse(url)
        mysql_pwd = os.environ.get("MYSQL_PWD") or parsed.password or ""
        env = os.environ.copy()
        env["MYSQL_PWD"] = mysql_pwd
        result = subprocess.run(
            [
                "mysqldump",
                "--no-tablespaces",
                f"--user={parsed.username}",
                f"--host={parsed.hostname}",
                f"--port={parsed.port or 3306}",
                parsed.path.lstrip("/"),
            ],
            capture_output=True,
            text=True,
            timeout=120,
            env=env,
        )
        if result.returncode != 0:
            raise HTTPException(
                status_code=500, detail=f"mysqldump failed: {result.stderr}"
            )
        from fastapi.responses import Response

        return Response(
            content=result.stdout,
            media_type="application/sql",
            headers={
                "Content-Disposition": f'attachment; filename="candway_backup_{datetime.now(UTC).strftime("%Y-%m-%d")}.sql"'
            },
        )
    except FileNotFoundError:
        raise HTTPException(status_code=500, detail="mysqldump not found on server")
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=500, detail="Database backup timed out")


@router.get("/health")
def admin_health(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    check_admin(current_user)
    try:
        db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False
    status_str = "healthy" if db_ok else "unhealthy"
    return {
        "status": status_str,
        "timestamp": datetime.now(UTC).isoformat(),
        "checks": {
            "database": "OK" if db_ok else "FAILED",
        },
    }


@router.get("/logs")
def get_system_logs(lines: int = 200, current_user: User = Depends(get_current_user)):
    lines = min(lines, 5000)
    check_permission(current_user, "view_logs")

    log_file = "backend.log"
    if not os.path.exists(log_file):
        return {"logs": ["Log file not found."]}

    try:
        with open(log_file, "r", encoding="utf-8") as f:
            all_lines = f.readlines()
            return {"logs": all_lines[-lines:]}
    except Exception:
        return {"logs": ["Error reading logs. Please check file permissions."]}


@router.get("/background-jobs")
def get_background_jobs(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    check_permission(current_user, "view_logs")

    active_jobs = (
        db.query(BatchJob)
        .filter(BatchJob.status == "active")
        .order_by(BatchJob.created_at.desc())
        .limit(10)
        .all()
    )

    email_logs = (
        db.query(AuditLog)
        .filter(AuditLog.action.in_(["EMAIL_SENT", "EMAIL_FAILED", "SYSTEM_ERROR"]))
        .order_by(AuditLog.timestamp.desc())
        .limit(20)
        .all()
    )

    return {
        "active_batch_jobs": [
            {
                "id": j.id,
                "recruiter_id": j.recruiter_id,
                "title": j.title,
                "target_role": j.target_role,
                "status": j.status,
                "worker_status": j.worker_status,
                "error_message": j.error_message,
                "created_at": j.created_at.isoformat() if j.created_at else None,
            }
            for j in active_jobs
        ],
        "recent_system_events": [
            {
                "id": e.id,
                "user_id": e.user_id,
                "action": e.action,
                "target_id": e.target_id,
                "details": e.details,
                "ip_address": e.ip_address,
                "timestamp": e.timestamp.isoformat() if e.timestamp else None,
            }
            for e in email_logs
        ],
    }


@router.get("/audit-trail")
def get_audit_trail(
    application_id: Optional[int] = None,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    check_permission(current_user, "view_logs")
    from backend.ai_audit import get_audit_trail as _get_audit_trail

    records = _get_audit_trail(application_id or 0, limit)
    return {"records": records, "total": len(records)}


@router.get("/drift-summary")
def get_drift_summary(
    current_user: User = Depends(get_current_user),
):
    check_permission(current_user, "view_logs")
    try:
        from backend.drift_monitor import compute_drift

        drift_data = compute_drift()
        return drift_data
    except Exception as e:
        logger.error(f"Drift summary error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to compute drift summary")


@router.get("/drift-history")
def get_drift_history(
    metric_name: str = "overall_score",
    current_user: User = Depends(get_current_user),
):
    check_permission(current_user, "view_logs")
    try:
        from backend.drift_monitor import get_drift_history as _get_drift_history

        records = _get_drift_history(metric_name=metric_name, limit=30)
        return {"records": records, "metric_name": metric_name}
    except Exception as e:
        logger.error(f"Drift history error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch drift history")


@router.get("/experiments")
def list_experiments(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    check_permission(current_user, "view_logs")
    from backend.database import ABExperiment

    exps = (
        db.query(ABExperiment).order_by(ABExperiment.started_at.desc()).limit(20).all()
    )
    return {
        "experiments": [
            {
                "id": e.id,
                "name": e.name,
                "model_a": e.model_a,
                "model_b": e.model_b,
                "sample_size_a": e.sample_size_a,
                "sample_size_b": e.sample_size_b,
                "avg_score_a": e.avg_score_a,
                "avg_score_b": e.avg_score_b,
                "is_active": e.is_active,
                "conclusion": e.conclusion,
                "started_at": e.started_at.isoformat() if e.started_at else None,
                "ended_at": e.ended_at.isoformat() if e.ended_at else None,
            }
            for e in exps
        ]
    }
