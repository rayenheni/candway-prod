"""
Anti-Cheat System for AI Interview
Detects manipulation attempts, contradictions, and suspicious patterns.

PHASE D: Anti-Cheat System
"""

import re
from typing import Any, Dict, List


class AntiCheatDetector:
    """
    Detects various cheating techniques used by candidates to manipulate scoring.
    """

    # Common buzzword stuffing patterns
    BUZZWORD_PATTERNS = [
        r"\b(machine learning|deep learning|AI|ML)\b.*\b(python|tensorflow|pytorch)\b",
        r"\b(agile|scrum|kanban)\b.*\b(team|lead|management)\b",
        r"\b(microservices|api|rest|graphql)\b.*\b(docker|kubernetes|aws)\b",
    ]

    @staticmethod
    def calculate_cheat_score(
        answer: str,
        cv_claims: List[str] = None,
        history: List[Dict] = None,
        previous_answers: List[str] = None,
    ) -> Dict[str, Any]:
        """
        Calculate a comprehensive cheat detection score.

        Returns:
            dict with:
                - cheat_detected: bool
                - cheat_score: int (0-40 penalty)
                - details: breakdown of detected issues
        """
        if not answer:
            return {"cheat_detected": False, "cheat_score": 0, "details": {}}

        scores = {
            "repetition_score": AntiCheatDetector._check_repetition(answer),
            "vague_score": AntiCheatDetector._check_vagueness(answer),
            "contradiction_score": 0,  # Will be calculated
            "overclaim_score": AntiCheatDetector._check_overclaiming(answer),
            "buzzword_score": AntiCheatDetector._check_buzzword_stuffing(answer),
        }

        # Calculate CV contradictions if CV claims provided
        if cv_claims:
            scores["contradiction_score"] = AntiCheatDetector._check_cv_contradiction(
                answer, cv_claims
            )

        # Calculate cross-turn contradictions from previous answers
        cross_turn_score = AntiCheatDetector._check_cross_turn_contradiction(
            answer, previous_answers or []
        )
        # Use the higher of CV-contradiction and cross-turn scores
        if cross_turn_score > scores["contradiction_score"]:
            scores["contradiction_score"] = cross_turn_score

        # Calculate total cheat penalty (max 40 points)
        cheat_penalty = sum(scores.values()) * 10

        cheat_detected = any(scores.values())

        return {
            "cheat_detected": cheat_detected,
            "cheat_score": min(cheat_penalty, 40),
            "details": scores,
            "action_required": "Request verification" if cheat_detected else None,
        }

    @staticmethod
    def _check_repetition(answer: str) -> int:
        """
        Detect repetitive content.
        Returns 0-3 based on severity.
        """
        if not answer or len(answer) < 50:
            return 0

        words = answer.lower().split()
        if len(words) < 10:
            return 0

        unique_ratio = len(set(words)) / len(words)

        if unique_ratio < 0.2:
            return 3  # High repetition
        elif unique_ratio < 0.3:
            return 2  # Medium repetition
        elif unique_ratio < 0.4:
            return 1  # Low repetition

        return 0

    @staticmethod
    def _check_vagueness(answer: str) -> int:
        """
        Detect vague/meaningless answers.
        Returns 0-3 based on severity.
        """
        if not answer:
            return 0

        # Very short answers
        # Very short answers (but allow simple confirmations)
        words = answer.split()
        if len(words) < 10:  # Increased threshold for more rigor
            confirmations = {
                "yes",
                "no",
                "exactly",
                "correct",
                "i did",
                "sure",
                "indeed",
                "absolutely",
                "okay",
                "fine",
                "ready",
            }
            if any(w in answer.lower() for w in confirmations):
                return 0

            # Allow concise evidence-backed answers (action verb/implementation + metric signal)
            from backend.rubric.evidence_analyzer import IMPLEMENTATION_SIGNALS, METRIC_PATTERN
            answer_lower = answer.lower()
            has_action = any(sig in answer_lower for sig in IMPLEMENTATION_SIGNALS) or any(
                act in answer_lower for act in ["reduced", "increased", "improved", "saved", "achieved", "solved", "fixed", "led"]
            )
            has_metric = bool(METRIC_PATTERN.search(answer_lower))
            if has_action and has_metric:
                return 0

            return 1  # Reduced penalty significantly for short answers

        # Generic filler phrases
        vague_patterns = [
            r"\b(good|great|excellent)\b.*\b(experience|knowledge)\b",
            r"\b(I think|I believe|maybe|possibly)\b",
            r"\b(learning|growing|developing)\b",
        ]

        vague_count = 0
        for pattern in vague_patterns:
            if re.search(pattern, answer.lower()):
                vague_count += 1

        if vague_count >= 3:
            return 3
        elif vague_count >= 2:
            return 2
        elif vague_count >= 1:
            return 1

        return 0

    @staticmethod
    def _check_cv_contradiction(answer: str, cv_claims: List[str]) -> int:
        """
        Check for contradictions between answer and CV claims.
        Returns 0-3 based on severity.

        Now actually compares answer content against specific CV claims:
        - If candidate denies having a skill/technology listed on CV
        - If candidate contradicts years of experience claimed
        - If candidate denies working at a company listed on CV
        """
        if not cv_claims:
            return 0

        answer_lower = answer.lower()
        contradiction_count = 0

        # Check each CV claim for explicit denial in the answer
        negation_patterns = [
            r"\b(do not|don\'t|dont|never|no|not)\b.*\b(use|know|have|worked|experience)\b",
            r"\b(no|zero|lack)\b.*\b(experience|background|skill|familiarity)\b",
            r"\b(unfamiliar|unknown|never heard|never used)\b",
            r"\b(don't know|do not know|no idea|no experience)\b",
            r"\b(not familiar|not experienced|not worked)\b",
            r"\b(hardly|barely|scarcely|rarely)\b.*\b(use|work|touch)\b",
        ]

        for claim in cv_claims[:10]:
            claim_lower = claim.lower()
            # Extract key terms from the claim (words > 3 chars)
            claim_terms = [w for w in re.findall(r"[a-z]+", claim_lower) if len(w) > 3]

            if not claim_terms:
                continue

            # Check if answer mentions the claim topic AND denies it
            for pattern in negation_patterns:
                if re.search(pattern, answer_lower):
                    # Check if any claim term appears near the negation
                    for term in claim_terms:
                        if term in answer_lower:
                            contradiction_count += 1
                            break
                    if contradiction_count > 0:
                        break

            # Also check: candidate says they have NO experience with something on CV
            for term in claim_terms:
                if term in answer_lower:
                    # Check for denial phrases nearby
                    denial_phrases = [
                        f"no experience with {term}",
                        f"never used {term}",
                        f"don't know {term}",
                        f"not familiar with {term}",
                        f"haven't worked with {term}",
                    ]
                    for phrase in denial_phrases:
                        if phrase in answer_lower:
                            contradiction_count += 1
                            break

        # Check if answer completely ignores major CV topics in a long response
        if len(answer.split()) > 50:
            claim_match = False
            for claim in cv_claims[:5]:
                claim_terms = [w for w in claim.lower().split() if len(w) > 4]
                if any(term in answer_lower for term in claim_terms):
                    claim_match = True
                    break
            if not claim_match:
                contradiction_count += 1

        return min(contradiction_count, 3)

    @staticmethod
    def _check_overclaiming(answer: str) -> int:
        """
        Detect overclaiming (impossible or exaggerated claims).
        Returns 0-3 based on severity.
        """
        if not answer:
            return 0

        # Extreme claims
        extreme_patterns = [
            r"\b(built|created|developed|wrote|coded)\b.*\b(alone|by myself|single-handedly|independently)\b.*\b(million|billion|1000000)\b",
            r"\b(alone|by myself|single-handedly)\b.*\b(entire|all|complete)\b",
            r"\b(revolutionary|game.?changing|breakthrough)\b",
            r"\b(increased|improved|boosted|grew)\b.*\b(1000%|5000%|10000%)\b",
        ]

        extreme_count = 0
        for pattern in extreme_patterns:
            if re.search(pattern, answer.lower()):
                extreme_count += 1

        return min(extreme_count, 3)

    @staticmethod
    def _check_buzzword_stuffing(answer: str) -> int:
        """
        Detect keyword/buzzword stuffing without substance.
        Returns 0-3 based on severity.

        FIX: Now checks if buzzwords are used in context (with verbs, descriptions)
        vs. just listed. Legitimate technical answers mentioning many technologies
        in context are not flagged.
        """
        if not answer or len(answer.split()) < 20:
            return 0

        # Count tech buzzwords
        buzzwords = [
            "python",
            "java",
            "javascript",
            "react",
            "angular",
            "vue",
            "aws",
            "gcp",
            "azure",
            "docker",
            "kubernetes",
            "machine learning",
            "ai",
            "ml",
            "deep learning",
            "microservices",
            "api",
            "rest",
            "graphql",
            "agile",
            "scrum",
            "kanban",
            "devops",
            "ci/cd",
            "sql",
            "nosql",
            "mongodb",
            "postgresql",
            "mysql",
        ]

        answer_lower = answer.lower()
        word_count = len(answer.split())

        # Count how many buzzwords appear
        found_buzzwords = [word for word in buzzwords if word in answer_lower]
        buzzword_count = len(found_buzzwords)

        # Check if buzzwords are used in context (surrounded by explanatory words)
        # A buzzword "in context" has verbs, adjectives, or descriptions nearby
        context_indicators = 0
        for bw in found_buzzwords:
            bw_pos = answer_lower.find(bw)
            if bw_pos >= 0:
                # Look at 30 chars before and after the buzzword
                context_window = answer_lower[
                    max(0, bw_pos - 30) : bw_pos + len(bw) + 30
                ]
                # Check for context indicators: verbs, prepositions, descriptive words
                has_context = any(
                    indicator in context_window
                    for indicator in [
                        "used",
                        "built",
                        "created",
                        "designed",
                        "implemented",
                        "developed",
                        "with",
                        "using",
                        "for",
                        "because",
                        "since",
                        "when",
                        "while",
                        "to",
                        "that",
                        "which",
                        "how",
                        "why",
                        "where",
                        "improved",
                        "reduced",
                        "increased",
                        "optimized",
                        "scaled",
                        "problem",
                        "challenge",
                        "solution",
                        "approach",
                        "method",
                        "team",
                        "project",
                        "client",
                        "product",
                        "system",
                    ]
                )
                if has_context:
                    context_indicators += 1

        # If most buzzwords are used in context, it's legitimate technical discussion
        if buzzword_count > 0:
            context_ratio = context_indicators / buzzword_count
            if context_ratio > 0.6:
                return 0  # Legitimate technical discussion

        # Only flag if high density AND low context usage
        buzzword_ratio = buzzword_count / word_count

        if buzzword_ratio > 0.3 and context_ratio < 0.3:
            return 3  # High stuffing, no context
        elif buzzword_ratio > 0.2 and context_ratio < 0.4:
            return 2  # Moderate stuffing
        elif buzzword_ratio > 0.15 and context_ratio < 0.2:
            return 1  # Mild stuffing

        return 0

    @staticmethod
    def _check_cross_turn_contradiction(
        answer: str, previous_answers: List[str]
    ) -> int:
        """
        Detect contradictions between current answer and candidate's own previous answers.
        Returns 0-3 based on severity.

        Detects patterns:
        - Numeric contradictions: "5 years XP" vs "2 years XP"
        - Role contradictions: "I was the lead" vs "I was a junior"
        - Explicit denial of previously claimed knowledge
        """
        if not answer or not previous_answers:
            return 0

        answer_lower = answer.lower()
        contradiction_count = 0

        # Extract numeric claims from current answer (years, team sizes, percentages)
        import re as _re

        current_nums = _re.findall(
            r"\b(\d+)\s*(?:years?|yrs?|people|members?|percent|%)\b", answer_lower
        )

        # Check each previous answer for conflicting numbers
        for prev in previous_answers[-5:]:  # check last 5 answers
            prev_lower = prev.lower()

            # 1. Direct contradiction: "I don't know X" after previously discussing X
            denial_patterns = [
                r"\b(never heard|don't know|no idea|unfamiliar|no experience with)\s+(.{3,30})$",
                r"\b(I don't|i do not)\s+(know|understand|have)\s+(any|much|enough)",
                r"\b(not familiar|no background|haven't worked)\s+(with|in|on)\s+(.{3,30})",
            ]
            for pattern in denial_patterns:
                denial_match = _re.search(pattern, answer_lower)
                if denial_match:
                    denied_topic = denial_match.group(0).lower()
                    # Check if previous answer mentions the denied topic
                    topic_words = set(_re.findall(r"[a-z]{4,}", denied_topic))
                    prev_words = set(_re.findall(r"[a-z]{4,}", prev_lower))
                    if (
                        topic_words
                        and prev_words
                        and len(topic_words & prev_words) >= 2
                    ):
                        contradiction_count += 2
                        break

            # 2. Numeric contradiction: conflicting experience claims
            prev_nums = _re.findall(
                r"\b(\d+)\s*(?:years?|yrs?|people|members?|percent|%)\b", prev_lower
            )
            for cn, pn in zip(current_nums, prev_nums):
                try:
                    if abs(int(cn) - int(pn)) >= 3:  # 3+ year discrepancy
                        contradiction_count += 1
                except ValueError:
                    pass

            # 3. Role level contradiction
            seniority_up = {
                "junior",
                "mid",
                "senior",
                "lead",
                "principal",
                "architect",
                "manager",
                "director",
                "vp",
                "head",
            }
            current_levels = {w for w in seniority_up if w in answer_lower}
            prev_levels = {w for w in seniority_up if w in prev_lower}
            if current_levels and prev_levels:
                # If they claimed different levels, flag it
                level_order = [
                    "junior",
                    "mid",
                    "senior",
                    "lead",
                    "principal",
                    "architect",
                    "manager",
                    "director",
                    "vp",
                    "head",
                ]
                max_cur = max(
                    (
                        level_order.index(lv)
                        for lv in current_levels
                        if lv in level_order
                    ),
                    default=-1,
                )
                max_prev = max(
                    (level_order.index(lv) for lv in prev_levels if lv in level_order),
                    default=-1,
                )
                if max_cur >= 0 and max_prev >= 0 and abs(max_cur - max_prev) >= 3:
                    contradiction_count += 1

            # 4. Possession contradiction: "I don't have X" after "I have X experience"
            negation_phrases = _re.findall(
                r"(?:don't|dont|do not|never|no)\s+(.{3,40})", answer_lower
            )
            for phrase in negation_phrases:
                phrase_clean = phrase.strip().lower()
                if phrase_clean in prev_lower or any(
                    _re.search(rf"\b{_re.escape(word)}\b", prev_lower)
                    for word in _re.findall(r"[a-z]{4,}", phrase_clean)
                    if word not in {"have", "with", "that", "this", "been", "ever"}
                ):
                    contradiction_count += 1

        return min(contradiction_count, 3)

    @staticmethod
    def apply_cheat_penalty(base_score: float, cheat_score: int) -> float:
        """
        Apply cheat penalty to base score.
        """
        penalty = cheat_score  # Each cheat type = 10 point penalty, max 40
        return max(0, base_score - penalty)


# Global instance for easy import
anti_cheat = AntiCheatDetector()
