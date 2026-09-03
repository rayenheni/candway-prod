from io import BytesIO

from backend.logger import logger

# Try to import pypdf, fallback to basic text if missing
try:
    import pypdf  # noqa: F401 - availability probe

    HAS_PDF = True
except ImportError:
    HAS_PDF = False

# Try to import python-docx, fallback to basic text if missing
try:
    import docx

    HAS_DOCX = True
except ImportError:
    HAS_DOCX = False

from backend.ai.llm import call_groq_cascade
from backend.pdf_parser import extract_text_from_pdf


def extract_text_from_file(file_content: bytes, filename: str) -> str:
    """
    Extracts text from PDF or Text file bytes.
    Handles scanned PDFs by detecting if text extraction returns empty/short content.
    """
    if not file_content or len(file_content) < 100:
        return "ERROR: File too small or empty."

    try:
        if filename.lower().endswith(".pdf"):
            if not HAS_PDF:
                return "ERROR: PDF Parsing Unavailable (pypdf missing)."

            text = extract_text_from_pdf(file_content)

            # Check for scanned PDF (no extractable text)
            if not text or len(text.strip()) < 50:
                return "ERROR: Could not extract text from this PDF. It may be a scanned document (image-only PDF). Please export your CV as a text-based PDF from Word or Google Docs."

            return text

        elif filename.lower().endswith(".docx"):
            if not HAS_DOCX:
                return "ERROR: DOCX parsing unavailable (python-docx missing)."

            doc = docx.Document(BytesIO(file_content))
            text = ""
            for para in doc.paragraphs:
                if para.text.strip():
                    text += para.text + "\n"
            return text
        else:
            # Assume text/md
            return file_content.decode("utf-8", errors="ignore")
    except Exception as e:
        logger.error(f"Error extracting text: {e}")
        return f"ERROR: Could not read file ({type(e).__name__}). Try a different PDF."


async def analyze_cv_with_groq(cv_text: str, declared_role: str = "") -> dict:
    """
    Sends CV text to AI (Local or Groq) to detect Industry, Experience, and Skills.
    """
    prompt = f"""
    You are an Expert Career Auditor for Candway. Analyze this CV text.

    DECLARED ROLE: {declared_role}
    CV CONTENT:
    {cv_text[:3000]}  # Limit chars

    TASK:
    1. Detect the specific INDUSTRY best fit for a Simulation (options: 'photovoltaic', 'industrial_automation', 'residential', 'universal').
       - If they mention 'solar', 'pv', 'inverter', 'renewable', map to 'photovoltaic'.
       - If they mention 'plc', 'scada', 'vfd', map to 'industrial_automation'.
    2. Assess Experience Level (Junior, Mid-Level, Senior).
    3. Extract top 5 hard skills.
    4. Identify 3 critical WEAKNESSES or MISSING SKILLS relative to the Declared Role.
    5. Provide a Match Score (0-100) based on fit for role.

    OUTPUT JSON ONLY:
    {{
        "industry": "string",
        "experience_level": "string",
        "skills": ["string"],
        "weaknesses": ["string"],
        "match_score": 0,
        "summary": "One sentence summary"
    }}
    """

    try:
        messages = [
            {"role": "system", "content": "You are a precise JSON extractor."},
            {"role": "user", "content": prompt},
        ]

        # Use the unified cascade which handles Local LLM vs Cloud (Groq)
        result = await call_groq_cascade(messages, temperature=0.1, json_mode=True)
        return result

    except Exception as e:
        logger.error(f"Unified CV Analysis Failed: {e}")
        return {
            "industry": "photovoltaic"
            if "solar" in declared_role.lower()
            else "universal",
            "experience_level": "Unknown",
            "skills": [],
            "error": "CV analysis failed",
        }


import re  # noqa: E402


def extract_pii(text: str) -> dict:
    """
    Extracts PII (Name, Email, Phone) locally using Regex and Heuristics.
    Improved name detection handles diverse CV layouts.
    """
    pii = {"name": None, "email": None, "phone": None}

    if not text:
        return pii

    # 1. Email Extraction (Primary)
    # Robust regex for standard formats
    email_pattern = r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"
    email_match = re.search(email_pattern, text)
    if email_match:
        pii["email"] = email_match.group(0).lower().strip()
    else:
        # Secondary pass: handle common PDF artifacts like spaces or line breaks around @
        # Search for something like "rayen @ gmail . com"
        greedy_pattern = r"[a-zA-Z0-9._%+-]+\s*@\s*[a-zA-Z0-9.-]+\s*\.\s*[a-zA-Z]{2,}"
        greedy_match = re.search(greedy_pattern, text)
        if greedy_match:
            clean_email = re.sub(r"\s+", "", greedy_match.group(0))
            pii["email"] = clean_email.lower().strip()

    # 2. Phone Extraction
    phone_pattern = r"(\+?\d{1,3}[\s.\-]?)?\(?\d{2,4}?\)?[\s.\-]?\d{3,4}[\s.\-]?\d{4}"
    phone_match = re.search(phone_pattern, text)
    if phone_match:
        pii["phone"] = phone_match.group(0).strip()

    # 3. Name Extraction — multi-strategy heuristic
    # Strategy: scan first 15 non-empty lines, score each as a name candidate.
    # The best-scoring line wins.
    _CV_SECTION_HEADERS = {
        "resume",
        "cv",
        "curriculum vitae",
        "profile",
        "summary",
        "objective",
        "contact",
        "details",
        "information",
        "phone",
        "email",
        "address",
        "experience",
        "education",
        "skills",
        "work experience",
        "employment",
        "references",
        "languages",
        "certifications",
        "projects",
        "achievements",
        "personal",
        "professional",
        "professional summary",
        "linkedin",
        "github",
        "portfolio",
        "page",
        "about",
        "overview",
        "declaration",
        "interests",
        "hobbies",
        "strengths",
        "areas of expertise",
        "core competencies",
    }

    lines = [line.strip() for line in text.split("\n") if line.strip()]
    best_name = None
    best_score = -1

    for line in lines[:15]:
        lower = line.lower()

        # Hard skip: looks like an email or URL
        if "@" in line or "http" in lower or "www." in lower or "linkedin.com" in lower:
            continue
        # Hard skip: section header
        if lower in _CV_SECTION_HEADERS or any(
            lower.startswith(h + ":") for h in _CV_SECTION_HEADERS
        ):
            continue
        # Hard skip: looks like a date (contains year 19xx/20xx)
        if re.search(r"\b(19|20)\d{2}\b", line):
            continue
        # Hard skip: more than 6 numeric characters (phone / ID / address)
        if len(re.findall(r"\d", line)) > 3:
            continue
        # Hard skip: contains special chars typical of addresses
        if any(c in line for c in ["/", "\\", "+", "|", "•", "●", "·", "→", "►"]):
            continue
        # Hard skip: probably a skill list or comma-separated items
        if line.count(",") >= 2:
            continue

        words = line.split()

        # Must be 1-4 words
        if len(words) < 1 or len(words) > 4:
            continue

        # Score candidates
        score = 0

        # Bonus: 2-3 word sequence (typical name)
        if 2 <= len(words) <= 3:
            score += 3
        elif len(words) == 1 and len(words[0]) >= 3:
            score += 0  # Possible but low confidence (single word)

        # Bonus: all words are Title Case or ALL CAPS (common in formal CVs)
        if all(w.istitle() or w.isupper() for w in words):
            score += 2

        # Bonus: if it's ALL CAPS convert it later
        if all(w.isupper() for w in words if len(w) > 1):
            score += 1

        # Bonus: appears in the first 5 lines (names usually at top)
        line_idx = lines.index(line) if line in lines else 15
        if line_idx < 3:
            score += 3
        elif line_idx < 5:
            score += 1

        # Penalty: contains numbers
        if re.search(r"\d", line):
            score -= 5

        # Penalty: contains punctuation (except hyphens/apostrophes in names)
        if re.search(r"[^\w\s\'\-]", line):
            score -= 3

        # Penalty: word is all lowercase (names are capitalized)
        if any(w.islower() and len(w) > 3 for w in words):
            score -= 2

        if score > best_score:
            best_score = score
            best_name = line

    if best_name and best_score >= 2:
        # Normalize: if ALL CAPS like "JOHN DOE", convert to "John Doe"
        if best_name.isupper():
            best_name = best_name.title()
        pii["name"] = best_name

    return pii


def anonymize_text(text: str, pii: dict) -> str:
    """
    Replaces found PII in text with placeholders.
    """
    if not text:
        return ""

    scrubbed = text

    # Redact Email
    if pii.get("email"):
        scrubbed = scrubbed.replace(pii["email"], "[EMAIL_REDACTED]")

    # Redact Phone
    if pii.get("phone"):
        scrubbed = scrubbed.replace(pii["phone"], "[PHONE_REDACTED]")

    # Redact Name (Case insensitive replace)
    if pii.get("name"):
        pattern = re.compile(re.escape(pii["name"]), re.IGNORECASE)
        scrubbed = pattern.sub("[NAME_REDACTED]", scrubbed)

    return scrubbed
