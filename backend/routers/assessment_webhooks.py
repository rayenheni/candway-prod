from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from backend.assessment_service import AssessmentService
from backend.database import get_db
from backend.logger import logger

router = APIRouter(prefix="/assessments/webhook", tags=["Assessment Webhooks"])


@router.post("/hackerrank")
async def hackerrank_webhook(request: Request, db: Session = Depends(get_db)):
    body = await request.body()
    signature = request.headers.get("X-HackerRank-Signature", "")

    if not AssessmentService.verify_webhook_signature("hackerrank", body, signature):
        raise HTTPException(status_code=401, detail="Invalid signature")

    import json

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    event_type = payload.get("event") or payload.get("event_type", "")
    if event_type not in ("test_completed", "candidate_test_completed", ""):
        return {"status": "ignored", "event": event_type}

    try:
        result = await AssessmentService.handle_webhook("hackerrank", payload, db)
        return result
    except Exception as e:
        logger.error(f"HackerRank webhook error: {e}")
        return {"status": "error", "detail": str(e)}


@router.post("/codility")
async def codility_webhook(request: Request, db: Session = Depends(get_db)):
    body = await request.body()
    signature = request.headers.get("X-Codility-Signature", "")

    if not AssessmentService.verify_webhook_signature("codility", body, signature):
        raise HTTPException(status_code=401, detail="Invalid signature")

    import json

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    event_type = payload.get("event") or payload.get("status", "")
    if event_type not in ("test_completed", "completed", ""):
        return {"status": "ignored", "event": event_type}

    try:
        result = await AssessmentService.handle_webhook("codility", payload, db)
        return result
    except Exception as e:
        logger.error(f"Codility webhook error: {e}")
        return {"status": "error", "detail": str(e)}
