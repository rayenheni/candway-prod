import json
from datetime import UTC, datetime
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import desc
from sqlalchemy.orm import Session

from backend.authz import get_application_for_recruiter
from backend.database import (
    Application,
    ApplicationStageHistory,
    PipelineAutomationRule,
    User,
)
from backend.dependencies import get_db, require_recruiter
from backend.logger import logger
from backend.routers.recruiter_candidates.applications import (
    ALLOWED_APPLICATION_STATUSES,
)
from backend.security import sanitize_content

router = APIRouter(tags=["Recruiter Enhancements - Automation Rules"])


def _utcnow():
    return datetime.now(UTC).replace(tzinfo=None)


class AutomationRuleCreate(BaseModel):
    name: str
    description: Optional[str] = None
    trigger_json: dict
    action_json: dict


class AutomationRuleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    trigger_json: Optional[dict] = None
    action_json: Optional[dict] = None
    is_active: Optional[bool] = None


@router.get("/automation-rules")
def get_automation_rules(
    recruiter: User = Depends(require_recruiter), db: Session = Depends(get_db)
):
    """Get all automation rules for the recruiter"""
    rules = (
        db.query(PipelineAutomationRule)
        .filter(PipelineAutomationRule.recruiter_id == recruiter.id)
        .order_by(desc(PipelineAutomationRule.created_at))
        .all()
    )

    return [
        {
            "id": r.id,
            "name": r.name,
            "description": r.description,
            "trigger": json.loads(r.trigger_json),
            "action": json.loads(r.action_json),
            "is_active": r.is_active,
            "execution_count": r.execution_count,
            "last_executed_at": r.last_executed_at.isoformat()
            if r.last_executed_at
            else None,
            "created_at": r.created_at.isoformat(),
        }
        for r in rules
    ]


@router.post("/automation-rules", status_code=status.HTTP_201_CREATED)
def create_automation_rule(
    data: AutomationRuleCreate,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    """Create a new automation rule"""
    rule = PipelineAutomationRule(
        recruiter_id=recruiter.id,
        company_id=getattr(recruiter, "_company_id", None),
        name=sanitize_content(data.name),
        description=sanitize_content(data.description) if data.description else None,
        trigger_json=json.dumps(data.trigger_json),
        action_json=json.dumps(data.action_json),
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)

    logger.info(f"Automation rule created: {rule.name} by {recruiter.email}")
    return {"success": True, "rule_id": rule.id}


@router.patch("/automation-rules/{rule_id}")
def update_automation_rule(
    rule_id: int,
    data: AutomationRuleUpdate,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    """Update an automation rule"""
    rule = (
        db.query(PipelineAutomationRule)
        .filter(
            PipelineAutomationRule.id == rule_id,
            PipelineAutomationRule.recruiter_id == recruiter.id,
        )
        .first()
    )
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    if data.name is not None:
        rule.name = sanitize_content(data.name)
    if data.description is not None:
        rule.description = sanitize_content(data.description)
    if data.trigger_json is not None:
        rule.trigger_json = json.dumps(data.trigger_json)
    if data.action_json is not None:
        rule.action_json = json.dumps(data.action_json)
    if data.is_active is not None:
        rule.is_active = data.is_active

    db.commit()
    return {"success": True}


@router.delete("/automation-rules/{rule_id}")
def delete_automation_rule(
    rule_id: int,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    """Delete an automation rule"""
    rule = (
        db.query(PipelineAutomationRule)
        .filter(
            PipelineAutomationRule.id == rule_id,
            PipelineAutomationRule.recruiter_id == recruiter.id,
        )
        .first()
    )
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    db.delete(rule)
    db.commit()
    return {"success": True}


@router.patch("/automation-rules/{rule_id}/toggle")
def toggle_automation_rule(
    rule_id: int,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    rule = (
        db.query(PipelineAutomationRule)
        .filter(
            PipelineAutomationRule.id == rule_id,
            PipelineAutomationRule.recruiter_id == recruiter.id,
        )
        .first()
    )
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    rule.is_active = not rule.is_active
    db.commit()

    return {"success": True, "is_active": rule.is_active}


@router.post("/automation-rules/evaluate")
async def evaluate_automation_rules(
    app_id: int,
    background_tasks: BackgroundTasks,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    """Manually trigger rule evaluation for an application"""
    app = get_application_for_recruiter(app_id, recruiter, db)

    rules = (
        db.query(PipelineAutomationRule)
        .filter(
            PipelineAutomationRule.recruiter_id == recruiter.id,
            PipelineAutomationRule.is_active,
        )
        .all()
    )

    triggered = []
    for rule in rules:
        trigger = json.loads(rule.trigger_json)
        action = json.loads(rule.action_json)

        if _evaluate_trigger(trigger, app):
            _execute_action(action, app, db, recruiter)
            rule.execution_count += 1
            rule.last_executed_at = _utcnow()
            triggered.append(rule.name)

    if triggered:
        db.commit()
        logger.info(f"Automation rules triggered for app {app_id}: {triggered}")

    return {"success": True, "triggered_rules": triggered}


def _evaluate_trigger(trigger: dict, app: Application) -> bool:
    """Evaluate if a trigger condition matches an application"""
    trigger_type = trigger.get("type")

    if trigger_type == "score_threshold":
        field = trigger.get("field", "overall_score")
        operator = trigger.get("operator", ">=")
        value = trigger.get("value", 0)

        app_value = getattr(app, field, 0) or 0

        if operator == ">=":
            return app_value >= value
        elif operator == ">":
            return app_value > value
        elif operator == "<=":
            return app_value <= value
        elif operator == "<":
            return app_value < value
        elif operator == "==":
            return app_value == value

    elif trigger_type == "status_change":
        return app.status == trigger.get("status")

    elif trigger_type == "interview_completed":
        return app.interview_state == "completed"

    elif trigger_type == "no_activity_days":
        days = trigger.get("days", 7)
        if app.updated_at:
            return (_utcnow() - app.updated_at).days >= days

    return False


def _execute_action(action: dict, app: Application, db: Session, recruiter: User):
    """Execute an automation rule action"""
    action_type = action.get("type")

    if action_type == "move_stage":
        target_stage = action.get("target_stage")
        if target_stage:
            if target_stage not in ALLOWED_APPLICATION_STATUSES:
                logger.warning(
                    "Automation rule move_stage skipped for app %s: '%s' is not a valid application status",
                    app.id,
                    target_stage,
                )
                return

            # Record stage history
            history = ApplicationStageHistory(
                company_id=app.company_id,
                application_id=app.id,
                stage_slug=app.status,
                stage_name=app.status,
                exited_at=_utcnow(),
                triggered_by=recruiter.id,
                trigger_type="auto_rule",
            )
            db.add(history)

            app.status = target_stage

            new_history = ApplicationStageHistory(
                company_id=app.company_id,
                application_id=app.id,
                stage_slug=target_stage,
                stage_name=target_stage,
                triggered_by=recruiter.id,
                trigger_type="auto_rule",
            )
            db.add(new_history)

    elif action_type == "send_reminder":
        # Handled by background task
        pass

    elif action_type == "assign_recruiter":
        assignee_id = action.get("assignee_id")
        if assignee_id:
            app.assigned_to = assignee_id
            app.assigned_at = _utcnow()
