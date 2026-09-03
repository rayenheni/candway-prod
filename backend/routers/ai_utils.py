import hashlib
import re
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.ai.llm import call_groq_cascade
from backend.database import TranslationCache, User
from backend.dependencies import get_current_user, get_db
from backend.logger import logger

router = APIRouter(prefix="/ai", tags=["ai-utils"])


class TranslationRequest(BaseModel):
    text: str
    target_lang: str  # 'en', 'fr', 'ar'
    context: Optional[str] = "General technical recruitment"


class TranslationResponse(BaseModel):
    translated_text: str
    detected_lang: Optional[str] = None
    placeholders_count: int
    cached: bool = False


# TECHNICAL EXCLUSION RULES (Regex Guards)
TECHNICAL_PATTERNS = {
    "email": r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
    "url": r'https?://[^\s<>"]+|www\.[^\s<>"]+',
    "code_block": r"```[\s\S]*?```",
    "log_file": r"/[a-zA-Z0-9._/ -]+\.log",
}


def protect_technical_content(text: str):
    """
    Replaces technical items with placeholders to prevent undesirable translation.
    Returns (modified_text, placeholder_map)
    """
    placeholder_map = {}
    counter = 0
    modified_text = text

    for label, pattern in TECHNICAL_PATTERNS.items():
        matches = re.findall(pattern, modified_text)
        for match in matches:
            placeholder = f"[[TECH_{label.upper()}_{counter}]]"
            placeholder_map[placeholder] = match
            modified_text = modified_text.replace(match, placeholder, 1)
            counter += 1

    return modified_text, placeholder_map


def restore_technical_content(text: str, placeholder_map: dict):
    """Restores the original technical content from placeholders."""
    restored_text = text
    for placeholder, original in placeholder_map.items():
        restored_text = restored_text.replace(placeholder, original)
    return restored_text


@router.post("/translate")
async def translate_text(
    req: TranslationRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Intelligent Translation Proxy with Cache:
    1. Checks if translation already exists for (hash(text+context), target_lang).
    2. If not, protects technical data and calls Groq AI.
    3. Caches and restores original content.
    """
    try:
        # 0. Cache Check Phase
        source_hash = hashlib.sha256(f"{req.text}|{req.context}".encode()).hexdigest()
        cached_entry = (
            db.query(TranslationCache)
            .filter(
                TranslationCache.source_hash == source_hash,
                TranslationCache.target_lang == req.target_lang,
            )
            .first()
        )

        if cached_entry:
            return {
                "translated_text": cached_entry.translated_text,
                "detected_lang": "Cached",
                "placeholders_count": 0,
                "cached": True,
            }

        # 1. Protection Phase
        protected_text, p_map = protect_technical_content(req.text)

        # 2. LLM Translation Phase
        target_name = {
            "en": "English",
            "fr": "French",
            "ar": "Arabic (specifically Tunisian Derja/Dialect)",
        }.get(req.target_lang, "English")

        from backend.credit_service import consume_credits_or_402, rollback_credits

        credit_tx = consume_credits_or_402(
            db,
            current_user,
            1,
            "translation",
            reference_type=None,
            reference_id=None,
        )

        system_prompt = f"""You are a professional technical translator for the Candway Intelligence Platform.
Your task is to translate the provided text into {target_name}.

RULES:
1. PRESERVE ALL PLACEHOLDERS: Do NOT translate anything inside double square brackets like [[TECH_EMAIL_0]].
2. TONE: Maintain a professional, modern, and helpful tone suitable for a tech recruitment platform.
3. CONTEXT: {req.context}.
4. TUNISIAN DERJA: If the target language is Arabic, use authentic Tunisian Derja (Tunisian Dialect) but keep it professional. Use words like 'عسلامة' (Hello), 'بروفايل' (Profile), 'خدمة' (Job/Work).

Return ONLY a JSON object with the following structure:
{{
    "translated_text": "The translated content with placeholders intact",
    "detected_source_lang": "The source language code"
}}
"""

        llm_response = await call_groq_cascade(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": protected_text},
            ],
            json_mode=True,
        )

        if not llm_response or "translated_text" not in llm_response:
            raise HTTPException(
                status_code=500, detail="AI Translation failed to produce valid output"
            )

        # 3. Restoration Phase
        final_text = restore_technical_content(llm_response["translated_text"], p_map)

        # 4. Cache Persistence Phase
        new_cache = TranslationCache(
            source_hash=source_hash,
            target_lang=req.target_lang,
            source_text=req.text,
            translated_text=final_text,
        )
        db.add(new_cache)
        db.commit()

        return {
            "translated_text": final_text,
            "detected_lang": llm_response.get("detected_source_lang"),
            "placeholders_count": len(p_map),
            "cached": False,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Translation Error: {e}", exc_info=True)
        try:
            from backend.credit_service import rollback_credits

            rollback_credits(db, credit_tx)
        except Exception:
            pass
        raise HTTPException(status_code=500, detail="Translation Service Error")
