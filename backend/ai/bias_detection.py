"""
Bias Detection Framework
=========================

Monitors scoring for demographic, linguistic, and cultural bias.
Provides audit trails and fairness metrics.

Features:
- Language bias detection (non-native English scoring)
- Cultural bias detection (region-specific references)
- Length bias detection (verbose vs. concise answers)
- Style bias detection (formal vs. informal communication)
- Statistical parity testing across groups
- Regular bias audit reports

Author: Candway Engineering
"""

import math
import statistics
import warnings
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class BiasIndicator:
    """A single bias signal detected in scoring"""

    type: str  # "language", "cultural", "length", "style", "gender", "age", "neurodiversity", "protected_attributes"
    severity: str  # "low", "medium", "high"
    description: str
    evidence: str
    affected_group: str
    score_delta: float  # Estimated score impact

    def to_dict(self) -> dict:
        return {
            "type": self.type,
            "severity": self.severity,
            "description": self.description,
            "evidence": self.evidence,
            "affected_group": self.affected_group,
            "estimated_score_impact": round(self.score_delta, 1),
        }


@dataclass
class BiasAuditReport:
    """Complete bias audit for an interview"""

    indicators: List[BiasIndicator] = field(default_factory=list)
    fairness_score: float = 100.0  # 100 = no bias detected
    risk_level: str = "Low"
    recommendations: List[str] = field(default_factory=list)
    statistical_tests: Dict[str, dict] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "fairness_score": round(self.fairness_score, 1),
            "risk_level": self.risk_level,
            "bias_indicators": [i.to_dict() for i in self.indicators],
            "recommendations": self.recommendations,
            "statistical_tests": self.statistical_tests,
            "total_indicators": len(self.indicators),
        }


def _count_syllables(word: str) -> int:
    """Simple syllable counter for readability estimation."""
    word = word.lower().strip(".,!?;:'\"-")
    if not word:
        return 1
    vowels = "aeiouy"
    count = 0
    prev_is_vowel = False
    for char in word:
        is_vowel = char in vowels
        if is_vowel and not prev_is_vowel:
            count += 1
        prev_is_vowel = is_vowel
    return max(1, count)


def detect_language_bias(
    answer: str,
    score: float,
    candidate_language: str = "English",
    is_native: bool = True,
) -> Optional[BiasIndicator]:
    """
    Detect if non-native speakers are being penalized for language vs. content.
    """
    if candidate_language != "English" or not is_native:
        words = answer.split()
        if len(words) < 3:
            return None

        # Estimate readability via simple Flesch-Kincaid-like heuristic
        word_count = len(words)
        sentence_count = max(
            1, answer.count(".") + answer.count("!") + answer.count("?")
        )
        syllables = sum(_count_syllables(w) for w in words)
        avg_syllables_per_word = syllables / word_count
        avg_words_per_sentence = word_count / sentence_count
        reading_ease = (
            206.835 - 1.015 * avg_words_per_sentence - 84.6 * avg_syllables_per_word
        )

        # Common idioms/jargon that may exclude non-native speakers
        idiom_indicators = [
            "hit the ground running",
            "think outside the box",
            "blue sky thinking",
            "drill down",
            "touch base",
            "circle back",
            "deep dive",
            "bandwidth",
            "low-hanging fruit",
            "move the needle",
            "game plan",
            "bleeding edge",
            "sweat equity",
            "boil the ocean",
            "ducks in a row",
            "get the ball rolling",
            "level playing field",
            "on the same page",
            "paradigm shift",
            "synergy",
            "value add",
            "actionable insights",
            "best of breed",
            "let's unpack",
            "off the table",
        ]
        idiom_count = sum(1 for idiom in idiom_indicators if idiom in answer.lower())

        flags = []
        if reading_ease < 30 and score < 60:
            flags.append(
                f"Very complex vocabulary (readability {reading_ease:.0f}/100) with low score"
            )
        if idiom_count >= 2 and score < 60:
            flags.append(
                f"Found {idiom_count} idioms/jargon terms that may exclude non-native speakers"
            )

        if flags:
            return BiasIndicator(
                type="language",
                severity="medium" if reading_ease < 20 else "low",
                description="; ".join(flags),
                evidence=f"Readability: {reading_ease:.1f}/100, idioms: {idiom_count}, "
                f"avg syllables/word: {avg_syllables_per_word:.2f}",
                affected_group="Non-native English speakers",
                score_delta=-3.0 if reading_ease < 20 else -1.5,
            )

    return None


def detect_length_bias(
    answer: str, score: float, avg_answer_length: float
) -> Optional[BiasIndicator]:
    """
    Detect if verbose or concise answers are being unfairly scored.
    """
    word_count = len(answer.split())

    # Very short answers that still contain correct technical content
    if word_count < 20 and score < 50:
        # Check if key technical terms are present (case-insensitive)
        technical_keywords = [
            "api",
            "database",
            "sql",
            "python",
            "java",
            "javascript",
            "react",
            "docker",
            "kubernetes",
            "aws",
            "azure",
            "gcp",
            "redis",
            "mongodb",
            "postgresql",
            "mysql",
            "fastapi",
            "django",
            "flask",
            "node",
            "async",
            "rest",
            "graphql",
            "microservice",
            "devops",
            "ci/cd",
            "git",
            "linux",
            "server",
            "cloud",
            "cache",
            "queue",
            "test",
        ]
        technical_count = sum(1 for kw in technical_keywords if kw in answer.lower())

        if technical_count >= 2:
            return BiasIndicator(
                type="length",
                severity="medium",
                description="Short answer with technical content may be undervalued",
                evidence=f"Answer has {word_count} words with {technical_count} technical terms but scored {score}",
                affected_group="Concise communicators",
                score_delta=-8.0,
            )

    # Very long answers that may be padded
    if word_count > 300 and score > 75:
        # Check signal-to-noise ratio
        unique_words = len(set(answer.lower().split()))
        diversity = unique_words / word_count if word_count > 0 else 0

        if diversity < 0.3:
            return BiasIndicator(
                type="length",
                severity="low",
                description="Long answer with low vocabulary diversity may be overvalued",
                evidence=f"Answer has {word_count} words but only {diversity:.1%} unique vocabulary",
                affected_group="Verbose communicators",
                score_delta=5.0,
            )

    return None


def detect_cultural_bias(
    answer: str, score: float, candidate_region: str = None
) -> Optional[BiasIndicator]:
    """
    Detect if region-specific references are affecting scores.
    """
    if not candidate_region:
        return None

    # Heuristic country list — this is a rough proxy only and should NOT be used
    # for automated decision-making or hiring decisions. Always involve human review.
    _NON_WESTERN_COUNTRIES = [
        "tunisia",
        "morocco",
        "algeria",
        "egypt",
        "libya",
        "mauritania",
        "sudan",
        "china",
        "india",
        "japan",
        "south korea",
        "vietnam",
        "thailand",
        "indonesia",
        "philippines",
        "malaysia",
        "singapore",
        "pakistan",
        "bangladesh",
        "sri lanka",
        "nepal",
        "myanmar",
        "cambodia",
        "laos",
        "mongolia",
        "taiwan",
        "nigeria",
        "kenya",
        "ethiopia",
        "ghana",
        "south africa",
        "tanzania",
        "uganda",
        "senegal",
        "cameroon",
        "ivory coast",
        "angola",
        "mozambique",
        "zambia",
        "brazil",
        "mexico",
        "argentina",
        "colombia",
        "chile",
        "peru",
        "venezuela",
        "ecuador",
        "bolivia",
        "paraguay",
        "uruguay",
        "costa rica",
        "panama",
        "turkey",
        "iran",
        "saudi arabia",
        "uae",
        "qatar",
        "kuwait",
        "oman",
        "jordan",
        "lebanon",
        "iraq",
        "syria",
        "yemen",
        "bahrain",
        "palestine",
        "russia",
        "ukraine",
        "poland",
        "romania",
        "czech republic",
        "hungary",
        "bulgaria",
        "serbia",
        "croatia",
        "slovakia",
        "lithuania",
        "latvia",
        "uk",
        "united kingdom",
        "france",
        "germany",
        "italy",
        "spain",
        "netherlands",
        "belgium",
        "switzerland",
        "sweden",
        "norway",
        "denmark",
        "finland",
        "australia",
        "new zealand",
        "canada",
        "usa",
        "united states",
    ]

    has_regional_ref = any(ref in answer.lower() for ref in _NON_WESTERN_COUNTRIES)

    if has_regional_ref and score < 55:
        return BiasIndicator(
            type="cultural",
            severity="low",
            description="Answer contains regional references that may not be recognized by evaluator",
            evidence=f"Regional reference detected for {candidate_region}",
            affected_group=f"Candidates from {candidate_region}",
            score_delta=-3.0,
        )

    return None


def detect_style_bias(answer: str, score: float) -> Optional[BiasIndicator]:
    """
    Flag communication style differences for human review — never adjust score.
    """
    informal_markers = [
        "lol",
        "haha",
        "yeah",
        "gonna",
        "wanna",
        "kinda",
        "sorta",
        "btw",
    ]
    informal_count = sum(1 for marker in informal_markers if marker in answer.lower())

    if informal_count >= 2:
        return BiasIndicator(
            type="style",
            severity="low",
            description="Informal communication style detected — flagging for human review, no score change",
            evidence=f"Found {informal_count} informal markers",
            affected_group="Informal communicators",
            score_delta=0.0,
        )

    return None


def detect_neurodiversity_accommodations(answer: str) -> Optional[BiasIndicator]:
    """
    Detect communication patterns common in neurodivergent candidates and flag
    for accommodation review rather than penalizing.
    """
    # Bullet-point vs paragraph structure
    lines = answer.strip().split("\n")
    bullet_lines = sum(
        1 for line in lines if line.strip().startswith(("-", "*", "•", "1.", "2."))
    )
    total_content_lines = sum(1 for line in lines if line.strip())
    uses_bullets = total_content_lines > 0 and bullet_lines / total_content_lines > 0.4

    # Literal language: low use of figurative expressions, metaphors, or idioms
    figurative_markers = [
        "like",
        "as if",
        "metaphor",
        "compare",
        "imagine",
        "picture this",
    ]
    figurative_count = sum(1 for m in figurative_markers if m in answer.lower())
    word_count = len(answer.split())
    literal_style = word_count > 20 and figurative_count == 0

    # Technical precision: specific numbers, dates, versions, measurements
    technical_precision = bool(
        sum(1 for token in answer.split() if any(c.isdigit() for c in token))
    )

    flags = []
    if uses_bullets:
        flags.append("Uses structured bullet-point format")
    if literal_style:
        flags.append(
            "Literal/figurative language ratio suggests direct communication style"
        )
    if technical_precision:
        flags.append("High technical precision with specific measurements/versions")

    if len(flags) >= 2:
        return BiasIndicator(
            type="neurodiversity",
            severity="low",
            description="Communication style consistent with neurodivergent presentation — "
            "flagging for accommodation review, no score adjustment",
            evidence="; ".join(flags),
            affected_group="Neurodivergent candidates",
            score_delta=0.0,
        )

    return None


def detect_gender_bias(answer: str) -> Optional[BiasIndicator]:
    """
    Check for gender-coded words and flag for human review.
    Does NOT make scoring decisions — only flags for human review.
    Based on established gender-coded word lists (Gaucher, Friesen, & Kay, 2011).
    """
    masculine_coded = [
        "assertive",
        "confident",
        "aggressive",
        "ambitious",
        "analytical",
        "competitive",
        "determined",
        "dominant",
        "forceful",
        "independent",
        "individual",
        "leadership",
        "objective",
        "outspoken",
        "self-reliant",
        "self-sufficient",
        "strong",
        "superior",
    ]
    feminine_coded = [
        "supportive",
        "caring",
        "compassionate",
        "considerate",
        "cooperative",
        "empathetic",
        "friendly",
        "gentle",
        "honest",
        "interpersonal",
        "kind",
        "loyal",
        "nurturing",
        "pleasant",
        "polite",
        "sensitive",
        "sympathetic",
        "trustworthy",
        "understanding",
        "warm",
    ]

    lower = answer.lower()
    masculine_score = sum(1 for w in masculine_coded if w in lower)
    feminine_score = sum(1 for w in feminine_coded if w in lower)

    if masculine_score >= 3 or feminine_score >= 3:
        bias_type = (
            "masculine-coded" if masculine_score > feminine_score else "feminine-coded"
        )
        return BiasIndicator(
            type="gender",
            severity="low",
            description=f"Job description/response uses {bias_type} language — "
            "flagging for human review, no score adjustment",
            evidence=f"Masculine-coded: {masculine_score}, Feminine-coded: {feminine_score}",
            affected_group="Gender-diverse candidates",
            score_delta=0.0,
        )

    return None


def detect_age_bias(answer: str) -> Optional[BiasIndicator]:
    """
    Check for age-coded language and flag for human review.
    Does NOT make scoring decisions.
    """
    age_coded_terms = {
        "young": "youth preference",
        "junior": "early-career preference",
        "senior": "late-career preference",
        "experienced": "late-career preference",
        "recent grad": "early-career preference",
        "fresh graduate": "early-career preference",
        "entry level": "early-career preference",
        "seasoned": "late-career preference",
        "veteran": "late-career preference",
        "digital native": "youth preference",
        "new blood": "youth preference",
        "fresh perspective": "youth preference",
        "overqualified": "late-career penalty",
        "high-potential": "youth preference",
    }

    lower = answer.lower()
    found = [
        (term, category) for term, category in age_coded_terms.items() if term in lower
    ]

    if found:
        categories = set(c for _, c in found)
        terms_found = [t for t, _ in found]
        return BiasIndicator(
            type="age",
            severity="low",
            description=f"Age-coded language detected ({', '.join(categories)}) — "
            "flagging for human review, no score adjustment",
            evidence=f"Terms found: {', '.join(terms_found)}",
            affected_group="Candidates across age spectrum",
            score_delta=0.0,
        )

    return None


def detect_protected_attributes_inference(answer: str) -> Optional[BiasIndicator]:
    """
    Check if the evaluation text is inferring protected attributes
    (race, religion, sexual orientation, disability) from CV or response content.
    This is a flag for human review only — never a score adjustment.
    """
    protected_inferences = {
        "race": [
            "ethnic sounding",
            "race",
            "caucasian",
            "african american",
            "asian american",
            "hispanic",
            "minority background",
        ],
        "religion": [
            "muslim",
            "christian",
            "jewish",
            "hindu",
            "buddhist",
            "sikh",
            "religious",
            "faith",
        ],
        "sexual_orientation": [
            "lgbtq",
            "gay",
            "lesbian",
            "bisexual",
            "transgender",
            "queer",
            "sexual orientation",
            "lifestyle choice",
        ],
        "disability": [
            "disabled",
            "handicap",
            "wheelchair",
            "accommodation",
            "special needs",
            "on the spectrum",
            "asperger",
            "adhd",
            "dyslexic",
            "mental health condition",
        ],
    }

    lower = answer.lower()
    found = []
    for category, terms in protected_inferences.items():
        for term in terms:
            if term in lower:
                found.append((category, term))

    if found:
        categories = set(c for c, _ in found)
        return BiasIndicator(
            type="protected_attributes",
            severity="high",
            description=f"Evaluation appears to infer protected attributes ({', '.join(categories)}) "
            "— flagging for immediate human review, no score adjustment",
            evidence=f"Matched terms: {', '.join(f'{t} ({c})' for c, t in found)}",
            affected_group="All candidates (protected group inference)",
            score_delta=0.0,
        )

    return None


def run_bias_audit(
    qa_pairs: List[dict],
    candidate_language: str = "English",
    is_native_speaker: bool = True,
    candidate_region: str = None,
) -> BiasAuditReport:
    """
    Run comprehensive bias audit on interview Q&A pairs.
    """
    report = BiasAuditReport()
    indicators = []

    if not qa_pairs:
        return report

    # Calculate average answer length
    answer_lengths = [
        len(qa.get("answer", "").split()) for qa in qa_pairs if qa.get("answer")
    ]
    avg_length = statistics.mean(answer_lengths) if answer_lengths else 0

    # Run detectors on each answer
    for qa in qa_pairs:
        answer = qa.get("answer", "")
        score = qa.get("score", 50)

        if not answer:
            continue

        # Language bias
        ind = detect_language_bias(answer, score, candidate_language, is_native_speaker)
        if ind:
            indicators.append(ind)

        # Length bias
        ind = detect_length_bias(answer, score, avg_length)
        if ind:
            indicators.append(ind)

        # Cultural bias
        ind = detect_cultural_bias(answer, score, candidate_region)
        if ind:
            indicators.append(ind)

        # Style bias
        ind = detect_style_bias(answer, score)
        if ind:
            indicators.append(ind)

        # Gender bias
        ind = detect_gender_bias(answer)
        if ind:
            indicators.append(ind)

        # Age bias
        ind = detect_age_bias(answer)
        if ind:
            indicators.append(ind)

        # Neurodiversity accommodations
        ind = detect_neurodiversity_accommodations(answer)
        if ind:
            indicators.append(ind)

        # Protected attributes inference
        ind = detect_protected_attributes_inference(answer)
        if ind:
            indicators.append(ind)

    report.indicators = indicators

    # Calculate fairness score
    severity_weights = {"low": 1, "medium": 3, "high": 5}
    total_penalty = sum(severity_weights.get(i.severity, 1) for i in indicators)
    report.fairness_score = max(0, 100 - total_penalty * 2)

    # Risk level
    high_count = sum(1 for i in indicators if i.severity == "high")
    medium_count = sum(1 for i in indicators if i.severity == "medium")

    if high_count >= 2 or total_penalty >= 15:
        report.risk_level = "High"
    elif high_count >= 1 or medium_count >= 3 or total_penalty >= 8:
        report.risk_level = "Medium"
    else:
        report.risk_level = "Low"

    # Recommendations
    if indicators:
        types_found = set(i.type for i in indicators)
        if "language" in types_found:
            report.recommendations.append(
                "Consider separating language mechanics from technical evaluation"
            )
        if "length" in types_found:
            report.recommendations.append(
                "Review scoring for answer length bias — content quality should matter more than verbosity"
            )
        if "cultural" in types_found:
            report.recommendations.append(
                "Train evaluators to recognize diverse cultural and regional references"
            )
        if "style" in types_found:
            report.recommendations.append(
                "Ensure communication style doesn't override technical competence in scoring"
            )
        if "gender" in types_found:
            report.recommendations.append(
                "Review for gendered language patterns that may affect candidate perception"
            )
        if "age" in types_found:
            report.recommendations.append(
                "Check for age-coded language that could bias evaluation"
            )
        if "neurodiversity" in types_found:
            report.recommendations.append(
                "Accommodate diverse communication styles - structured responses are valid evidence of competence"
            )
        if "protected_attributes" in types_found:
            report.recommendations.append(
                "IMMEDIATE REVIEW REQUIRED: Evaluation appears to infer protected attributes. Conduct human audit."
            )

    # Statistical tests
    if len(qa_pairs) >= 5:
        scores = [qa.get("score", 50) for qa in qa_pairs if qa.get("score")]
        if scores:
            report.statistical_tests["score_distribution"] = {
                "mean": round(statistics.mean(scores), 1),
                "std_dev": round(statistics.stdev(scores), 1) if len(scores) > 1 else 0,
                "min": min(scores),
                "max": max(scores),
                "coefficient_of_variation": round(
                    statistics.stdev(scores) / statistics.mean(scores), 2
                )
                if statistics.mean(scores) > 0
                else 0,
            }

    return report


def compute_statistical_parity(
    group_a_scores: List[float], group_b_scores: List[float], threshold: float = 0.05
) -> dict:
    """
    Compute statistical parity between two groups using Welch's t-test.
    Returns test result with proper p-value.
    """
    if not group_a_scores or not group_b_scores:
        return {"test": "insufficient_data", "parity": True, "p_value_approx": 1.0}

    mean_a = statistics.mean(group_a_scores)
    mean_b = statistics.mean(group_b_scores)
    n_a = len(group_a_scores)
    n_b = len(group_b_scores)

    # Effect size (Cohen's d)
    std_a = statistics.stdev(group_a_scores) if n_a > 1 else 1
    std_b = statistics.stdev(group_b_scores) if n_b > 1 else 1
    pooled_std = math.sqrt((std_a**2 + std_b**2) / 2)
    effect_size = abs(mean_a - mean_b) / pooled_std if pooled_std > 0 else 0

    # Welch's t-test: handles unequal variances and sample sizes
    try:
        from scipy import stats as _stats

        # Suppress unimportant warnings from scipy (e.g., small sample sizes)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            t_stat, p_value = _stats.ttest_ind(
                group_a_scores, group_b_scores, equal_var=False
            )
        # t_stat from ttest_ind is signed; take abs for two-sided
        t_stat = abs(float(t_stat))
        p_value = float(p_value)
    except ImportError:
        # Fallback if scipy is unavailable: normal approximation (valid for n>30 each)
        se = pooled_std * math.sqrt(1.0 / n_a + 1.0 / n_b)
        t_stat = abs(mean_a - mean_b) / se if se > 0 else 0
        # Normal approximation (t ≈ normal for df > 30)
        df = n_a + n_b - 2
        if df > 30:
            from math import erf

            p_value = 1.0 - erf(t_stat / math.sqrt(2))
        else:
            # Conservative bound: Bonferroni-like for small samples
            p_value = 2.0 * (1.0 - min(0.999, t_stat / (df**0.5) * 0.5 + 0.5))
    except Exception:
        p_value = 1.0

    return {
        "test": "welch_t_test",
        "group_a_mean": round(mean_a, 1),
        "group_b_mean": round(mean_b, 1),
        "effect_size": round(effect_size, 2),
        "p_value_approx": round(p_value, 3),
        "parity": p_value > threshold,
        "sample_sizes": {"a": n_a, "b": n_b},
    }
