import json
import logging
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.ai_engine import AIEngine
from backend.database import SessionLocal, Job, SalesCampaign, SalesLead, User, get_db
from backend.dependencies import get_current_user
from backend.routers.admin.common import check_permission
from backend.profile_helpers import (
    get_user_subscription_status,
    get_user_usage_ai_interviews,
    get_user_usage_cvs,
)
from backend.sales_autobot import SalesAutopilot

router = APIRouter(prefix="/admin/ai/sales", tags=["admin_sales"])
logger = logging.getLogger("candway_app.ai_sales")


# --- Schemas ---
class SalesLeadRequest(BaseModel):
    source: str = "internal"  # internal, external (mock)
    criteria: str = "High Engagement"


class AutopilotMission(BaseModel):
    niche: str = "Tunisian Startups"
    run_outreach: bool = False


class OutreachRequest(BaseModel):
    lead_id: int
    channel: str = "email"  # email, linkedin, whatsapp
    context: Optional[str] = None


class StatusUpdate(BaseModel):
    status: str


# --- Endpoints ---


@router.get("/leads")
def get_sales_leads(
    status: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    check_permission(current_user, "manage_marketing")
    query = db.query(SalesLead)
    if status:
        query = query.filter(SalesLead.status == status)
    return query.order_by(SalesLead.score.desc()).all()


@router.post("/leads/{lead_id}/status")
def update_lead_status(
    lead_id: int,
    payload: StatusUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    check_permission(current_user, "manage_marketing")
    lead = db.query(SalesLead).filter(SalesLead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    lead.status = payload.status
    db.commit()
    return {"message": "Status updated"}


@router.post("/autopilot/launch")
async def launch_autopilot(
    payload: AutopilotMission,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Launches an autonomous sales mission in the background.
    """
    check_permission(current_user, "manage_marketing")
    def run_sales_mission():
        session = SessionLocal()
        try:
            bot = SalesAutopilot(session)
            import asyncio

            asyncio.run(
                bot.run_mission(
                    payload.niche,
                    run_outreach=payload.run_outreach,
                )
            )
        except Exception:
            session.rollback()
            logger.exception("Sales autopilot background task failed")
        finally:
            session.close()

    background_tasks.add_task(run_sales_mission)

    return {
        "message": f"Autopilot mission for '{payload.niche}' launched in background."
    }


@router.get("/campaigns")
def get_campaigns(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    check_permission(current_user, "manage_marketing")
    return db.query(SalesCampaign).order_by(SalesCampaign.created_at.desc()).all()


@router.post("/leads/scan-internal")
async def generate_internal_leads(
    payload: SalesLeadRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Identify potential sales leads from internal platform users.
    """
    check_permission(current_user, "manage_marketing")
    ai = AIEngine(db)

    # Target: Recruiters who are active but haven't upgraded
    leads = (
        db.query(User)
        .filter(User.role == "recruiter", User.deleted_at.is_(None))
        .limit(10)
        .all()
    )

    for lead in leads:
        job_count = db.query(Job).filter(Job.recruiter_id == lead.id).count()
        usage_score = (get_user_usage_ai_interviews(lead) or 0) + (
            get_user_usage_cvs(lead) or 0
        )

        prompt = f"""
        Analyze this Recruiter for Sales Potential for Candway Premium:
        - User: {lead.full_name or "Anonymous"} ({lead.email})
        - Plan: {get_user_subscription_status(lead) or "Free"}
        - Jobs Posted: {job_count}
        - Tool Usage: {usage_score}

        Return JSON with "score" (0-100), "category", and "rationale".
        """

        try:
            raw_analysis = await ai.generate_text(
                prompt, system_prompt="You are a Senior SaaS Sales Lead."
            )
            if "{" in raw_analysis:
                raw_analysis = raw_analysis[
                    raw_analysis.find("{") : raw_analysis.rfind("}") + 1
                ]
            analysis_data = json.loads(raw_analysis)

            # Upsert into SalesLead table for persistence
            existing = db.query(SalesLead).filter(SalesLead.email == lead.email).first()
            if not existing:
                new_lead = SalesLead(
                    name=lead.full_name or "Unknown",
                    email=lead.email,
                    company="Platform User",
                    source="internal_scan",
                    score=analysis_data.get("score", 50),
                    status="qualified" if analysis_data.get("score", 0) > 70 else "new",
                    ai_notes=analysis_data.get("rationale"),
                )
                db.add(new_lead)
        except Exception as e:
            logger.error(f"Internal Scan Error for {lead.email}: {e}")

    db.commit()
    return {"message": "Internal scan completed. Check Leads Inbox."}


@router.post("/outreach")
async def generate_outreach(
    payload: OutreachRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Manual outreach drafting for any lead.
    """
    check_permission(current_user, "manage_marketing")
    ai = AIEngine(db)

    lead = db.query(SalesLead).filter(SalesLead.id == payload.lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    prompt = f"""
    Create a highly persuasive {payload.channel} message for:
    Name: {lead.name}
    Company: {lead.company}
    Strategic Context: {lead.ai_notes}

    Channel constraints:
    - Email: Subject line + Professional body.
    - LinkedIn: Soft-intro + clear value prop.
    - WhatsApp: Concise and benefit-first.

    Goal: High conversion.
    """

    content = await ai.generate_text(
        prompt, system_prompt="You are a Sales Copywriting Legend."
    )
    return {"channel": payload.channel, "content": content}
