from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy.orm import Session

from backend.database import Coupon, SalesLead, User
from backend.dependencies import get_current_user, get_db
from backend.email_service import email_service
from backend.profile_helpers import get_user_email, get_user_name
from backend.routers.admin.common import check_permission, paginate
from backend.schemas import CouponCreate, MarketingCampaign

marketing_router = APIRouter()


# --- MARKETING ---
@marketing_router.get("/marketing/leads")
def get_marketing_leads(
    page: int = 1,
    per_page: int = 30,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    check_permission(current_user, "view_analytics")
    query = db.query(SalesLead).order_by(SalesLead.created_at.desc())
    result = paginate(query, page, per_page)
    return {
        "total": result["total"],
        "page": result["page"],
        "per_page": result["per_page"],
        "total_pages": result["total_pages"],
        "leads": [
            {
                "id": item.id,
                "email": item.email,
                "name": item.name,
                "company": item.company,
                "status": item.status,
                "created_at": item.created_at.isoformat() if item.created_at else None,
            }
            for item in result["items"]
        ],
    }


@marketing_router.post("/marketing/send")
def send_marketing_campaign(
    campaign: MarketingCampaign,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # P0-07 FIX: Sending a bulk marketing campaign is a legal /
    # financial action, not a content action. A user with the
    # "manage_content" permission can edit blog posts but should
    # NOT be able to email the entire userbase. Use the dedicated
    # "manage_marketing" permission so this is auditable and
    # reversible.
    check_permission(current_user, "manage_marketing")
    users = db.query(User).filter(User.role != "admin").all()
    recipients = [
        {"email": get_user_email(u), "name": get_user_name(u)}
        for u in users
        if get_user_email(u)
    ]
    background_tasks.add_task(
        email_service.send_bulk_emails, recipients, campaign.subject, campaign.content
    )
    return {"message": f"Queued for {len(recipients)} users"}


# --- COUPONS ---
@marketing_router.get("/coupons")
def get_coupons(
    page: int = 1,
    per_page: int = 30,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    check_permission(current_user, "manage_finance")
    query = db.query(Coupon)
    result = paginate(query, page, per_page)
    return {
        "total": result["total"],
        "page": result["page"],
        "per_page": result["per_page"],
        "total_pages": result["total_pages"],
        "coupons": [
            {
                "id": c.id,
                "code": c.code,
                "discount_percent": c.discount_percent,
                "expires_in_days": c.expires_in_days,
                "is_active": c.is_active,
                "created_at": c.created_at.isoformat() if c.created_at else None,
            }
            for c in result["items"]
        ],
    }


@marketing_router.post("/coupons")
def create_coupon(
    coupon: CouponCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    check_permission(current_user, "manage_finance")
    expires = (
        datetime.now(UTC) + timedelta(days=coupon.expires_in_days)
        if coupon.expires_in_days
        else None
    )
    new_coupon = Coupon(
        code=coupon.code.upper(),
        discount_percent=coupon.discount_percent,
        max_uses=coupon.max_uses,
        expires_at=expires,
        is_active=True,
    )
    db.add(new_coupon)
    db.commit()
    return {"message": "Coupon created"}


@marketing_router.delete("/coupons/{coupon_id}")
def delete_coupon(
    coupon_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    check_permission(current_user, "manage_finance")
    cp = db.query(Coupon).filter(Coupon.id == coupon_id).first()
    if cp:
        db.delete(cp)
        db.commit()
    return {"message": "Deleted"}
