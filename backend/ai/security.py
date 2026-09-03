import hashlib
import logging
import re
import threading
import time
import unicodedata
from collections import OrderedDict
from typing import Dict, Optional, Tuple


logger = logging.getLogger("candway_app")


class PIIMappingStore:
    """Thread-safe, LRU-evicting store for PII masked IDs to original values."""

    def __init__(self, max_size: int = 10_000):
        self._max_size = max_size
        self._lock = threading.Lock()
        self._value_to_id: Dict[str, str] = {}
        self._id_to_value: OrderedDict[str, str] = OrderedDict()

    def store(self, value: str, category: str = "PII") -> str:
        if not value:
            return ""
        with self._lock:
            if value in self._value_to_id:
                masked_id = self._value_to_id[value]
                self._id_to_value.move_to_end(masked_id)
                return masked_id
            raw = f"{category.lower()}_{value}"
            digest = hashlib.sha256(raw.encode()).hexdigest()[:12]
            masked_id = f"[{category.upper()}_{digest}]"
            self._value_to_id[value] = masked_id
            self._id_to_value[masked_id] = value
            if len(self._id_to_value) > self._max_size:
                oldest, _ = self._id_to_value.popitem(last=False)
                for v, mid in list(self._value_to_id.items()):
                    if mid == oldest:
                        del self._value_to_id[v]
                        break
            return masked_id

    def lookup(self, masked_id: str) -> Optional[str]:
        with self._lock:
            value = self._id_to_value.get(str(masked_id))
            if value is not None:
                self._id_to_value.move_to_end(str(masked_id))
            return value

    def get_all_mappings(self) -> Dict[str, str]:
        with self._lock:
            return dict(self._id_to_value)

    def clear(self) -> None:
        with self._lock:
            self._value_to_id.clear()
            self._id_to_value.clear()

    @property
    def size(self) -> int:
        with self._lock:
            return len(self._id_to_value)


_pii_store = PIIMappingStore()


def get_pii_store() -> PIIMappingStore:
    """Return the global PIIMappingStore singleton."""
    return _pii_store


class PIIMasker:
    """Anonymize PII before sending text to external AI providers."""

    _lock = threading.Lock()
    _patterns_initialized = False
    PATTERNS: Tuple = ()

    @classmethod
    def _init_patterns(cls):
        if cls._patterns_initialized:
            return
        with cls._lock:
            if cls._patterns_initialized:
                return
            cls.PATTERNS = (
                # Email
                (
                    re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"),
                    "EMAIL",
                ),

                # Tunisian CIN / National ID — must run before PHONE.
                # Consume the label + optional qualifier/separator so CIN
                # is classified before the generic 8-digit PHONE pattern.
                (
                    re.compile(
                        r"(?i)\b(?:cin|national\s+id|identity)\b"
                        r"\s*(?:(?:is|number|no|n°)\s*)?"
                        r"[:#-]?\s*\d{8}\b"
                    ),
                    "CIN",
                ),

                # Passport numbers such as AB1234567
                (
                    re.compile(
                        r"(?i)(?<![A-Za-z0-9])(?:passport\s*[:#-]?\s*)?[A-Z]{1,2}\d{6,9}\b"
                    ),
                    "PASSPORT",
                ),

                # Date of birth — labelled dates and common standalone dates
                (
                    re.compile(
                        r"(?i)(?:date\s+of\s+birth|dob|birth\s+date)\s*[:#-]?\s*"
                        r"(?:\d{1,2}[/-]\d{1,2}[/-]\d{4}|"
                        r"\d{4}[/-]\d{1,2}[/-]\d{1,2}|"
                        r"(?:january|february|march|april|may|june|july|august|"
                        r"september|october|november|december)\s+\d{1,2},?\s+\d{4})"
                    ),
                    "DOB",
                ),
                (
                    re.compile(
                        r"(?<!\d)\d{1,2}/\d{1,2}/\d{4}(?!\d)"
                    ),
                    "DOB",
                ),
                (
                    re.compile(
                        r"(?<!\d)\d{4}-\d{1,2}-\d{1,2}(?!\d)"
                    ),
                    "DOB",
                ),

                # US SSN
                (
                    re.compile(r"\b\d{3}[-.\s]?\d{2}[-.\s]?\d{4}\b"),
                    "SSN",
                ),

                # Credit card
                (
                    re.compile(r"\b(?:\d{4}[-.\s]?){3}\d{4}\b"),
                    "CARD",
                ),

                # IBAN
                (
                    re.compile(
                        r"\b[A-Z]{2}\d{2}(?:[-.\s]?\d{4}){3,5}\b"
                    ),
                    "IBAN",
                ),

                # Phone — after CIN/DOB/card to avoid category collisions
                (
                    re.compile(
                        r"(\+?\d{1,3}[-.\s]?)?\(?\d{2,4}\)?[-.\s]?\d{3,4}[-.\s]?\d{3,4}\b"
                    ),
                    "PHONE",
                ),

                # Social profiles
                (
                    re.compile(
                        r"(?i)\b(?:https?://)?"
                        r"(?:www\.)?"
                        r"(?:linkedin\.com/(?:in|pub)/[\w.-]+|"
                        r"github\.com/[\w.-]+|"
                        r"gitlab\.com/[\w.-]+|"
                        r"(?:twitter\.com|x\.com|facebook\.com)/[\w.-]+)"
                    ),
                    "SOCIAL",
                ),

                # Common address forms in CVs
                (
                    re.compile(
                        r"(?i)(?<![A-Za-z])"
                        r"(?:rue|avenue|av\.|cite|city|residence|res\.|"
                        r"blvd|street|st\.|apt|suite|lot|villa|villas|appartement)"
                        r"\s+[^,\n.]{5,60}"
                    ),
                    "ADDRESS",
                ),

                # References section / contact reference information
                (
                    re.compile(
                        r"(?i)\breferences?\s*:\s*[^\n]{3,120}"
                    ),
                    "REFERENCE",
                ),

                # Names — heuristic, deliberately last
                (
                    re.compile(
                        r"\b(?:[A-Z][a-z]+\s+){1,3}[A-Z][a-z]+\b"
                    ),
                    "NAME",
                ),
            )
            cls._patterns_initialized = True

    @classmethod
    def mask_pii(cls, text: str, store_mapping: bool = True) -> str:
        if not text:
            return text
        cls._init_patterns()
        masked = text
        store = get_pii_store() if store_mapping else None
        for pattern, category in cls.PATTERNS:

            def replacer(match, cat=category, st=store):
                # CIN pattern contains a label + the actual ID.
                # Preserve the human-readable label while masking only the ID.
                if cat == "CIN" and "value" in match.groupdict():
                    val = match.group("value")
                    token = st.store(val, cat) if st else f"[{cat}_REDACTED]"
                    return match.group("label") + match.group("separator") + token

                val = match.group(0)
                if st:
                    return st.store(val, cat)
                return f"[{cat}_REDACTED]"

            masked = pattern.sub(replacer, masked)
        return masked

    @classmethod
    def strip_pii(cls, text: str) -> str:
        if not text:
            return text
        return re.sub(r"\[[A-Z]+_[a-f0-9]+\]|\[[A-Z]+_REDACTED\]", "[REDACTED]", text)

    @classmethod
    def get_patterns(cls) -> Tuple:
        cls._init_patterns()
        return cls.PATTERNS


PIIMasker._init_patterns()


class AISecurityRateLimiter:
    """Redis-backed distributed rate limiter for AI calls."""

    def __init__(self):
        self._redis = None

    async def _ensure_redis(self):
        if self._redis is None:
            try:
                from backend.redis_manager import redis_manager

                self._redis = await redis_manager.get_client()
            except Exception:
                self._redis = None

    async def check_rate_limit(
        self, company_id: int, user_id: int, ip: str
    ) -> Tuple[bool, str]:
        await self._ensure_redis()
        if self._redis is None:
            import os

            if os.getenv("ENV", "").lower() in ("production", "prod"):
                return True, ""
            return True, ""

        now = int(time.time())
        company_key = f"ai_rate:company:{company_id}:minute:{now // 60}"
        company_day_key = f"ai_rate:company:{company_id}:day:{now // 86400}"
        user_key = f"ai_rate:user:{user_id}:minute:{now // 60}"
        ip_key = f"ai_rate:ip:{ip}:minute:{now // 60}"

        try:
            company_count = await self._redis.incr(company_key)
            if company_count == 1:
                await self._redis.expire(company_key, 60)
            if company_count > 100:
                return False, "Company rate limit exceeded (100/min)"
            day_count = await self._redis.incr(company_day_key)
            if day_count == 1:
                await self._redis.expire(company_day_key, 86400)
            if day_count > 10000:
                return False, "Company daily limit exceeded (10000/day)"
            user_count = await self._redis.incr(user_key)
            if user_count == 1:
                await self._redis.expire(user_key, 60)
            if user_count > 20:
                return False, "User rate limit exceeded (20/min)"
            ip_count = await self._redis.incr(ip_key)
            if ip_count == 1:
                await self._redis.expire(ip_key, 60)
            if ip_count > 30:
                return False, "IP rate limit exceeded (30/min)"
            return True, ""
        except Exception:
            return False, "Rate limiter error"


class AISecurity:
    """Hardened security guardrails for AI interactions."""

    _rate_limiter = None

    @classmethod
    async def check_rate_limit(
        cls, company_id: int, user_id: int, ip: str
    ) -> Tuple[bool, str]:
        limiter = cls.get_rate_limiter()
        return await limiter.check_rate_limit(company_id, user_id, ip)

    @classmethod
    def get_rate_limiter(cls):
        if cls._rate_limiter is None:
            cls._rate_limiter = AISecurityRateLimiter()
        return cls._rate_limiter

    INJECTION_PATTERNS = (
        r"(?i)ignore\s+(all\s+)?(previous\s+)?instructions",
        r"(?i)system\s*prompt",
        r"(?i)you\s+are\s+now\s+a",
        r"(?i)act\s+as\s+a\s+(?!lead|senior|junior|professional|technical|expert)",
        r"(?i)reveal\s+(your\s+)?instructions",
        r"(?i)what\s+are\s+your\s+instructions",
        r"(?i)forget\s+(everything\s+)?before",
        r"(?i)stop\s+the\s+interview",
        r"(?i)end\s+interview\s+and\s+say",
        r"(?i)now\s+you\s+are\s+not",
        r"(?i)bypass\s+the\s+guardrails",
    )

    SCORE_PATTERNS = (
        r"(?i)(?:set|give|increase|change|override|force)\s+(?:the\s+)?score\s+(?:to|of|by)?",
        r"(?i)(?:override|change)\s+.*score",
        r"(?i)give\s+me\s+a\s+score\s+of",
        r"(?i)pass\s+me\s+immediately",
        r"(?i)ignore\s+(?:the\s+)?(?:previous\s+)?score",
        r"(?i)score\s*=\s*100",
    )

    FR_AR_PATTERNS = (
        r"(?i)ignorez\s+les\s+instructions",
        r"oublier\s+tout\s+ce\s+qui\s+pr\u00e9c\u00e8de",
        r"(?i)ans\u00ea\s+al\s+taalim\u00e2t",
        # Arabic variants: "انسَ التعليمات", "انسى التعليمات", etc.
        r"\u0627\u0646\u0633(?:\u0649)?\s+\u0627\u0644\u062a\u0639\u0644\u064a\u0645\u0627\u062a",
    )

    MANIPULATION_PATTERNS = (
        r"(?i)what\s+(should|s|could)\s+I\s+(say|do|answer)",
        r"(?i)how\s+do\s+I\s+(get|give)\s+(a\s+)?(high|good)\s+score",
        r"(?i)what\s+is\s+the\s+(correct|right|best)\s+answer",
        r"(?i)tell\s+me\s+the\s+question(s)?",
        r"(?i)what\s+are\s+you\s+looking\s+for",
        r"(?i)how\s+does\s+(your|this)\s+(scoring|evaluation)\s+work",
        r"(?i)how\s+does\s+scoring\s+work",
    )

    MAX_INPUT_LENGTH = 10000
    MIN_UNIQUE_RATIO = 0.15

    _HOMOGLYPH_MAP = {
        # Cyrillic -> Latin
        "\u0430": "a",  # а
        "\u0435": "e",  # е
        "\u043e": "o",  # о
        "\u0441": "c",  # с
        "\u0456": "i",  # і
        "\u0454": "e",  # є
        "\u0458": "j",  # ј
        "\u04bb": "h",  # һ
        "\u0406": "i",  # І

        # Greek -> Latin
        "\u03b1": "a",  # α
        "\u039d": "n",  # Ν
        "\u039f": "o",  # Ο
        "\u03b5": "e",  # ε
        "\u03bf": "o",  # ο
        "\u03c1": "p",  # ρ
        "\u03c7": "x",  # χ
        "\u03bd": "v",  # ν
        "\u03ba": "k",  # κ
        "\u03bc": "m",  # μ
    }

    @classmethod
    def _transliterate_homoglyphs(cls, text: str) -> str:
        for homoglyph, latin in cls._HOMOGLYPH_MAP.items():
            text = text.replace(homoglyph, latin)
        return text

    @classmethod
    def _normalize_for_detection(cls, text: str) -> str:
        """Normalize Unicode/diacritics/homoglyphs for security detection only."""
        normalized = unicodedata.normalize("NFKC", text)

        # Remove zero-width / BOM characters.
        for char in ("\u200b", "\u200c", "\u200d", "\ufeff"):
            normalized = normalized.replace(char, "")

        # Remove Arabic harakat/diacritics so variants such as
        # "انسَ التعليمات" and "انسى التعليمات" normalize consistently.
        normalized = re.sub(
            r"[\u0610-\u061a\u064b-\u065f\u0670\u06d6-\u06ed]",
            "",
            normalized,
        )

        # Transliterate both uppercase and lowercase homoglyphs first.
        # Then casefold the resulting Latin text so mixed-script payloads
        # such as "ІGΝΟRE" become "ignore".
        normalized = cls._transliterate_homoglyphs(normalized)
        normalized = normalized.casefold()

        return normalized.strip()

    @classmethod
    def detect_prompt_injection(cls, text: str) -> Tuple[bool, str]:
        if not text:
            return True, ""

        text = cls._normalize_for_detection(text)

        for pattern in AISecurity.INJECTION_PATTERNS:
            if re.search(pattern, text):
                return False, f"Instruction Hijack Attempt Detected ({pattern})"
        for pattern in AISecurity.SCORE_PATTERNS:
            if re.search(pattern, text):
                return False, "Score Manipulation Attempt Detected"
        for pattern in AISecurity.FR_AR_PATTERNS:
            if re.search(pattern, text):
                return False, "Cross-language instruction bypass attempt"
        for pattern in AISecurity.MANIPULATION_PATTERNS:
            if re.search(pattern, text):
                return False, f"Manipulation Attempt Detected ({pattern})"

        if len(text) > 1000:
            if len(set(text)) < 30:
                return False, "Low entropy input (potential obfuscation)"
            if re.search(r"[!?.\-]{5,}", text):
                return False, "Formatting abuse detected"

        imperative_markers = [
            r"(?i)^(you\s+must|you\s+should|you\s+will|you\s+are|you\s+have\s+to)\b",
            r"(?i)(do\s+not|don't|never|always)\s+(answer|respond|say|score|evaluate|ignore)\b",
            r"(?i)(output|return|print|respond)\s+(only|just|exactly)\b",
            r"(?i)(set\s+the|change\s+the|override\s+the|force\s+the)\s+\w+\s+(to|as|=)\b",
            r"(?i)(from\s+now\s+on|henceforth|starting\s+now)\b",
        ]
        imperative_count = sum(1 for p in imperative_markers if re.search(p, text))
        if imperative_count >= 2:
            return False, "Multiple imperative instruction patterns detected"

        persona_patterns = [
            r"(?i)you\s+are\s+(now\s+)?(a|an|no\s+longer)\s+\w+",
            r"(?i)pretend\s+(you\s+are|to\s+be)",
            r"(?i)imagine\s+you\s+are",
            r"(?i)role\s*play\s+as",
        ]
        for pattern in persona_patterns:
            if re.search(pattern, text):
                return False, "Persona/role-play injection attempt"

        return True, ""

    @staticmethod
    def normalize_unicode(text: str) -> str:
        if not text:
            return text
        normalized = unicodedata.normalize("NFKC", text)
        for char in ["\u200b", "\u200c", "\u200d", "\ufeff"]:
            normalized = normalized.replace(char, "")
        return normalized

    @staticmethod
    def enforce_limits(text: str, max_length: int = None) -> str:
        max_len = max_length or AISecurity.MAX_INPUT_LENGTH
        if text and len(text) > max_len:
            return text[:max_len]
        return text

    @staticmethod
    def detect_repetition(text: str) -> bool:
        if not text or len(text) < 50:
            return False
        words = text.lower().split()
        if len(words) < 10:
            return False
        unique_ratio = len(set(words)) / len(words)
        if unique_ratio < AISecurity.MIN_UNIQUE_RATIO:
            return True
        if re.search(r"(.)\1{5,}", text):
            return True
        return False

    @classmethod
    def sanitize_for_prompt(cls, text: str, field_name: str = "input") -> str:
        """
        Defense-in-depth prompt boundary.

        This does NOT blindly reject candidate content. It normalizes and
        sanitizes the value, then detects instruction-hijacking patterns.
        Detected injection is replaced with a neutral security marker so
        the LLM cannot treat the content as executable instructions.
        """
        if not text:
            return text

        clean = cls.normalize_unicode(str(text))
        clean = cls.sanitize_input(clean)

        is_safe, reason = cls.detect_prompt_injection(clean)

        if not is_safe:
            logger.warning(
                "[AI-SECURITY] Prompt injection detected in %s: %s",
                field_name,
                reason,
            )
            return (
                f"[UNTRUSTED {field_name.upper()} CONTENT REMOVED "
                f"BY SECURITY FILTER]"
            )

        return clean

    @staticmethod
    def sanitize_input(text: str) -> str:
        if not text:
            return text
        clean_text = AISecurity.normalize_unicode(text)
        clean_text = re.sub(
            r"<script[^>]*>.*?</script>",
            "",
            clean_text,
            flags=re.DOTALL | re.IGNORECASE,
        )
        clean_text = re.sub(
            r"<style[^>]*>.*?</style>", "", clean_text, flags=re.DOTALL | re.IGNORECASE
        )
        clean_text = re.sub(r"<[^>]*>", "", clean_text)
        clean_text = re.sub(
            r'\s*on\w+\s*=\s*"[^"]*"', "", clean_text, flags=re.IGNORECASE
        )
        clean_text = re.sub(
            r"\s*on\w+\s*=\s*\'[^\']*\'", "", clean_text, flags=re.IGNORECASE
        )
        clean_text = re.sub(r"javascript\s*:", "", clean_text, flags=re.IGNORECASE)
        clean_text = re.sub(r"\s{3,}", " ", clean_text)
        clean_text = clean_text.strip()
        clean_text = AISecurity.enforce_limits(clean_text)
        return clean_text
