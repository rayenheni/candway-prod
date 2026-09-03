import io
import json
from datetime import datetime

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from backend.authz import get_application_for_recruiter
from backend.database import User, get_db
from backend.dependencies import require_recruiter
from backend.utils.pdf_generator import generate_application_pdf

router = APIRouter(prefix="/reports", tags=["Reports"])

REPORT_STYLE = ""  # Kept for compatibility if imported elsewhere


@router.get("/application/{application_id}/pdf")
async def generate_pdf_report(
    application_id: int,
    db: Session = Depends(get_db),
    recruiter: User = Depends(require_recruiter),
):
    app = get_application_for_recruiter(application_id, recruiter, db)

    # Parse analysis data
    analysis = {}
    try:
        if app.analysis_json:
            analysis = json.loads(app.analysis_json)
    except Exception:
        pass

    # Reusing the shared utility
    pdf_bytes = generate_application_pdf(app, analysis)

    filename = f"Report_{app.full_name.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.pdf"

    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
