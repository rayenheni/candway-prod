"""Admin financial dashboard endpoints (Monetization S8).

manage_finance-gated: overview, revenue, customers, credits, forecast and
CSV/PDF export. All KPIs are computed live by ``AdminFinancialService`` from
existing monetization tables — no new infrastructure.
"""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from backend.admin_financial_service import AdminFinancialService
from backend.database import User
from backend.dependencies import get_current_user, get_db
from backend.logger import logger
from backend.routers.admin.common import check_permission

router = APIRouter(tags=["admin"])


@router.get("/finance/overview")
def finance_overview(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    check_permission(current_user, "manage_finance")
    return AdminFinancialService.get_overview(db)


@router.get("/finance/revenue")
def finance_revenue(
    months: int = 6,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    check_permission(current_user, "manage_finance")
    if months > 24:
        months = 24
    return AdminFinancialService.get_revenue(db, months)


@router.get("/finance/customers")
def finance_customers(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    check_permission(current_user, "manage_finance")
    return AdminFinancialService.get_customers(db)


@router.get("/finance/credits")
def finance_credits(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    check_permission(current_user, "manage_finance")
    return AdminFinancialService.get_credits(db)


@router.get("/finance/forecast")
def finance_forecast(
    months: int = 3,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    check_permission(current_user, "manage_finance")
    if months > 12:
        months = 12
    return AdminFinancialService.get_forecast(db, months)


@router.get("/finance/export")
def finance_export(
    section: str = "overview",
    format: str = "csv",  # noqa: A002 - query param named `format`
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Export financial data as CSV or PDF."""
    check_permission(current_user, "manage_finance")

    if section not in ("revenue", "customers", "credits", "overview"):
        raise HTTPException(status_code=400, detail="Invalid export section")

    try:
        if format == "pdf":
            if section == "overview":
                content = AdminFinancialService.export_pdf(db, section)
            else:
                content = AdminFinancialService.export_pdf(db, "overview")
                # PDF export always renders the composite summary.
                logger.info(f"PDF export requested for section {section}")
            if not content:
                raise HTTPException(status_code=500, detail="PDF generation failed")
            stamp = datetime.now(UTC).strftime("%Y%m%d")
            return Response(
                content=content,
                media_type="application/pdf",
                headers={
                    "Content-Disposition": (
                        f'attachment; filename="candway-finance-{section}-{stamp}.pdf"'
                    )
                },
            )

        # CSV (default)
        content = AdminFinancialService.export_csv(db, section)
        stamp = datetime.now(UTC).strftime("%Y%m%d")
        return Response(
            content=content,
            media_type="text/csv; charset=utf-8",
            headers={
                "Content-Disposition": (
                    f'attachment; filename="candway-finance-{section}-{stamp}.csv"'
                )
            },
        )
    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001
        logger.error(f"finance_export failed (section={section}, format={format}): {e}")
        raise HTTPException(status_code=500, detail="Export failed")
