import json
import math
from typing import List, Optional

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from backend.ai.llm import call_groq_cascade
from backend.database import (
    Application,
    EvaluationResult,
    EvaluationSession,
    Job,
    RubricScoringDetail,
)
from backend.logger import logger


class CopilotEngine:
    @staticmethod
    async def detect_intent(question: str) -> dict:
        prompt = f"""
You are an AI assistant that classifies recruiter questions.

Classify the intent of this recruiter question into exactly one of:
- "search_candidates" — looking for candidates with specific skills/roles
- "job_analytics" — asking about stats, counts, metrics, pipeline data
- "compare_candidates" — asking to compare two or more candidates
- "schedule_interview" — wanting to set up an interview
- "general_qa" — anything else, general help

Also extract structured search params if intent is "search_candidates":
{{
  "skills": ["skill1", "skill2"],
  "min_score": 0,
  "role": "",
  "limit": 5
}}

Question: "{question}"

Return JSON only:
{{
  "intent": "...",
  "search_params": {{ "skills": [], "min_score": 0, "role": "", "limit": 5 }},
  "candidate_names": [],
  "confidence": 0.0
}}
"""
        try:
            result = await call_groq_cascade(
                [{"role": "user", "content": prompt}], json_mode=True, temperature=0.1
            )
            if isinstance(result, dict):
                return result
            if isinstance(result, str):
                return json.loads(result)
        except Exception as e:
            logger.error(f"[COPILOT] Intent detection failed: {e}")
        return {
            "intent": "general_qa",
            "search_params": {},
            "candidate_names": [],
            "confidence": 0.0,
        }

    @staticmethod
    def semantic_search(
        query_embedding: list,
        recruiter_id: int,
        db: Session,
        limit: int = 10,
        company_id: Optional[int] = None,
    ) -> List[Application]:
        filters = [
            or_(
                Job.recruiter_id == recruiter_id,
                Application.assigned_to == recruiter_id,
            ),
            Application.cv_embedding.isnot(None),
            Application.cv_embedding != "",
        ]
        if company_id is not None:
            filters.append(Job.company_id == company_id)
        apps = (
            db.query(Application)
            .outerjoin(Job, Application.job_id == Job.id)
            .filter(and_(*filters))
            .all()
        )
        scored = []
        for app in apps:
            try:
                emb = json.loads(app.cv_embedding)
                if not emb or not isinstance(emb, list):
                    continue
                sim = CopilotEngine._cosine_similarity(query_embedding, emb)
                fs = next(
                    (
                        es.evaluation_result.final_score or 0
                        for es in (app.evaluation_sessions or [])
                        if es.evaluation_result
                    ),
                    0,
                )
                scored.append((fs, sim, app))
            except (json.JSONDecodeError, TypeError, ValueError):
                continue
        scored.sort(key=lambda x: (x[0], x[1]), reverse=True)
        return [app for _, _, app in scored[:limit]]

    @staticmethod
    def _cosine_similarity(a: list, b: list) -> float:
        if not a or not b or len(a) != len(b):
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        na = math.sqrt(sum(x * x for x in a))
        nb = math.sqrt(sum(y * y for y in b))
        if na == 0 or nb == 0:
            return 0.0
        return dot / (na * nb)

    @staticmethod
    def full_text_search(
        query: str,
        recruiter_id: int,
        db: Session,
        limit: int = 10,
        company_id: Optional[int] = None,
    ) -> List[Application]:
        terms = [t.strip() for t in query.split() if len(t.strip()) > 2]
        if not terms:
            return []
        filters = [
            or_(
                Job.recruiter_id == recruiter_id,
                Application.assigned_to == recruiter_id,
            ),
        ]
        if company_id is not None:
            filters.append(Job.company_id == company_id)
        for term in terms:
            pattern = f"%{term}%"
            filters.append(
                or_(
                    Application.cv_text_anonymized.ilike(pattern),
                    Application.declared_role.ilike(pattern),
                    Application.full_name.ilike(pattern),
                )
            )
        return (
            db.query(Application)
            .outerjoin(Job, Application.job_id == Job.id)
            .filter(and_(*filters))
            .outerjoin(
                EvaluationSession, EvaluationSession.application_id == Application.id
            )
            .outerjoin(
                EvaluationResult,
                EvaluationResult.evaluation_session_id == EvaluationSession.id,
            )
            .order_by(EvaluationResult.final_score.desc().nullslast())
            .limit(limit)
            .all()
        )

    @staticmethod
    async def generate_response(
        intent: str, candidates: list, context: dict, question: str
    ) -> str:
        candidates_json = (
            json.dumps(candidates[:5], ensure_ascii=False, default=str)
            if candidates
            else "[]"
        )
        prompt = f"""You are an AI Recruiter Assistant. Respond helpfully and concisely.

Intent: {intent}
Question: "{question}"
Found {len(candidates)} matching candidates.

Context: {json.dumps(context, default=str)[:1000]}

Candidates data: {candidates_json}

Return JSON only:
{{"reply": "Your response here...", "suggested_actions": ["action1", "action2"]}}
"""
        try:
            result = await call_groq_cascade(
                [{"role": "user", "content": prompt}], json_mode=True, temperature=0.3
            )
            if isinstance(result, dict):
                return result.get(
                    "reply", "I found some candidates. Check the list above."
                ), result.get("suggested_actions", [])
            if isinstance(result, str):
                parsed = json.loads(result)
                return parsed.get("reply", "I found some candidates."), parsed.get(
                    "suggested_actions", []
                )
        except Exception as e:
            logger.error(f"[COPILOT] Response generation failed: {e}")

        if candidates:
            return (
                f"I found {len(candidates)} matching candidates. Take a look at the results above.",
                ["View all candidates", "Refine search"],
            )
        return "I couldn't find matching candidates. Try different search terms.", [
            "Search with different skills",
            "Browse all candidates",
        ]

    @staticmethod
    def build_candidate_context(application: Application, db: Session) -> dict:
        _sessions = getattr(application, "evaluation_sessions", None)
        _er_candidate = (
            _sessions[0].evaluation_result
            if _sessions and _sessions[0].evaluation_result
            else None
        )
        _sc = _er_candidate
        _cv = getattr(application, "cv_document", None)
        _cv_score = _sc.cv_score if _sc else None
        _final_score = _sc.final_score if _sc else None
        _declared_role = (
            getattr(_cv, "declared_role", None) or application.declared_role
        )
        _analysis_json = (
            getattr(_cv, "analysis_json", None) or application.analysis_json
        )

        context = {
            "id": application.id,
            "name": application.full_name,
            "role": _declared_role,
            "cv_score": _cv_score,
            "overall_score": _final_score,
            "status": application.status,
            "skills": [],
            "interview_score": None,
            "rubric_summary": None,
        }
        if _analysis_json:
            try:
                analysis = (
                    json.loads(_analysis_json)
                    if isinstance(_analysis_json, str)
                    else _analysis_json
                )
                context["skills"] = analysis.get("skills", [])[:10]
                context["summary"] = analysis.get("summary", "")
            except (json.JSONDecodeError, TypeError):
                pass
        summary_rows = (
            db.query(RubricScoringDetail)
            .join(
                EvaluationResult,
                RubricScoringDetail.evaluation_result_id == EvaluationResult.id,
            )
            .join(
                EvaluationSession,
                EvaluationResult.evaluation_session_id == EvaluationSession.id,
            )
            .filter(EvaluationSession.application_id == application.id)
            .all()
        )
        if summary_rows:
            scores = [row.score for row in summary_rows if row.score is not None]
            context["interview_score"] = (
                round(sum(scores) / len(scores), 1) if scores else None
            )
            context["rubric_summary"] = {
                "overall": context["interview_score"],
                "categories": [],
                "gaps": [],
            }
        return context

    @staticmethod
    def extract_search_params(llm_output: dict) -> dict:
        params = llm_output.get("search_params", {})
        if not params:
            return {"skills": [], "min_score": 0, "role": "", "limit": 5}
        return {
            "skills": params.get("skills", []),
            "min_score": params.get("min_score", 0) or 0,
            "role": params.get("role", ""),
            "limit": min(params.get("limit", 5) or 5, 20),
        }
