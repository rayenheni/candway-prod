from typing import List

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import or_
from sqlalchemy.orm import Session

from backend.ai.llm import get_embedding
from backend.copilot_engine import CopilotEngine
from backend.database import Application, Job, User
from backend.dependencies import get_db, require_credits, require_recruiter
from backend.logger import logger
from backend.profile_helpers import get_user_company_name, get_user_name
from backend.routers.recruiter_dashboard import get_recruiter_stats
from backend.tenant import get_current_company_id

router = APIRouter(prefix="/hiring", tags=["copilot"])


class CopilotChatRequest(BaseModel):
    question: str
    history: List[dict] = []


@router.post("/chat")
async def chat_with_copilot(
    req: CopilotChatRequest,
    _credit_tx: object = Depends(require_credits("copilot_chat", credits=1)),
    recruiter: User = Depends(require_recruiter),
    company_id: int = Depends(get_current_company_id),
    db: Session = Depends(get_db),
):
    intent_result = await CopilotEngine.detect_intent(req.question)
    intent = intent_result.get("intent", "general_qa")
    candidates_found = []
    candidate_cards = []
    suggested_actions = []

    if intent == "search_candidates":
        params = CopilotEngine.extract_search_params(intent_result)
        query_text = " ".join(params.get("skills", [])) or req.question

        embedding = await get_embedding(query_text)
        if embedding:
            apps = CopilotEngine.semantic_search(
                embedding, recruiter.id, db, params["limit"], company_id=company_id
            )
        else:
            apps = CopilotEngine.full_text_search(
                query_text, recruiter.id, db, params["limit"], company_id=company_id
            )

        role_filter = params.get("role", "").lower()
        min_score = params.get("min_score", 0)
        for app in apps:
            if role_filter and role_filter not in (app.declared_role or "").lower():
                continue
            _er = (
                app.evaluation_sessions[0].evaluation_result
                if app.evaluation_sessions
                and app.evaluation_sessions[0].evaluation_result
                else None
            )
            score = max(
                (_er.final_score if _er else None) or 0,
                (_er.cv_score if _er else None) or 0,
            )
            if score < min_score:
                continue

            context = CopilotEngine.build_candidate_context(app, db)
            candidates_found.append(context)
            candidate_cards.append(
                {
                    "id": app.id,
                    "name": app.full_name or "Candidate",
                    "role": app.declared_role or "Candidate",
                    "score": score,
                    "match_reason": context.get("summary", "")[:120],
                    "skills": context.get("skills", []),
                    "status": app.status,
                }
            )

        suggested_actions = [
            f"Find {params['skills'][0]} developers"
            if params.get("skills")
            else "Search by skill",
            "Compare top candidates",
            "View analytics dashboard",
        ]

    elif intent == "job_analytics":
        try:
            stats = get_recruiter_stats(recruiter=recruiter, db=db)
            context = {
                "stats": stats,
                "has_data": bool(stats.get("total_applications", 0) > 0),
            }
            suggested_actions = [
                "View full analytics",
                "Check recent candidates",
                "Create a job",
            ]
        except Exception as e:
            logger.error(f"[COPILOT] Analytics fetch failed: {e}")
            context = {"stats": {}, "has_data": False}
            suggested_actions = ["Create a job posting", "Import candidates"]

    elif intent == "compare_candidates":
        names = intent_result.get("candidate_names", [])
        id_list = [n for n in names if isinstance(n, int)]
        if id_list:
            query = db.query(Application).filter(Application.id.in_(id_list))
            query = query.outerjoin(Job, Application.job_id == Job.id).filter(
                or_(
                    Job.company_id == company_id,
                    Application.assigned_to == recruiter.id,
                )
            )
            apps = query.all()
        else:
            apps = []
        for app in apps:
            context = CopilotEngine.build_candidate_context(app, db)
            candidates_found.append(context)
            _er = (
                app.evaluation_sessions[0].evaluation_result
                if app.evaluation_sessions
                and app.evaluation_sessions[0].evaluation_result
                else None
            )
            score = max(
                (_er.final_score if _er else None) or 0,
                (_er.cv_score if _er else None) or 0,
            )
            candidate_cards.append(
                {
                    "id": app.id,
                    "name": app.full_name or "Candidate",
                    "role": app.declared_role or "Candidate",
                    "score": score,
                    "skills": context.get("skills", []),
                    "status": app.status,
                }
            )
        suggested_actions = [
            "Rank all candidates",
            "View detailed comparison",
            "Schedule interview",
        ]

    elif intent == "schedule_interview":
        suggested_actions = [
            "View calendar",
            "Check available slots",
            "Send interview invites",
        ]

    context = {
        "recruiter_name": get_user_name(recruiter)
        or get_user_company_name(recruiter)
        or "Recruiter"
    }
    reply, suggested = await CopilotEngine.generate_response(
        intent, candidates_found, context, req.question
    )
    if suggested:
        suggested_actions = suggested

    return {
        "reply": reply,
        "candidates": candidate_cards,
        "intent": intent,
        "suggested_actions": suggested_actions[:5],
    }
