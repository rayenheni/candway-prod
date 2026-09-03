import json
import logging
from datetime import UTC, datetime
from typing import Dict, List

from sqlalchemy.orm import Session

from backend.ai_engine import AIEngine
from backend.database import AuditLog, SalesCampaign, SalesLead

logger = logging.getLogger("candway_app.sales_autobot")


class SalesAutopilot:
    def __init__(self, db: Session):
        self.db = db
        self.ai = AIEngine(db)

    async def run_mission(self, niche: str, mission_name: str = None, run_outreach: bool = False):
        """
        Executes a full Autonomous Sales Mission.
        1. Discovery (Scraping Simulation)
        2. Prospecting (Scoring)
        3. Pre-Outreach (Drafting)
        """
        if not mission_name:
            mission_name = (
                f"Autopilot: {niche} - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            )

        campaign = SalesCampaign(name=mission_name, niche=niche, status="running")
        self.db.add(campaign)
        self.db.commit()
        self.db.refresh(campaign)

        logger.info(f"Starting Sales Mission: {mission_name} for niche: {niche}")

        try:
            # Phase 1: Discovery
            leads_discovered = await self._discover_leads(niche)
            campaign.total_leads_found = len(leads_discovered)
            self.db.commit()

            # Phase 2: Prospecting & Qualification
            for raw_lead in leads_discovered:
                await self._process_lead(raw_lead, niche)
                self.db.commit()

            if run_outreach:
                await self.automated_outreach()

            campaign.status = "completed"
            campaign.completed_at = datetime.now(UTC)
            self.db.commit()
            logger.info(f"Mission {mission_name} completed successfully.")

        except Exception as e:
            logger.error(f"Mission {mission_name} failed: {e}")
            self.db.rollback()
            campaign.status = "failed"
            self.db.commit()

    async def _discover_leads(self, niche: str) -> List[Dict]:
        """
        Uses AI to research and find high-potential companies in the niche.
        Currently simulates external scraping by generating hyper-realistic leads.
        """
        prompt = f"""
        Research and discover 5 high-potential companies or startups based in Tunisia (or North Africa) that are currently growing and need AI recruitment solutions.
        Niche: {niche}

        For each company, provide:
        - Company Name
        - Likely Hiring Manager Name
        - Likely Role (e.g. CTO, HR Director)
        - Strategic Context (Why they are a good fit right now?)

        Return JSON list: [ {{"company": "...", "name": "...", "role": "...", "context": "..."}} ]
        """

        try:
            raw_response = await self.ai.generate_text(
                prompt, system_prompt="You are a Lead Generation Specialist."
            )
            # Basic parsing helper
            if "```json" in raw_response:
                raw_response = raw_response.split("```json")[1].split("```")[0].strip()
            elif "[" in raw_response:
                raw_response = raw_response[
                    raw_response.find("[") : raw_response.rfind("]") + 1
                ]

            return json.loads(raw_response)
        except Exception as e:
            logger.error(f"Lead Discovery Error: {e}")
            return []

    async def _process_lead(self, raw_lead: Dict, niche: str):
        """
        Qualifies and saves a discovered lead.
        """
        # Prospecting AI Analysis
        prompt = f"""
        Analyze this Lead for Candway AI Recruitment Platform:
        Company: {raw_lead.get("company")}
        Contact: {raw_lead.get("name")} ({raw_lead.get("role")})
        Context: {raw_lead.get("context")}
        Target Niche: {niche}

        1. Calculate a Sales Match Score (0-100).
        2. Formulate a personalized outreach strategy.
        3. Identify their biggest pain point we can solve.

        Return JSON: {{"score": 85, "strategy": "...", "pain_point": "..."}}
        """

        analysis = {
            "score": 50,
            "strategy": "Standard Pitch",
            "pain_point": "Inefficient screening",
        }
        try:
            raw_analysis = await self.ai.generate_text(
                prompt, system_prompt="You are an Expert Sales Psychologist."
            )
            if "{" in raw_analysis:
                raw_analysis = raw_analysis[
                    raw_analysis.find("{") : raw_analysis.rfind("}") + 1
                ]
            analysis = json.loads(raw_analysis)
        except Exception:
            pass

        # Save to DB
        lead = SalesLead(
            name=raw_lead.get("name"),
            company=raw_lead.get("company"),
            role=raw_lead.get("role"),
            source="autopilot_discovery",
            status="qualified" if analysis.get("score", 0) > 60 else "new",
            score=analysis.get("score", 0),
            ai_notes=f"Strategy: {analysis.get('strategy')}\nPain Point: {analysis.get('pain_point')}\nContext: {raw_lead.get('context')}",
        )
        self.db.add(lead)

    async def automated_outreach(self, limit: int = 5):
        """
        Finds qualified leads and drafts/sends outreach autonomously.
        """
        leads = (
            self.db.query(SalesLead)
            .filter(
                SalesLead.status == "qualified", SalesLead.last_contacted_at.is_(None)
            )
            .limit(limit)
            .all()
        )

        for lead in leads:
            try:
                # Drafting the perfect pitch
                prompt = f"""
                Draft a high-conversion 1-on-1 personalized email for {lead.name} at {lead.company}.
                Bio/Context: {lead.ai_notes}
                Goal: Get a 15-min demo for Candway's AI-powered Technical Screening.

                Keep it under 100 words. Bold, innovative, and direct.
                """
                content = await self.ai.generate_text(
                    prompt, system_prompt="You are a Top 1% Sales Copywriter."
                )

                # In a real scenario, we would trigger the actual email service here.
                # For now, we log it and update status.
                logger.info(
                    f"Drafted autonomous outreach for {lead.email or lead.name}"
                )

                lead.status = "contacted"
                lead.last_contacted_at = datetime.now(UTC)

                # Mock Outreach Logging
                audit = AuditLog(
                    user_id=1,  # Admin
                    action="SALES_AUTOPILOT_OUTREACH",
                    target_id=str(lead.id),
                    details=f"Autonomous outreach drafted for {lead.company}: {content[:100]}...",
                )
                self.db.add(audit)

            except Exception as e:
                logger.error(f"Outreach error for lead {lead.id}: {e}")

        self.db.commit()
