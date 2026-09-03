import json
import re
import traceback
from datetime import datetime
from typing import Optional, Tuple

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.ai.security import AISecurity
from backend.ai_quota_service import check_interview_quota
from backend.authz import get_application_for_recruiter
from backend.database import Application, User
from backend.dependencies import get_current_user, get_db, get_interview_access
from backend.logger import logger
from backend.profile_helpers import get_user_is_super_admin
from backend.routers.ai_interview.utils import (
    normalize_interview_language,
    safe_user_role,
    strip_prompt_injections,
)

router = APIRouter(tags=["ai-interview"])


class InterviewGenRequest(BaseModel):
    application_id: int
    language: Optional[str] = Field("English", max_length=50)


@router.post("/generate-interview")
async def generate_interview_questions(
    req: InterviewGenRequest,
    quota_info: dict = Depends(check_interview_quota),
    db: Session = Depends(get_db),
    auth: Tuple[Optional[User], Application] = Depends(get_interview_access),
):
    current_user, app = auth
    if not app:
        if current_user and safe_user_role(current_user) in ["recruiter", "admin"]:
            app = get_application_for_recruiter(req.application_id, current_user, db)
        else:
            app = (
                db.query(Application)
                .filter(Application.id == req.application_id)
                .first()
            )

    if not app:
        raise HTTPException(status_code=404, detail="Application not found")

    if current_user:
        if (
            safe_user_role(current_user) not in ["recruiter", "admin"]
            and app.user_id != current_user.id
        ):
            raise HTTPException(status_code=403, detail="Not authorized")

    role = app.declared_role or "Software Engineer"
    cv_raw = app.cv_text_anonymized or "No CV context available."
    cv_context = strip_prompt_injections(AISecurity.sanitize_input(cv_raw))[:1000]
    language = (
        req.language
        if req.language and req.language != "English"
        else (app.language or "English")
    )

    # IMPORTANT: AI interview configuration must come exclusively from the
    # frozen EvaluationConfigSnapshot. Never read the live rubric here.
    rubric_context_str = ""
    try:
        from backend.rubric.interview_starter import InterviewStarter
        from backend.rubric.config_reader import EvaluationConfigReader

        # The preview endpoint may be called before the interview has been
        # explicitly started. Start it once so the recruiter configuration
        # is resolved and frozen into the snapshot.
        eval_session = None
        for existing_session in (app.evaluation_sessions or []):
            if getattr(existing_session, "config_snapshot", None) is not None:
                eval_session = existing_session
                break

        if eval_session is None:
            eval_session = InterviewStarter.start(db, app)
            db.commit()

        reader = EvaluationConfigReader(eval_session)
        parsed_rubric = reader.get_rubric()

        # Use only the frozen rubric JSON from the snapshot.
        raw_crit = parsed_rubric.raw_json

        if isinstance(raw_crit, str):
            raw_crit = json.loads(raw_crit)

        if isinstance(raw_crit, dict):
            skills_found = []

            # Support the canonical snapshot structure.
            for skill in parsed_rubric.skills or []:
                if isinstance(skill, dict):
                    name = skill.get("name")
                    if name:
                        skills_found.append(name)

            # Defensive fallback for category/subcategory structures already
            # frozen inside resolved_rubric_json.
            if not skills_found:
                for cat in raw_crit.get("categories", []):
                    if not isinstance(cat, dict):
                        continue
                    for sub in cat.get("subcategories", []):
                        if not isinstance(sub, dict):
                            continue
                        for sk in sub.get("skills", []):
                            if isinstance(sk, dict):
                                name = sk.get("name")
                                if name:
                                    skills_found.append(name)

            if skills_found:
                rubric_context_str = (
                    f"\nJOB RUBRIC SKILLS TO COVER: "
                    f"{', '.join(skills_found[:10])}\n"
                )

    except Exception as r_err:
        logger.warning(
            "Could not read frozen rubric context for preview questions: %s",
            r_err,
            exc_info=True,
        )

    prompt = f"""
    Generate 10 SCENARIO-BASED interview questions for a "{role}" position in Tunisia's tech market.
    Language: {language}
    Context from Candidate CV: {cv_context[:500]}...
    {rubric_context_str}
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
        from backend.ai.llm import call_groq_cascade
        from backend.credit_service import consume_credits_or_402, rollback_credits

        credit_tx = consume_credits_or_402(
            db,
            current_user,
            5,
            "interview_question_gen",
            reference_type="application",
            reference_id=app.id,
        )
        try:
            result = await call_groq_cascade(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=2000,
                json_mode=True,
                company_id=app.company_id,
            )
        except Exception:
            rollback_credits(db, credit_tx)
            raise
        if result and isinstance(result, dict) and "questions" in result:
            return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"AI question generation failed: {e}", exc_info=True)

    return {
        "questions": [
            f"Describe your experience with {role}.",
            "What is a key technical challenge you've solved?",
            "How do you stay updated with technology?",
            "Explain a complex concept to a junior developer.",
            "What are your career goals?",
        ]
    }


def _is_question_cv_relevant(
    question_text: str, cv_context: str, declared_role: str
) -> bool:
    if not question_text or (not cv_context and not declared_role):
        return True

    question_lower = str(question_text).lower()[:500]
    cv_lower = str(cv_context).lower()

    question_keywords = re.findall(r"[a-z]+[a-z0-9+#.\-]*", question_lower)
    cv_keywords = re.findall(r"[a-z]+[a-z0-9+#.\-]*", cv_lower)

    overlap_count = sum(
        1 for kw in question_keywords if kw in cv_keywords and len(kw) > 3
    )
    has_role_match = declared_role.lower() in question_lower or any(
        role_term in question_lower for role_term in declared_role.lower().split()
    )

    return (has_role_match and overlap_count >= 1) or overlap_count >= 3


def detect_language_intelligent(message_text: str, fallback: str = "English") -> str:
    if not message_text:
        return fallback

    explicit = normalize_interview_language(message_text)
    if explicit:
        return explicit

    text_lower = message_text.lower()

    # Arabic: explicit language names / dialect names.
    if any(
        word in text_lower
        for word in ["arabic", "العربية", "العربي", "عربي", "derja", "darija"]
    ):
        return "Arabic"

    # Arabic script is a strong signal even when no language name is used.
    arabic_chars = len(re.findall(r"[\u0600-\u06FF]", message_text))
    total_chars = len(message_text)
    if total_chars > 0 and (arabic_chars / total_chars) > 0.25:
        return "Arabic"

    # French lexical markers. Use several common words rather than
    # relying only on accented characters.
    french_markers = {
        "bonjour",
        "merci",
        "comment",
        "vous",
        "votre",
        "vos",
        "avec",
        "dans",
        "pour",
        "quelle",
        "quel",
        "quels",
        "quelles",
        "êtes",
        "avez",
        "être",
        "avoir",
        "sur",
        "cette",
        "cela",
        "ce",
        "ces",
        "une",
        "des",
        "les",
        "nous",
        "notre",
        "problème",
        "expérience",
        "travail",
        "équipe",
        "poste",
        "entretien",
    }

    tokens = set(re.findall(r"[a-zA-ZÀ-ÿ]+", text_lower))
    french_hits = len(tokens & french_markers)

    if french_hits >= 2:
        return "French"

    # Common French phrases / signals that can be enough on their own.
    french_phrases = [
        "bonjour",
        "merci",
        "s'il vous plaît",
        "à bientôt",
        "excusez",
        "comment allez-vous",
        "comment allez vous",
        "avez-vous",
        "avez vous",
        "êtes-vous",
        "êtes vous",
    ]

    if any(phrase in text_lower for phrase in french_phrases):
        return "French"

    # Accented French characters are an additional signal.
    french_chars = len(
        re.findall(
            r"[àâäéèêëïîôöùûüçÀÂÄÉÈÊËÏÎÔÖÙÛÜÇ]",
            message_text,
        )
    )

    if total_chars > 0 and (french_chars / total_chars) > 0.05:
        return "French"

    # English lexical markers.
    english_markers = {
        "hello",
        "hi",
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
        "experience",
        "work",
        "team",
        "job",
        "tell",
        "about",
        "have",
        "are",
        "this",
        "that",
        "can",
        "could",
        "would",
        "why",
        "when",
        "where",
    }

    english_hits = len(tokens & english_markers)

    if english_hits >= 2:
        return "English"

    return fallback


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
        return arabic_chars < 8
    return french_hits >= 3 and french_hits > english_hits


def _fallback_interview_question(
    current_q_index: int,
    declared_role: str,
    language: str = "English",
    technical_focus: str = None,
) -> str:
    if language == "French":
        return "L'IA a rencontré une difficulté technique. Veuillez patienter ou réessayer."
    elif language == "Arabic":
        return "Mouchkel technique: El AI ma najemch ya3tik so2el tawwa. Jarreb marra okhra."
    else:
        return "TECHNICAL DELAY: We're experiencing a brief technical issue. Please bear with us and retry."




@router.get("/test/groq-connection")
async def test_groq_connection(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Bug S-07: this endpoint was authenticated but not authorised.
    # Any logged-in user — candidate, recruiter, or guest — could fire
    # a Groq API call with attacker-controlled parameters. Worse, the
    # response includes ``api_key_env`` and ``api_key_db`` booleans
    # that leak whether the system has credentials configured. The
    # endpoint is now locked to admin / super-admin only.
    user_role = getattr(current_user, "role", "")
    is_super = get_user_is_super_admin(current_user)
    if user_role != "admin" and not is_super:
        logger.warning(
            f"[TEST] Non-admin user {current_user.id} ({user_role}) "
            f"attempted groq-connection probe — denied"
        )
        raise HTTPException(
            status_code=403,
            detail="Admin access required",
        )

    from backend.ai.llm import call_groq_cascade

    logger.info(f"[TEST] Groq connection test initiated by user {current_user.id}")

    try:
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

        logger.info(f"[TEST] Groq API responded: {str(response)[:200]}")

        return {
            "status": "success",
            "message": "Groq API is working correctly",
            "api_key_env": has_env_key,
            "api_key_db": db_key_exists,
            "groq_response": response,
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"[TEST] Groq test failed: {type(e).__name__}: {str(e)}")
        logger.error(f"[TEST] Traceback: {traceback.format_exc()}")

        return JSONResponse(
            status_code=500,
            content={"detail": "Groq API test failed"},
        )
