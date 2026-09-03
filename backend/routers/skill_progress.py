import json

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.dependencies import get_current_user
from backend.models.evaluation.profile import CandidateProfile, RecruiterProfile

router = APIRouter()

SKILL_CATEGORIES = {
    "React": "Frontend",
    "Vue": "Frontend",
    "Angular": "Frontend",
    "Svelte": "Frontend",
    "TypeScript": "Frontend",
    "JavaScript": "Frontend",
    "CSS": "Frontend",
    "HTML": "Frontend",
    "Tailwind": "Frontend",
    "Next.js": "Frontend",
    "Webpack": "Frontend",
    "Redux": "Frontend",
    "Node.js": "Backend",
    "Python": "Backend",
    "Django": "Backend",
    "Flask": "Backend",
    "FastAPI": "Backend",
    "Express": "Backend",
    "Go": "Backend",
    "Rust": "Backend",
    "Java": "Backend",
    "C#": "Backend",
    "PHP": "Backend",
    "Ruby": "Backend",
    "GraphQL": "Backend",
    "REST": "Backend",
    "PostgreSQL": "Backend",
    "MySQL": "Backend",
    "MongoDB": "Backend",
    "Redis": "Backend",
    "SQL": "Backend",
    "Docker": "Tools & DevOps",
    "Kubernetes": "Tools & DevOps",
    "AWS": "Tools & DevOps",
    "Azure": "Tools & DevOps",
    "GCP": "Tools & DevOps",
    "CI/CD": "Tools & DevOps",
    "Git": "Tools & DevOps",
    "Linux": "Tools & DevOps",
    "Terraform": "Tools & DevOps",
    "Nginx": "Tools & DevOps",
    "Jenkins": "Tools & DevOps",
    "Communication": "Soft Skills",
    "Leadership": "Soft Skills",
    "Problem Solving": "Soft Skills",
    "Teamwork": "Soft Skills",
    "Project Management": "Soft Skills",
    "Agile": "Soft Skills",
}


def derive_categories(skill_list: list[str]) -> list[dict]:
    result = []
    for name in skill_list:
        cat = SKILL_CATEGORIES.get(name, "Other")
        result.append({"name": name, "category": cat})
    return result


@router.get("/skill-progress")
def get_skill_progress(
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if user.role == "candidate":
        profile = (
            db.query(CandidateProfile)
            .filter(CandidateProfile.user_id == user.id)
            .first()
        )
        skills_raw = profile.skills if profile else None
    elif user.role == "recruiter":
        profile = (
            db.query(RecruiterProfile)
            .filter(RecruiterProfile.user_id == user.id)
            .first()
        )
        skills_raw = None
    else:
        skills_raw = None

    skill_entries = []
    if skills_raw:
        try:
            parsed = (
                json.loads(skills_raw) if isinstance(skills_raw, str) else skills_raw
            )
            if isinstance(parsed, list):
                skill_entries = derive_categories(parsed)
        except (json.JSONDecodeError, TypeError):
            pass

    categories_map: dict[str, list] = {}
    for entry in skill_entries:
        categories_map.setdefault(entry["category"], []).append(
            {
                "name": entry["name"],
                "level": 80,
                "trend": "+0",
                "verified": False,
            }
        )

    categories = [{"name": k, "skills": v} for k, v in categories_map.items()]
    total = sum(len(c["skills"]) for c in categories)
    avg = 80 if total else 0
    return {
        "categories": categories,
        "stats": {
            "total_skills": total,
            "avg_level": avg,
            "verified_count": 0,
            "improving_count": 0,
        },
    }
