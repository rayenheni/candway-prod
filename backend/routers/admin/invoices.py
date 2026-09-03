import io
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from backend.database import CompanyVerification, Invoice, Transaction, User
from backend.dependencies import get_current_user, get_db
from backend.pdf_generator import generate_invoice_pdf
from backend.routers.admin.common import check_permission, paginate
from backend.schemas import InvoiceCreate, InvoiceUpdate

router = APIRouter(tags=["admin"])


def _create_invoice_internal(
    db: Session,
    user_id: int,
    amount: float,
    transaction_id: int = None,
    is_ttc: bool = True,
    company_id: int = None,
):
    tva_rate = 19.0
    stamp_duty = 1.000

    tx = None
    if transaction_id:
        tx = db.query(Transaction).filter(Transaction.id == transaction_id).first()

    if tx and tx.amount_ht > 0:
        amount_ht = tx.amount_ht
        tva_amount = tx.tva_amount
        total_ttc = tx.amount_ttc
    else:
        if is_ttc:
            if amount > stamp_duty:
                amount_ht = (amount - stamp_duty) / (1 + (tva_rate / 100))
                tva_amount = amount_ht * (tva_rate / 100)
                total_ttc = amount
            else:
                amount_ht = 0.0
                tva_amount = 0.0
                total_ttc = amount
        else:
            amount_ht = amount
            tva_amount = amount_ht * (tva_rate / 100)
            total_ttc = amount_ht + tva_amount + stamp_duty

    year = datetime.now(UTC).year
    last_invoice = (
        db.query(Invoice)
        .filter(Invoice.invoice_number.like(f"INV-{year}-%"))
        .order_by(Invoice.id.desc())
        .with_for_update()
        .first()
    )

    if last_invoice:
        try:
            last_seq = int(last_invoice.invoice_number.split("-")[-1])
            new_seq = last_seq + 1
        except (ValueError, IndexError):
            new_seq = 1
    else:
        new_seq = 1

    invoice_number = f"INV-{year}-{new_seq:04d}"

    client = db.query(User).filter(User.id == user_id).first()
    if not client:
        return None

    kyb = (
        db.query(CompanyVerification)
        .filter(
            CompanyVerification.user_id == client.id,
            CompanyVerification.status == "approved",
        )
        .first()
    )
    client_mf = kyb.matricule_fiscale if kyb else None

    new_invoice = Invoice(
        invoice_number=invoice_number,
        user_id=user_id,
        company_id=company_id,
        transaction_id=transaction_id,
        amount_ht=amount_ht,
        tva_rate=tva_rate,
        tva_amount=tva_amount,
        stamp_duty=stamp_duty,
        total_ttc=total_ttc,
        client_name=kyb.company_name if kyb else client.name,
        client_mf=client_mf,
        client_address=kyb.address if kyb else "N/A",
        status="paid",
    )

    db.add(new_invoice)
    db.commit()
    db.refresh(new_invoice)
    return new_invoice


@router.post("/invoices/generate")
def generate_tunisian_invoice(
    invoice_data: InvoiceCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    check_permission(current_user, "manage_finance")

    tva_rate = 19.0
    stamp_duty = 1.000

    amount_ht = invoice_data.amount_ht
    tva_amount = amount_ht * (tva_rate / 100)
    total_ttc = amount_ht + tva_amount + stamp_duty

    year = datetime.now(UTC).year
    last_invoice = (
        db.query(Invoice)
        .filter(Invoice.invoice_number.like(f"INV-{year}-%"))
        .order_by(Invoice.id.desc())
        .with_for_update()
        .first()
    )

    if last_invoice:
        try:
            last_seq = int(last_invoice.invoice_number.split("-")[-1])
            new_seq = last_seq + 1
        except (ValueError, IndexError):
            new_seq = 1
    else:
        new_seq = 1

    invoice_number = f"INV-{year}-{new_seq:04d}"

    client = db.query(User).filter(User.id == invoice_data.user_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client user not found")

    kyb = (
        db.query(CompanyVerification)
        .filter(
            CompanyVerification.user_id == client.id,
            CompanyVerification.status == "approved",
        )
        .first()
    )
    client_mf = kyb.matricule_fiscale if kyb else None

    new_invoice = Invoice(
        invoice_number=invoice_number,
        user_id=invoice_data.user_id,
        company_id=invoice_data.company_id,
        transaction_id=invoice_data.transaction_id,
        amount_ht=amount_ht,
        tva_rate=tva_rate,
        tva_amount=tva_amount,
        stamp_duty=stamp_duty,
        total_ttc=total_ttc,
        client_name=kyb.company_name if kyb else client.name,
        client_mf=client_mf,
        client_address=kyb.address if kyb else "N/A",
        status="unpaid",
    )

    db.add(new_invoice)
    db.commit()
    db.refresh(new_invoice)

    return new_invoice


@router.get("/invoices")
def get_all_invoices(
    page: int = 1,
    per_page: int = 30,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    check_permission(current_user, "manage_finance")
    query = db.query(Invoice).order_by(Invoice.created_at.desc())
    result = paginate(query, page, per_page)
    return {
        "total": result["total"],
        "page": result["page"],
        "per_page": result["per_page"],
        "total_pages": result["total_pages"],
        "invoices": result["items"],
    }


@router.get("/invoices/{invoice_id}/download")
async def download_invoice_pdf(
    invoice_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        check_permission(current_user, "manage_finance")

        invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
        if not invoice:
            raise HTTPException(status_code=404, detail="Invoice not found")

        pdf_data = {
            "invoice_number": invoice.invoice_number,
            "date": invoice.created_at.strftime("%Y-%m-%d")
            if invoice.created_at
            else "N/A",
            "client_name": invoice.client_name or "Valued Client",
            "client_mf": invoice.client_mf or "N/A",
            "client_address": invoice.client_address or "N/A",
            "amount_ht": invoice.amount_ht or 0.0,
            "tva_rate": invoice.tva_rate or 19.0,
            "tva_amount": invoice.tva_amount or 0.0,
            "stamp_duty": invoice.stamp_duty or 1.0,
            "total_ttc": invoice.total_ttc or 0.0,
            "status": invoice.status or "paid",
            "transaction_id": invoice.transaction_id or "N/A",
            "description": "Candway Talent Intelligence Platform - Professional Services",
        }

        pdf_bytes = generate_invoice_pdf(pdf_data)

        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename=Invoice_{invoice.invoice_number}.pdf",
                "Cache-Control": "no-cache",
            },
        )
    except Exception as e:
        import logging

        logger = logging.getLogger("uvicorn")
        logger.error(f"Invoice Download Error: {str(e)}")
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail="Failed to generate invoice PDF")


@router.get("/invoices/{invoice_id}/xml")
def download_invoice_xml(
    invoice_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    check_permission(current_user, "manage_finance")

    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    from backend.xml_generator import generate_teif_xml

    xml_data = {
        "invoice_number": invoice.invoice_number,
        "date": invoice.created_at.strftime("%Y-%m-%d"),
        "client_name": invoice.client_name,
        "client_mf": invoice.client_mf,
        "amount_ht": invoice.amount_ht,
        "tva_amount": invoice.tva_amount,
        "total_ttc": invoice.total_ttc,
        "transaction_id": invoice.transaction_id,
    }

    xml_bytes = generate_teif_xml(xml_data)

    return Response(
        content=xml_bytes,
        media_type="application/xml",
        headers={
            "Content-Disposition": f"attachment; filename=Invoice_{invoice.invoice_number}.xml"
        },
    )


@router.put("/invoices/{invoice_id}")
def update_invoice(
    invoice_id: int,
    invoice_data: InvoiceUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    check_permission(current_user, "manage_finance")

    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    update_data = invoice_data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(invoice, key, value)

    db.commit()
    db.refresh(invoice)
    return invoice
