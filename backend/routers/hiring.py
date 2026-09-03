import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.ai.llm import call_groq_cascade
from backend.authz import get_application_for_recruiter
from backend.database import User
from backend.dependencies import get_current_user, get_db
from backend.schemas import (
    HiringChatRequest,
)

router = APIRouter(prefix="/hiring", tags=["hiring"])


@router.post("/candidate/{application_id}/chat")
async def chat_with_candidate_context(
    application_id: int,
    request: HiringChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Chat with an expert AI Recruiter Assistant about a specific candidate.
    Context-Aware RAG: Uses Job Description, CV, Interview Answers, and Scores.
    """

    # Access Control: Only Recruiters and Admins
    if current_user.role not in ["recruiter", "admin"]:
        raise HTTPException(status_code=403, detail="Access denied. Recruiters only.")

    # 1. Fetch Application & Candidate Data
    app = get_application_for_recruiter(application_id, current_user, db)

    # 2. Resolve Job Context
    job_title = "General Context"
    job_description = "No specific job description provided."

    if app.job:
        job_title = app.job.title
        job_description = app.job.description or app.job.required_skills
    elif app.batch_job:
        job_title = app.batch_job.title
        job_description = app.batch_job.description or app.batch_job.target_role
    elif app.declared_role:
        job_title = app.declared_role

    # 3. Retrieve Candidate Data
    cv_text = app.cv_text_anonymized or "CV Text Not Available"

    # Interview Answers (Parse from Log)
    interview_answers = "No interview conducted yet."
    if app.interview_log:
        try:
            log = json.loads(app.interview_log)
            # Summarize Q&A
            qa_summary = []
            for entry in log:
                role = entry.get("role")
                content = entry.get("content")
                if role == "assistant":
                    qa_summary.append(f"Q: {content}")
                elif role == "user":
                    qa_summary.append(f"A: {content}")
            if qa_summary:
                interview_answers = "\n".join(qa_summary[-10:])  # last 10 turns
        except Exception as e:
            from backend.logger import logger

            logger.error(f"Error parsing interview log for app {application_id}: {e}")
            pass

    # AI Scores
    _er = (
        app.evaluation_sessions[0].evaluation_result
        if app.evaluation_sessions and app.evaluation_sessions[0].evaluation_result
        else None
    )
    ai_score = f"Overall: {_er.final_score if _er else None}, CV: {_er.cv_score if _er else None}"

    # 4. Construct System Prompt
    system_prompt = f"""You are an expert AI Recruiter Assistant helping a hiring manager.

    **THE GOAL:** Evaluate if the candidate fits the following role:
    - Role: {job_title}
    - Requirements: {job_description}

    **THE CANDIDATE:**
    - CV Summary: {cv_text[:2000]}... (truncated)
    - Scenario Answers: {interview_answers}
    - AI Assessment Score: {ai_score}

    **INSTRUCTION:**
    Act as a senior technical recruiter advisor. Your response must be highly structured, critical, and easy to skim.

    **FORMAT RULES (STRICT):**
    - You MUST output raw HTML (no markdown code blocks, just tags: `<b>`, `<ul>`, `<li>`, `<br>`).
    - Structure your answer into these clear sections:
        1. **Executive Summary**: One distinct sentence verdict.
        2. **Key Strengths**: Bullet points matching candidate skills to job requirements.
        3. **Critical Gaps**: Honest assessment of what is missing.
        4. **Suggested Interview Question**: One tailored question to probe the gaps.

    **TONE:**
    - Objective, slightly critical, and professional.
    - Use bold text `<b>` for key metrics or skills.
    - Do NOT use generic filler like "This candidate seems promising." Be specific.
    """

    # 5. Build Messages
    messages = [{"role": "system", "content": system_prompt}]

    # Append History (Last 5 turns to keep context small)
    for msg in request.history[-5:]:
        messages.append(
            {"role": msg.get("role", "user"), "content": msg.get("content", "")}
        )

    messages.append({"role": "user", "content": request.question})

    # 6. LLM Call
    try:
        # Use Cascade (Local -> Groq)
        response = await call_groq_cascade(messages, temperature=0.5, json_mode=False)
        return {"reply": response}
    except Exception as e:
        from backend.logger import logger

        logger.error(f"Chat Error: {e}")
        return {
            "reply": "I'm having trouble analyzing this candidate right now. Please try again."
        }


# Note: Global /chat endpoint moved to routers/copilot.py for cleaner separation.
