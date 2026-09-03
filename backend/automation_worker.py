import json

from backend.database import Application, PipelineAutomationRule, SessionLocal
from backend.logger import logger
from backend.routers.recruiter_enhancements.automation import (
    _evaluate_trigger,
    _execute_action,
    _utcnow,
)


def evaluate_application_rules(
    application_id: int, company_id: int = None
) -> list[dict]:
    db = SessionLocal()
    try:
        app = db.query(Application).filter(Application.id == application_id).first()
        if not app:
            logger.warning(f"Automation worker: application {application_id} not found")
            return []

        if company_id is not None and app.company_id != company_id:
            logger.warning(
                f"Automation worker: tenant mismatch for app {application_id} "
                f"(expected company {company_id}, got {app.company_id}) — skipping"
            )
            return []

        job = app.job if app.job_id else (app.batch_job if app.batch_id else None)
        if not job:
            return []

        company_id = app.company_id
        rules = (
            db.query(PipelineAutomationRule)
            .filter(
                PipelineAutomationRule.company_id == company_id,
                PipelineAutomationRule.is_active,
            )
            .all()
        )

        if not rules:
            return []

        triggered = []
        recruiter_id = job.recruiter_id
        for rule in rules:
            trigger = json.loads(rule.trigger_json)
            action = json.loads(rule.action_json)

            if _evaluate_trigger(trigger, app):
                dummy_recruiter = job.recruiter if hasattr(job, "recruiter") else None
                if not dummy_recruiter:
                    from backend.database import User

                    dummy_recruiter = (
                        db.query(User).filter(User.id == recruiter_id).first()
                    )

                _execute_action(action, app, db, dummy_recruiter)
                rule.execution_count = (rule.execution_count or 0) + 1
                rule.last_executed_at = _utcnow()
                triggered.append(
                    {
                        "rule_id": rule.id,
                        "rule_name": rule.name,
                        "trigger_type": trigger.get("type"),
                        "action_type": action.get("type"),
                    }
                )

        if triggered:
            db.commit()
            logger.info(
                f"Automation worker: {len(triggered)} rules triggered for app {application_id}: "
                f"{[t['rule_name'] for t in triggered]}"
            )
        return triggered
    except Exception as e:
        db.rollback()
        logger.error(f"Automation worker: failed for app {application_id}: {e}")
        return []
    finally:
        db.close()
