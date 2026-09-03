# Onboarding API Endpoints
# Provides CV analysis and calibration questions for onboarding flow
# Enhanced: robust error handling, structured fallbacks, cleaner async patterns

import asyncio
import copy
import json
import logging
import re
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session, selectinload

from backend.ai.llm import call_groq_cascade
from backend.ai.privacy import scrub_pii
from backend.config import get_settings
from backend.cv_service import extract_text_from_file
from backend.database import Application, EvaluationSession, User
from backend.dependencies import get_current_user, get_db
from backend.entity_writer import sync_ai_interview_session, sync_cv_document
from backend.models.ats.types import ApplicationType
from backend.profile_helpers import get_user_email, get_user_name
from backend.scoring_service import ScoringService
from backend.services.application_service import ApplicationService

router = APIRouter(prefix="/onboarding", tags=["onboarding"])
logger = logging.getLogger(__name__)
settings = get_settings()


# ─────────────────────────────────────────────
# REQUEST / RESPONSE MODELS
# ─────────────────────────────────────────────


class AnalyzeCVRequest(BaseModel):
    file_content: str = Field(..., description="Base64-encoded file content")
    file_name: str = Field(..., min_length=1)
    declared_role: str = Field(..., min_length=1)

    @field_validator("file_name")
    @classmethod
    def validate_extension(cls, v: str) -> str:
        allowed = {".pdf", ".docx", ".doc", ".txt"}
        ext = "." + v.rsplit(".", 1)[-1].lower() if "." in v else ""
        if ext not in allowed:
            raise ValueError(
                f"Unsupported file type '{ext}'. Use PDF, DOCX, DOC, or TXT."
            )
        return v


class CalibrationRequest(BaseModel):
    application_id: Optional[int] = None
    role: str = Field(..., min_length=1)
    skills: List[str] = Field(default_factory=list)
    level: str = Field(default="Mid")
    cv_summary: str = Field(default="")
    intelligence_layer: Optional[Dict[str, Any]] = Field(default_factory=dict)

    @field_validator("level")
    @classmethod
    def validate_level(cls, v: str) -> str:
        allowed = {"Junior", "Mid", "Senior"}
        if v not in allowed:
            return "Mid"
        return v


class CalibrationAnswers(BaseModel):
    application_id: int
    role: str = Field(..., min_length=1)
    skills: List[str] = Field(default_factory=list)
    level: str = Field(default="Mid")
    answers: List[Dict[str, Any]] = Field(..., min_length=1)

    @field_validator("answers")
    @classmethod
    def validate_answers(cls, v: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        for i, ans in enumerate(v):
            if not isinstance(ans, dict):
                raise ValueError(f"Answer at index {i} must be a dict")
            if "answer" not in ans:
                raise ValueError(f"Answer at index {i} must contain 'answer' key")
        return v


class SaveCalibrationRequest(BaseModel):
    application_id: int
    score: Optional[float] = None
    strengths: List[str] = Field(default_factory=list)
    weaknesses: List[str] = Field(default_factory=list)
    feedback: Optional[str] = None
    answers: List[Dict[str, Any]] = Field(default_factory=list)
    questions: List[Dict[str, Any]] = Field(default_factory=list)
    skills_verified: List[str] = Field(default_factory=list)
    level: Optional[str] = None
    language: Optional[str] = "English"
    motivation: Optional[str] = ""


# ─────────────────────────────────────────────
# GROQ CLIENT HELPER
# ─────────────────────────────────────────────


async def groq_complete(
    messages: List[Dict],
    max_tokens: int = 1000,
    temperature: float = 0.2,
    json_mode: bool = True,
    timeout: float = 30.0,
) -> Optional[str]:
    """
    Centralized Groq completion wrapper (uses resilient cascade).
    """
    try:
        result = await asyncio.wait_for(
            call_groq_cascade(
                messages,
                temperature=temperature,
                max_tokens=max_tokens,
                json_mode=json_mode,
            ),
            timeout=timeout,
        )
        if isinstance(result, dict):
            return json.dumps(result)
        return result
    except asyncio.TimeoutError:
        logger.warning(f"[Onboarding] AI completion timed out after {timeout}s")
        return None
    except Exception as e:
        logger.error(f"[Onboarding] AI completion failed: {e}")
        return None


def safe_json(content: Optional[str]) -> Optional[Dict]:
    """Parse JSON safely, returning None on failure."""
    if not content:
        return None
    try:
        return json.loads(content)
    except json.JSONDecodeError as e:
        logger.warning("JSON parse error: %s | content[:200]=%s", e, content[:200])
        return None


# ─────────────────────────────────────────────
# CV PARSING
# ─────────────────────────────────────────────

_CV_SCHEMA = """{
    "personal_info": {"name": "", "email": "", "phone": "", "location": ""},
    "experiences": [
        {"title": "", "company": "", "duration": "", "description": "", "achievements": []}
    ],
    "projects": [
        {"name": "", "role": "", "description": "", "technologies": [], "outcome": ""}
    ],
    "skills": {
        "technical": [],
        "tools": [],
        "soft": [],
        "languages": []
    },
    "education": [
        {"degree": "", "institution": "", "year": "", "gpa": ""}
    ],
    "certifications": [],
    "summary": ""
}"""

_CV_EMPTY: Dict[str, Any] = {
    "personal_info": {},
    "experiences": [],
    "projects": [],
    "skills": {"technical": [], "tools": [], "soft": [], "languages": []},
    "education": [],
    "certifications": [],
    "summary": "",
}


async def parse_cv(cv_text: str) -> Dict[str, Any]:
    """
    Parse raw CV text into structured data.
    Returns a well-typed dict; never raises.
    """
    prompt = (
        f"You are a CV Parsing Expert. Extract structured information from this CV.\n\n"
        f"CV TEXT:\n{cv_text[:4000]}\n\n"
        f"Return ONLY valid JSON matching this schema exactly:\n{_CV_SCHEMA}\n\n"
        "RULES:\n"
        "- Extract ONLY what is explicitly stated in the CV.\n"
        "- Do NOT infer, guess, or hallucinate.\n"
        "- Use empty arrays/objects when data is absent.\n"
        "- Maximum 5 entries per list category."
    )

    content = await groq_complete(
        messages=[
            {
                "role": "system",
                "content": "You are an expert CV parser. Return only valid JSON.",
            },
            {"role": "user", "content": prompt},
        ],
        max_tokens=1500,
        temperature=0.1,
    )

    parsed = safe_json(content)
    if not parsed:
        logger.warning("CV parsing returned no usable data; using empty structure.")
        return copy.deepcopy(_CV_EMPTY)

    result = copy.deepcopy(_CV_EMPTY)
    result.update(parsed)
    return result


# ─────────────────────────────────────────────
# INTELLIGENCE LAYER
# ─────────────────────────────────────────────

# Role → required baseline skills
_ROLE_SKILLS: Dict[str, List[str]] = {
    "Software Engineer": [
        "Python",
        "JavaScript",
        "React",
        "Node.js",
        "SQL",
        "Git",
        "Docker",
        "Algorithms",
    ],
    "Frontend Developer": [
        "JavaScript",
        "React",
        "CSS",
        "HTML",
        "TypeScript",
        "Redux",
        "Web Performance",
    ],
    "Backend Developer": [
        "Python",
        "Node.js",
        "SQL",
        "PostgreSQL",
        "REST API",
        "Docker",
        "Redis",
        "Security",
    ],
    "Fullstack Developer": [
        "React",
        "Node.js",
        "JavaScript",
        "SQL",
        "Git",
        "CSS",
        "TypeScript",
        "API Design",
    ],
    "Mobile Developer": [
        "React Native",
        "Flutter",
        "Swift",
        "Kotlin",
        "Mobile UI",
        "Firebase",
    ],
    "Data Scientist": [
        "Python",
        "SQL",
        "Machine Learning",
        "TensorFlow",
        "Statistics",
        "Pandas",
        "NLP",
    ],
    "Data Analyst": [
        "SQL",
        "Python",
        "Excel",
        "Tableau",
        "PowerBI",
        "Statistics",
        "Data Cleaning",
    ],
    "Product Manager": [
        "Roadmapping",
        "User Research",
        "Agile",
        "Jira",
        "Prioritization",
        "Product Discovery",
    ],
    "Marketing Manager": [
        "SEO",
        "Google Analytics",
        "Social Media",
        "CRM",
        "Content Strategy",
        "Email Marketing",
    ],
    "DevOps": [
        "Docker",
        "Kubernetes",
        "AWS",
        "CI/CD",
        "Linux",
        "Terraform",
        "Monitoring",
        "Shell Scripting",
    ],
    "Designer": [
        "Figma",
        "UI Design",
        "UX Research",
        "Prototyping",
        "Adobe XD",
        "Design Systems",
    ],
    "Quality Assurance": [
        "Automation Testing",
        "Selenium",
        "Jest",
        "Manual Testing",
        "Bug Reporting",
        "Cypress",
    ],
    "Sales / Account Manager": [
        "CRM",
        "Negotiation",
        "Salesforce",
        "Lead Generation",
        "Communication",
    ],
    "HR / Recruiter": [
        "Sourcing",
        "Interviewing",
        "ATS",
        "Employer Branding",
        "Talent Management",
    ],
    "Community Manager": [
        "Social Media Strategy",
        "Engagement",
        "Content Creation",
        "Moderation",
        "Analytics",
        "Brand Voice",
    ],
}


def _get_required_skills(role: str) -> List[str]:
    if not role:
        return []

    if role in _ROLE_SKILLS:
        return _ROLE_SKILLS[role]

    role_lower = role.lower()

    aliases = {
        "frontend": "Frontend Developer",
        "backend": "Backend Developer",
        "fullstack": "Fullstack Developer",
        "full-stack": "Fullstack Developer",
        "mobile": "Mobile Developer",
        "web developer": "Software Engineer",
        "software developer": "Software Engineer",
        "qa": "Quality Assurance",
        "quality assurance": "Quality Assurance",
        "tester": "Quality Assurance",
        "designer": "Designer",
        "ux designer": "Designer",
        "ui designer": "Designer",
        "data scientist": "Data Scientist",
        "data engineer": "Data Scientist",
        "data analyst": "Data Analyst",
        "marketing manager": "Marketing Manager",
        "product manager": "Product Manager",
        "hr": "HR / Recruiter",
        "recruiter": "HR / Recruiter",
        "community manager": "Community Manager",
        "social media manager": "Community Manager",
        "digital marketing": "Marketing Manager",
    }

    for key, target in aliases.items():
        if re.search(r"\b" + re.escape(key) + r"\b", role_lower):
            return _ROLE_SKILLS[target]

    if any(k in role_lower for k in ["tech", "software", "comput", "info"]):
        return _ROLE_SKILLS["Software Engineer"]

    return []


# Experience count → seniority heuristic
def _estimate_level(experiences: List[Dict]) -> str:
    n = len(experiences)
    if n >= 5:
        return "Senior"
    if n >= 2:
        return "Mid"
    return "Junior"


def generate_intelligence_layer(
    role: str,
    cv_data: Dict[str, Any],
    user_skills: List[str],
    level: str,
    skills_with_confidence: List[dict] = None,
) -> Dict[str, Any]:
    """
    Derive strengths, gaps, and verification targets from parsed CV + user-supplied skills.
    Enhanced version includes evidence quotes and confidence scores.
    """
    skills_section = cv_data.get("skills", {})
    cv_skills_flat_raw = (
        skills_section.get("technical", [])
        + skills_section.get("tools", [])
        + skills_section.get("soft", [])
    )

    # Normalize CV skills
    cv_skills_flat = []
    for s in cv_skills_flat_raw:
        if isinstance(s, str):
            cv_skills_flat.append(s)
        elif isinstance(s, dict):
            cv_skills_flat.append(s.get("name") or s.get("skill") or str(s))
        elif s:
            cv_skills_flat.append(str(s))

    cv_lower = {s.lower() for s in cv_skills_flat if isinstance(s, str)}

    # Normalize user skills (should already be strings but let's be safe)
    user_skills_clean = []
    for s in user_skills:
        if isinstance(s, str):
            user_skills_clean.append(s)
        elif isinstance(s, dict):
            user_skills_clean.append(s.get("name") or s.get("skill") or str(s))
        elif s:
            user_skills_clean.append(str(s))

    {s.lower(): s for s in user_skills_clean if isinstance(s, str)}

    cv_verified = [s for s in user_skills_clean if s.lower() in cv_lower]
    user_added = [s for s in user_skills_clean if s.lower() not in cv_lower]

    required = _get_required_skills(role)
    gaps = [
        s for s in required if s.lower() not in {u.lower() for u in user_skills_clean}
    ]

    estimated_level = _estimate_level(cv_data.get("experiences", []))
    confidence = min(100, len(cv_verified) * 20) if cv_verified else 0

    # Build enhanced strengths with evidence
    extracted_strengths = []
    if skills_with_confidence:
        for s in skills_with_confidence[:8]:
            extracted_strengths.append(
                {
                    "skill": s.get("skill", "") or s.get("name", ""),
                    "confidence": s.get("confidence", 50),
                    "evidence": s.get("evidence", "")[:100],
                    "category": s.get("category", "technical"),
                }
            )
    else:
        # Fallback to simple list
        extracted_strengths = [
            {
                "skill": s,
                "confidence": 70,
                "evidence": "From CV",
                "category": "technical",
            }
            for s in cv_verified[:5]
        ]

    # Calculate CV quality score
    cv_quality_elements = (
        len(cv_data.get("experiences", [])) * 10
        + len(cv_data.get("projects", [])) * 15
        + len(cv_data.get("skills", {}).get("technical", [])) * 5
        + len(cv_data.get("education", [])) * 5
    )
    cv_quality_score = min(100, cv_quality_elements)

    return {
        "cv_quality_score": cv_quality_score,
        "extracted_strengths": extracted_strengths,
        "strengths": cv_verified[:5] or user_skills[:5],
        "weaknesses": gaps[:3],
        "missing_critical_skills": [
            {
                "skill": g,
                "reason": f"Not in CV but required for {role}",
                "priority": "high" if g in required[:2] else "medium",
            }
            for g in gaps[:3]
        ],
        "skills_to_verify": user_added[:3],
        "estimated_level": estimated_level,
        "confidence_score": confidence,
        "skill_sources": {
            "cv_verified": cv_verified,
            "user_added": user_added,
            "cv_skills": cv_skills_flat[:10],
        },
    }


# ─────────────────────────────────────────────
# ROLE-BASED FALLBACK QUESTIONS
# ─────────────────────────────────────────────

_FALLBACK_QUESTIONS: Dict[str, List[Dict[str, str]]] = {
    "Software Engineer": [
        {
            "type": "qcm",
            "question": "Which architecture is best suited for a system requiring independent scaling of components and high fault tolerance?",
            "options": [
                "A. Monolithic Architecture",
                "B. Microservices Architecture",
                "C. Serverless only",
                "D. Single Database instance",
            ],
            "correct_answer": "Microservices Architecture",
        },
        {
            "type": "qcm",
            "question": "A production API is suddenly 300% slower. What is the first step in a professional debugging workflow?",
            "options": [
                "A. Restart the server immediately",
                "B. Check monitoring logs and latency metrics",
                "C. Rewrite the slow endpoint",
                "D. Increase the database size",
            ],
            "correct_answer": "Check monitoring logs and latency metrics",
        },
        {
            "type": "qcm",
            "question": "When is it most appropriate to choose a NoSQL database over a Relational (SQL) database?",
            "options": [
                "A. When strict ACID compliance is the only priority",
                "B. When handling unstructured data with high horizontal scalability needs",
                "C. When you have exactly 1000 users",
                "D. For simple blog sites",
            ],
            "correct_answer": "When handling unstructured data with high horizontal scalability needs",
        },
    ],
    "Data Scientist": [
        {
            "type": "qcm",
            "question": "Which algorithm is generally more robust against over-fitting on small datasets?",
            "options": [
                "A. Deep Neural Network",
                "B. Random Forest",
                "C. Simple Linear Regression",
                "D. K-Means Clustering",
            ],
            "correct_answer": "Random Forest",
        },
        {
            "type": "qcm",
            "question": "How should you handle a feature with 40% missing values in a critical dataset?",
            "options": [
                "A. Delete the entire column",
                "B. Impute with mean/median or use a model-based imputation",
                "C. Ignore the missing values",
                "D. Fill with zeros",
            ],
            "correct_answer": "Impute with mean/median or use a model-based imputation",
        },
    ],
    "Product Manager": [
        {
            "type": "qcm",
            "question": "Which framework is most effective for prioritizing 10 feature requests with limited resources?",
            "options": [
                "A. First-come, first-served",
                "B. RICE (Reach, Impact, Confidence, Effort)",
                "C. CEO preference",
                "D. Random selection",
            ],
            "correct_answer": "RICE (Reach, Impact, Confidence, Effort)",
        }
    ],
    "Marketing Manager": [
        {
            "type": "qcm",
            "question": "If your marketing budget is cut by 50%, where should you prioritize spending to protect the immediate pipeline?",
            "options": [
                "A. Brand awareness campaigns",
                "B. High-intent conversion channels (e.g. SEM)",
                "C. New market research",
                "D. Hiring more staff",
            ],
            "correct_answer": "High-intent conversion channels (e.g. SEM)",
        }
    ],
    "DevOps": [
        {
            "type": "qcm",
            "question": "What is the primary indicator of a Kubernetes pod being in a 'CrashLoopBackOff' state?",
            "options": [
                "A. The pod is running too fast",
                "B. The container is failing and being restarted repeatedly",
                "C. The node is out of disk space",
                "D. Network latency is high",
            ],
            "correct_answer": "The container is failing and being restarted repeatedly",
        }
    ],
}

_DEFAULT_FALLBACK = [
    {
        "type": "qcm",
        "question": "Which of the following is a primary benefit of using a Load Balancer?",
        "options": [
            "A. Increased latency",
            "B. Single point of failure",
            "C. Distributed traffic",
            "D. Direct DB access",
        ],
        "correct_answer": "Distributed traffic",
    },
    {
        "type": "qcm",
        "question": "In a professional environment, how should you handle a high-priority bug?",
        "options": [
            "A. Ignore it",
            "B. Document and triage",
            "C. Wait for the weekend",
            "D. Delete the code",
        ],
        "correct_answer": "Document and triage",
    },
    {
        "type": "qcm",
        "question": "What does ACID stand for in database transactions?",
        "options": [
            "A. Atomicity, Consistency, Isolation, Durability",
            "B. Availability, Consistency, Integrity, Delivery",
            "C. Access, Control, Index, Data",
            "D. None of the above",
        ],
        "correct_answer": "Atomicity, Consistency, Isolation, Durability",
    },
]

_GENERIC_SUBSTRINGS = frozenset(
    [
        "tell me about yourself",
        "what is your greatest strength",
        "where do you see yourself",
        "why do you want to work",
    ]
)


def get_fallback_questions(role: str, level: str) -> List[Dict[str, str]]:
    base = _FALLBACK_QUESTIONS.get(role, _DEFAULT_FALLBACK)
    if level == "Junior":
        return [
            q for q in base if q.get("type") != "qcm" or len(q.get("options", [])) <= 4
        ][:3] or base[:3]
    return base[:3]


def _is_generic(question: str) -> bool:
    q_lower = question.lower()
    return any(pat in q_lower for pat in _GENERIC_SUBSTRINGS)


def _normalise_questions(raw: Any, role: str, level: str) -> List[Dict[str, Any]]:
    questions: List[Dict[str, Any]] = []

    if isinstance(raw, dict):
        items = raw.get("questions", [])
    elif isinstance(raw, list):
        items = raw
    else:
        items = []

    for item in items[:3]:
        if isinstance(item, str) and item.strip():
            if not _is_generic(item):
                questions.append(
                    {"type": "skill_verification", "question": item.strip()}
                )
        elif isinstance(item, dict):
            q = item.get("question", "")
            t = item.get("type", "qcm")
            opts = item.get("options", [])
            ans = item.get("correct_answer", "")

            if q and not _is_generic(q):
                validated_opts = [o for o in opts if isinstance(o, str) and o.strip()][
                    :4
                ]
                questions.append(
                    {
                        "type": t,
                        "question": q,
                        "options": validated_opts if validated_opts else [],
                        "correct_answer": ans if isinstance(ans, str) else "",
                    }
                )

    if len(questions) < 3:
        logger.info(
            "AI questions insufficient (%d); appending role-based fallback.",
            len(questions),
        )
        fallback = get_fallback_questions(role, level)
        needed = 3 - len(questions)
        questions.extend(fallback[:needed])

    return questions[:3]


# ─────────────────────────────────────────────
# ENDPOINTS
# ─────────────────────────────────────────────


@router.post("/analyze-cv-json", summary="Parse and analyse a CV")
async def analyze_cv_json(
    request: AnalyzeCVRequest,
    current_user: Optional[User] = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Accepts a base64-encoded CV file, extracts text, runs AI analysis,
    and returns a structured profile with an intelligence layer.
    """
    import base64

    logger.info(
        "[CV] analyze-cv-json | file=%s role=%s user=%s",
        request.file_name,
        request.declared_role,
        current_user.id if current_user else "anon",
    )

    # ── Decode ──
    try:
        content = base64.b64decode(request.file_content)
    except Exception:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Invalid base64 file encoding."
        )

    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "File exceeds 10 MB limit.")

    # ── Extract text ──
    try:
        cv_text = extract_text_from_file(content, request.file_name)
    except Exception as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Could not read file: {e}")

    if not cv_text or len(cv_text.strip()) < 20 or cv_text.startswith("ERROR:"):
        error_msg = (
            cv_text
            if cv_text.startswith("ERROR:")
            else "No readable text found. Please upload a text-based PDF or DOCX."
        )
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            error_msg,
        )

    cv_summary = scrub_pii(cv_text[:4000].replace("\n", " ").strip())

    # ── Parse + Analyse in parallel ──
    from backend.ai import (
        analyze_cv,
        extract_skills_from_cv,
        extract_skills_with_confidence,
    )

    # Run enhanced skill extraction in parallel (resilient to AI failures)
    cv_parsed = copy.deepcopy(_CV_EMPTY)
    skills_basic = {}
    skills_confident = {}
    analysis_result = {}
    try:
        results = await asyncio.gather(
            parse_cv(cv_text),
            extract_skills_from_cv(cv_text, request.declared_role),
            extract_skills_with_confidence(cv_text, request.declared_role),
            return_exceptions=True,
        )
        if isinstance(results[0], dict):
            cv_parsed = results[0]
        if isinstance(results[1], dict):
            skills_basic = results[1]
        if isinstance(results[2], dict):
            skills_confident = results[2]
    except Exception as e:
        logger.error(f"[CV] AI extraction failed: {e}")

    # Get analysis result (resilient)
    try:
        analysis_result = await analyze_cv(cv_text, request.declared_role)
    except Exception as e:
        logger.error(f"[CV] analyze_cv failed: {e}")
        analysis_result = {}

    # Extract with confidence data (if available)
    skills_with_confidence = (
        skills_confident.get("skills_with_confidence", [])
        if isinstance(skills_confident, dict)
        else []
    )

    # ── Map analysis fields ──
    detected_role_or_industry = (
        analysis_result.get("detected_role")
        or analysis_result.get("detected_industry")
        or request.declared_role
    )
    experience_level = (
        analysis_result.get("experience_level")
        or analysis_result.get("seniority_level")
        or "Mid"
    )
    verdict = analysis_result.get("verdict") or "pending"

    try:
        score = float(
            analysis_result.get("score") or analysis_result.get("overall_score") or 0
        )
    except (ValueError, TypeError):
        score = 0.0

    # ── Merge skills from multiple sources ──
    extracted = (
        skills_basic.get("extracted_skills", {})
        if isinstance(skills_basic, dict)
        else {}
    )
    base_skills = analysis_result.get("skills", [])
    if isinstance(base_skills, str):
        base_skills = [s.strip() for s in base_skills.split(",")]
    elif isinstance(base_skills, dict):
        base_skills = list(base_skills.keys())

    # Also include skills with confidence
    confident_skills = (
        skills_confident.get("all", []) if isinstance(skills_confident, dict) else []
    )

    raw_all = (
        extracted.get("technical", [])
        + extracted.get("tools", [])
        + confident_skills
        + base_skills[:10]
    )

    # Ensure all items are strings (some might be dicts from structured AI output)
    string_skills = []
    for s in raw_all:
        if isinstance(s, str):
            string_skills.append(s)
        elif isinstance(s, dict):
            # Extract 'name' or 'skill' if it's a dict
            name = s.get("name") or s.get("skill") or str(s)
            string_skills.append(name)
        elif s:
            string_skills.append(str(s))

    all_skills = list(dict.fromkeys(string_skills))[:15]

    # ── Intelligence layer ──
    intelligence = generate_intelligence_layer(
        role=request.declared_role,
        cv_data=cv_parsed,
        user_skills=all_skills,
        level=experience_level,
        skills_with_confidence=skills_with_confidence,
    )

    # ── Structured skills for frontend ──
    raw_skills = cv_parsed.get("skills", {})
    structured_skills = {
        "technical": raw_skills.get("technical", []),
        "tools": raw_skills.get("tools", []),
        "soft": raw_skills.get("soft", []),
        "languages": raw_skills.get("languages", []),
        "cv_source": True,
    }

    # ── Persist if authenticated ──
    app_id: Optional[int] = None
    if current_user:
        try:
            sanitized_text = scrub_pii(cv_text)
            # Reuse existing application if one exists in 'applied' or 'analyzed' state
            # Filter via @property accessor (delegates to EvaluationSession) — queries the deprecated column
            # as a rough pre-filter, then applies the latest-session check in Python.
            _candidates = (
                db.query(Application)
                .options(selectinload(Application.evaluation_sessions))
                .filter(
                    Application.user_id == current_user.id,
                    Application.status.in_(["applied", "analyzed"]),
                )
                .order_by(Application.created_at.desc())
                .all()
            )
            existing_app = None
            for _app in _candidates:
                if _app.interview_state in (None, "not_started"):
                    existing_app = _app
                    break

            # Merge cv_parsed structured data into analysis_result for persistence
            merged = analysis_result.copy()
            cv_exp = cv_parsed.get("experiences", [])
            if cv_exp and not merged.get("experience"):
                merged["experience"] = [
                    {
                        "title": e.get("title", ""),
                        "company": e.get("company", ""),
                        "duration": e.get("duration", ""),
                        "description": e.get("description", ""),
                    }
                    for e in cv_exp
                ]
            cv_edu = cv_parsed.get("education", [])
            if cv_edu and not merged.get("education"):
                merged["education"] = cv_edu
            cv_skills_flat = []
            for cat in ["technical", "tools", "soft"]:
                for s in cv_parsed.get("skills", {}).get(cat, []):
                    if isinstance(s, str):
                        cv_skills_flat.append({"name": s, "level": 70})
                    elif isinstance(s, dict):
                        cv_skills_flat.append(s)
            if cv_skills_flat and not merged.get("skills"):
                merged["skills"] = cv_skills_flat
            if cv_parsed.get("summary") and not merged.get("summary"):
                merged["summary"] = cv_parsed["summary"]
            merged["cv_parsed"] = cv_parsed

            if existing_app:
                app = existing_app
                sync_cv_document(db, app, cv_text_anonymized=sanitized_text[:40_000])
                sync_cv_document(db, app, analysis_json=merged)
                sync_cv_document(db, app, declared_role=request.declared_role)
                ScoringService.set_cv_only(
                    app,
                    db,
                    cv_score=score,
                    verdict=verdict,
                    computed_by="onboarding_cv",
                )
                app_id = app.id
            else:
                company_id = getattr(current_user, "_company_id", None)
                if not company_id:
                    raise HTTPException(
                        status_code=403,
                        detail="Candidate company membership is required",
                    )
                app = ApplicationService.create_application(
                    db,
                    company_id=company_id,
                    application_type=ApplicationType.MANUAL,
                    user_id=current_user.id,
                    candidate_email=get_user_email(current_user),
                    candidate_phone=getattr(current_user, "phone", ""),
                    candidate_name=get_user_name(current_user) or "Unknown",
                    status="applied",
                    declared_role=request.declared_role,
                    cv_text_anonymized=sanitized_text[:40_000],
                    analysis_json=json.dumps(merged),
                )
                db.commit()
                db.refresh(app)
                ScoringService.set_cv_only(
                    app, db, cv_score=score, computed_by="onboarding_cv"
                )
                app_id = app.id
        except Exception as e:
            logger.error("[CV] DB persist failed: %s", e)
            db.rollback()

    return {
        "success": True,
        "application_id": app_id,
        "detected_role": detected_role_or_industry,
        "experience_level": experience_level,
        "skills": all_skills[:10],
        "score": round(score, 1),
        "verdict": verdict,
        "cv_summary": cv_summary,
        "cv_parsed": cv_parsed,
        "structured_skills": structured_skills,
        "intelligence_layer": intelligence,
        "strengths": analysis_result.get("strengths")
        or intelligence.get("strengths", []),
        "weaknesses": analysis_result.get("weaknesses")
        or intelligence.get("weaknesses", []),
        "red_flags": analysis_result.get("red_flags", []),
        "market_positioning": analysis_result.get("market_positioning", ""),
        "skill_metrics": analysis_result.get("skill_metrics", {}),
        "explainability": analysis_result.get("explainability", {}),
        "seniority_level": experience_level,
    }


@router.post(
    "/calibration-questions", summary="Generate tailored calibration questions"
)
async def generate_calibration_questions(
    request: CalibrationRequest,
    current_user: Optional[User] = Depends(get_current_user),
):
    """
    Generate 3 personalised, non-generic calibration questions based on the
    candidate's role, skills, CV context, and intelligence layer.
    """
    from backend.ai.prompts import get_calibration_questions_prompt, track_prompt_usage

    # FIX: use request.intelligence_layer (was undefined 'intelligence')
    intelligence = request.intelligence_layer or {}
    user_id = str(current_user.id) if current_user else None
    try:
        result = get_calibration_questions_prompt(
            role=request.role,
            skills=request.skills,
            level=request.level,
            cv_context=request.cv_summary,
            intelligence_layer=intelligence,
            user_id=user_id,
        )
        prompt, prompt_info = (
            result
            if isinstance(result, tuple)
            else (result, {"version": "1", "variant": "A"})
        )
    except Exception as e:
        logger.warning("[Calibration] prompt build failed: %s", e)
        gaps = ", ".join(intelligence.get("gaps", [])[:3]) or "none"
        prompt = (
            f"Generate 3 specific calibration questions for a {request.level} {request.role}.\n"
            f"Skills: {', '.join(request.skills[:8])}\nGaps: {gaps}\n"
            'Return JSON: {"questions": [{"type": "...", "question": "..."}]}'
        )
        prompt_info = {"version": "fallback", "variant": "A"}

    logger.info(
        "[Calibration] role=%s level=%s prompt_v%s_%s",
        request.role,
        request.level,
        prompt_info.get("version", "?"),
        prompt_info.get("variant", "?"),
    )

    parsed = None
    try:
        content = await call_groq_cascade(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an expert technical interviewer creating a warm-up quiz (QCM). "
                        "Generate highly specific Multiple Choice Questions "
                        "tailored to the candidate's background. "
                        "Return ONLY a JSON object with a 'questions' array. "
                        "Each question object MUST have 'type', 'question', 'options' (array of 4), and 'correct_answer'. "
                        "Output your response as valid JSON."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            max_tokens=1000,
            temperature=0.35,
            json_mode=True,
        )

        if isinstance(content, dict):
            # Detect mock fallback from call_groq_cascade (has no "questions" key)
            if "questions" in content:
                parsed = content
            else:
                logger.warning(
                    "[Calibration] AI returned mock fallback (no questions key)"
                )
        else:
            parsed = safe_json(content)
    except Exception as e:
        logger.warning("[Calibration] AI generation failed: %s", e)

    questions = _normalise_questions(parsed, request.role, request.level)

    # Track prompt usage (non-blocking)
    try:
        track_prompt_usage(
            "calibration_questions",
            prompt_info.get("version", "1"),
            prompt_info.get("variant", "A"),
            success=bool(parsed),
        )
    except Exception:
        pass

    source = "ai" if parsed else "role_based"

    app_id = request.application_id
    if app_id and current_user:
        db_session = next(get_db())
        try:
            app = db_session.query(Application).filter(Application.id == app_id).first()
            if app and app.user_id == current_user.id:
                current_cal = (
                    json.loads(app.calibration_json) if app.calibration_json else {}
                )
                current_cal["generated_questions"] = questions
                sync_ai_interview_session(
                    db_session, app, calibration_json=json.dumps(current_cal)
                )
                db_session.commit()
                logger.info("[Calibration] Questions persisted to app_id=%s", app_id)
        finally:
            db_session.close()

    # Strip correct_answer from client response (security: prevent answer leakage)
    client_questions = []
    for q in questions:
        q_copy = dict(q)
        q_copy.pop("correct_answer", None)
        client_questions.append(q_copy)

    return {
        "success": True,
        "questions": client_questions,
        "source": source,
        "prompt_info": prompt_info,
        "intelligence_summary": {
            "skills_to_verify": intelligence.get("skills_to_verify", []),
            "gaps": intelligence.get("gaps", []),
        },
    }


@router.post("/save-calibration", summary="Save calibration results to application")
async def save_calibration_results(
    request: SaveCalibrationRequest,
    current_user: Optional[User] = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not current_user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Authentication required.")

    app = db.query(Application).filter(Application.id == request.application_id).first()
    if not app:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Application not found")

    if app.user_id != current_user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not authorized")

    calibration_data = {
        "score": request.score,
        "strengths": request.strengths,
        "weaknesses": request.weaknesses,
        "feedback": request.feedback,
        "answers": request.answers,
        "questions": request.questions,
        "skills_verified": request.skills_verified,
        "level": request.level,
        "language": request.language,
        "motivation": request.motivation,
    }

    sync_ai_interview_session(
        db,
        app,
        calibration_json=json.dumps(calibration_data),
        calibration_score=request.score,
        calibration_verified_skills=json.dumps(request.skills_verified),
    )

    if request.language:
        app.language = request.language

    db.commit()

    logger.info(
        "[Calibration] Saved for app %s | score=%s",
        request.application_id,
        request.score,
    )

    return {"success": True, "message": "Calibration saved"}


@router.post(
    "/evaluate-calibration", summary="Evaluate candidate's calibration answers"
)
async def evaluate_calibration_answers(
    request: CalibrationAnswers,
    current_user: Optional[User] = Depends(get_current_user),
):
    """
    Evaluate calibration answers using AI.
    Returns a score, strengths, weaknesses, and concise feedback.
    Falls back to a neutral result if the AI service is unavailable.
    """
    if not current_user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Authentication required.")

    logger.info(
        "[Evaluate] user=%s role=%s level=%s",
        current_user.id,
        request.role,
        request.level,
    )

    if not request.answers:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "No answers provided."
        )

    db_session = next(get_db())
    try:
        app = (
            db_session.query(Application)
            .options(
                selectinload(Application.evaluation_sessions).selectinload(
                    EvaluationSession.evaluation_result
                ),
                selectinload(Application.cv_document),
            )
            .filter(Application.id == request.application_id)
            .first()
        )
        if not app or app.user_id != current_user.id:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND, "Application session not found."
            )

        _ai = app.evaluation_sessions[0] if app.evaluation_sessions else None
        _er_ob = (
            app.evaluation_sessions[0].evaluation_result
            if app.evaluation_sessions and app.evaluation_sessions[0].evaluation_result
            else None
        )
        _sc = _er_ob
        _ev = app.evaluation_state
        _cv = app.cv_document
        _calibration_json = (
            getattr(_ai, "calibration_json", None) or app.calibration_json
        )
        _analysis_json_ob = getattr(_cv, "analysis_json", None) or app.analysis_json
        _final_score_ob = _sc.final_score if _sc else None
        _declared_role_ob = getattr(_cv, "declared_role", None) or app.declared_role

        cal_data = json.loads(_calibration_json) if _calibration_json else {}
        persisted_questions = cal_data.get("generated_questions", [])

        correct_count = 0
        total_q = len(persisted_questions)
        answers_context = []

        for i, ans_obj in enumerate(request.answers):
            answer_val = ans_obj.get("answer", "").strip()
            if i < total_q:
                q_obj = persisted_questions[i]
                correct_ans = q_obj.get("correct_answer", "").strip()
                option_prefix = re.match(r"^[A-D][\.\)\-\:]\s*", answer_val)
                answer_body = (
                    re.sub(r"^[A-D][\.\)\-\:]\s*", "", answer_val).strip()
                    if option_prefix
                    else answer_val
                )
                is_correct = (
                    answer_val == correct_ans
                    or answer_body == correct_ans
                    or answer_body.lower() == correct_ans.lower()
                )
                if is_correct:
                    correct_count += 1

                answers_context.append(
                    {
                        "question": q_obj.get("question"),
                        "candidate_answer": answer_val,
                        "correct_answer": correct_ans,
                        "status": "Correct" if is_correct else "Incorrect",
                    }
                )
    finally:
        db_session.close()

    cv_score = float(_final_score_ob or 0)
    if total_q > 0:
        qcm_perf = correct_count / total_q * 100
        aura_score = (cv_score * 0.4) + (qcm_perf * 0.6)
    else:
        aura_score = cv_score

    # Use AI for Feedback and Nuance (Why they got it wrong)
    answers_block = "\n".join(
        [
            f"Q: {a['question']}\nCandidate: {a['candidate_answer']}\nStatus: {a['status']}"
            for a in answers_context
        ]
    )

    prompt = (
        f"You are evaluating a {request.level} {request.role} candidate's warm-up QCM results.\n\n"
        f"CV BASELINE: {cv_score}/100\n"
        f"AURA SCORE: {round(aura_score)}/100\n"
        f"RESULTS:\n{answers_block}\n\n"
        "Provide a concise summary of their readiness. If they failed easy questions, mention the gap. "
        "Keep it encouraging but professional.\n\n"
        "Return ONLY a JSON object:\n"
        "{\n"
        '  "strengths": [<up to 3 strings>],\n'
        '  "weaknesses": [<up to 3 strings>],\n'
        '  "feedback": "<one concise paragraph>"\n'
        "}"
    )

    content = await groq_complete(
        messages=[
            {
                "role": "system",
                "content": "You are an expert technical mentor. Evaluate results and return only JSON.",
            },
            {"role": "user", "content": prompt},
        ],
        max_tokens=400,
        temperature=0.1,
    )

    result = safe_json(content) or {}

    final_response = {
        "success": True,
        "overall_score": round(aura_score),
        "strengths": result.get("strengths", []),
        "weaknesses": result.get("weaknesses", []),
        "feedback": result.get("feedback", "Calibration complete."),
        "source": "qcm_logic",
    }

    cal_data["score"] = aura_score
    cal_data["answers"] = request.answers
    cal_data["evaluation"] = final_response
    db_commit = next(get_db())
    try:
        sync_ai_interview_session(
            db_commit,
            app,
            calibration_json=json.dumps(cal_data),
            calibration_score=aura_score,
        )
        db_commit.merge(app)
        db_commit.commit()
    finally:
        db_commit.close()

    return final_response


# ──────────────────────────────────────────────────────────────
# AI ONBOARDING INSIGHTS
# ──────────────────────────────────────────────────────────────


@router.get("/insights", summary="Get AI onboarding insights for candidate")
async def get_onboarding_insights(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """
    Generate AI-powered onboarding insights including:
    - Candidate persona
    - Personality snapshot
    - Role fit estimation
    - Recommended focus areas
    """
    app = (
        db.query(Application)
        .options(
            selectinload(Application.evaluation_sessions).selectinload(
                EvaluationSession.evaluation_result
            ),
            selectinload(Application.cv_document),
        )
        .filter(Application.user_id == current_user.id)
        .order_by(Application.created_at.desc())
        .first()
    )

    if not app:
        return {"status": "no_data", "insights": None}

    _ai2 = app.evaluation_sessions[0] if app.evaluation_sessions else None
    _er_o2 = (
        app.evaluation_sessions[0].evaluation_result
        if app.evaluation_sessions and app.evaluation_sessions[0].evaluation_result
        else None
    )
    _sc2 = _er_o2
    _cv2 = app.cv_document
    _calibration_json2 = getattr(_ai2, "calibration_json", None) or app.calibration_json
    _analysis_json2 = getattr(_cv2, "analysis_json", None) or app.analysis_json
    _final_score2 = _sc2.final_score if _sc2 else None
    _declared_role2 = getattr(_cv2, "declared_role", None) or app.declared_role

    calibration = safe_json(_calibration_json2) if _calibration_json2 else {}
    analysis_data = safe_json(_analysis_json2) if _analysis_json2 else {}
    score = _final_score2 or 0
    role = _declared_role2 or "General"
    level = calibration.get("level") or analysis_data.get("seniority_level") or "Mid"

    # Determine candidate persona based on data
    skills_data = analysis_data.get("skill_metrics", {}) or {}
    strengths = analysis_data.get("strengths", [])
    weaknesses = analysis_data.get("weaknesses", []) or analysis_data.get("gaps", [])

    # Candidate persona classification
    technical_depth = int(skills_data.get("Technical", 0) or 0)
    communication_score = int(skills_data.get("Communication", 0) or 0)
    leadership_score = int(skills_data.get("Leadership", 0) or 0)

    if technical_depth >= 80 and communication_score >= 70:
        persona = "The Complete Architect"
        persona_desc = "Strong technical foundation with excellent communication. Ready for leadership roles."
    elif technical_depth >= 80:
        persona = "The Technical Expert"
        persona_desc = "Deep technical skills. Focus on developing soft skills and leadership presence."
    elif communication_score >= 75:
        persona = "The People Leader"
        persona_desc = "Strong interpersonal skills. Building technical depth will unlock senior roles."
    elif leadership_score >= 70:
        persona = "The Emerging Leader"
        persona_desc = "Showing leadership potential. Focus on domain expertise for maximum impact."
    elif score >= 60:
        persona = "The Solid Performer"
        persona_desc = "Well-rounded profile with room to grow in specialized areas."
    else:
        persona = "The Rising Talent"
        persona_desc = (
            "Early career professional with significant growth potential ahead."
        )

    # Personality snapshot from calibration answers
    calibration_answers = calibration.get("answers", []) if calibration else []
    personality_traits = []
    if calibration_answers:
        cal_score_val = calibration.get("score", 0) or 0
        if cal_score_val >= 70:
            personality_traits = ["Analytical", "Precise", "Knowledgeable"]
        elif cal_score_val >= 50:
            personality_traits = ["Curious", "Growing", "Engaged"]
        else:
            personality_traits = ["Exploratory", "Learning", "Motivated"]
    else:
        personality_traits = ["Motivated", "Career-driven", "Ambitious"]

    # Role fit estimation
    role_fit = (
        "Excellent Match"
        if score >= 80
        else "Good Match"
        if score >= 65
        else "Moderate Match"
        if score >= 45
        else "Needs Development"
    )

    # Recommended focus areas for onboarding
    focus_areas = []
    if weaknesses:
        for w in weaknesses[:3]:
            if isinstance(w, str):
                focus_areas.append({"area": w, "type": "improvement"})
    if not focus_areas:
        focus_areas = [
            {"area": "Technical skill demonstration", "type": "improvement"},
            {"area": "Communication clarity", "type": "growth"},
        ]

    if analysis_data.get("interview_focus_areas"):
        for area in analysis_data["interview_focus_areas"][:2]:
            if isinstance(area, str):
                focus_areas.append({"area": area, "type": "interview_focus"})

    return {
        "status": "ready",
        "candidate_persona": {
            "type": persona,
            "description": persona_desc,
            "strengths": strengths[:5] if strengths else ["Adaptable", "Motivated"],
            "growth_areas": weaknesses[:5]
            if weaknesses
            else ["Domain depth", "Technical breadth"],
        },
        "personality_snapshot": {
            "traits": personality_traits,
            "learning_style": calibration.get("evaluation", {}).get(
                "feedback", "Balanced learner"
            ),
            "engagement_level": "High" if score >= 60 else "Moderate",
        },
        "role_fit": {
            "estimation": role_fit,
            "declared_role": role,
            "level": level,
            "score": score,
        },
        "recommended_focus": {
            "areas": focus_areas[:5],
            "next_steps": [
                "Complete your AI interview assessment",
                "Explore personalized course recommendations",
                "Review your skill gap analysis",
                "Set your career target preferences",
            ],
        },
    }
