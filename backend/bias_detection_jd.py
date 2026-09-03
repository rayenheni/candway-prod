import json
import re

from backend.ai.llm import call_groq_cascade
from backend.logger import logger


class JDBiasDetector:
    MASCULINE_CODED = [
        "aggressive",
        "ambitious",
        "assertive",
        "autonomous",
        "challenge",
        "competitive",
        "confident",
        "courageous",
        "decide",
        "decisive",
        "determined",
        "dominate",
        "dominating",
        "driven",
        "fearless",
        "fight",
        "fights",
        "hack",
        "hacker",
        "hardcore",
        "imperative",
        "independent",
        "individual",
        "leader",
        "leaders",
        "leadership",
        "logical",
        "objective",
        "opinion",
        "opinionated",
        "outspoken",
        "persist",
        "persistent",
        "rockstar",
        "rule",
        "rules",
        "self-confident",
        "self-reliant",
        "superior",
        "champion",
        "alpha",
    ]

    FEMININE_CODED = [
        "agree",
        "agreeable",
        "assist",
        "assists",
        "care",
        "cares",
        "collaborative",
        "commit",
        "committed",
        "communal",
        "compassion",
        "compassionate",
        "considerate",
        "cooperate",
        "cooperation",
        "cooperative",
        "courteous",
        "dedicated",
        "dependable",
        "emotional",
        "empathy",
        "faithful",
        "gentle",
        "genuine",
        "honest",
        "interpersonal",
        "kind",
        "kinship",
        "loyal",
        "loyalty",
        "modest",
        "nurture",
        "nurturing",
        "patient",
        "polite",
        "quiet",
        "responsive",
        "sensitive",
        "support",
        "supportive",
        "sympathetic",
        "tactful",
        "tender",
        "trustworthy",
        "understanding",
        "warm",
        "yield",
        "yielding",
    ]

    AGE_DISCRIMINATION = [
        "young",
        "junior",
        "senior",
        "fresh",
        "recent grad",
        "recent graduate",
        "new grad",
        "digital native",
        "over 40",
        "under 40",
        "generational",
        "years of experience required",
    ]

    UNNECESSARY_REQUIREMENTS = [
        "bachelor's",
        "bachelor",
        "master's",
        "master",
        "phd",
        "ph.d.",
        "degree required",
        "degree in",
    ]

    HEDGING_WORDS = [
        "maybe",
        "perhaps",
        "might",
        "could",
        "possibly",
        "hopefully",
        "ideally",
        "preferred",
        "nice to have",
        "optional",
    ]

    OVERCONFIDENCE_WORDS = [
        "must",
        "always",
        "never",
        "perfect",
        "flawless",
        "guaranteed",
        "absolute",
        "unquestionably",
        "undoubtedly",
    ]

    @classmethod
    def rule_based_scan(cls, text: str) -> list:
        if not text:
            return []
        text_lower = text.lower()
        flags = []

        word_lists = {
            "masculine_coded": (cls.MASCULINE_CODED, "gendered_language", "low"),
            "feminine_coded": (cls.FEMININE_CODED, "gendered_language", "low"),
            "age_discrimination": (cls.AGE_DISCRIMINATION, "age_bias", "high"),
            "unnecessary_requirements": (
                cls.UNNECESSARY_REQUIREMENTS,
                "requirement_fairness",
                "medium",
            ),
            "hedging": (cls.HEDGING_WORDS, "confidence_balance", "low"),
            "overconfidence": (cls.OVERCONFIDENCE_WORDS, "confidence_balance", "low"),
        }

        for category, (words, flag_category, severity) in word_lists.items():
            for word in words:
                pattern = r"\b" + re.escape(word) + r"\b"
                for match in re.finditer(pattern, text_lower):
                    start = match.start()
                    end = match.end()
                    context_start = max(0, start - 60)
                    context_end = min(len(text), end + 60)
                    context = text[context_start:context_end].strip()

                    alternatives = cls._get_alternatives(word, category)
                    flags.append(
                        {
                            "category": flag_category,
                            "severity": severity,
                            "found": word,
                            "context": context,
                            "position": [start, end],
                            "alternatives": alternatives,
                            "sub_category": category,
                        }
                    )

        return flags

    @classmethod
    def _get_alternatives(cls, word: str, category: str) -> list:
        alt_map = {
            "aggressive": ["ambitious", "driven", "energetic"],
            "ambitious": ["driven", "goal-oriented", "motivated"],
            "assertive": ["confident", "assured", "self-assured"],
            "rockstar": ["exceptional", "top-tier", "outstanding"],
            "champion": ["leader", "advocate", "supporter"],
            "alpha": ["leader", "pioneer", "leading"],
            "dominate": ["excel", "lead", "succeed"],
            "dominating": ["leading", "preeminent", "outstanding"],
            "hack": ["solve creatively", "innovate", "build"],
            "hacker": ["developer", "engineer", "builder"],
            "hardcore": ["dedicated", "passionate", "committed"],
            "fight": ["drive", "push", "strive"],
            "fights": ["drives", "pushes", "strives"],
            "assist": ["support", "help", "enable"],
            "assists": ["supports", "helps", "enables"],
            "nurture": ["develop", "support", "cultivate"],
            "nurturing": ["supportive", "encouraging", "developing"],
            "emotional": ["passionate", "engaged", "invested"],
            "sensitive": ["attentive", "perceptive", "considerate"],
            "young": [""],
            "junior": [""],
            "fresh": ["new", "recent", "early-career"],
            "senior": ["experienced", "seasoned", "advanced"],
            "recent grad": ["early-career professional", "new graduate"],
            "recent graduate": ["early-career professional", "new graduate"],
            "new grad": ["early-career professional"],
            "digital native": ["tech-savvy", "technology-oriented"],
        }
        return alt_map.get(word, [])

    @classmethod
    async def llm_analysis(cls, text: str, title: str, flags: list) -> dict:
        flag_summary = ""
        if flags:
            masc = [f["found"] for f in flags if f["sub_category"] == "masculine_coded"]
            fem = [f["found"] for f in flags if f["sub_category"] == "feminine_coded"]
            age = [f["found"] for f in flags if f["category"] == "age_bias"]
            req = [f["found"] for f in flags if f["category"] == "requirement_fairness"]
            if masc:
                flag_summary += (
                    f"\n- Masculine-coded words found: {', '.join(set(masc))}"
                )
            if fem:
                flag_summary += f"\n- Feminine-coded words found: {', '.join(set(fem))}"
            if age:
                flag_summary += f"\n- Age-related terms found: {', '.join(set(age))}"
            if req:
                flag_summary += (
                    f"\n- Potentially unnecessary requirements: {', '.join(set(req))}"
                )

        prompt = f"""You are an expert in inclusive hiring and job description bias analysis.
Analyze this job description for bias, inclusivity, and accessibility issues.

Job Title: {title}

Description:
{text}

Rule-based scan found:{flag_summary if flag_summary else chr(10) + "- No rule-based flags detected"}

Return JSON with:
1. "tone_assessment": A brief 1-sentence analysis of the overall tone.
2. "inclusivity_issues": List of 0-3 additional nuanced issues not caught by the rule scan.
3. "accessibility_notes": Suggestions to improve readability/accessibility.
4. "gender_inclusivity_score": 0-100 numeric score for gender-inclusive language.
5. "age_inclusivity_score": 0-100 numeric score for age-inclusive language.
6. "requirement_fairness_score": 0-100 numeric score for fair requirements.
7. "confidence_balance_score": 0-100 numeric score for tone confidence.
8. "accessibility_score": 0-100 numeric score for reading level/accessibility.
9. "overall_inclusivity_score": 0-100 combined score.
10. "reading_level": Estimated reading level (e.g. "College", "Grade 10", "Professional").

Be thorough but fair. Return ONLY valid JSON."""

        try:
            result = await call_groq_cascade(
                [{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=2048,
                json_mode=True,
            )
            if isinstance(result, dict):
                return result
            if isinstance(result, str):
                return json.loads(result)
            return {}
        except Exception as e:
            logger.error(f"[JD Bias] LLM analysis failed: {e}")
            return {
                "tone_assessment": "Analysis unavailable.",
                "inclusivity_issues": [],
                "accessibility_notes": "",
                "gender_inclusivity_score": 50,
                "age_inclusivity_score": 50,
                "requirement_fairness_score": 50,
                "confidence_balance_score": 50,
                "accessibility_score": 50,
                "overall_inclusivity_score": 50,
                "reading_level": "Unknown",
            }

    @classmethod
    async def generate_inclusive_rewrite(
        cls, text: str, flags: list, style: str = "neutral"
    ) -> str:
        flag_details = ""
        if flags:
            unique_issues = {}
            for f in flags:
                key = f["found"]
                if key not in unique_issues:
                    unique_issues[key] = f["alternatives"]
            if unique_issues:
                flag_details = "\n".join(
                    [
                        f"- Replace '{word}' with one of: {', '.join(alts) if alts else 'remove/rewrite'}"
                        for word, alts in unique_issues.items()
                    ]
                )

        style_guide = {
            "neutral": "professional, neutral tone that appeals to all candidates equally",
            "warm": "friendly, welcoming tone that emphasizes belonging and inclusion",
            "professional": "formal, business-appropriate tone that remains inclusive",
            "innovative": "forward-thinking, modern tone that highlights creativity and growth",
        }

        tone = style_guide.get(style, style_guide["neutral"])

        prompt = f"""Rewrite this job description to be more inclusive while keeping the core meaning.
Style: {tone}

Original:
{text}

Specific changes needed:{flag_details if flag_details else chr(10) + "- Review for general inclusivity improvements"}

Return JSON:
{{
  "rewritten_description": "The full rewritten job description text",
  "changelog": [
    {{"original": "aggressive", "replacement": "ambitious", "reason": "Masculine-coded term"}}
  ],
  "summary": "Brief summary of changes made"
}}

Return ONLY valid JSON."""

        try:
            result = await call_groq_cascade(
                [{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=2048,
                json_mode=True,
            )
            if isinstance(result, dict):
                return result
            if isinstance(result, str):
                return json.loads(result)
            return {
                "rewritten_description": text,
                "changelog": [],
                "summary": "Rewrite unavailable.",
            }
        except Exception as e:
            logger.error(f"[JD Bias] Rewrite failed: {e}")
            return {
                "rewritten_description": text,
                "changelog": [],
                "summary": "Rewrite unavailable.",
            }

    @classmethod
    def compute_score(cls, rule_flags: list, llm_analysis: dict) -> dict:
        deductions = {}

        for f in rule_flags:
            cat = f["category"]
            severity = f["severity"]
            points = {"low": 2, "medium": 5, "high": 10}
            if cat not in deductions:
                deductions[cat] = 0
            deductions[cat] += points.get(severity, 2)

        llm_scores = {
            "gender_inclusivity": llm_analysis.get("gender_inclusivity_score", 50),
            "age_inclusivity": llm_analysis.get("age_inclusivity_score", 50),
            "requirement_fairness": llm_analysis.get("requirement_fairness_score", 50),
            "confidence_balance": llm_analysis.get("confidence_balance_score", 50),
            "accessibility": llm_analysis.get("accessibility_score", 50),
        }

        cat_scores = {}
        for cat, llm_score in llm_scores.items():
            rule_deduction = deductions.get(cat, 0)
            cat_scores[cat] = max(0, min(100, llm_score - rule_deduction))

        overall_llm = llm_analysis.get("overall_inclusivity_score", 50)
        total_deduction = sum(deductions.values())
        overall = max(0, min(100, (overall_llm * 0.6 + (100 - total_deduction) * 0.4)))

        return {
            "overall_score": round(overall),
            "category_scores": {k: round(v) for k, v in cat_scores.items()},
            "grade": cls.get_grade(overall),
        }

    @staticmethod
    def get_grade(score: float) -> str:
        if score >= 90:
            return "A"
        if score >= 80:
            return "B"
        if score >= 65:
            return "C"
        if score >= 50:
            return "D"
        return "F"

    @classmethod
    async def analyze_jd(
        cls, job_title: str, description: str, skills: list = None
    ) -> dict:
        if not description:
            return {
                "overall_score": 0,
                "grade": "F",
                "flags": [],
                "category_scores": {},
                "rewritten_description": "",
                "summary": "No description provided to analyze.",
            }

        rule_flags = cls.rule_based_scan(description)

        try:
            llm_result = await cls.llm_analysis(description, job_title, rule_flags)
        except Exception as e:
            logger.error(f"[JD Bias] LLM analysis error: {e}")
            llm_result = {}

        scores = cls.compute_score(rule_flags, llm_result)

        try:
            rewrite_result = await cls.generate_inclusive_rewrite(
                description, rule_flags
            )
        except Exception as e:
            logger.error(f"[JD Bias] Rewrite error: {e}")
            rewrite_result = {
                "rewritten_description": description,
                "changelog": [],
                "summary": "",
            }

        grade = scores["grade"]

        flagged_categories = {}
        for f in rule_flags:
            cat = f["category"]
            if cat not in flagged_categories:
                flagged_categories[cat] = 0
            flagged_categories[cat] += 1

        summary_parts = []
        if flagged_categories.get("gendered_language", 0) > 0:
            summary_parts.append(
                f"{flagged_categories['gendered_language']} gendered language terms"
            )
        if flagged_categories.get("age_bias", 0) > 0:
            summary_parts.append(f"{flagged_categories['age_bias']} age-related terms")
        if flagged_categories.get("requirement_fairness", 0) > 0:
            summary_parts.append(
                f"{flagged_categories['requirement_fairness']} potentially unnecessary requirements"
            )
        if flagged_categories.get("confidence_balance", 0) > 0:
            summary_parts.append(
                f"{flagged_categories['confidence_balance']} confidence language issues"
            )

        if summary_parts:
            summary = f"Your job description uses {', '.join(summary_parts)}. Grade: {grade}. "
            if grade in ("A", "B"):
                summary += "This description is generally inclusive with minor improvements possible."
            elif grade == "C":
                summary += "Consider revising flagged terms to attract a more diverse applicant pool."
            else:
                summary += "Significant bias detected. We strongly recommend using the inclusive rewrite."
        else:
            summary = f"Your job description scores well on inclusivity. Grade: {grade}. No significant bias detected."

        return {
            "overall_score": scores["overall_score"],
            "grade": grade,
            "flags": sorted(
                rule_flags,
                key=lambda x: {"high": 0, "medium": 1, "low": 2}.get(x["severity"], 3),
            ),
            "category_scores": scores["category_scores"],
            "rewritten_description": rewrite_result.get(
                "rewritten_description", description
            ),
            "changelog": rewrite_result.get("changelog", []),
            "rewrite_summary": rewrite_result.get("summary", ""),
            "summary": summary,
            "tone_assessment": llm_result.get("tone_assessment", ""),
            "inclusivity_issues": llm_result.get("inclusivity_issues", []),
            "accessibility_notes": llm_result.get("accessibility_notes", ""),
            "reading_level": llm_result.get("reading_level", "Unknown"),
        }

    @classmethod
    def get_word_lists(cls) -> dict:
        return {
            "masculine_coded": sorted(cls.MASCULINE_CODED),
            "feminine_coded": sorted(cls.FEMININE_CODED),
            "age_discrimination": sorted(cls.AGE_DISCRIMINATION),
            "unnecessary_requirements": sorted(cls.UNNECESSARY_REQUIREMENTS),
            "hedging": sorted(cls.HEDGING_WORDS),
            "overconfidence": sorted(cls.OVERCONFIDENCE_WORDS),
        }
