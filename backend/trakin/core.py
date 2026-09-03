import inspect
import logging
import traceback
from datetime import datetime
from typing import Callable

from backend.database import AuditLog, SessionLocal

logger = logging.getLogger(__name__)


async def safe_execute(task_name: str, func: Callable, *args, **kwargs):
    """
    Trakin Sentinel: Safely executes a background task with strict error boundaries and audit logging.
    Usage: background_tasks.add_task(safe_execute, "MyTask", my_func, arg1, arg2...)
    """
    start_time = datetime.now()
    logger.info(f"[TRAKIN] SENTINEL WATCH: Starting {task_name}...")

    try:
        if inspect.iscoroutinefunction(func):
            await func(*args, **kwargs)
        else:
            func(*args, **kwargs)

        duration = (datetime.now() - start_time).total_seconds()
        logger.info(f"[TRAKIN] SENTINEL: {task_name} completed in {duration:.2f}s")

    except Exception as e:
        duration = (datetime.now() - start_time).total_seconds()
        error_msg = str(e)
        stack_trace = traceback.format_exc()

        logger.error(
            f"[TRAKIN] SENTINEL ALERT: {task_name} FAILED after {duration:.2f}s: {error_msg}"
        )

        # Log failure to DB
        try:
            db = SessionLocal()
            audit = AuditLog(
                user_id=None,  # System
                action="task_failure",
                target_id=task_name,
                details=f"Error: {error_msg}\nTrace: {stack_trace[:500]}...",  # Truncate for DB
                ip_address="trakin_sentinel",
            )
            db.add(audit)
            db.commit()
            db.close()
        except Exception as db_e:
            logger.error(f"[TRAKIN] CRITICAL: Failed to log task failure to DB: {db_e}")
