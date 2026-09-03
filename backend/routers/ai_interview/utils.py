import os
import re
from datetime import UTC, datetime
from typing import Optional

from backend.database import User
from backend.logger import logger
from backend.profile_helpers import get_user_skills

INTERVIEW_TOTAL_QUESTIONS = 15
from backend.scoring_engine import ScoringConfig  # noqa: E402

DIMENSION_WEIGHTS = ScoringConfig.DIMENSION_WEIGHTS

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


def safe_user_id(user: Optional[User]) -> str:
    if user and hasattr(user, "id") and user.id:
        return f"user_{user.id}"
    return "guest"


def safe_user_role(user: Optional[User]) -> str:
    if user and hasattr(user, "role") and user.role:
        return user.role
    return "guest"


def safe_user_skills(user: Optional[User]) -> list:
    if not user:
        return []
    skills_str = get_user_skills(user)
    if not skills_str:
        return []
    return [s.strip() for s in skills_str.split(",") if s.strip()]


def _utcnow():
    return datetime.now(UTC).replace(tzinfo=None)


def _sanitise_filename(filename: str) -> str:
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
        "français": "French",

        "arabic": "Arabic",
        "ar": "Arabic",
        "derja": "Arabic",
        "darija": "Arabic",
        "العربية": "Arabic",
        "العربي": "Arabic",
        "عربي": "Arabic",
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


def _extract_cv_focus_terms(cv_context: str, max_terms: int = 6) -> list:
    if not cv_context or len(str(cv_context).strip()) < 10:
        return []

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

    for keyword in sorted(tech_keywords, key=len, reverse=True):
        if keyword in text:
            display_name = keyword.replace(" ", " ").title()
            if display_name.lower() not in seen:
                found_skills.append(display_name)
                seen.add(display_name.lower())
                if len(found_skills) >= 4:
                    break

    if len(found_skills) < max_terms:
        for keyword in sorted(role_keywords, key=len, reverse=True):
            if keyword in text:
                display_name = keyword.replace(" ", " ").title()
                if display_name.lower() not in seen:
                    found_skills.append(display_name)
                    seen.add(display_name.lower())
                    if len(found_skills) >= max_terms:
                        break

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
            found_skills.append(token.title())
            seen.add(token.lower())
            if len(found_skills) >= max_terms:
                break

    return found_skills if found_skills else ["Professional Experience"]


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

    question = _get_graceful_fallback(q_index, language, role)

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


def strip_prompt_injections(text: str) -> str:
    if not text or not isinstance(text, str):
        return text
    cleaned = _INJECTION_RE.sub("[REDACTED]", text)
    if cleaned != text:
        logger.warning("Prompt injection attempt detected and stripped.")
    return cleaned


def is_lazy_answer(
    message: str, question: str, language: str = "English", turn_index: int = 1
) -> bool:
    m = message.strip().lower()
    if not m:
        return True

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


def calculate_adaptive_score(
    previous_score: float,
    question_score: float,
    question_number: int,
    is_handshake: bool = False,
    initial_score: float = 75.0,
) -> float:
    if is_handshake or question_number <= 1:
        return previous_score or initial_score

    prev = previous_score if previous_score is not None else initial_score

    if question_number <= 3:
        max_change = 35
    elif question_number <= 8:
        max_change = 22
    elif question_number <= 15:
        max_change = 15
    else:
        max_change = 10

    diff = question_score - prev

    damping = 0.85

    clamped_diff = max(-max_change, min(max_change, diff))
    new_val = prev + (clamped_diff * damping)

    return round(max(0.0, min(100.0, new_val)), 2)


def derive_dashboard_insights_from_skills(skill_metrics: dict) -> dict:
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


def resolve_total_questions(app) -> int:
    job_total = getattr(getattr(app, "job", None), "total_questions", None)
    batch_total = getattr(getattr(app, "batch_job", None), "total_questions", None)
    return int(job_total or batch_total or INTERVIEW_TOTAL_QUESTIONS)


def summarize_cv_for_interview(cv_text: str, max_chars: int = 3000) -> str:
    if not cv_text or len(cv_text) <= max_chars:
        return cv_text or ""

    parts = []
    job_matches = re.findall(
        r"(?:Work|Experience|Job|Position|Professional).*?(?=\n\n|\n[A-Z]|$)",
        cv_text,
        re.IGNORECASE | re.DOTALL,
    )
    if job_matches:
        for match in job_matches[:2]:
            parts.append(match[:800])

    skills_match = re.search(
        r"(?:Skills|Technical|Expertise|Stack).*?(?=\n\n|\n[A-Z]|$)",
        cv_text,
        re.IGNORECASE | re.DOTALL,
    )
    if skills_match:
        parts.append(skills_match.group()[:800])

    project_match = re.search(
        r"(?:Project|Achievement|Portfolio).*?(?=\n\n|\n[A-Z]|$)",
        cv_text,
        re.IGNORECASE | re.DOTALL,
    )
    if project_match:
        parts.append(project_match.group()[:800])

    edu_match = re.search(
        r"(?:Education|Academic|Formation|University).*?(?=\n\n|\n[A-Z]|$)",
        cv_text,
        re.IGNORECASE | re.DOTALL,
    )
    if edu_match:
        parts.append(edu_match.group()[:300])

    summary = "\n---\n".join(parts)
    return summary[:max_chars]
