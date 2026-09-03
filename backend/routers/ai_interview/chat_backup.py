import asyncio
import html
import json
import os
import re
import shutil
import tempfile
import traceback
from datetime import UTC, datetime
from typing import Optional, Tuple

import httpx
from fastapi import (
    APIRouter,
    BackgroundTask,
    BackgroundTasks,
    Depends,
    File,
    HTTPException,
    UploadFile,
)
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import text, update
from sqlalchemy.orm import Session

from backend.ai import evaluate_complete_interview, generate_dynamic_interview_turn
from backend.ai.engine import InterviewEngine
from backend.ai.interview import evaluate_answer, generate_skill_driven_turn
from backend.ai.interview_customization import update_engine_state
from backend.ai.security import AISecurity
from backend.ai.security_layer import SecurityLayer
from backend.ai.state_machine import (
    InterviewState,
    get_interview_strategy,
    initialize_engine_state,
)
from backend.ai_quota_service import check_interview_quota
from backend.config import get_settings

# DB & Config
from backend.database import Application, User
from backend.dependencies import get_current_user, get_db, get_interview_access
from backend.entity_writer import sync_cv_document

# from backend.routers.career import run_proactive_roadmap_generation <-- MOVED INSIDE FUNCTION TO FIX CIRCULAR IMPORT
from backend.logger import logger  # For proper error logging
from backend.metrics import (
    record_ai_call,
)
from backend.simple_rate_limiter import interview_rate_limiter
from backend.tenant import _resolve_company_id

# Try importing edge-tts for Human-like voice
try:
    import edge_tts

    EDGE_TTS_AVAILABLE = True
except ImportError:
    EDGE_TTS_AVAILABLE = False

router = APIRouter(prefix="/ai", tags=["ai-interview"])
INTERVIEW_TOTAL_QUESTIONS = 15


# Safe user property helpers - handle None (guest) users
def safe_user_id(user: Optional[User]) -> str:
    """Returns a safe identifier for logging, works for guests too."""
    if user and hasattr(user, "id") and user.id:
        return f"user_{user.id}"
    return "guest"


def safe_user_role(user: Optional[User]) -> str:
    """Returns a safe role string for authorization checks."""
    if user and hasattr(user, "role") and user.role:
        return user.role
    return "guest"


def safe_user_skills(user: Optional[User]) -> list:
    """Returns a list of user skills, safely handling None users."""
    if not user:
        return []
    skills_str = getattr(user, "skills", "") or ""
    if not skills_str:
        return []
    return [s.strip() for s in skills_str.split(",") if s.strip()]


def _utcnow():
    return datetime.now(UTC).replace(tzinfo=None)


def _sanitise_filename(filename: str) -> str:
    """Sanitise upload filename to prevent path traversal attacks."""
    name = os.path.basename(filename)
    name = re.sub(r"[^\w\-\.]", "_", name)
    if not name or name.startswith("."):
        name = "upload"
    return name[:100]


def _normalize_text_for_compare(text: str) -> str:
    if not text:
        return ""
    return " ".join(str(text).strip().lower().split())


def normalize_interview_language(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip().lower()
    if not text:
        return None

    direct_map = {
        "english": "English",
        "en": "English",
        "french": "French",
        "fr": "French",
        "francais": "French",
        "arabic": "Arabic",
        "ar": "Arabic",
        "derja": "Arabic",
        "darija": "Arabic",
    }
    if text in direct_map:
        return direct_map[text]

    if re.search(r"\b(french|francais|fr)\b", text):
        return "French"
    if re.search(r"\b(arabic|derja|darija|ar)\b", text):
        return "Arabic"
    if re.search(r"\b(english|en)\b", text):
        return "English"
    return None


def _fallback_interview_question(
    current_q_index: int,
    declared_role: str,
    language: str = "English",
    technical_focus: str = None,
) -> str:
    # Phase 19: GUTTED - No more templates allowed.
    if language == "French":
        return "L'IA a rencontré une difficulté technique. Veuillez patienter ou réessayer."
    elif language == "Arabic":
        return "Mouchkel technique: El AI ma najemch ya3tik so2el tawwa. Jarreb marra okhra."
    else:
        return "TECHNICAL DELAY: We're experiencing a brief technical issue. Please bear with us and retry."


def _msg(key: str, language: str = "English", **kwargs) -> str:
    lang = normalize_interview_language(language) or "English"
    catalog = {
        "English": {
            "continuing_assessment": "Continuing the technical assessment.",
            "timeout_reply": "Interview time limit exceeded. Thank you for your participation.",
            "integrity_feedback": "INTEGRITY VIOLATION: {reason}. Your integrity score has been reset.",
            "completion_reply": "Interview Phase Complete. Proceeding to evaluation...",
            "response_noted": "Response noted.",
            "proceeding_evaluation": "Proceeding with evaluation.",
            "lazy_feedback": "Please provide more detailed answers to help us understand your experience better.",
            "security_block": "I cannot process that request. Please focus on the professional technical interview topic.",
            "welcome_feedback": "Welcome! Let's begin your assessment.",
            "answer_recorded": "Answer recorded.",
            "answer_evaluated": "Answer evaluated",
            "practice_lazy_feedback": "Please provide more detailed answers to practice effectively.",
        },
        "French": {
            "continuing_assessment": "Entretien technique en cours.",
            "timeout_reply": "Le temps de l'entretien est ecoule. Merci pour votre participation.",
            "integrity_feedback": "VIOLATION D'INTEGRITE: {reason}. Votre score d'integrite a ete reinitialise.",
            "completion_reply": "Phase d'entretien terminee. Passage a l'evaluation...",
            "response_noted": "Reponse enregistree.",
            "proceeding_evaluation": "Evaluation en cours.",
            "lazy_feedback": "Merci de donner des reponses plus detaillees pour mieux evaluer votre experience.",
            "security_block": "Je ne peux pas traiter cette demande. Merci de rester sur le sujet de l'entretien technique.",
            "welcome_feedback": "Bienvenue! Commencons votre evaluation.",
            "answer_recorded": "Reponse enregistree.",
            "answer_evaluated": "Reponse evaluee",
            "practice_lazy_feedback": "Merci de donner des reponses plus detaillees pour pratiquer efficacement.",
        },
        "Arabic": {
            "continuing_assessment": "Nkammlou l'entretien technique.",
            "timeout_reply": "W9et l'entretien wfaa. Merci 3la moucharaktik.",
            "integrity_feedback": "MOUKHALEFA NZAHA: {reason}. Score mte3 nzahetk tsaffa.",
            "completion_reply": "Mar7alet l'entretien kmlet. Nmorrou ll evaluation...",
            "response_noted": "Ijebtek tetsajlet.",
            "proceeding_evaluation": "Evaluation mchemya.",
            "lazy_feedback": "Aatina ijebet akther tafsil bech n9aymou khebretk b d9a.",
            "security_block": "Ma najemch n3amel m3a hedha et-talab. Kammel fel mawthou3 mta3 l'entretien technique.",
            "welcome_feedback": "Marhbe bik! Yalla nabdaou l'evaluation.",
            "answer_recorded": "Ijebtek tetsajlet.",
            "answer_evaluated": "Ijeba mtaqayyma",
            "practice_lazy_feedback": "Aatina ijebet akther tafsil bech tetdarrab bchkl afdal.",
        },
    }
    language_bucket = catalog.get(lang, catalog["English"])
    template = language_bucket.get(key, catalog["English"].get(key, ""))
    return template.format(**kwargs) if kwargs else template


def _extract_qa_pairs_from_history(history: list) -> list:
    """Reconstruct QA pairs from legacy chat history [{role, content}, ...]."""
    qa_pairs = []
    current_question = None
    for item in history or []:
        role = (item or {}).get("role")
        content = (item or {}).get("content")
        if not isinstance(content, str):
            continue
        if role == "assistant":
            current_question = content
        elif role == "user" and current_question:
            qa_pairs.append({"question": current_question, "answer": content})
    return qa_pairs


def _is_question_cv_relevant(
    question_text: str, cv_context: str, declared_role: str
) -> bool:
    """
    CRITICAL FIX: Verify the generated question is relevant to candidate's CV or role.
    Returns True if question appears to match candidate's experience/skills.
    """
    if not question_text or (not cv_context and not declared_role):
        return True  # Assume relevant if no context

    question_lower = str(question_text).lower()[:500]  # First 500 chars
    cv_lower = str(cv_context).lower()

    # Extract keywords from question (tech terms, tools, concepts)
    question_keywords = re.findall(r"[a-z]+[a-z0-9+#.\-]*", question_lower)
    cv_keywords = re.findall(r"[a-z]+[a-z0-9+#.\-]*", cv_lower)

    # Check for overlap - at least 2-3 keywords should match
    overlap_count = sum(
        1 for kw in question_keywords if kw in cv_keywords and len(kw) > 3
    )
    has_role_match = declared_role.lower() in question_lower or any(
        role_term in question_lower for role_term in declared_role.lower().split()
    )

    # If question mentions specific tech/tool from CV or matches role, it's relevant
    # V2: Require BOTH role match AND some technical keyword overlap for true personalization
    # Or a strong overlap count (>2)
    return (has_role_match and overlap_count >= 1) or overlap_count >= 3


def detect_language_intelligent(message_text: str, fallback: str = "English") -> str:
    """Detects language using mentions, script patterns, and common phrases."""
    if not message_text:
        return fallback
    explicit = normalize_interview_language(message_text)
    if explicit:
        return explicit
    text_lower = message_text.lower()
    if any(word in text_lower for word in ["arabic", "العربية", "derja", "darija"]):
        return "Arabic"
    if any(word in text_lower for word in ["french", "français", "francais"]):
        return "French"
    if any(word in text_lower for word in ["english"]):
        return "English"
    arabic_chars = len(re.findall(r"[\u0600-\u06FF]", message_text))
    french_chars = len(re.findall(r"[àâäéèêëïîôöùûüçÀÂÄÉÈÊËÏÎÔÖÙÛÜÇ]", message_text))
    total_chars = len(message_text)
    if total_chars > 0:
        if (arabic_chars / total_chars) > 0.4:
            return "Arabic"
        if (french_chars / total_chars) > 0.1:
            return "French"
    arabic_phrases = ["السلام عليكم", "الحمد لله", "بسم الله", "شكرا", "من فضلك"]
    french_phrases = ["bonjour", "merci", "s'il vous plaît", "à bientôt", "excusez"]
    if any(phrase in message_text for phrase in arabic_phrases):
        return "Arabic"
    if any(phrase in message_text for phrase in french_phrases):
        return "French"
    return fallback


def summarize_cv_for_interview(cv_text: str, max_chars: int = 3000) -> str:
    """
    [v2] Extracts high-density technical and experience context from CV.
    Increased max_chars for Llama 3/Groq depth.
    """
    if not cv_text or len(cv_text) <= max_chars:
        return cv_text or ""

    parts = []
    # Primary Job experience (grab more of it now)
    job_matches = re.findall(
        r"(?:Work|Experience|Job|Position|Professional).*?(?=\n\n|\n[A-Z]|$)",
        cv_text,
        re.IGNORECASE | re.DOTALL,
    )
    if job_matches:
        for match in job_matches[:2]:  # Get first 2 roles
            parts.append(match[:800])

    # Technical Skills / Knowledge
    skills_match = re.search(
        r"(?:Skills|Technical|Expertise|Stack).*?(?=\n\n|\n[A-Z]|$)",
        cv_text,
        re.IGNORECASE | re.DOTALL,
    )
    if skills_match:
        parts.append(skills_match.group()[:800])

    # Project Highlights
    project_match = re.search(
        r"(?:Project|Achievement|Portfolio).*?(?=\n\n|\n[A-Z]|$)",
        cv_text,
        re.IGNORECASE | re.DOTALL,
    )
    if project_match:
        parts.append(project_match.group()[:800])

    # Education
    edu_match = re.search(
        r"(?:Education|Academic|Formation|University).*?(?=\n\n|\n[A-Z]|$)",
        cv_text,
        re.IGNORECASE | re.DOTALL,
    )
    if edu_match:
        parts.append(edu_match.group()[:300])

    summary = "\n---\n".join(parts)
    return summary[:max_chars]


def _extract_cv_focus_terms(cv_context: str, max_terms: int = 6) -> list:
    """
    [v2] Extract prioritized technical skills and experience terms from CV.
    Filters out structural resume words and prioritizes hard skills.
    """
    if not cv_context or len(str(cv_context).strip()) < 10:
        return []

    # Structural/Meta keywords to strictly BLOCKED (never used as questions)
    blacklist = {
        "education",
        "skills",
        "experience",
        "projects",
        "languages",
        "langues",
        "formation",
        "certifications",
        "interests",
        "hobbies",
        "summary",
        "profile",
        "contact",
        "about",
        "professional",
        "key",
        "technical",
        "competences",
        "hard",
        "soft",
        "details",
        "anglais",
        "fran",
        "français",
        "francais",
        "arabic",
        "arabe",
        "english",
        "french",
        "page",
        "copyright",
        "rights",
        "reserved",
        "tous",
        "droits",
        "réservés",
        "resume",
        "cv",
        "curriculum",
        "vitae",
        "mobi",
        "pdf",
        "ceo",
        "director",
        "manager",
        "lead",
        "senior",
        "head",
        "chief",
        "president",
    }

    # Pre-clean: Remove common resume headers
    headers_to_remove = [
        r"\bexperience\b",
        r"\beducation\b",
        r"\blanguages\b",
        r"\blangues\b",
        r"\bskills\b",
        r"\bcertifications\b",
        r"\bprojects\b",
        r"\binterests\b",
        r"\bprofile\b",
        r"\bformation\b",
        r"\bprofessional summary\b",
        r"\bcontact\b",
        r"\bhobbies\b",
        r"\bpersonal info\b",
        r"\bdetails\b",
    ]
    text = str(cv_context).lower()
    for header in headers_to_remove:
        text = re.sub(header, "", text)

    # Tier 1: Hard Technical Keywords (Priority)
    tech_keywords = {
        "python",
        "javascript",
        "java",
        "csharp",
        "php",
        "ruby",
        "go",
        "rust",
        "swift",
        "kotlin",
        "react",
        "angular",
        "vue",
        "nodejs",
        "node.js",
        "django",
        "flask",
        "spring",
        "fastapi",
        "docker",
        "kubernetes",
        "aws",
        "azure",
        "gcp",
        "jenkins",
        "gitlab",
        "sql",
        "mongodb",
        "postgresql",
        "mysql",
        "redis",
        "elasticsearch",
        "flutter",
        "react native",
        "machine learning",
        "ml",
        "tensorflow",
        "pytorch",
        "nlp",
        "ai",
        "deep learning",
        "devops",
        "ci/cd",
        "api",
        "rest",
        "graphql",
        "microservices",
        "cloud",
        "serverless",
        "testing",
        "automation",
        "security",
        "cybersecurity",
    }

    # Tier 2: Role-based keywords
    role_keywords = {
        "community manager",
        "product manager",
        "scrum master",
        "agile",
        "kanban",
        "frontend",
        "backend",
        "fullstack",
        "data engineer",
        "data scientist",
        "penetration testing",
        "infosec",
        "governance",
        "strategy",
    }

    found_skills = []
    seen = set()

    # Priority 1: Pick up to 4 hard technical skills
    for keyword in sorted(tech_keywords, key=len, reverse=True):
        if keyword in text:
            display_name = keyword.replace(" ", " ").title()
            if display_name.lower() not in seen:
                found_skills.append(display_name)
                seen.add(display_name.lower())
                if len(found_skills) >= 4:
                    break

    # Priority 2: Pick role keywords if still have space
    if len(found_skills) < max_terms:
        for keyword in sorted(role_keywords, key=len, reverse=True):
            if keyword in text:
                display_name = keyword.replace(" ", " ").title()
                if display_name.lower() not in seen:
                    found_skills.append(display_name)
                    seen.add(display_name.lower())
                    if len(found_skills) >= max_terms:
                        break

    # Fallback: Extract words that look like skills (3-15 chars, mostly letters)
    if len(found_skills) < max_terms:
        raw_tokens = re.findall(r"\b[a-z][a-z0-9+#.\-]{2,15}\b", text)
        stop = {
            "with",
            "from",
            "that",
            "this",
            "have",
            "your",
            "pour",
            "avec",
            "dans",
            "sur",
            "des",
            "les",
            "and",
            "the",
            "for",
            "work",
            "experience",
            "skills",
            "technical",
            "profile",
            "context",
            "standard",
            "manager",
            "candidate",
            "role",
            "project",
            "projects",
            "education",
            "learning",
            "key",
            "professional",
            "languages",
            "langues",
            "formation",
            "native",
            "fluent",
            "intermediate",
            "advanced",
            "summary",
            "personal",
            "details",
        }
        for token in raw_tokens:
            if (
                token in stop
                or token in blacklist
                or len(token) < 3
                or token.lower() in seen
            ):
                continue
            # Ensure it's not a common English word
            found_skills.append(token.title())
            seen.add(token.lower())
            if len(found_skills) >= max_terms:
                break

    return found_skills if found_skills else ["Professional Experience"]


def _extract_role_terms(role: str) -> list:
    if not role:
        return []
    raw_tokens = re.findall(r"[A-Za-z][A-Za-z0-9+#.\-]{2,}", str(role).lower())
    stop = {"and", "the", "for", "senior", "junior", "lead"}
    return [t for t in raw_tokens if t not in stop]


def _question_is_role_cv_relevant(question: str, role: str, cv_terms: list) -> bool:
    if not question:
        return False
    q = str(question).lower()
    role_terms = _extract_role_terms(role)
    has_role = any(term in q for term in role_terms[:3]) if role_terms else False
    has_cv = (
        any(str(term).lower() in q for term in (cv_terms or [])[:4])
        if cv_terms
        else False
    )
    return has_role or has_cv


def _build_role_cv_question(role: str, cv_terms: list, language: str) -> str:
    if language == "French":
        return "L'IA est en train de préparer votre prochaine question personnalisée..."
    else:
        return "AI is preparing your personalized technical question..."


def _is_language_mismatch(text: str, language: str) -> bool:
    lang = normalize_interview_language(language) or "English"
    content = str(text or "").strip()
    if not content:
        return False
    lower = content.lower()
    arabic_chars = len(re.findall(r"[\u0600-\u06FF]", content))
    latin_tokens = re.findall(r"[a-zA-Z']+", lower)

    english_markers = {
        "the",
        "and",
        "with",
        "your",
        "you",
        "what",
        "how",
        "walk",
        "through",
        "project",
        "role",
        "for",
        "to",
        "of",
    }
    french_markers = {
        "vous",
        "avec",
        "dans",
        "pour",
        "quelle",
        "comment",
        "votre",
        "vos",
        "est",
        "que",
        "des",
        "une",
        "sur",
        "du",
    }

    english_hits = sum(1 for t in latin_tokens if t in english_markers)
    french_hits = sum(1 for t in latin_tokens if t in french_markers)

    if lang == "French":
        return english_hits >= 3 and english_hits > french_hits
    if lang == "Arabic":
        # If almost no Arabic script is present, treat as mismatch.
        return arabic_chars < 8
    # English mode
    return french_hits >= 3 and french_hits > english_hits


def calculate_adaptive_score(
    previous_score: float,
    question_score: float,
    question_number: int,
    is_handshake: bool = False,
    initial_score: float = 75.0,
) -> float:
    """
    [v2.2] Asymmetric adaptive scoring.
    Drops are faster than gains to prevent 'sticky' high scores (MAJ-02).
    """
    if is_handshake or question_number <= 1:
        return previous_score or initial_score

    prev = previous_score if previous_score is not None else initial_score

    # Max change allowed per turn
    if question_number <= 3:
        max_change = 35  # Highly sensitive start
    elif question_number <= 8:
        max_change = 22  # Active pivot
    elif question_number <= 15:
        max_change = 15  # Stability zone
    else:
        max_change = 10  # Fine-tuning

    diff = question_score - prev

    # Asymmetric damping: losses are damped more than gains to prevent excessive volatility
    # Gain damping = 0.85 (keep 85% of improvement), Loss damping = 0.85 (keep 85% of loss)
    # Using symmetric damping to avoid penalizing improvement
    damping = 0.85

    clamped_diff = max(-max_change, min(max_change, diff))
    new_val = prev + (clamped_diff * damping)

    return round(max(0.0, min(100.0, new_val)), 2)


def derive_dashboard_insights_from_skills(skill_metrics: dict) -> dict:
    """Derive dashboard-facing insights from live interview skill metrics."""
    if not isinstance(skill_metrics, dict) or not skill_metrics:
        return {
            "strengths": [],
            "missing_skills": [],
            "weaknesses": [],
            "action_plan": [],
            "gap_analysis": [],
        }

    normalized_scores = {}
    for skill, raw_score in skill_metrics.items():
        try:
            score_val = float(raw_score)
        except Exception:
            continue
        clean_skill = str(skill).strip() or "Skill"
        normalized_scores[clean_skill] = max(0.0, min(100.0, score_val))

    if not normalized_scores:
        return {
            "strengths": [],
            "missing_skills": [],
            "weaknesses": [],
            "action_plan": [],
            "gap_analysis": [],
        }

    ranked = sorted(normalized_scores.items(), key=lambda item: item[1], reverse=True)
    strengths = [skill for skill, score in ranked if score >= 70][:6]
    focus_pairs = sorted(normalized_scores.items(), key=lambda item: item[1])[:4]
    missing_skills = [skill for skill, _ in focus_pairs if skill not in strengths]

    action_plan = []
    gap_analysis = []
    for skill, score in focus_pairs:
        if score >= 70:
            continue
        target = 70
        delta = int(max(0, round(target - score)))
        action_plan.append(
            f"Improve {skill} by {delta} points through scenario-based practice and concrete project examples."
        )
        gap_analysis.append(
            {
                "skill": skill,
                "current_score": round(score, 1),
                "target_score": target,
                "gap_level": "High" if score < 50 else "Medium",
                "action": f"Practice {skill} with real examples and measurable outcomes.",
            }
        )

    if not action_plan:
        action_plan = [
            "Maintain your strongest skills and keep refining communication clarity in technical answers."
        ]

    return {
        "strengths": strengths,
        "missing_skills": missing_skills,
        "weaknesses": missing_skills,
        "action_plan": action_plan,
        "gap_analysis": gap_analysis,
    }


# AI HARDENING (AI-01): Prompt injection sanitizer applied before any LLM call.
_INJECTION_PATTERNS = [
    r"ignore (all |previous |prior )?instructions",
    r"you are now",
    r"disregard (all |your |previous )?(instructions|prompt|context)",
    r"forget (everything|all|what|your)",
    r"act as (a |an )?(different|new|another|evil|hacker|jailbreak)",
    r"respond (only|always|just) (as|with|in)",
    r"new (persona|identity|role|mode)",
    r"system prompt",
    r"\[/?inst\]",
    r"<\|im_(start|end)\|>",
    r"give me (a |the )?(high|perfect|maximum|100) score",
    r"mark (me|this|my answer) (as |with )?(correct|perfect|10|100)",
]
_INJECTION_RE = re.compile("|".join(_INJECTION_PATTERNS), re.IGNORECASE)


def strip_prompt_injections(text: str) -> str:
    """Remove prompt injection patterns from user-provided text."""
    if not text or not isinstance(text, str):
        return text
    cleaned = _INJECTION_RE.sub("[REDACTED]", text)
    if cleaned != text:
        logger.warning("Prompt injection attempt detected and stripped.")
    return cleaned


def is_lazy_answer(
    message: str, question: str, language: str = "English", turn_index: int = 1
) -> bool:
    """Smart lazy detection that ignores technical conciseness and valid binary answers."""
    m = message.strip().lower()
    if not m:
        return True

    # FIX (AI-05): Only apply whitelist on the VERY first turn (language selection / ready signal).
    # After turn 1, 'ok', 'okay', 'ready' etc. are lazy non-answers and MUST be flagged.
    whitelist_start = {
        "french",
        "english",
        "arabic",
        "ready",
        "start",
        "commencer",
        "yalla",
    }
    if turn_index <= 1 and m in whitelist_start:
        return False
    # Explicitly flag known non-answers on all turns after the first.
    lazy_only = {
        "ok",
        "okay",
        "go on",
        "tell me",
        "d'accord",
        "what",
        "go",
        "yes",
        "no",
        "oui",
        "non",
    }
    if m in lazy_only:
        return True

    min_len = 5 if language == "Arabic" else (8 if language == "French" else 10)
    token_count = len(re.findall(r"[A-Za-z0-9\u0600-\u06FF]+", m))
    tech_keywords = [
        "code",
        "function",
        "api",
        "database",
        "sql",
        "aws",
        "react",
        "node",
        "error",
        "try",
        "catch",
        "system",
    ]
    if len(m) < min_len:
        if any(w in m for w in ["yes", "no", "true", "false", "non", "oui"]):
            if "?" in (question or "") and len(m.split()) <= 2:
                return False
        return True
    if token_count <= 2:
        if any(tk in m for tk in tech_keywords):
            return False
        return True
    if any(tk in m for tk in tech_keywords):
        return False
    return False


# Redundant definition removed (MIN-03). Consolidated into definition at line 250.

GRACEFUL_FALLBACKS = {
    "English": [
        "Walk me through the most technically challenging project on your CV.",
        "Describe a production problem you had to diagnose under time pressure.",
        "How do you approach learning a new technology that's required for a role?",
    ],
    "French": [
        "Décrivez le projet le plus complexe de votre CV technique.",
        "Racontez un problème en production que vous avez résolu sous pression.",
        "Comment abordez-vous l'apprentissage d'une nouvelle technologie requise pour un rôle ?",
    ],
    "Arabic": [
        "Wassef a9wa projet fi CV mte3k.",
        "Hadthni 3an mochkla fi production 7allitha bi sor3a.",
    ],
}


def _get_graceful_fallback(q_index: int, language: str, declared_role: str) -> str:
    pool = GRACEFUL_FALLBACKS.get(language, GRACEFUL_FALLBACKS["English"])
    return pool[(q_index - 1) % len(pool)]


def get_fallback_turn(
    q_index: int,
    role: str,
    current_score: float,
    language: str = "English",
    initial_skills: dict = None,
) -> dict:
    """Guaranteed valid turn structure for error recovery. Bug #2: Dynamic baseline."""

    # Bug #2: Dynamic fallback score based on CV skills if available
    baseline = 75.0
    if initial_skills and isinstance(initial_skills, dict):
        tech_val = initial_skills.get("Technical")
        if tech_val is not None:
            baseline = float(tech_val)
        else:
            vals = [
                float(v) for v in initial_skills.values() if isinstance(v, (int, float))
            ]
            if vals:
                baseline = sum(vals) / len(vals)

    score = current_score or baseline

    # Bug #27: Use randomize fallback questions (defined in interview.py but accessed via local logic if needed)
    # For simplicity, we just provide a robust message here.
    question = _get_graceful_fallback(q_index, language, role)

    # Use initial skills for fallback if provided
    skills = (
        initial_skills.copy()
        if initial_skills
        else {
            "Technical": baseline,
            "Communication": baseline,
            "Problem Solving": baseline,
            "Adaptability": baseline,
            "Confidence": baseline,
        }
    )

    return {
        "reply": question,
        "current_score": score,
        "feedback": _msg("continuing_assessment", language),
        "score_reasoning": _msg("proceeding_evaluation", language),
        "skills": skills,
        "talent_analysis": {},
        "is_vague": False,
        "hint_text": "",
    }


# --- Schemas ---
class ChatRequest(BaseModel):
    candidate_id: int
    message: str = Field(..., max_length=5000)
    language: Optional[str] = Field(None, max_length=50)


class FraudReport(BaseModel):
    application_id: int
    reason: str = Field(..., max_length=1000)


class InterviewGenRequest(BaseModel):
    application_id: int
    language: Optional[str] = Field("English", max_length=50)


class ProctoringSyncRequest(BaseModel):
    application_id: int
    violation_type: str = Field(..., max_length=100)
    timestamp: str = Field(..., max_length=100)
    details: str = Field("", max_length=1000)


class VideoUploadRequest(BaseModel):
    application_id: int


# --- Endpoints ---


@router.post("/generate-interview")
async def generate_interview_questions(
    req: InterviewGenRequest,
    quota_info: dict = Depends(check_interview_quota),
    db: Session = Depends(get_db),
    auth: Tuple[Optional[User], Application] = Depends(get_interview_access),
):
    """
    Generate tailored interview questions based on candidate's application.
    """
    current_user, app = auth
    if not app:
        # TENANT ISOLATION: require company_id on fallback query
        company_id = _resolve_company_id(current_user, db) if current_user else None
        if company_id is None:
            raise HTTPException(status_code=404, detail="Application not found")
        app = (
            db.query(Application)
            .filter(
                Application.id == req.application_id,
                Application.company_id == company_id,
            )
            .first()
        )

    if not app:
        raise HTTPException(status_code=404, detail="Application not found")

    # Check permissions (Recruiter, Admin, or Owner/HMAC-Authorized)
    if current_user:
        if (
            safe_user_role(current_user) not in ["recruiter", "admin"]
            and app.user_id != current_user.id
        ):
            raise HTTPException(status_code=403, detail="Not authorized")
    # If no current_user, get_interview_access already verified HMAC token for this app

    # Construct Prompt
    role = app.declared_role or "Software Engineer"
    role = app.declared_role or "Software Engineer"
    cv_raw = app.cv_text_anonymized or "No CV context available."
    # AI HARDENING (AI-01 + AI-04): Sanitize CV for prompt injection BEFORE embedding.
    cv_context = strip_prompt_injections(AISecurity.sanitize_input(cv_raw))[:1000]
    language = (
        req.language
        if req.language and req.language != "English"
        else (app.language or "English")
    )
    prompt = f"""
    Generate 10 SCENARIO-BASED interview questions for a "{role}" position in Tunisia's tech market.
    Language: {language}
    Context from Candidate CV: {cv_context[:500]}...

    CRITICAL: You MUST write the questions in {language}.
    - If {language} is Arabic -> Use Tunisian Derja or Modern Standard Arabic.
    - If {language} is French -> Use Professional French.

    TUNISIAN CONTEXT: Reference Tunisian companies (Vermeg, InstaDeep, Sofrecom, Expensya, BIAT),
    local tech stacks (Java/Spring for offshore, React/Node for startups, no Stripe — use Flouci/D17),
    and real Tunisian work scenarios (offshore for EU clients, bilingual FR/EN teams).

    QUESTION FORMAT — Each question MUST be a REALISTIC SCENARIO:
    ❌ BAD: "What is Docker?" or "Explain REST vs GraphQL"
    ✅ GOOD: "You're at a Tunisian fintech. Your API returns 500 errors for 20% of payments after deployment. The French client calls urgently. Walk me through your incident response."

    STRUCTURE (10 questions with difficulty progression):
    - Q1-Q3: WARMUP — Approachable scenarios testing fundamentals
    - Q4-Q7: CORE — Challenging work situations requiring step-by-step technical reasoning
    - Q8-Q9: DEEP DIVE — Complex multi-dimensional problems with trade-offs
    - Q10: STRESS — Time pressure, conflicting priorities, or ethical dilemmas

    Output strictly a JSON object with a "questions" key containing a list of 10 strings.
    Example: {{"questions": ["Scenario Q1...", "Scenario Q2...", ...]}}
    """
    try:
        # Use Groq/Llama
        settings = get_settings()
        payload = {
            "messages": [{"role": "user", "content": prompt}],
            "model": "groq/compound",
            # AI HARDENING (AI-04): temperature=0.3 for question generation (some variety OK).
            # Evaluation/scoring calls must use temperature=0 (set there separately).
            "temperature": 0.3,
            "response_format": {"type": "json_object"},
        }
        import httpx

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                settings.groq_api_url,
                json=payload,
                headers={"Authorization": f"Bearer {settings.groq_api_key}"},
            )
        if response.status_code != 200:
            # Fallback
            return {
                "questions": [
                    f"Explain your experience with {role}.",
                    "What was your most challenging project?",
                    "How do you handle technical debt?",
                    "Describe a time you failed.",
                    "What are your salary expectations?",
                ]
            }
        data = response.json()
        content = data["choices"][0]["message"]["content"]
        import json

        return json.loads(content)
    except Exception as e:
        # SECURITY FIX: Log internally but don't expose details to client
        logger.error(f"AI question generation failed: {e}", exc_info=True)
        # Return fallback questions without exposing error details
        return {
            "questions": [
                f"Describe your experience with {role}.",
                "What is a key technical challenge you've solved?",
                "How do you stay updated with technology?",
                "Explain a complex concept to a junior developer.",
                "What are your career goals?",
            ]
        }


@router.post("/interview/upload-video")
async def upload_interview_video(
    application_id: int = Depends(lambda application_id: application_id),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    auth: Tuple[Optional[User], Application] = Depends(get_interview_access),
    background_tasks: BackgroundTasks = BackgroundTasks(),
):
    """
    Upload recorded interview video and trigger transcription.
    """
    current_user, app = auth
    if not app:
        company_id = _resolve_company_id(current_user, db) if current_user else None
        if company_id is None:
            raise HTTPException(status_code=404, detail="Application not found")
        app = (
            db.query(Application)
            .filter(
                Application.id == application_id,
                Application.company_id == company_id,
            )
            .first()
        )

    if not app:
        raise HTTPException(status_code=404, detail="Application not found")

    # SECURITY FIX: Validate file upload thoroughly
    MAX_SIZE = 50 * 1024 * 1024  # 50MB

    # Read file content
    content = await file.read()

    # Check file size
    if len(content) > MAX_SIZE:
        raise HTTPException(status_code=413, detail="Video file too large (max 50MB)")

    # Check file is not empty
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="File is empty")

    # SECURITY: Validate file extension - only allow webm
    # Check both the uploaded filename and the actual content
    original_filename = file.filename or ""
    if not original_filename.lower().endswith((".webm", ".mp4", ".mov", ".avi")):
        raise HTTPException(
            status_code=400, detail="Invalid file type. Only video files allowed."
        )

    # SECURITY: Check file magic bytes (first few bytes) to verify it's actually a video
    # WebM files start with 1A 45 DF A3
    # MP4 files start with ftyp (at offset 4)
    if len(content) >= 4:
        first_four = content[:4]
        is_webm = first_four == b"\x1a\x45\xdf\xa3"
        is_mp4_like = b"ftyp" in first_four or content[4:8] == b"ftyp"

        if not (is_webm or is_mp4_like):
            # Additional check for other video formats
            # RIFF for AVI/WAV
            if not (
                len(content) >= 12
                and content[:4] == b"RIFF"
                and content[8:12] == b"AVI "
            ):
                logger.warning(
                    f"Suspicious file upload for app {application_id}: magic bytes {first_four.hex()}"
                )
                raise HTTPException(
                    status_code=400, detail="File is not a valid video file"
                )

    await file.seek(0)

    # Save File with secure filename
    upload_dir = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), "uploads", "videos"
    )
    if not os.path.exists(upload_dir):
        os.makedirs(upload_dir, exist_ok=True)

    # Use random filename to prevent path traversal and prediction
    import secrets

    random_suffix = secrets.token_hex(8)
    filename = f"video_{application_id}_{random_suffix}.webm"

    # SECURITY: Ensure filename doesn't contain path traversal
    filename = os.path.basename(filename)
    file_path = os.path.join(upload_dir, filename)

    # SECURITY: Use absolute path and verify it's within upload_dir
    upload_dir_abs = os.path.abspath(upload_dir)
    file_path_abs = os.path.abspath(file_path)
    if not file_path_abs.startswith(upload_dir_abs):
        raise HTTPException(status_code=400, detail="Invalid file path")

    with open(file_path, "wb") as buffer:
        buffer.write(content)

    # Store path in DB
    app.video_file_path = f"uploads/videos/{filename}"
    db.commit()

    # Trigger Background Transcription
    background_tasks.add_task(process_video_transcription, app.id, app.company_id)

    return {"status": "success", "message": "Video uploaded, processing started."}


async def process_video_transcription(application_id: int, company_id: int):
    """
    Background task to transcribe video audio using Groq Whisper.
    Uses context manager for safe commit/rollback.
    """
    from backend.database import SessionLocal

    with SessionLocal() as db:
        with db.begin():
            try:
                app = (
                    db.query(Application)
                    .filter(
                        Application.id == application_id,
                        Application.company_id == company_id,
                    )
                    .first()
                )
                if not app or not app.video_file_path:
                    return

                settings = get_settings()
                full_path = os.path.join(
                    os.path.dirname(os.path.dirname(__file__)), app.video_file_path
                )

                if not os.path.exists(full_path):
                    logger.error(
                        f"Video file not found for app {application_id}: {full_path}"
                    )
                    return

                # Call Groq Whisper
                with open(full_path, "rb") as audio_file:
                    files = {
                        "file": (os.path.basename(full_path), audio_file, "video/webm")
                    }
                    data = {"model": "whisper-large-v3", "response_format": "json"}
                    async with httpx.AsyncClient(timeout=120.0) as client:
                        response = await client.post(
                            "https://api.groq.com/openai/v1/audio/transcriptions",
                            headers={
                                "Authorization": f"Bearer {settings.groq_api_key}"
                            },
                            files=files,
                            data=data,
                        )

                if response.status_code == 200:
                    result = response.json()
                    transcript = result.get("text", "")
                    app.video_transcript = transcript
                    logger.info(
                        f"Video transcription successful for app {application_id}"
                    )

                    if transcript:
                        try:
                            analysis = json.loads(app.analysis_json or "{}")
                            analysis["video_verification"] = (
                                "Transcription available for review."
                            )
                            sync_cv_document(db, app, analysis_json=analysis)
                        except Exception:
                            pass
                else:
                    logger.error(
                        f"Groq Video STT Failed ({response.status_code}): {response.text}"
                    )
                    app.interview_state = "transcription_failed"
                    app.video_transcript = f"Transcription failed with status {response.status_code}. Manual review required."
                    logger.info(
                        f"Interview transcription marked as failed for app {application_id}"
                    )

            except Exception as e:
                logger.error(
                    f"Error in process_video_transcription: {e}", exc_info=True
                )
                app = (
                    db.query(Application)
                    .filter(
                        Application.id == application_id,
                        Application.company_id == company_id,
                    )
                    .first()
                )
                if app:
                    app.interview_state = "transcription_failed"
                    app.video_transcript = f"Transcription error: {str(e)[:200]}"
                raise


@router.post("/voice/stt")
async def speech_to_text(
    file: UploadFile = File(...), current_user: User = Depends(get_current_user)
):
    """
    Speech-to-text using Groq Whisper.
    Security: uses tempfile.mkstemp() for atomic secure temp file creation.
    """
    file_path = None
    try:
        # Use mkstemp for cryptographically secure temp file
        temp_dir = tempfile.gettempdir()
        fd, file_path = tempfile.mkstemp(suffix=".webm", dir=temp_dir)
        os.close(fd)  # Close fd — we'll reopen for writing

        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # STT using Groq Whisper
        settings = get_settings()
        with open(file_path, "rb") as audio_file:
            files = {"file": (file.filename, audio_file, file.content_type)}
            data = {"model": "whisper-large-v3", "response_format": "json"}
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    "https://api.groq.com/openai/v1/audio/transcriptions",
                    headers={"Authorization": f"Bearer {settings.groq_api_key}"},
                    files=files,
                    data=data,
                )

        if response.status_code == 200:
            result = response.json()
            transcript = result.get("text", "")
            logger.info(f"STT Successful: {transcript[:50]}...")
            return {"text": transcript}
        else:
            logger.error(f"Groq STT Failed: {response.status_code} - {response.text}")
            return JSONResponse(
                status_code=503,
                content={
                    "error": "STT_UNAVAILABLE",
                    "text": "",
                    "message": "Voice transcription failed. Please type your answer.",
                },
            )
    except Exception as e:
        logger.error(f"STT Exception: {e}", exc_info=True)
        return JSONResponse(
            status_code=503,
            content={
                "error": "STT_UNAVAILABLE",
                "text": "",
                "message": "Voice transcription unavailable. Please type your answer.",
            },
        )
    finally:
        # Robust cleanup — ignore OS errors
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
            except OSError:
                pass


async def generate_interview_turn_with_timeout(
    cv_context: str,
    declared_role: str,
    history: list,
    current_q_index: int,
    total_questions: int,
    language: str,
    job_title: str,
    job_description: str,
    app_id: int,
    current_score: float,
    initial_skills: dict = None,
    seniority_level: str = "Junior",
    interview_instructions: dict = None,
    instruction_state: dict = None,
) -> dict:
    """Tries to generate question with AI. If timeout or malformed JSON, uses smart fallback."""
    response = None
    from backend.ai.llm import call_groq_cascade

    try:
        # First attempt: Normal generation
        async with asyncio.timeout(120):  # 2 min timeout
            response = await generate_dynamic_interview_turn(
                cv_context=cv_context,
                declared_role=declared_role,
                history=history,
                current_q_index=current_q_index,
                current_score=current_score,
                total_questions=total_questions,
                language=language,
                job_title=job_title,
                job_description=job_description,
                initial_skills=initial_skills,
                seniority_level=seniority_level,
                interview_instructions=interview_instructions,
                instruction_state=instruction_state,
            )

            # Layer 2: Validate response structure
            if response and isinstance(response, dict):
                # Phase 16: Check for connectivity error dict from llm.py
                reply_val = str(response.get("reply", "")).lower()
                if (
                    "connectivity issues" in reply_val
                    or "manually reviewing" in reply_val
                ):
                    logger.error(
                        f"[AI ERROR] App {app_id}: Caught connectivity error dict, triggering Layer 2 retry."
                    )
                    # Fall through to Layer 2 retry
                elif "reply" in response:
                    logger.info(
                        f"[AI SUCCESS] App {app_id}: Q{current_q_index} generated successfully"
                    )
                    return response
                else:
                    logger.warning(
                        f"[AI WARNING] App {app_id}: Missing 'reply' field after generation"
                    )
            else:
                logger.warning(
                    f"[AI WARNING] App {app_id}: Invalid response type/structure on attempt 1"
                )
                record_ai_call(success=False)

    except asyncio.TimeoutError:
        logger.warning(
            f"[AI TIMEOUT] App {app_id} Q{current_q_index}: Timeout on first attempt (120s), retrying..."
        )
        record_ai_call(success=False, timeout=True)
    except Exception as e:
        logger.error(
            f"[AI ERROR] App {app_id} Q{current_q_index}: {type(e).__name__}: {e}"
        )
        record_ai_call(success=False)

    # Second attempt: Use faster model logic
    try:
        logger.info(f"[AI RETRY] App {app_id}: Attempting faster retry model...")
        async with asyncio.timeout(60):  # 1 min
            # Phase 19: Purely dynamic retry prompt
            prompt = f"The candidate is interviewing for {declared_role}. This is turn {current_q_index}/{total_questions}. Ask one deep technical question relevant to this role and the interview context."
            response = await call_groq_cascade(
                [
                    {
                        "role": "system",
                        "content": f"You are an expert technical interviewer for {declared_role}. Ask ONE concise, challenging technical question. Output only the question text.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.5,
                max_tokens=200,
                json_mode=False,
            )

            if response and isinstance(response, str):
                logger.info(
                    f"[RETRY SUCCESS] App {app_id}: Got text response from faster model"
                )
                # Phase 21: DO NOT return a hardcoded dict. Return the text and let caller handle.
                return {
                    "reply": response.strip(),
                    "current_score": current_score,
                    "feedback": _msg("response_noted", language),
                    "skills": initial_skills.copy()
                    if initial_skills
                    else {
                        "Technical": current_score,
                        "Communication": round(current_score * 0.92, 1),
                        "Problem Solving": round(current_score * 1.05, 1)
                        if current_score < 90
                        else 95,
                        "Adaptability": round(current_score * 0.88, 1),
                        "Confidence": round(current_score * 0.95, 1),
                    },
                }
    except Exception as e:
        logger.error(f"[FALLBACK ERROR] App {app_id}: {type(e).__name__}: {e}")

    # Layer 3: Final content cleaning & Unescape HTML entities. Fallback if everything failed.
    if not response or not isinstance(response, dict) or "reply" not in response:
        logger.error(
            f"[AI TOTAL FAIL] App {app_id}: All attempts failed. Triggering hard fallback question."
        )
        response = get_fallback_turn(
            current_q_index, declared_role, current_score, language
        )

    if response and "reply" in response:
        response["reply"] = html.unescape(str(response["reply"]))

    if response and "feedback" in response:
        response["feedback"] = html.unescape(str(response["feedback"]))

    return response


async def _interview_chat_core(
    req: ChatRequest,
    db: Session,
    current_user: Optional[User],
    background_tasks: BackgroundTasks,
    application: Optional[Application] = None,
):
    """
    HYBRID SYSTEM: Pre-generated questions + Real-time scoring
    - Questions generated during CV analysis (consistent, no API failures)
    - Scoring happens during interview (feedback, progress tracking)
    """
    # INPUT VALIDATION: Prevent DoS and ensure data quality
    if not req.message or not req.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")
    if len(req.message) > 5000:
        raise HTTPException(
            status_code=400, detail="Message too long (maximum 5000 characters)"
        )
    # RATE LIMITING: Prevent abuse.
    # Use user_id for logged-in users, or candidate_id for guest users.
    if current_user:
        identifier = f"user_{safe_user_id(current_user)}"
    else:
        identifier = f"app_{req.candidate_id}"

    is_allowed, retry_after = interview_rate_limiter.is_allowed(
        identifier, max_requests=10, window_seconds=300
    )
    if not is_allowed:
        raise HTTPException(
            status_code=429,
            detail=f"Too many requests. Please wait {retry_after} seconds before trying again.",
            headers={"Retry-After": str(retry_after)},
        )
    # Dynamic 1-Call-Per-Question Interview Flow.
    # PHASE 15: Initialize Engine
    engine = InterviewEngine(db)

    # PHASE 4 FIX (Bug #18): with_for_update() prevents race conditions for concurrent turns
    if application:
        app = application
    else:
        query = (
            db.query(Application)
            .with_for_update()
            .filter(Application.id == req.candidate_id)
        )
        if current_user and safe_user_role(current_user) not in ["recruiter", "admin"]:
            query = query.filter(Application.user_id == current_user.id)
        elif current_user:
            # TENANT ISOLATION: recruiters/admins must also be scoped to their company
            company_id = _resolve_company_id(current_user, db)
            if company_id is not None:
                query = query.filter(Application.company_id == company_id)
        app = query.first()

    if not app:
        db.commit()
        raise HTTPException(status_code=404, detail="Application not found")

    # === IDEMPOTENCY: Atomic turn counter to prevent duplicate processing ===
    # Calculate expected turn: each user message = 1 turn increment
    current_seq = app.interview_turn_seq or 0
    expected_seq = current_seq  # This is the turn we're trying to process

    # Attempt atomic increment: UPDATE ... WHERE id = :id AND interview_turn_seq = :expected
    result = db.execute(
        update(Application)
        .where(Application.id == app.id)
        .where(Application.interview_turn_seq == expected_seq)
        .values(interview_turn_seq=expected_seq + 1)
    )
    db.commit()

    if result.rowcount == 0:
        # Turn already processed - return current state without reprocessing
        logger.info(
            f"[IDEMPOTENCY] Turn {expected_seq} already processed for app {app.id}, returning current state"
        )
        history = []
        if app.interview_log and app.interview_log not in ["[]", "null"]:
            try:
                history = json.loads(app.interview_log)
            except Exception:
                history = []

        return {
            "reply": "Your answer has already been recorded. Please wait for the next question.",
            "type": "duplicate",
            "current_question": (len(history) // 2) + 1 if history else 1,
            "progress": {
                "current": (len(history) // 2) + 1 if history else 1,
                "total": INTERVIEW_TOTAL_QUESTIONS,
                "percentage": round(float(app.overall_score or 0)),
            },
        }

    # Rowcount == 1 means we successfully claimed this turn - proceed with AI generation
    logger.info(f"[IDEMPOTENCY] Claimed turn {expected_seq + 1} for app {app.id}")

    # 1. Load context and history
    cv_context = app.cv_text_anonymized or ""
    job_description = getattr(app, "job_description", None) or (
        app.batch_job.description if app.batch_job else ""
    )
    language_context = (
        normalize_interview_language(req.language)
        or normalize_interview_language(getattr(app, "language", None))
        or "English"
    )

    history = []
    if app.interview_log and app.interview_log != "null":
        try:
            history = json.loads(app.interview_log)
            if not isinstance(history, list):
                history = []
        except Exception as e:
            logger.error(
                f"Failed to parse interview log for app {req.candidate_id}: {e}"
            )
            history = []

    # Reconstruct instruction tracking state from log (Step 3)

    # 2. Security Check (Phase 15: Centralized Security Layer)
    is_safe, sanitized_message, reason = SecurityLayer.process_candidate_input(
        req.message
    )

    if not is_safe:
        user_id_log = safe_user_id(current_user) if current_user else f"Guest:{app.id}"
        logger.warning(
            f"SECURITY ALERT: User {user_id_log} attempted injection: {reason}"
        )

        # Log to engine
        await engine.record_answer(app.id, -1, f"[VIOLATION] {reason}")

        security_lang = (
            normalize_interview_language(req.language)
            or normalize_interview_language(getattr(app, "language", None))
            or "English"
        )
        history.append({"role": "user", "content": sanitized_message})
        ai_reply = _msg("security_block", security_lang)
        history.append({"role": "assistant", "content": ai_reply})

        # Phase 19: REMOVED weighted penalty for integrity.
        # We still block the injection and log it, but don't deduct live score.
        app.interview_log = json.dumps(history)
        db.commit()

        return {
            "reply": ai_reply,
            "type": "warning",
            "feedback": _msg("integrity_feedback", security_lang, reason=reason),
            "current_score": app.overall_score,
            "total_questions": INTERVIEW_TOTAL_QUESTIONS,
            "current_question": len(history) // 2 + 1,
            "progress": {
                "current": len(history) // 2 + 1,
                "total": INTERVIEW_TOTAL_QUESTIONS,
                "percentage": round(app.overall_score),
            },
        }

    # 3. TIME LIMIT ENFORCEMENT (30 Minutes)
    MAX_DURATION_SECONDS = 30 * 60
    has_saved_progress = bool(app.interview_progress and app.interview_progress > 0)
    has_history = bool(app.interview_log and app.interview_log not in ["[]", "null"])
    fresh_interview = (not has_saved_progress) and (not has_history)

    # Set opened_at ONLY once — when it is null (first message)
    # Commit immediately so it persists even if AI call fails
    if not app.opened_at:
        app.opened_at = _utcnow()
        db.commit()

    elapsed = max(0.0, (_utcnow() - app.opened_at).total_seconds())

    if elapsed > MAX_DURATION_SECONDS and not fresh_interview:
        final_score = (
            app.overall_score if app.overall_score is not None else (app.cv_score or 0)
        )
        await engine.transition_to(
            app.id, InterviewState.COMPLETED, reason="Session Timeout"
        )
        db.commit()
        timeout_lang = (
            normalize_interview_language(req.language)
            or normalize_interview_language(getattr(app, "language", None))
            or "English"
        )
        return {
            "reply": _msg("timeout_reply", timeout_lang),
            "type": "timeout",
            "time_limit_reached": True,
            "time_left": 0,
            "feedback": _msg("timeout_reply", timeout_lang),
            "score_reasoning": _msg("proceeding_evaluation", timeout_lang),
            "current_score": round(float(final_score), 2),
            "total_questions": INTERVIEW_TOTAL_QUESTIONS,
            "current_question": max(1, app.interview_progress or 1),
            "progress": {
                "current": max(1, app.interview_progress or 1),
                "total": INTERVIEW_TOTAL_QUESTIONS,
                "percentage": 100,
                "state": "completed",
            },
        }

    # 4. Handshake Logic
    # Handshake words that should only apply on the very first turn
    HANDSHAKE_WORDS = {
        "ready",
        "start",
        "begin",
        "start interview",
        "commencer",
        "yalla",
        "hi",
        "hello",
        "arabic",
        "french",
        "francais",
        "english",
        "bonjour",
    }

    # Single-word responses that are NEVER a valid technical answer (any turn)
    ALWAYS_LAZY = {"ok", "okay", "d'accord", "go", "yes", "no", "oui", "non"}

    # First, determine current turn index (before appending)
    ai_turns = sum(1 for m in history if m.get("role") == "assistant")
    current_q_index = ai_turns + 1

    # Handshake applies ONLY on turn 1
    msg_lower = sanitized_message.lower().strip()
    is_handshake = current_q_index <= 1 and msg_lower in HANDSHAKE_WORDS

    # On turns > 1, treat ALWAYS_LAZY words as lazy answers, never as handshake
    if current_q_index > 1 and msg_lower in ALWAYS_LAZY:
        is_handshake = False

    # PHASE 15: State Transition on Start
    if is_handshake and app.interview_state == "not_started":
        await engine.transition_to(
            app.id, InterviewState.IN_PROGRESS, reason="Interview Started via Handshake"
        )

    should_append = True
    if len(history) > 0 and history[-1].get("role") == "user":
        if history[-1].get("content", "") == sanitized_message:
            should_append = False
            logger.info(f"[IDEMPOTENCY] Deduped duplicate message for app {app.id}")

    ai_turns = sum(1 for m in history if m.get("role") == "assistant")
    current_q_index = ai_turns + 1

    if should_append:
        history.append({"role": "user", "content": sanitized_message})
        if len(history) > 100:
            # Truncate to even number to preserve user/assistant pairs
            max_len = 100 if 100 % 2 == 0 else 99
            history = history[-max_len:]
            # Ensure history starts with a user message (Groq requirement)
            while history and history[0].get("role") != "user":
                history.pop(0)
            # Safety check — if history is now empty after trimming, reset it
            if not history:
                logger.warning(
                    f"[HISTORY] History empty after role-order fix for app {app.id}"
                )
    else:
        # If we skipped appending but the last message *is* assistant, then something is wrong
        # usually it means we are re-processing the last user message.
        pass
    # Guard against history being None
    history_to_search = (history or [])[:-1]
    for msg in reversed(history_to_search):
        if msg.get("role") == "assistant":
            break

    # Sync Role: Ensure declared_role matches detected_role from analysis if possible
    if app.analysis_json:
        try:
            analysis = json.loads(app.analysis_json)
            detected_role = analysis.get("detected_role") or analysis.get("role")
            if detected_role and app.declared_role != detected_role:
                logger.info(
                    f"[ROLE SYNC] Updating app {req.candidate_id} role: '{app.declared_role}' -> '{detected_role}'"
                )
                sync_cv_document(db, app, declared_role=detected_role)
                db.commit()
        except Exception as e:
            logger.error(f"[ROLE SYNC ERROR] App {req.candidate_id}: {e}")

    # PHASE 15: Handle End of Interview - Early Return
    if current_q_index > INTERVIEW_TOTAL_QUESTIONS and not is_handshake:
        await engine.transition_to(
            app.id, InterviewState.EVALUATING, reason="Max questions reached"
        )
        app.interview_state = "completed"
        app.status = "screening"
        db.commit()

        logger.info(f"[ENGINE] App {app.id}: Reached turn limit. Moving to EVALUATING.")

        completion_msg = {
            "English": "Interview complete. Thank you for your answers. Your results are being processed.",
            "French": "Entretien terminé. Merci pour vos réponses. Vos résultats sont en cours de traitement.",
            "Arabic": "L'entretien est terminé. Chokran 3la ijebetak. Nta7lo nkayymo neta2ijak.",
        }.get(language_context, "Interview complete. Thank you.")

        return {
            "reply": completion_msg,
            "type": "complete",
            "current_score": round(float(app.overall_score or app.cv_score or 0), 2),
            "feedback": "Your interview has been recorded.",
            "score_phase": "live",
            "score_label": f"Final score after {INTERVIEW_TOTAL_QUESTIONS} questions",
            "total_questions": INTERVIEW_TOTAL_QUESTIONS,
            "current_question": INTERVIEW_TOTAL_QUESTIONS,
            "interview_started": True,
            "unverified_skill_claims": [],
            "progress": {
                "current": INTERVIEW_TOTAL_QUESTIONS,
                "total": INTERVIEW_TOTAL_QUESTIONS,
                "percentage": 100,
                "state": "completed",
            },
        }

    # PHASE 15: Log answer received (if not handshake)
    if not is_handshake and should_append:
        await engine.record_answer(app.id, current_q_index - 1, sanitized_message)

    logger.info(
        f"[DEBUG INTERVIEW] App {req.candidate_id} | Turn: {current_q_index} | Msg: '{sanitized_message[:30]}...' | is_handshake: {is_handshake} | History: {len(history)} items"
    )

    # === ENGINE v2: STATEFUL INTERVIEW PIPELINE ===
    analysis_json = app.analysis_json or "{}"
    try:
        analysis_data = json.loads(analysis_json)
    except Exception:
        analysis_data = {}

    # NEW: Load calibration data from onboarding if available
    calibration_data = None
    if app.calibration_json:
        try:
            calibration_data = json.loads(app.calibration_json)
            logger.info(
                f"[CALIBRATION] Loaded calibration data for app {app.id} | score: {calibration_data.get('score')}"
            )
        except Exception as e:
            logger.warning(f"[CALIBRATION] Failed to parse calibration_json: {e}")

    engine_state = analysis_data.get("engine_v2_state")

    # 1. INITIALIZATION (If first turn or missing state)
    if not engine_state:
        logger.info(f"[ENGINE v2] Initializing state for app {app.id}")

        # PRIORITY 1: Use onboarding-refined skills if available
        skills_list = analysis_data.get("skills") or []

        # PRIORITY 2: Fallback to re-extraction only if onboarding skills are missing
        if not skills_list:
            from backend.ai.cv_analysis import extract_skills_from_cv

            skills_resp = await extract_skills_from_cv(cv_context, app.declared_role)
            skills_list = skills_resp.get("extracted_skills", {}).get("technical", [])
            logger.info(
                f"[ENGINE v2] No onboarding skills found. Re-extracted: {len(skills_list)}"
            )
        else:
            logger.info(
                f"[ENGINE v2] Using onboarding-refined skills: {len(skills_list)}"
            )

        # Determine strategy parameters
        role_conf = analysis_data.get("role_confidence", 0.5)

        # Seed metrics from CV analysis
        initial_metrics = analysis_data.get("skill_metrics")

        strategy = get_interview_strategy(skills_list, role_conf)
        engine_state = initialize_engine_state(
            strategy, skills=skills_list, initial_metrics=initial_metrics
        )

        # Phase 24: Reinforce seniority level from onboarding if available
        if analysis_data.get("seniority_level"):
            engine_state["seniority_level"] = analysis_data["seniority_level"]

        logger.info(
            f"[ENGINE v2] Strategy Resolved: {strategy} | Skills: {len(skills_list)} | Seniority: {engine_state.get('seniority_level', 'Default')}"
        )

    # 2. EVALUATION (Process previous answer)
    last_eval = {}
    if not is_handshake and sanitized_message:
        logger.info(f"[ENGINE v2] Evaluating Answer | Turn: {engine_state['turn']}")

        # Get last question and focus from history or state
        last_q = ""
        if history:
            for msg in reversed(history):
                if msg.get("role") == "assistant":
                    last_q = msg.get("content", "")
                    break

        last_focus = engine_state.get("current_focus")
        history_summary = "\n".join(
            [
                f"Q: {h['question']}\nA: {h['answer'][:100]}"
                for h in engine_state.get("history", [])[-2:]
            ]
        )

        last_eval = await evaluate_answer(
            question=last_q,
            answer=sanitized_message,
            focus=last_focus,
            history_summary=history_summary,
            declared_role=app.declared_role,
        )

        # Update engine state with evaluation (including category blending)
        engine_state = update_engine_state(
            state=engine_state,
            last_focus=last_focus,
            last_score=last_eval["score"],
            category_scores=last_eval.get("skills"),
        )

        # Sync simple score to DB for compatibility
        app.overall_score = last_eval["score"]

        # Append to engine history
        engine_state["history"].append(
            {
                "question": last_q,
                "answer": sanitized_message,
                "focus": last_focus,
                "score": last_eval["score"],
                "quality": last_eval["quality"],
            }
        )

    # 3. TERMINATION CHECK (Durable limit)
    if engine_state["turn"] >= engine_state["max_turns"]:
        logger.info(
            f"[ENGINE v3.1] Max turns reached ({engine_state['max_turns']}). Terminating."
        )
        await engine.transition_to(
            app.id, InterviewState.EVALUATING, reason="Max questions reached"
        )
        engine_state["terminated"] = True

        # v3.1 JUDGMENT: Compute final structured decision
        try:
            from backend.ai.interview import compute_final_decision

            final_decision = await compute_final_decision(
                engine_state, app.declared_role, calibration_data
            )
            engine_state["final_decision"] = final_decision
            logger.info(
                f"[JUDGMENT] Final Decision for application {app.id}: {final_decision.get('decision')}"
            )
        except Exception as e:
            logger.error(f"[JUDGMENT] Final decision failed: {e}")

        # Save state before exit
        analysis_data["engine_v2_state"] = engine_state
        sync_cv_document(db, app, analysis_json=analysis_data)
        db.commit()

        # Return completion response
        return {
            "reply": _msg("interview_complete", language_context),
            "type": "complete",
            "current_score": app.overall_score,
            "final_decision": engine_state.get("final_decision", {}),
            "progress": {
                "current": engine_state["turn"],
                "total": engine_state["max_turns"],
                "percentage": 100,
            },
        }

    # 4. GENERATION (Next question with calibration intelligence)
    logger.info(f"[ENGINE v2] Generating Turn {engine_state['turn'] + 1}")
    turn_resp = await generate_skill_driven_turn(
        state=engine_state,
        cv_context=cv_context,
        declared_role=app.declared_role,
        language=language_context,
        job_description=job_description,
        intelligence_layer=analysis_data,
        calibration_data=calibration_data,  # NEW: Pass calibration data for smarter questions
    )

    # Apply results to history (Frontend logic)
    history.append({"role": "user", "content": sanitized_message})
    history.append({"role": "assistant", "content": turn_resp["reply"]})
    app.interview_log = json.dumps(history)

    # 5. PERSISTENCE
    analysis_data["engine_v2_state"] = engine_state
    sync_cv_document(db, app, analysis_json=analysis_data)
    app.interview_progress = engine_state["turn"]
    db.commit()

    # 6. RETURN
    return {
        "reply": turn_resp["reply"],
        "hint_text": turn_resp["hint_text"],
        "type": "question",
        "current_score": app.overall_score,
        "skills": engine_state.get("live_skill_metrics", {}),
        "feedback": last_eval.get("feedback", ""),
        "score_reasoning": last_eval.get("reasoning", ""),
        "is_vague": last_eval.get("quality") == "vague",
        "current_question": engine_state["turn"],
        "progress": {
            "current": engine_state["turn"],
            "total": engine_state["max_turns"],
            "percentage": int((engine_state["turn"] / engine_state["max_turns"]) * 100),
        },
    }

    # End of Engine v2 Pipeline


@router.post("/voice/tts")
async def text_to_speech(payload: dict, current_user: User = Depends(get_current_user)):
    """
    High-Quality TTS using Edge-TTS (Microsoft Neural).
    Security: limits text input to prevent abuse.
    """
    import re

    text = payload.get("text", "")
    if not text or not text.strip():
        raise HTTPException(400, "Text is required")

    # Security: limit TTS input to prevent abuse
    MAX_TTS_CHARS = 2000
    if len(text) > MAX_TTS_CHARS:
        raise HTTPException(
            400, f"Text too long. Maximum {MAX_TTS_CHARS} characters allowed."
        )

    # Additional: strip HTML/script tags in case frontend sends rich text
    text = re.sub(r"<[^>]+>", "", text).strip()
    if not text:
        raise HTTPException(400, "Text is empty after sanitization")

    if not EDGE_TTS_AVAILABLE:
        return JSONResponse(
            status_code=503,
            content={
                "error": "TTS_SERVICE_UNAVAILABLE",
                "message": "AI Voice engine not installed on server. Falling back to browser voice.",
                "fallback": "browser_speech",
                "text": text,
            },
        )

    output_file = None
    try:
        voice = "en-US-ChristopherNeural"
        output_file = os.path.join(
            tempfile.gettempdir(), f"tts_{datetime.now().timestamp()}.mp3"
        )
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(output_file)

        # Cleanup helper
        def cleanup():
            if output_file and os.path.exists(output_file):
                try:
                    os.remove(output_file)
                except Exception:
                    pass

        return StreamingResponse(
            open(output_file, "rb"),
            media_type="audio/mpeg",
            background=BackgroundTask(cleanup),
        )
    except Exception as e:
        logger.error(f"TTS Generation failed: {e}")
        if output_file and os.path.exists(output_file):
            os.remove(output_file)
        return JSONResponse(
            status_code=500,
            content={
                "error": "TTS_GENERATION_FAILED",
                "message": str(e),
                "fallback": "browser_speech",
                "text": text,
            },
        )


# from backend.ai_service import evaluate_complete_interview # Removed redundant import


# --- REC #2: Auto Final Evaluation ---
async def run_background_final_evaluation(application_id: int, company_id: int):
    """
    Background task: performs the full AI evaluation after interview chat finishes.
    Opens its own DB session so it does not block the HTTP response.
    Uses context manager for safe commit/rollback.
    """
    from backend.database import SessionLocal

    with SessionLocal() as db:
        with db.begin():
            try:
                app = (
                    db.query(Application)
                    .filter(
                        Application.id == application_id,
                        Application.company_id == company_id,
                    )
                    .first()
                )
                if not app:
                    logger.warning(
                        f"[BG EVAL] App {application_id} not found. Skipping."
                    )
                    return

                # ATOMIC STATE CLAIM: Only proceed if evaluation_state is "pending"
                # Use raw SQL for atomic update to prevent race conditions
                # Tenant isolation: include company_id to prevent cross-tenant claims
                result = db.execute(
                    text(
                        "UPDATE applications SET evaluation_state='running', evaluation_started_at=NOW() "
                        "WHERE id=:id AND company_id=:company_id AND evaluation_state='pending'"
                    ),
                    {"id": application_id, "company_id": app.company_id},
                )
                db.commit()

                if result.rowcount == 0:
                    # Another evaluation is running or already completed/failed
                    logger.info(
                        f"[BG EVAL] Skipping — evaluation_state is not 'pending' for app {application_id}. "
                        f"Current state: {app.evaluation_state}"
                    )
                    return

                # Refresh app object after state change
                db.refresh(app)

                qa_pairs = []
                try:
                    if app.interview_qa_structured:
                        qa_pairs = json.loads(app.interview_qa_structured)
                    elif app.interview_log:
                        legacy_history = json.loads(app.interview_log)
                        qa_pairs = _extract_qa_pairs_from_history(legacy_history)
                except Exception as e:
                    logger.error(
                        f"[BG EVAL] QA load failed for app {application_id}: {e}"
                    )

                violations = []
                try:
                    if app.proctoring_violations:
                        violations = json.loads(app.proctoring_violations)
                except Exception:
                    pass

                logger.info(
                    f"[BG EVAL] Running final evaluation for app {application_id} ({len(qa_pairs)} QA pairs)"
                )
                result = await evaluate_complete_interview(
                    cv_text=app.cv_text_anonymized or "",
                    declared_role=app.declared_role or "Professional",
                    qa_pairs=qa_pairs,
                    violations=violations,
                )

                if result.get("final_score") is not None:
                    live_score = float(app.overall_score or app.cv_score or 50.0)
                    eval_score = float(result["final_score"])
                    app.overall_score = round(
                        (live_score * 0.4) + (eval_score * 0.6), 2
                    )
                    logger.info(
                        f"[BG EVAL] Blended score: {live_score} (live) + {eval_score} (eval) -> {app.overall_score}"
                    )
                else:
                    logger.warning(
                        f"[BG EVAL] evaluate_complete_interview returned no final_score for app {application_id}. Using weighted average fallback."
                    )
                    if qa_pairs:
                        valid_scores = [
                            q.get("score")
                            for q in qa_pairs
                            if q.get("score") and q.get("score") > 0
                        ]
                        if valid_scores:
                            midpoint = len(valid_scores) // 2
                            if midpoint > 0:
                                avg_early = sum(valid_scores[:midpoint]) / midpoint
                            else:
                                avg_early = valid_scores[0]
                            late_count = len(valid_scores) - midpoint
                            if late_count > 0:
                                avg_late = sum(valid_scores[midpoint:]) / late_count
                            else:
                                avg_late = valid_scores[-1]
                            app.overall_score = round(
                                (avg_early * 0.4) + (avg_late * 0.6), 2
                            )
                        else:
                            app.overall_score = app.cv_score or 50.0
                    else:
                        app.overall_score = app.cv_score or 50.0

                # DATA SYNC: Merge AI Results into analysis_json for Dashboard
                try:
                    analysis_data = {}
                    if app.analysis_json:
                        try:
                            analysis_data = json.loads(app.analysis_json)
                        except Exception:
                            analysis_data = {}

                    if isinstance(result, dict):
                        if "skill_metrics" in result and isinstance(
                            result["skill_metrics"], dict
                        ):
                            prev_metrics = analysis_data.get("skill_metrics", {})
                            if isinstance(prev_metrics, dict):
                                merged_metrics = prev_metrics.copy()
                                for k, v in result["skill_metrics"].items():
                                    if k in merged_metrics:
                                        merged_metrics[k] = round(
                                            (float(merged_metrics[k]) * 0.5)
                                            + (float(v) * 0.5),
                                            1,
                                        )
                                    else:
                                        merged_metrics[k] = float(v)
                                analysis_data["skill_metrics"] = merged_metrics
                            else:
                                analysis_data["skill_metrics"] = result["skill_metrics"]

                        if "strengths" in result:
                            analysis_data["strengths"] = result["strengths"]
                        if "weaknesses" in result:
                            analysis_data["weaknesses"] = result["weaknesses"]
                        if "explainability" in result:
                            analysis_data["explainability"] = result["explainability"]
                        if "recommendation" in result:
                            analysis_data["verdict"] = result["recommendation"]

                        sync_cv_document(db, app, analysis_json=analysis_data)
                        logger.info(
                            f"[BG EVAL] Synced AI analysis data to analysis_json for app {application_id}"
                        )

                        if "detailed_feedback" in result:
                            try:
                                history = json.loads(app.interview_log or "[]")
                                if isinstance(history, list):
                                    summary_msg = f"Interview Complete. Evaluation Summary: {result['detailed_feedback']}"
                                    history.append(
                                        {"role": "assistant", "content": summary_msg}
                                    )
                                    app.interview_log = json.dumps(history)
                                    logger.info(
                                        f"[BG EVAL] Appended final summary to interview_log for app {application_id}"
                                    )
                            except Exception as hist_err:
                                logger.error(
                                    f"[BG EVAL] Failed to append summary to log: {hist_err}"
                                )

                except Exception as sync_err:
                    logger.error(
                        f"[BG EVAL] Data sync failed for app {application_id}: {sync_err}"
                    )

                app.status = "screening"
                notes = result.get("detailed_feedback", "")
                if notes:
                    app.recruiter_notes = f"AI Evaluation: {notes[:2000]}"

                app.interview_state = "completed"
                # Mark final evaluation as done
                app.final_eval_done = True
                app.final_eval_timestamp = _utcnow()
                # Update evaluation state machine
                app.evaluation_state = "completed"
                app.evaluation_completed_at = _utcnow()
                app.evaluation_source = "background"
                logger.info(
                    f"[BG EVAL] Final score {app.overall_score:.1f} saved for app {application_id}"
                )

                # REC #3: Notify recruiter on interview completion
                try:
                    recruiter_email = None
                    if app.batch_job and app.batch_job.recruiter:
                        recruiter_email = app.batch_job.recruiter.email
                    elif app.job and app.job.recruiter_id:
                        recruiter_u = (
                            db.query(User)
                            .filter(User.id == app.job.recruiter_id)
                            .first()
                        )
                        if recruiter_u:
                            recruiter_email = recruiter_u.email

                    if recruiter_email:
                        from backend.config import get_settings
                        from backend.email_service import EmailService

                        settings = get_settings()
                        email_service = EmailService()

                        campaign_title = "Technical Interview"
                        if app.batch_job:
                            campaign_title = app.batch_job.title
                        elif app.job:
                            campaign_title = app.job.title

                        dashboard_url = f"{settings.frontend_url}/recruiter/campaigns"
                        if app.batch_id:
                            dashboard_url = f"{settings.frontend_url}/recruiter/campaigns-view?id={app.batch_id}"

                        email_service.send_interview_complete_email(
                            recruiter_email=recruiter_email,
                            candidate_name=app.full_name or "A candidate",
                            campaign_title=campaign_title,
                            final_score=app.overall_score,
                            dashboard_url=dashboard_url,
                        )
                        logger.info(
                            f"[BG EVAL] Completion notification sent to recruiter {recruiter_email}"
                        )
                except Exception as email_err:
                    logger.error(
                        f"[BG EVAL] Failed to send completion notification: {email_err}"
                    )

            except Exception as e:
                logger.error(
                    f"[BG EVAL] Unhandled error for app {application_id}: {e}",
                    exc_info=True,
                )
                app.evaluation_state = "failed"
                db.commit()
                raise


@router.post("/interview/evaluate-final")
async def evaluate_final_interview(
    payload: dict,
    db: Session = Depends(get_db),
    auth: Tuple[Optional[User], Application] = Depends(get_interview_access),
):
    """
    REQUEST 3: Final Batch Evaluation
    Evaluates ALL interview answers in one go.
    """
    current_user, app = auth
    # Fix: Accepting a dict payload to match frontend JSON body
    application_id = payload.get("application_id")
    force = payload.get("force_reevaluation", False)

    if not app:
        if not application_id:
            raise HTTPException(400, "application_id required")
        # TENANT ISOLATION: require company_id on fallback query
        company_id = _resolve_company_id(current_user, db) if current_user else None
        if company_id is None:
            raise HTTPException(404, "Application not found")
        app = (
            db.query(Application)
            .filter(
                Application.id == application_id,
                Application.company_id == company_id,
            )
            .first()
        )
        if not app:
            raise HTTPException(404, "Application not found")

    # --- OWNERSHIP CHECK (already verified above) ---

    # EVALUATION STATE MACHINE: Coordinated evaluation
    is_recruiter = current_user and safe_user_role(current_user) in [
        "admin",
        "recruiter",
    ]

    if app.evaluation_state == "completed":
        if not force:
            logger.info(
                f"[EVAL-FINAL] Evaluation already completed for app {application_id}. "
                f"Completed at: {app.evaluation_completed_at}, source: {app.evaluation_source}"
            )
            return {
                "success": True,
                "message": "Evaluation already completed",
                "final_score": app.overall_score,
                "completed_at": app.evaluation_completed_at.isoformat()
                if app.evaluation_completed_at
                else None,
                "source": app.evaluation_source,
            }
        elif is_recruiter:
            # Allow force re-evaluation for recruiters/admins
            logger.info(
                f"[EVAL-FINAL] Force re-evaluation requested for app {application_id}"
            )
            app.evaluation_state = "pending"
            db.commit()
        else:
            raise HTTPException(
                403, "Force re-evaluation requires recruiter or admin role"
            )

    # ATOMIC STATE CLAIM: Try to claim evaluation slot
    # Tenant isolation: include company_id to prevent cross-tenant claims
    result = db.execute(
        text(
            "UPDATE applications SET evaluation_state='running', evaluation_started_at=NOW() "
            "WHERE id=:id AND company_id=:company_id AND evaluation_state='pending'"
        ),
        {"id": application_id, "company_id": app.company_id},
    )
    db.commit()

    if result.rowcount == 0:
        logger.info(
            f"[EVAL-FINAL] Could not claim evaluation — state: {app.evaluation_state} for app {application_id}"
        )
        return {
            "success": False,
            "message": f"Evaluation in progress or already completed (state: {app.evaluation_state})",
            "state": app.evaluation_state,
        }

    db.refresh(app)

    # --- Candway 2.5: Use Structured QA Storage ---
    qa_pairs = []
    try:
        if app.interview_qa_structured:
            qa_pairs = json.loads(app.interview_qa_structured)
        elif app.interview_log:
            # Fallback for legacy records
            history = json.loads(app.interview_log)
            qa_pairs = _extract_qa_pairs_from_history(history)
            logger.warning(f"Using legacy history for app {application_id}")
    except Exception as e:
        logger.error(f"Error loading QA pairs for app {application_id}: {e}")
    # Load violations
    violations = []
    try:
        if app.proctoring_violations:
            violations = json.loads(app.proctoring_violations)
    except Exception as viol_err:
        logger.error(f"Violation loading failed for app {application_id}: {viol_err}")

    # Call AI (Request 3)
    result = await evaluate_complete_interview(
        cv_text=app.cv_text_anonymized,
        declared_role=app.declared_role,
        qa_pairs=qa_pairs,
        violations=violations,
    )
    # Update Final Score
    # Update Final Score with 40/60 Blend (Bug #3)
    if result.get("final_score") is not None:
        live_score = float(app.overall_score or app.cv_score or 50.0)
        eval_score = float(result["final_score"])
        app.overall_score = round((live_score * 0.4) + (eval_score * 0.6), 2)
        app.recruiter_notes = f"AI Evaluation: {result.get('detailed_feedback')}"
        logger.info(
            f"[EVAL-FINAL] Blended score: {live_score} (live) + {eval_score} (eval) -> {app.overall_score}"
        )

        # --- Phase 4: Integration - Generate Career Roadmap ---
        # Guard: Skip roadmap for guest applications
        if not current_user:
            logger.info(
                f"[ROADMAP] Skipping roadmap for guest application {application_id}"
            )
        else:
            try:
                from backend.ai.roadmap import generate_career_roadmap
                from backend.database import Course

                # Fetch available courses
                available_courses = (
                    db.query(Course).filter(Course.status == "published").all()
                )
                courses_formatted = [
                    {"id": c.id, "title": c.title, "description": c.description}
                    for c in available_courses
                ]

                # Safe skills extraction — handles None user, None skills, empty string
                candidate_profile = (
                    getattr(current_user, "candidate_profile", None)
                    if current_user
                    else None
                )
                if candidate_profile and candidate_profile.skills:
                    current_skills = safe_user_skills(current_user)
                else:
                    # Fall back to skills detected in the interview analysis
                    current_skills = []
                    if app.analysis_json:
                        try:
                            analysis_data = json.loads(app.analysis_json)
                            skill_metrics = analysis_data.get("skill_metrics", {})
                            current_skills = (
                                list(skill_metrics.keys())
                                if isinstance(skill_metrics, dict)
                                else []
                            )
                        except Exception:
                            pass

                roadmap_result = await generate_career_roadmap(
                    target_role=app.declared_role or "Professional",
                    current_skills=current_skills,
                    available_courses=courses_formatted,
                    audit_context={
                        "interview_score": app.overall_score,
                        "interview_feedback": result.get("detailed_feedback"),
                        "qa_pairs": qa_pairs,
                    },
                )

                if roadmap_result:
                    sync_cv_document(db, app, roadmap_json=roadmap_result)
                    logger.info(f"Roadmap generated for app {application_id}")
            except Exception as roadmap_err:
                logger.error(
                    f"Failed to generate roadmap: {roadmap_err}", exc_info=True
                )

    # Keep interview transcript in role/content format and enrich dashboard analysis.
    try:
        analysis_data = {}
        if app.analysis_json:
            try:
                analysis_data = json.loads(app.analysis_json)
            except Exception:
                analysis_data = {}
        if not isinstance(analysis_data, dict):
            analysis_data = {}

        if isinstance(result, dict):
            if isinstance(result.get("skill_metrics"), dict):
                analysis_data["skill_metrics"] = result["skill_metrics"]
                derived = derive_dashboard_insights_from_skills(result["skill_metrics"])
                analysis_data["strengths"] = (
                    result.get("strengths") or derived["strengths"]
                )
                analysis_data["missing_skills"] = (
                    result.get("weaknesses") or derived["missing_skills"]
                )
                analysis_data["weaknesses"] = (
                    result.get("weaknesses") or derived["weaknesses"]
                )
                analysis_data["action_plan"] = (
                    result.get("action_plan") or derived["action_plan"]
                )

                explainability = analysis_data.get("explainability")
                if not isinstance(explainability, dict):
                    explainability = {}
                if isinstance(result.get("explainability"), dict):
                    explainability.update(result["explainability"])
                if not explainability.get("gap_analysis"):
                    explainability["gap_analysis"] = derived["gap_analysis"]
                analysis_data["explainability"] = explainability

            if result.get("detailed_feedback"):
                analysis_data["summary"] = result["detailed_feedback"]
                app.recruiter_notes = (
                    f"AI Evaluation: {result.get('detailed_feedback')}"
                )

        sync_cv_document(db, app, analysis_json=analysis_data)

        history = []
        if app.interview_log and app.interview_log != "null":
            try:
                parsed_history = json.loads(app.interview_log)
                if isinstance(parsed_history, list):
                    history = parsed_history
            except Exception:
                history = []

        if result.get("detailed_feedback"):
            summary_msg = f"Interview Complete. Evaluation Summary: {result.get('detailed_feedback')}"
            if not any(
                isinstance(item, dict)
                and item.get("role") in {"assistant", "ai", "bot"}
                and isinstance(item.get("content"), str)
                and "Evaluation Summary:" in item.get("content", "")
                for item in history
            ):
                history.append({"role": "assistant", "content": summary_msg})
                app.interview_log = json.dumps(history)
    except Exception as sync_err:
        logger.error(
            f"Final evaluation sync failed for app {application_id}: {sync_err}",
            exc_info=True,
        )

    app.interview_state = "completed"
    if app.status in ["interviewing", "invited", "pending", "applied"]:
        app.status = "screening"
    # Mark final evaluation as done
    app.final_eval_done = True
    app.final_eval_timestamp = _utcnow()
    # Evaluation state machine
    app.evaluation_state = "completed"
    app.evaluation_completed_at = _utcnow()
    app.evaluation_source = "manual"
    # Bug #26: Include roadmap in response for completion modal
    if app.roadmap_json:
        result["roadmap_json"] = json.loads(app.roadmap_json)

    db.commit()
    return result


@router.post("/interview/report-fraud")
async def report_fraud(
    req: FraudReport,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Role gate — candidates cannot report fraud
    if not current_user or safe_user_role(current_user) not in ["recruiter", "admin"]:
        raise HTTPException(
            status_code=403,
            detail="Only recruiters and admins can submit fraud reports",
        )

    # TENANT ISOLATION: recruiter/admin must be scoped to their company
    company_id = _resolve_company_id(current_user, db)
    if company_id is None:
        raise HTTPException(status_code=404, detail="Application not found")

    app = (
        db.query(Application)
        .filter(
            Application.id == req.application_id,
            Application.company_id == company_id,
        )
        .first()
    )
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")

    # STRICT FRAUD SCORE
    app.fraud_score = 100.0
    app.verdict = f"FRAUD DETECTED by {safe_user_id(current_user)}: {req.reason}"
    app.fraud_reported_by = (
        current_user.id
    )  # Safe to access directly - role-gated above
    app.fraud_reported_at = _utcnow()
    db.commit()
    return {
        "success": True,
        "message": "Fraud report submitted successfully",
        "fraud_score": app.fraud_score,
    }


@router.post("/interview/upload-segment")
async def upload_video_segment(
    application_id: int,
    video_segment: UploadFile = File(...),
    db: Session = Depends(get_db),
    auth: Tuple[Optional[User], Application] = Depends(get_interview_access),
):
    """
    Enterprise: Receive and store video segments.
    Segments are merged or stored sequentially for recruiter review.
    Security: sanitises filename and validates path is inside upload_dir.
    """
    current_user, app = auth
    if not app:
        company_id = _resolve_company_id(current_user, db) if current_user else None
        if company_id is None:
            raise HTTPException(status_code=404, detail="Application not found")
        app = (
            db.query(Application)
            .filter(
                Application.id == application_id,
                Application.company_id == company_id,
            )
            .first()
        )
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")

    # Storage Path
    upload_dir = os.path.join(
        "uploads", "interviews", str(application_id), "video_segments"
    )
    os.makedirs(upload_dir, exist_ok=True)

    # Sanitise filename
    safe_filename = _sanitise_filename(video_segment.filename)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_path = os.path.join(upload_dir, f"{timestamp}_{safe_filename}")

    # Final safety check — ensure resolved path is inside upload_dir
    resolved = os.path.realpath(file_path)
    if not resolved.startswith(os.path.realpath(upload_dir)):
        raise HTTPException(status_code=400, detail="Invalid filename")

    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(video_segment.file, buffer)

        # Update app record if it's the first segment or to track progress
        if not app.video_file_path:
            app.video_file_path = file_path
            db.commit()

        return {"status": "success", "file": file_path}
    except Exception as e:
        logger.error(f"Failed to save video segment: {e}")
        raise HTTPException(status_code=500, detail="Failed to save video segment")


@router.post("/interview/sync-proctoring")
async def sync_proctoring(
    req: ProctoringSyncRequest,
    db: Session = Depends(get_db),
    auth: Tuple[Optional[User], Application] = Depends(get_interview_access),
):
    """
    SERVER-SIDE PROCTORING: Sync violations from client to DB.
    Computes trust score server-side based on violation history.
    """
    current_user, app = auth
    if not app:
        company_id = _resolve_company_id(current_user, db) if current_user else None
        if company_id is None:
            raise HTTPException(status_code=404, detail="Application not found")
        app = (
            db.query(Application)
            .filter(
                Application.id == req.application_id,
                Application.company_id == company_id,
            )
            .first()
        )
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    try:
        violations = json.loads(app.proctoring_violations or "[]")

        # Bug #19: Throttle identical violations (prevent spam)
        now = datetime.now()
        if violations:
            last_v = violations[-1]
            try:
                last_time = datetime.fromisoformat(last_v.get("server_timestamp"))
                if (
                    last_v.get("type") == req.violation_type
                    and (now - last_time).total_seconds() < 5
                ):
                    return {"status": "throttled", "count": len(violations)}
            except Exception:
                pass

        violations.append(
            {
                "type": req.violation_type,
                "timestamp": req.timestamp,
                "details": req.details,
                "server_timestamp": now.isoformat(),
            }
        )
        app.proctoring_violations = json.dumps(violations)

        # TIERED FLAGGING: Combined approach for better detection
        CRITICAL_VIOLATIONS = {"DevTools opened", "Multiple faces detected"}
        HIGH_VIOLATIONS = {"Tab switch detected", "Suspiciously fast answer"}

        critical_count = sum(
            1 for v in violations if v.get("type") in CRITICAL_VIOLATIONS
        )
        high_count = sum(1 for v in violations if v.get("type") in HIGH_VIOLATIONS)

        # Bug #21: Weighted penalties for trust score
        PENALTY_MAP = {
            "Face not detected": -0.5,  # Less harsh for glitches
            "Multiple faces detected": -2.0,
            "Tab switch detected": -3.0,
            "DevTools opened": -10.0,
            "Window focus lost": -1.0,
            "Suspiciously fast answer": -5.0,
            "Right-click attempt": -0.2,
        }
        trust = 100.0
        for v in violations:
            penalty = PENALTY_MAP.get(v.get("type"), -1.0)
            trust = max(0.0, trust + penalty)

        should_flag = (
            trust < 50
            or critical_count >= 1
            or high_count >= 8
            or len(violations) > 20
            or (trust < 70 and len(violations) > 10)
        )

        if should_flag:
            app.interview_state = "flagged"
            app.verdict = (
                f"Proctoring: {len(violations)} violations, trust={round(trust)}%"
            )
            logger.warning(
                f"[PROCTOR] Flagged app {app.id}: {len(violations)} violations, trust={round(trust)}%"
            )

        review_recommended = trust < 70 or len(violations) > 8

        db.commit()
        return {
            "status": "synced",
            "count": len(violations),
            "server_trust_score": round(trust, 1),
            "review_recommended": review_recommended,
        }
    except Exception as e:
        logger.error(f"Proctoring sync failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to sync proctoring data")


@router.post("/interview/case-study/generate")
async def generate_case_study(
    payload: dict,
    db: Session = Depends(get_db),
    auth: Tuple[Optional[User], Application] = Depends(get_interview_access),
):
    current_user, app = auth
    """
    Generate a case study for a specific skill gap.
    Payload: { "skill": "Python" }
    """
    skill = payload.get("skill")
    if not skill:
        raise HTTPException(status_code=400, detail="Skill required")

    # OWNERSHIP CHECK (if app was fetched via fallback)
    if (
        app
        and current_user
        and safe_user_role(current_user) not in ["recruiter", "admin"]
    ):
        if app.user_id and app.user_id != current_user.id:
            raise HTTPException(
                status_code=403, detail="Not authorized to access this application"
            )
    # Mock generation or use minimal LLM call
    # For speed/robustness in demo, we return a structured template
    return {
        "success": True,
        "data": {
            "title": f"Strategic Implementation of {skill} in Financial Systems",
            "scenario": f"You are tasked with modernizing a legacy financial system using {skill}. The current system handles 10k transactions per second but suffers from latency.",
            "task": f"Design a microservices architecture using {skill} that reduces latency by 40% while ensuring ACID compliance.",
            "constraints": [
                "Must be scalable to 50k TPS",
                "Cannot increase infrastructure cost by more than 20%",
                "Must maintain 99.99% availability",
            ],
        },
    }


@router.post("/interview/case-study/submit")
async def submit_case_study(
    payload: dict,
    db: Session = Depends(get_db),
    auth: Tuple[Optional[User], Application] = Depends(get_interview_access),
):
    current_user, app = auth
    """
    Submit a case study response for analysis.
    Payload: { "skill": "Python", "response": "My solution is..." }
    """
    # Mock Analysis
    # In real world, send to LLM for grading
    return {
        "success": True,
        "data": {
            "score": 85,
            "feedback": "Strong architectural patterns proposed. Good handling of scalability constraints. Could be more specific on database consistency models.",
            "verdict": "Pass",
        },
    }


@router.post("/interview/resume")
async def resume_interview(
    payload: dict,
    db: Session = Depends(get_db),
    auth: Tuple[Optional[User], Application] = Depends(get_interview_access),
):
    """
    Resume a paused or in-progress interview from last saved state.
    Returns interview history and progress for frontend to restore.
    """
    current_user, app = auth
    application_id = payload.get("application_id")
    if not application_id:
        raise HTTPException(status_code=400, detail="application_id required")

    if not app:
        company_id = _resolve_company_id(current_user, db) if current_user else None
        if company_id is None:
            raise HTTPException(status_code=404, detail="Application not found")
        app = (
            db.query(Application)
            .filter(
                Application.id == application_id,
                Application.company_id == company_id,
            )
            .first()
        )
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")

    # OWNERSHIP CHECK
    if current_user and safe_user_role(current_user) not in ["recruiter", "admin"]:
        if app.user_id and app.user_id != current_user.id:
            raise HTTPException(
                status_code=403, detail="Not authorized to access this application"
            )

    # Check if interview can be resumed
    if app.interview_state not in ["in_progress", "paused"]:
        return {
            "can_resume": False,
            "reason": f"Interview is {app.interview_state}",
            "progress": 0,
        }
    # Load saved history
    history = []
    if app.interview_log and app.interview_log != "null":
        try:
            history = json.loads(app.interview_log)
            if not isinstance(history, list):
                history = []
        except Exception as e:
            logger.error(f"Failed to parse resume log for app {application_id}: {e}")
            history = []
    # Load skill metrics for talent graph restoration
    skill_metrics = None
    cv_skill_metrics = None
    try:
        if app.analysis_json:
            analysis = json.loads(app.analysis_json)
            skill_metrics = analysis.get("skill_metrics")
            cv_skill_metrics = analysis.get("cv_skill_metrics") or skill_metrics
    except Exception:
        pass
    # Load structured QA for dashboard sync
    qa_history = []
    try:
        if app.interview_qa_structured:
            qa_history = json.loads(app.interview_qa_structured)
    except Exception:
        pass

    return {
        "can_resume": True,
        "application_id": app.id,
        "progress": max(app.interview_progress or 0, len(history) // 2),
        "total_questions": INTERVIEW_TOTAL_QUESTIONS,
        "history": history,
        "qa_history": qa_history,
        "current_score": app.overall_score or 75,
        "language": normalize_interview_language(app.language) or "English",
        "last_saved": app.interview_last_saved.isoformat()
        if app.interview_last_saved
        else None,
        "state": app.interview_state,
        "skill_metrics": skill_metrics,
        "cv_skill_metrics": cv_skill_metrics,
    }


@router.post("/interview/pause")
async def pause_interview(
    payload: dict,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    auth: Tuple[Optional[User], Application] = Depends(get_interview_access),
):
    """
    Pause the interview and save current state.
    Candidate can resume later from dashboard.
    """
    current_user, app = auth
    application_id = payload.get("application_id")
    if not application_id:
        raise HTTPException(status_code=400, detail="application_id required")

    if not app:
        company_id = _resolve_company_id(current_user, db) if current_user else None
        if company_id is None:
            raise HTTPException(status_code=404, detail="Application not found")
        app = (
            db.query(Application)
            .filter(
                Application.id == application_id,
                Application.company_id == company_id,
            )
            .first()
        )
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")

    # OWNERSHIP CHECK
    if current_user and safe_user_role(current_user) not in ["recruiter", "admin"]:
        if app.user_id and app.user_id != current_user.id:
            raise HTTPException(
                status_code=403, detail="Not authorized to access this application"
            )

    # Update state to paused
    app.interview_state = "paused"
    app.interview_last_saved = _utcnow()

    # PROACTIVE FEATURE: Trigger roadmap on pause as well
    from backend.routers.career import run_proactive_roadmap_generation

    target_role = app.declared_role or getattr(app, "job_title", "Professional")
    if current_user:
        if current_user:
            background_tasks.add_task(
                run_proactive_roadmap_generation, current_user.id, target_role, db
            )
    else:
        logger.info(f"[ROADMAP] Skipping for guest app {app.id}")

    db.commit()
    user_id_log = safe_user_id(current_user) if current_user else f"Guest:{app.id}"
    logger.info(
        f"Interview paused: user_id={user_id_log}, app_id={application_id}, "
        f"progress={app.interview_progress}/{INTERVIEW_TOTAL_QUESTIONS}"
    )
    return {
        "success": True,
        "message": "Interview paused successfully. You can resume anytime from your dashboard.",
        "progress": app.interview_progress,
        "total_questions": INTERVIEW_TOTAL_QUESTIONS,
        "percentage": round((app.interview_progress / INTERVIEW_TOTAL_QUESTIONS) * 100)
        if app.interview_progress
        else 0,
    }


@router.post("/interview/chat")
async def interview_chat(
    req: ChatRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    auth: Tuple[Optional[User], Application] = Depends(get_interview_access),
):
    print("DEBUG: === interview_chat START ===")
    print(f"DEBUG: candidate_id from req: {req.candidate_id}")
    current_user, app = auth
    print(
        f"DEBUG: after auth - user: {current_user.id if current_user else None}, app: {app.id if app else None}"
    )
    if not app:
        print("DEBUG: ERROR app is None!")
    try:
        return await _interview_chat_core(
            req, db, current_user, background_tasks, application=app
        )
    except HTTPException:
        raise
    except Exception as e:
        print("=== CRASH ERROR ===")
        print(f"REQ Candidate ID: {req.candidate_id}")
        import traceback

        print(traceback.format_exc())
        print("===================")
        logger.error(f"Global Crash in Interview Chat: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail="Internal interview processing error"
        )


# ═══════════════════════════════════════════════════════════════
# PRACTICE INTERVIEW MODE - No DB persistence, no proctoring
# ═══════════════════════════════════════════════════════════════


class PracticeRequest(BaseModel):
    message: str = Field(..., max_length=5000)
    role: str = Field("Software Engineer", max_length=100)
    language: Optional[str] = Field("English", max_length=50)
    history: Optional[list] = []
    current_score: Optional[float] = 75.0


@router.post("/interview/practice")
async def practice_interview(
    req: PracticeRequest, current_user: User = Depends(get_current_user)
):
    """
    Practice Interview Mode.
    - Reuses AI question generation
    - Does NOT save to database
    - No proctoring, no time limit
    - Rate limited to 20 messages per 10 minutes
    """
    # Rate limit practice mode - use safe_user_id to handle guests
    identifier = f"practice_{safe_user_id(current_user)}"
    is_allowed, retry_after = interview_rate_limiter.is_allowed(
        identifier, max_requests=20, window_seconds=600
    )
    if not is_allowed:
        raise HTTPException(
            status_code=429,
            detail=f"Practice rate limit reached. Please wait {retry_after} seconds.",
            headers={"Retry-After": str(retry_after)},
        )

    # Input validation
    if not req.message or not req.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")
    if len(req.message) > 5000:
        raise HTTPException(
            status_code=400, detail="Message too long (max 5000 characters)"
        )

    # Security check
    is_safe, reason = AISecurity.detect_prompt_injection(req.message)
    if not is_safe:
        return {
            "reply": "Please focus on professional interview topics.",
            "type": "warning",
            "feedback": f"Input flagged: {reason}",
            "current_score": 0,
            "skills": {
                "Technical": 0,
                "Communication": 0,
                "Problem Solving": 0,
                "Adaptability": 0,
                "Confidence": 0,
            },
            "is_practice": True,
        }

    # Build history from client-sent context
    history = req.history or []
    sanitized_message = AISecurity.sanitize_input(req.message)
    history.append({"role": "user", "content": sanitized_message})

    ai_turns = sum(1 for m in history if m.get("role") == "assistant")
    current_q_index = ai_turns + 1
    practice_language = normalize_interview_language(req.language) or "English"

    # Check for handshake
    is_handshake = req.message.lower().strip() in [
        "ready",
        "start",
        "begin",
        "commencer",
        "yalla",
        "go",
        "hi",
        "hello",
        "arabic",
        "french",
        "english",
        "ok",
        "okay",
    ]

    # Check completion (5 questions for practice mode)
    PRACTICE_TOTAL = 5
    if current_q_index > PRACTICE_TOTAL:
        return {
            "reply": "Practice session complete! You answered all 5 questions.",
            "type": "complete",
            "current_score": req.current_score or 75,
            "feedback": "Great practice! Ready for the real interview?",
            "skills": {
                "Technical": 75,
                "Communication": 75,
                "Problem Solving": 75,
                "Adaptability": 75,
                "Confidence": 75,
            },
            "total_questions": PRACTICE_TOTAL,
            "current_question": PRACTICE_TOTAL,
            "is_practice": True,
            "progress": {
                "current": PRACTICE_TOTAL,
                "total": PRACTICE_TOTAL,
                "percentage": 100,
            },
        }

    # Generate AI response using existing engine
    try:
        ai_response = await generate_interview_turn_with_timeout(
            cv_context="Practice mode - no CV context available. Generate generic questions for the role.",
            declared_role=req.role or "Software Engineer",
            history=history[-20:],  # Keep last 20 messages
            current_q_index=current_q_index,
            total_questions=PRACTICE_TOTAL,
            language=practice_language,
            job_title=req.role,
            job_description=None,
            app_id=0,
            current_score=req.current_score or 75.0,
        )
    except Exception as e:
        logger.error(f"Practice interview AI error: {e}", exc_info=True)
        ai_response = get_fallback_turn(
            current_q_index, req.role, req.current_score or 75.0, practice_language
        )

    # Lazy detection (same as real interview)
    previous_ai_text = ""
    for msg in reversed(history[:-1]):
        if msg.get("role") == "assistant":
            previous_ai_text = msg.get("content", "")
            break

    is_lazy = is_lazy_answer(sanitized_message, previous_ai_text, practice_language)
    if is_lazy and not is_handshake:
        new_score = calculate_adaptive_score(
            req.current_score or 75.0, 10.0, current_q_index, False
        )
        ai_response["feedback"] = _msg("practice_lazy_feedback", practice_language)
    else:
        raw_score = ai_response.get("current_score", req.current_score or 75.0)
        new_score = calculate_adaptive_score(
            req.current_score or 75.0, raw_score, current_q_index, is_handshake
        )

    ai_response["current_score"] = new_score
    ai_response["is_practice"] = True
    ai_response["total_questions"] = PRACTICE_TOTAL
    ai_response["current_question"] = current_q_index
    ai_response["progress"] = {
        "current": current_q_index,
        "total": PRACTICE_TOTAL,
        "percentage": round((current_q_index / PRACTICE_TOTAL) * 100),
    }

    # Add the AI reply to history for client to send back next turn
    reply_text = ai_response.get("reply", "Dynamic error during practice generation.")

    if (
        isinstance(reply_text, str)
        and reply_text.strip().startswith("{")
        and reply_text.strip().endswith("}")
    ):
        try:
            import json

            reply_text = json.loads(reply_text)
        except Exception:
            pass

    if isinstance(reply_text, dict):
        parts = []
        company = reply_text.get("company_context", "")
        team = reply_text.get("team_size", "")
        stack = reply_text.get("tech_stack", "")
        scenario = reply_text.get("scenario", "")
        problem = reply_text.get("problem", "")
        action = reply_text.get("actionRequest", reply_text.get("action_request", ""))

        if company or team or stack:
            context_str = "Context: " + ", ".join(filter(None, [company, team, stack]))
            parts.append(context_str)

        if scenario:
            parts.append(scenario)
        if problem:
            parts.append(problem)
        if action:
            parts.append(action)

        if not parts:
            prompt = reply_text.get("prompt", "")
            if prompt:
                parts.append(prompt)

        if parts:
            reply_text = "\n\n".join(parts)
        else:
            try:
                clean_dict = {
                    k: v
                    for k, v in reply_text.items()
                    if k not in ["scenario_type", "type", "current_score", "skills"]
                }
                reply_text = " ".join([str(v) for v in clean_dict.values()])
            except Exception:
                import json

                reply_text = json.dumps(reply_text)

    history.append({"role": "assistant", "content": str(reply_text)})
    ai_response["history"] = history

    return ai_response


# TEST ENDPOINT: Verify Groq API is working
@router.get("/test/groq-connection")
async def test_groq_connection(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Test endpoint to verify Groq API connectivity and configuration.
    Only available to authenticated users.
    """
    from backend.ai.llm import call_groq_cascade

    logger.info(f"[TEST] Groq connection test initiated by user {current_user.id}")

    try:
        # Test 1: Check API Key configuration
        from backend.config import get_settings

        settings = get_settings()

        has_env_key = bool(settings.groq_api_key)
        db_key_exists = False
        try:
            from backend.database import SystemConfig

            config = (
                db.query(SystemConfig)
                .filter(SystemConfig.key == "groq_api_key")
                .first()
            )
            db_key_exists = bool(config and config.value)
        except Exception as e:
            logger.warning(f"[TEST] Could not check DB for API key: {e}")

        logger.info(f"[TEST] API Key Status - ENV: {has_env_key}, DB: {db_key_exists}")

        # Test 2: Try simple AI call
        logger.info("[TEST] Attempting simple Groq API call...")
        response = await call_groq_cascade(
            messages=[
                {
                    "role": "user",
                    "content": 'Say \'Hello\' in JSON format: {"message": "..."}',
                }
            ],
            temperature=0.5,
            max_tokens=100,
            json_mode=True,
        )

        logger.info(f"[TEST] ✅ Groq API responded: {str(response)[:200]}")

        return {
            "status": "success",
            "message": "Groq API is working correctly",
            "api_key_env": has_env_key,
            "api_key_db": db_key_exists,
            "groq_response": response,
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"[TEST] ❌ Groq test failed: {type(e).__name__}: {str(e)}")
        logger.error(f"[TEST] Traceback: {traceback.format_exc()}")

        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "message": f"Groq API test failed: {str(e)}",
                "error_type": type(e).__name__,
                "timestamp": datetime.now().isoformat(),
            },
        )
