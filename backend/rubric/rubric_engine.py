import re
from typing import Any, Dict, List, Optional, Tuple

from backend.logger import logger

KEYWORD_MATCH_THRESHOLD = 0.10

QUALITY_MULTIPLIERS = {
    "strong": 1.0,
    "medium": 0.7,
    "weak": 0.4,
}

CONFIDENCE_MARGINS = {
    "strong": 5,
    "medium": 10,
    "weak": 20,
}


class SkillScoreResult:
    def __init__(
        self,
        skill_name: str,
        skill_id: str,
        base_score: int,
        quality: str,
        quality_multiplier: float,
        final_score: int,
        confidence_lower: int,
        confidence_upper: int,
        evidence_sentences: List[str],
        matched_level: Optional[str],
        matched_keywords: List[str],
        missing_competencies: List[str],
        explanation: str,
    ):
        self.skill_name = skill_name
        self.skill_id = skill_id
        self.base_score = base_score
        self.quality = quality
        self.quality_multiplier = quality_multiplier
        self.final_score = final_score
        self.confidence_lower = confidence_lower
        self.confidence_upper = confidence_upper
        self.evidence_sentences = evidence_sentences
        self.matched_level = matched_level
        self.matched_keywords = matched_keywords
        self.missing_competencies = missing_competencies
        self.explanation = explanation

    def to_dict(self) -> dict:
        return {
            "skill_name": self.skill_name,
            "skill_id": self.skill_id,
            "base_score": self.base_score,
            "quality": self.quality,
            "quality_multiplier": self.quality_multiplier,
            "final_score": self.final_score,
            "confidence_range": [self.confidence_lower, self.confidence_upper],
            "evidence": self.evidence_sentences,
            "matched_level": self.matched_level,
            "matched_keywords": self.matched_keywords,
            "missing_competencies": self.missing_competencies,
            "explanation": self.explanation,
        }


def score_answer(
    answer_text: str,
    extracted_skills: List[Dict[str, Any]],
    job_rubric,
    seniority: str = "mid",
) -> Dict[str, SkillScoreResult]:
    rubric_lookup = job_rubric.build_lookup()
    results = {}

    for extraction in extracted_skills:
        skill_name = extraction.get("skill_name", "").lower().strip()
        evidence = extraction.get("evidence_sentences", [])
        quality = extraction.get("quality", "weak")

        rubric_skill = rubric_lookup.get(skill_name)
        if not rubric_skill:
            logger.warning(
                f"[RUBRIC-ENGINE] Extracted skill '{skill_name}' not found in rubric lookup — skipping score"
            )
            continue

        levels = rubric_skill.levels.get(seniority, [])
        if not levels:
            continue

        base_score, matched_level_desc, matched_keywords = _find_best_level(
            evidence=evidence,
            levels=levels,
        )

        multiplier = QUALITY_MULTIPLIERS.get(quality, 0.4)
        # Rubric score is the source of truth.
        # Evidence quality affects confidence, but must not arbitrarily
        # destroy a demonstrated rubric level.
        #
        # Keep the rubric-derived score intact here. Performance
        # adjustments (rewards/penalties) are applied centrally after
        # rubric aggregation.
        final_score = min(100, max(0, int(base_score)))
        margin = CONFIDENCE_MARGINS.get(quality, 20)

        missing = _get_missing_competencies(base_score, levels)

        explanation = _build_explanation(
            skill_name=skill_name,
            base_score=base_score,
            quality=quality,
            quality_multiplier=multiplier,
            evidence=evidence,
            matched_level=matched_level_desc,
            missing_competencies=missing,
        )

        score_item = SkillScoreResult(
            skill_name=skill_name,
            skill_id=rubric_skill.id,
            base_score=base_score,
            quality=quality,
            quality_multiplier=multiplier,
            final_score=final_score,
            confidence_lower=max(0, final_score - margin),
            confidence_upper=min(100, final_score + margin),
            evidence_sentences=evidence,
            matched_level=matched_level_desc,
            matched_keywords=matched_keywords,
            missing_competencies=missing,
            explanation=explanation,
        )
        if skill_name not in results or final_score > results[skill_name].final_score:
            results[skill_name] = score_item

    return results


def _normalize_stem(word: str) -> str:
    """Normalize word to root stem for deterministic morphological keyword matching.
    Strips common inflectional suffixes while preserving word roots.
    """
    w = word.lower().strip()
    if len(w) <= 3:
        return w

    suffixes = [
        "ations", "ation", "ating", "ated", "ate", "izing", "ized", "ments", "ment",
        "ings", "ing", "edly", "able", "ably", "ness",
        "ions", "ion", "ies", "ied", "ed", "es", "s"
    ]
    stem = w
    for suf in suffixes:
        if w.endswith(suf) and len(w) - len(suf) >= 3:
            stem = w[:-len(suf)]
            break

    # Double consonant reduction (e.g., 'running' -> 'runn' -> 'run')
    if len(stem) >= 4 and stem[-1] == stem[-2] and stem[-1] not in "aeioulsz":
        stem = stem[:-1]

    # Trailing 'e' drop (e.g., 'manage' -> 'manag', 'analyze' -> 'analyz')
    if len(stem) >= 4 and stem.endswith("e"):
        stem = stem[:-1]

    return stem


def _keyword_matches_in_text(kw: str, evidence_text: str) -> bool:
    """Deterministic morphological keyword matching for rubric evaluation.
    Matches exact whole words or safe morphological inflections (stemming + max length diff).
    """
    kw_clean = kw.lower().strip()
    if not kw_clean:
        return False

    # 1. Exact whole-word regex match (highest precision)
    if re.search(r"\b" + re.escape(kw_clean) + r"\b", evidence_text):
        return True

    # 2. Acronym bidirectionality: Rubric keyword -> Acronym or Acronym -> Expanded
    acronym_map = {
        "crm": "customer relationship management",
        "erp": "enterprise resource planning",
        "kpi": "key performance indicator",
        "okr": "objectives and key results",
        "sql": "structured query language",
        "saas": "software as a service",
        "b2b": "business to business",
        "b2c": "business to consumer",
        "api": "application programming interface",
        "ux": "user experience",
        "ui": "user interface",
        "aws": "amazon web services",
        "k8s": "kubernetes",
    }
    for acr, exp in acronym_map.items():
        if kw_clean == acr and re.search(r"\b" + re.escape(exp) + r"\b", evidence_text.lower()):
            return True
        elif kw_clean == exp and re.search(r"\b" + re.escape(acr) + r"\b", evidence_text.lower()):
            return True

    # 3. Extract words from keyword and evidence text
    kw_words = re.findall(r"[a-z0-9]+", kw_clean)
    text_words = re.findall(r"[a-z0-9]+", evidence_text.lower())

    if not kw_words or not text_words:
        return False

    if len(kw_words) > 1:
        kw_stems = [_normalize_stem(w) for w in kw_words]
        text_stems = [_normalize_stem(w) for w in text_words]
        return all(st in text_stems for st in kw_stems)

    # 4. Single-word morphological matching with strict length difference boundary (<= 3)
    target_stem = _normalize_stem(kw_clean)
    for tw in text_words:
        if abs(len(tw) - len(kw_clean)) <= 3:
            if _normalize_stem(tw) == target_stem:
                return True

    return False


def _find_best_level(
    evidence: List[str],
    levels: list,
) -> Tuple[int, Optional[str], List[str]]:
    if not evidence or not levels:
        return (0, None, [])

    evidence_text = " ".join(evidence).lower()

    best_score = 0
    best_desc = None
    best_keywords = []

    for level in sorted(levels, key=lambda lev: lev.score_threshold):
        descriptor_keywords = [kw.lower() for kw in level.keywords]

        if not descriptor_keywords:
            continue

        matches = [
            kw
            for kw in descriptor_keywords
            if _keyword_matches_in_text(kw, evidence_text)
        ]
        match_ratio = (
            len(matches) / len(descriptor_keywords) if descriptor_keywords else 0
        )

        if match_ratio >= KEYWORD_MATCH_THRESHOLD or len(matches) >= 1:
            best_score = level.score_threshold
            best_desc = level.description
            best_keywords = list(matches)

    return (best_score, best_desc, best_keywords)


def _get_missing_competencies(current_score: int, levels: list) -> List[str]:
    missing = []
    for level in sorted(levels, key=lambda lev: lev.score_threshold):
        if level.score_threshold > current_score:
            missing.append(level.description)
    return missing


def _build_explanation(
    skill_name: str,
    base_score: int,
    quality: str,
    quality_multiplier: float,
    evidence: List[str],
    matched_level: Optional[str],
    missing_competencies: List[str],
) -> str:
    parts = []
    skill_display = skill_name.capitalize()
    parts.append(f"{skill_display} score = {int(base_score * quality_multiplier)}")

    if matched_level:
        parts.append(f"because candidate demonstrated: {matched_level}")

    if evidence:
        evidence_short = evidence[0][:120]
        parts.append(f'Evidence: "{evidence_short}"')

    if quality != "strong":
        parts.append(f"Evidence quality: {quality} ({quality_multiplier}x multiplier)")

    if missing_competencies:
        parts.append("Missing for higher score: " + "; ".join(missing_competencies[:2]))

    return ". ".join(parts) + "."
