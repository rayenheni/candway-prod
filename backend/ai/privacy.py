import re

from backend.ai.security import PIIMasker
from backend.logger import logger


def scrub_pii(text: str) -> str:
    """
    Scrubs Personal Identifiable Information (PII) from string.
    Targets: Emails, Phone Numbers, and common Street Address patterns.
    Name scrubbing is heuristic-based (start of line or before email).
    """
    if not text:
        return ""

    scrubbed = text

    # 1. Scrub Emails
    email_pattern = r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"
    scrubbed = re.sub(email_pattern, "[EMAIL_REDACTED]", scrubbed)

    # 2. Scrub Phone Numbers (Generic patterns for global/local formats)
    phone_pattern = (
        r"(\+?\d{1,3}[-.\s]?)?\(?\d{2,4}?\)?[-.\s]?\d{2,4}[-.\s]?\d{2,4}[-.\s]?\d{0,4}"
    )

    def phone_repl(match):
        m = match.group(0).strip()
        digits = re.sub(r"\D", "", m)
        if len(digits) >= 8:
            return " [PHONE_REDACTED] "
        return match.group(0)

    scrubbed = re.sub(phone_pattern, phone_repl, scrubbed)

    # 3. Scrub Addresses (Common keywords in Tunisian/French/English CVs)
    address_keywords = [
        "Rue",
        "Avenue",
        r"Av\.",
        "Cite",
        "Cit",
        "Residence",
        r"Res\.",
        "Blvd",
        "Street",
        r"St\.",
        "Apt",
        "Suite",
        "Lot",
        "Villas",
        "Appartement",
    ]
    for kw in address_keywords:
        addr_pattern = rf"(?i)({kw}\s+[^,\n.]{{5,40}})"
        scrubbed = re.sub(addr_pattern, "[ADDRESS_REDACTED]", scrubbed)

    # 4. Heuristic Name Scrubbing
    name_labels = ["Name:", "Nom:", "Full Name:", "Candidate:", "Identity:"]
    for label in name_labels:
        pattern = rf"(?i)({label}\s+[^,\n.]{{2,30}})"
        scrubbed = re.sub(pattern, f"{label} [NAME_REDACTED]", scrubbed)

    # 5. Additional PII via PIIMasker (new comprehensive patterns)
    scrubbed = PIIMasker.mask_pii(scrubbed, store_mapping=False)

    return scrubbed


def audit_ai_call(
    pipeline_stage: str,
    application_id: int,
    pii_count: int,
    pii_categories: list,
    success: bool,
    error_message: str = None,
):
    """
    Audit log for AI pipeline PII compliance.
    Never logs raw PII — only counts and categories.
    PII masking is unconditional and always enforced.
    """
    entry = {
        "pipeline_stage": pipeline_stage,
        "application_id": application_id,
        "pii_count": pii_count,
        "pii_categories": sorted(set(pii_categories)),
        "success": success,
    }
    if error_message:
        entry["error_message"] = error_message

    logger.info(
        f"[PII-AUDIT] {pipeline_stage} | app={application_id} | "
        f"pii_count={pii_count} | categories={entry['pii_categories']} | "
        f"success={success}"
    )
    return entry


def count_pii_categories(text: str) -> tuple:
    """
    Count PII categories found in text and return (count, categories_list).
    Does NOT log the actual PII values.
    """
    if not text:
        return 0, []

    from backend.ai.security import PIIMasker

    PIIMasker._init_patterns()  # Ensure patterns are initialized before iteration
    categories_found = set()
    for pattern, category in PIIMasker.PATTERNS:
        if pattern.search(text):
            categories_found.add(category)
    return len(categories_found), list(categories_found)
