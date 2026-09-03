from datetime import datetime
from typing import List

from fastapi import Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from backend.database import CampaignTemplate, User
from backend.dependencies import get_db, require_recruiter
from backend.logger import logger
from backend.tenant import get_current_company_id

from . import router


class TemplateCreate(BaseModel):
    name: str
    role: str
    description: str
    subject_template: str
    body_template: str


class TemplateResponse(BaseModel):
    id: int
    name: str
    role: str
    description: str
    subject_template: str
    body_template: str
    is_default: bool
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


@router.get("/templates", response_model=List[TemplateResponse])
def get_templates(
    recruiter: User = Depends(require_recruiter), db: Session = Depends(get_db)
):
    templates = (
        db.query(CampaignTemplate)
        .filter(
            CampaignTemplate.is_active,
            (CampaignTemplate.recruiter_id == recruiter.id)
            | (CampaignTemplate.is_default),
        )
        .order_by(CampaignTemplate.is_default.desc(), CampaignTemplate.name)
        .all()
    )
    return templates


@router.post(
    "/templates", response_model=TemplateResponse, status_code=status.HTTP_201_CREATED
)
def create_template(
    data: TemplateCreate,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
    company_id: int = Depends(get_current_company_id),
):
    template = CampaignTemplate(
        recruiter_id=recruiter.id,
        company_id=company_id,
        name=data.name,
        role=data.role,
        description=data.description,
        subject_template=data.subject_template,
        body_template=data.body_template,
        is_default=False,
        is_active=True,
    )
    db.add(template)
    db.commit()
    db.refresh(template)
    logger.info(f"Template created: {template.name} by {recruiter.email}")
    return template


@router.put(
    "/templates/{template_id}", response_model=TemplateResponse
)
def update_template(
    template_id: int,
    data: TemplateCreate,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    template = (
        db.query(CampaignTemplate)
        .filter(
            CampaignTemplate.id == template_id,
            (CampaignTemplate.recruiter_id == recruiter.id)
            | (CampaignTemplate.is_default),
        )
        .first()
    )

    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    template.name = data.name
    template.role = data.role
    template.description = data.description
    template.subject_template = data.subject_template
    template.body_template = data.body_template
    db.commit()
    db.refresh(template)
    logger.info(f"Template updated: {template.name} by {recruiter.email}")
    return template


@router.delete("/templates/{template_id}")
def delete_template(
    template_id: int,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    template = (
        db.query(CampaignTemplate)
        .filter(
            CampaignTemplate.id == template_id,
            CampaignTemplate.recruiter_id == recruiter.id,
        )
        .first()
    )

    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    if template.is_default:
        raise HTTPException(status_code=400, detail="Cannot delete system templates")

    db.delete(template)
    db.commit()
    return {"success": True}


@router.post("/templates/seed-defaults")
def seed_default_templates(
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
    company_id: int = Depends(get_current_company_id),
):
    defaults = [
        {
            "name": "Software Engineer",
            "role": "Software Engineer",
            "description": "Template for software engineering roles",
            "subject_template": "Exciting Opportunity: Software Engineer Position at {{company}}",
            "body_template": """Dear {{name}},

I came across your profile and was impressed by your experience as a {{role}}. We have an exciting opportunity at our company that might be a great fit.

Role: {{role}}
Location: {{location}}
Details: {{details}}

Would you be interested in exploring this opportunity? I'd love to schedule a brief call to discuss.

Best regards""",
        },
        {
            "name": "Sales Representative",
            "role": "Sales Representative",
            "description": "Template for sales positions",
            "subject_template": "Sales Opportunity: Join Our Growing Team",
            "body_template": """Hi {{name}},

Your sales experience caught my attention. We're looking for a motivated {{role}} to join our team.

If you're passionate about sales and looking for a new challenge, let's talk!

Best regards""",
        },
        {
            "name": "Product Manager",
            "role": "Product Manager",
            "description": "Template for product management roles",
            "subject_template": "Product Manager Role - Innovative Tech Company",
            "body_template": """Hello {{name}},

I saw your background in product management and think you'd be a great fit for our team.

We're looking for a strategic {{role}} to help shape our product roadmap.

Interested in learning more?""",
        },
    ]

    for d in defaults:
        existing = (
            db.query(CampaignTemplate)
            .filter(CampaignTemplate.name == d["name"], CampaignTemplate.is_default)
            .first()
        )

        if not existing:
            template = CampaignTemplate(
                recruiter_id=None,
                company_id=company_id,
                name=d["name"],
                role=d["role"],
                description=d["description"],
                subject_template=d["subject_template"],
                body_template=d["body_template"],
                is_default=True,
                is_active=True,
            )
            db.add(template)

    db.commit()
    return {"success": True, "message": "Default templates seeded"}
