import json

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.ai.llm import get_embedding
from backend.database import Application, EvaluationResult, EvaluationSession, User
from backend.dependencies import get_db, require_recruiter
from backend.entity_writer import sync_cv_document
from backend.logger import logger

router = APIRouter(prefix="/hiring", tags=["copilot-admin"])


@router.post("/embed-candidates")
async def embed_candidates(
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    apps = (
        db.query(Application)
        .filter(
            Application.cv_embedding.is_(None),
            Application.cv_text_anonymized.isnot(None),
            Application.cv_text_anonymized != "",
        )
        .limit(50)
        .all()
    )
    if not apps:
        return {"message": "No candidates need embedding", "embedded": 0}

    embedded_count = 0
    for app in apps:
        try:
            text = (app.cv_text_anonymized or "")[:4000]
            if not text.strip():
                continue
            text_for_embedding = (
                f"{app.declared_role or ''} {app.full_name or ''} {text}"
            )
            embedding = await get_embedding(text_for_embedding)
            if embedding and isinstance(embedding, list):
                sync_cv_document(db, app, cv_embedding=json.dumps(embedding))
                embedded_count += 1
            else:
                skills_text = (
                    " ".join(json.loads(app.analysis_json).get("skills", []))
                    if app.analysis_json
                    else text
                )
                embedding2 = await get_embedding(skills_text[:4000])
                if embedding2 and isinstance(embedding2, list):
                    sync_cv_document(db, app, cv_embedding=json.dumps(embedding2))
                    embedded_count += 1
        except Exception as e:
            logger.error(f"[EMBED] Failed for app {app.id}: {e}")
            continue

    db.commit()
    return {
        "message": f"Embedded {embedded_count} candidates",
        "embedded": embedded_count,
        "total_pending": len(apps),
    }


@router.get("/copilot/analytics")
def get_copilot_analytics(
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    total_candidates = (
        db.query(Application).filter(Application.user_id == recruiter.id).count()
    )
    with_embeddings = (
        db.query(Application)
        .filter(
            Application.cv_embedding.isnot(None),
            Application.cv_embedding != "",
        )
        .count()
    )
    total_interviews = (
        db.query(Application)
        .join(EvaluationSession, EvaluationSession.application_id == Application.id)
        .join(
            EvaluationResult,
            EvaluationResult.evaluation_session_id == EvaluationSession.id,
        )
        .filter(
            EvaluationResult.final_score.isnot(None),
        )
        .count()
    )
    avg_score = (
        db.query(func.avg(EvaluationResult.final_score))
        .join(EvaluationSession, EvaluationSession.application_id == Application.id)
        .join(
            EvaluationResult,
            EvaluationResult.evaluation_session_id == EvaluationSession.id,
        )
        .filter(
            EvaluationResult.final_score.isnot(None),
        )
        .scalar()
        or 0
    )

    return {
        "total_candidates": total_candidates,
        "with_embeddings": with_embeddings,
        "total_interviews": total_interviews,
        "avg_score": round(float(avg_score), 1),
        "embedding_coverage": round(
            with_embeddings / max(total_candidates, 1) * 100, 1
        ),
    }
