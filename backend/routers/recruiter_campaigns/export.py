"""Campaign shortlist + CSV/PDF export endpoints.

Used by the campaign detail page (frontend/src/services/campaigns.service.ts):

  PATCH /recruiter/campaigns/{batch_id}/candidates/{app_id}/shortlist
  GET   /recruiter/campaigns/{batch_id}/export/csv?scope=all|shortlisted
  GET   /recruiter/campaigns/{batch_id}/export/pdf?scope=all|shortlisted&tier=bool

Scores mirror GET /{batch_id}/candidates: canonical EvaluationResult.cv_score
(legacy Application.analysis_score fallback) and the interview final score
only once the interview is completed/flagged.
"""

import csv
import io
from datetime import UTC, datetime
from typing import Literal, Optional

from fastapi import Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session, selectinload

from backend.authz import get_batch_for_recruiter
from backend.database import Application, EvaluationSession, User
from backend.dependencies import get_db, require_recruiter
from backend.logger import logger
from backend.models.ats.pipeline import ApplicationStageHistory

from . import router

Scope = Literal["all", "shortlisted"]

# Tier thresholds for the "Tiered PDF" export (best available score).
_TIERS = (
    ("Tier A - Strong (75+)", 75.0),
    ("Tier B - Promising (50-74)", 50.0),
    ("Tier C - Below bar (<50)", 0.0),
)


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _campaign_app(db: Session, batch_id: int, app_id: int, company_id) -> Application:
    app = (
        db.query(Application)
        .filter(
            Application.id == app_id,
            Application.batch_id == batch_id,
            Application.company_id == company_id,
            Application.deleted_at.is_(None),
        )
        .first()
    )
    if app is None:
        raise HTTPException(status_code=404, detail="Candidate not found in campaign")
    return app


@router.patch("/{batch_id}/candidates/{app_id}/shortlist")
def shortlist_campaign_candidate(
    batch_id: int,
    app_id: int,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    batch = get_batch_for_recruiter(batch_id, recruiter, db)
    # The tenant-checked batch is authoritative for the company scope; the
    # request-scoped recruiter._company_id may be unset or stale.
    app = _campaign_app(db, batch_id, app_id, batch.company_id)

    if app.status != "shortlisted":
        now = _utcnow()
        prev = (
            db.query(ApplicationStageHistory)
            .filter(
                ApplicationStageHistory.application_id == app.id,
                ApplicationStageHistory.exited_at.is_(None),
            )
            .first()
        )
        if prev is not None:
            # Legacy Column[] attributes: assignment is correct at runtime.
            prev.exited_at = now  # type: ignore[assignment]
            if prev.entered_at:
                prev.duration_seconds = int(  # type: ignore[assignment]
                    (now - prev.entered_at).total_seconds()
                )
        db.add(
            ApplicationStageHistory(
                company_id=app.company_id,
                application_id=app.id,
                stage_slug="shortlisted",
                stage_name="Shortlisted",
                entered_at=now,
                triggered_by=recruiter.id,
                trigger_type="manual",
            )
        )
        app.status = "shortlisted"  # type: ignore[assignment]
        db.commit()
        logger.info(
            "Campaign %s: app %s shortlisted by recruiter %s",
            batch_id,
            app.id,
            recruiter.id,
        )

    return {"success": True, "status": app.status}


def _rows(db: Session, batch_id: int, company_id, scope: Scope) -> list[dict]:
    query = (
        db.query(Application)
        .options(
            selectinload(Application.evaluation_sessions).selectinload(
                EvaluationSession.evaluation_result
            )
        )
        .filter(
            Application.batch_id == batch_id,
            Application.company_id == company_id,
            Application.deleted_at.is_(None),
        )
    )
    if scope == "shortlisted":
        query = query.filter(Application.status == "shortlisted")

    rows = []
    for app in query.order_by(Application.id.asc()).all():
        es = app.evaluation_sessions[0] if app.evaluation_sessions else None
        er = es.evaluation_result if es else None
        state = (es.interview_state if es else None) or "not_started"
        cv_score = er.cv_score if er and er.cv_score is not None else app.analysis_score
        interview_score = (
            er.final_score
            if er and er.final_score and state in ("completed", "flagged")
            else None
        )
        rows.append(
            {
                "name": app.full_name or "",
                "email": app.email or "",
                "status": app.status or "",
                "cv_score": cv_score,
                "interview_score": interview_score,
                "interview_state": state,
                "applied_at": app.created_at.isoformat() if app.created_at else "",
            }
        )
    # Best score first, unscored last (matches the list's default ordering).
    rows.sort(key=_sort_key)
    return rows


def _sort_key(row: dict) -> tuple[bool, float]:
    best = _best_score(row)
    return (best is None, -(best or 0.0))


def _best_score(row: dict) -> Optional[float]:
    if row["interview_score"] is not None:
        return float(row["interview_score"])
    if row["cv_score"] is not None:
        return float(row["cv_score"])
    return None


def _csv_safe(value) -> str:
    """Neutralise spreadsheet formula injection in candidate-supplied text."""
    text = "" if value is None else str(value)
    if text and text[0] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + text
    return text


def _fmt(score) -> str:
    return "" if score is None else f"{float(score):.0f}"


@router.get("/{batch_id}/export/csv")
def export_campaign_csv(
    batch_id: int,
    scope: Scope = Query("all"),
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    batch = get_batch_for_recruiter(batch_id, recruiter, db)
    rows = _rows(db, batch_id, batch.company_id, scope)

    buf = io.StringIO()
    # UTF-8 BOM so Excel detects the encoding (accented / Arabic names).
    buf.write("\ufeff")
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(
        [
            "name",
            "email",
            "status",
            "cv_score",
            "interview_score",
            "interview_state",
            "applied_at",
        ]
    )
    for r in rows:
        writer.writerow(
            [
                _csv_safe(r["name"]),
                _csv_safe(r["email"]),
                r["status"],
                _fmt(r["cv_score"]),
                _fmt(r["interview_score"]),
                r["interview_state"],
                r["applied_at"],
            ]
        )

    filename = f"campaign_{batch_id}_{scope}.csv"
    return Response(
        content=buf.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _latin1(value) -> str:
    # Known limitation: FPDF 1.7 core fonts are latin-1 only, so non-latin-1
    # text (e.g. Arabic names) is rendered as "?" in the PDF. We never crash
    # on it; the CSV export preserves the full Unicode text.
    return str(value or "").encode("latin-1", errors="replace").decode("latin-1")


def _render_pdf(
    title: str, subtitle: str, sections: list[tuple[str, list[dict]]]
) -> bytes:
    from fpdf import FPDF

    pdf = FPDF(orientation="L", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=12)
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, _latin1(title), ln=1)
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 6, _latin1(subtitle), ln=1)
    pdf.ln(3)

    cols = (
        ("Name", 70),
        ("Email", 80),
        ("Status", 30),
        ("CV", 18),
        ("Interview", 22),
        ("Interview state", 40),
    )
    for heading, rows in sections:
        if heading:
            pdf.set_font("Helvetica", "B", 12)
            pdf.cell(0, 8, _latin1(f"{heading} ({len(rows)})"), ln=1)
        pdf.set_font("Helvetica", "B", 9)
        for label, width in cols:
            pdf.cell(width, 7, label, border=1)
        pdf.ln()
        pdf.set_font("Helvetica", "", 9)
        if not rows:
            pdf.cell(sum(w for _, w in cols), 7, "No candidates", border=1, ln=1)
        for r in rows:
            values = (
                r["name"][:40],
                r["email"][:45],
                r["status"],
                _fmt(r["cv_score"]),
                _fmt(r["interview_score"]),
                r["interview_state"],
            )
            for (_, width), value in zip(cols, values):
                pdf.cell(width, 7, _latin1(value), border=1)
            pdf.ln()
        pdf.ln(4)

    return bytes(pdf.output(dest="S"), "latin-1")


@router.get("/{batch_id}/export/pdf")
def export_campaign_pdf(
    batch_id: int,
    scope: Scope = Query("shortlisted"),
    tier: bool = Query(False),
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    batch = get_batch_for_recruiter(batch_id, recruiter, db)
    rows = _rows(db, batch_id, batch.company_id, scope)

    sections: list[tuple[str, list[dict]]]
    if tier:
        buckets: dict[str, list[dict]] = {label: [] for label, _ in _TIERS}
        unscored: list[dict] = []
        for r in rows:
            best = _best_score(r)
            if best is None:
                unscored.append(r)
                continue
            for label, floor in _TIERS:
                if best >= floor:
                    buckets[label].append(r)
                    break
        sections = [*buckets.items(), ("Not yet scored", unscored)]
    else:
        sections = [("", rows)]

    title = str(batch.title or f"Campaign {batch_id}")
    subtitle = (
        f"{'Shortlisted candidates' if scope == 'shortlisted' else 'All candidates'}"
        f" - {len(rows)} total - generated {_utcnow():%Y-%m-%d %H:%M} UTC"
    )
    content = _render_pdf(title, subtitle, sections)

    filename = f"campaign_{batch_id}_{scope}{'_tiered' if tier else ''}.pdf"
    return Response(
        content=content,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
