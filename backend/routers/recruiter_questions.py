import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.ai.llm import call_groq_cascade
from backend.authz import get_job_for_recruiter
from backend.database import User
from backend.dependencies import get_db, require_recruiter
from backend.logger import logger

router = APIRouter(prefix="/recruiter/questions", tags=["Recruiter Questions"])


class QuestionRow(BaseModel):
    id: int
    job_id: int
    question: str
    type: str = "technical"
    difficulty: str = "medium"
    skill_focus: Optional[str] = None


class QuestionCreateRequest(BaseModel):
    job_id: int
    question: str
    type: str = "technical"
    difficulty: str = "medium"
    skill_focus: Optional[str] = None


class QuestionGenerateRequest(BaseModel):
    job_id: int
    count: int = 5
    skills: Optional[list] = None


@router.post("/generate")
async def generate_questions(
    req: QuestionGenerateRequest,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    job = get_job_for_recruiter(req.job_id, recruiter, db)

    skills = req.skills or (
        job.required_skills.split(", ") if job.required_skills else []
    )
    prompt = f"""
Generate {req.count} interview questions for {job.title}.
Skills: {", ".join(skills[:8])}
Job description: {job.description[:1000] if job.description else ""}

Return JSON only: {{"questions": [
  {{"question": "question text", "type": "technical|behavioral|scenario", "difficulty": "junior|mid|senior", "skill_focus": "skill name"}}
]}}
"""
    try:
        result = await call_groq_cascade(
            [{"role": "user", "content": prompt}], json_mode=True
        )
        if isinstance(result, dict):
            questions = result.get("questions", [])
        elif isinstance(result, str):
            questions = json.loads(result).get("questions", [])
        else:
            questions = []
    except Exception as e:
        logger.error(f"[QUESTIONS] Generation failed: {e}")
        questions = [
            {
                "question": f"Describe your experience with {s}.",
                "type": "technical",
                "difficulty": "mid",
                "skill_focus": s,
            }
            for s in skills[: req.count]
        ]

    saved = []
    for q in questions[: req.count]:
        try:
            from backend.database import InterviewQuestion

            iq = InterviewQuestion(
                job_id=req.job_id,
                company_id=job.company_id,
                question=q.get("question", ""),
                type=q.get("type", "technical"),
                difficulty=q.get("difficulty", "mid"),
                skill_focus=q.get("skill_focus", ""),
            )
            db.add(iq)
            db.flush()
            saved.append(
                {
                    "id": iq.id,
                    "question": iq.question,
                    "type": iq.type,
                    "difficulty": iq.difficulty,
                    "skill_focus": iq.skill_focus,
                }
            )
        except Exception as e:
            logger.error(f"[QUESTIONS] Failed to save question: {e}")

    db.commit()
    return {"questions": saved, "total": len(saved)}


@router.get("/{job_id}")
def get_questions(
    job_id: int,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    from backend.database import InterviewQuestion

    _job = get_job_for_recruiter(job_id, recruiter, db)
    questions = (
        db.query(InterviewQuestion).filter(InterviewQuestion.job_id == job_id).all()
    )
    return [
        {
            "id": q.id,
            "job_id": q.job_id,
            "question": q.question,
            "type": q.type,
            "difficulty": q.difficulty,
            "skill_focus": q.skill_focus,
        }
        for q in questions
    ]


@router.post("/")
def create_question(
    req: QuestionCreateRequest,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    from backend.database import InterviewQuestion

    job = get_job_for_recruiter(req.job_id, recruiter, db)
    iq = InterviewQuestion(
        job_id=req.job_id,
        company_id=job.company_id,
        question=req.question,
        type=req.type,
        difficulty=req.difficulty,
        skill_focus=req.skill_focus,
    )
    db.add(iq)
    db.commit()
    db.refresh(iq)
    return {
        "id": iq.id,
        "question": iq.question,
        "type": iq.type,
        "difficulty": iq.difficulty,
        "skill_focus": iq.skill_focus,
    }


@router.delete("/{question_id}")
def delete_question(
    question_id: int,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    from backend.database import InterviewQuestion

    q = db.query(InterviewQuestion).filter(InterviewQuestion.id == question_id).first()
    if not q:
        raise HTTPException(status_code=404, detail="Question not found")
    get_job_for_recruiter(q.job_id, recruiter, db)
    db.delete(q)
    db.delete(q)
    db.commit()
    return {"message": "Question deleted"}
