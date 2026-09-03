"""
backend/ai/interview_customization.py

Recruiter Interview Customization Engine
Steps 2–7 from the architecture spec:
  - Instruction normalization (Step 2)
  - Interview state tracking (Step 3)
  - Priority-based focus selection (Step 4)
  - Prompt injection helpers (Step 5)
  - Post-generation validation (Step 6)
  - State update (Step 7)
"""

import json
import logging
import re
from dataclasses import dataclass, field

logger = logging.getLogger("candway_app")


@dataclass
class SkillFocus:
    name: str
    description: str = ""
    keywords: list = field(default_factory=list)
    level_text: str = ""
    is_required: bool = False
    coverage_context: str = ""


# ---------------------------------------------------------------------------
# STEP 2: INSTRUCTION NORMALIZATION
# ---------------------------------------------------------------------------


def normalize_instructions(raw_text: str) -> dict:
    """
    Parse free-form recruiter text into a structured dict.
    Patterns detected:
      - "Must ask about X"  → must_topics
      - "Ask about X every N questions" → frequency_rules
      - Lines that look like standalone questions ("...?") → custom_questions
    Fallback: everything goes into "raw" so the LLM can still read it.
    """
    if not raw_text or not raw_text.strip():
        return {
            "must_topics": [],
            "frequency_rules": [],
            "custom_questions": [],
            "raw": "",
        }

    raw = raw_text.strip()
    result = {
        "must_topics": [],
        "frequency_rules": [],
        "custom_questions": [],
        "raw": raw,
    }

    try:
        lines = []
        # Split only on newlines and bullet points, NOT on periods (preserves abbreviations like Ph.D., e.g., i.e.)
        for para in raw.splitlines():
            # Split on bullet points and numbered lists
            parts = re.split(r"\n\s*[•\-*]\s*|\n\s*\d+\.\s*", para)
            for part in parts:
                cleaned = part.strip().strip("•-* \t")
                if cleaned:
                    lines.append(cleaned)

        for line in lines:
            low = line.lower()

            # Frequency rule: "ask about X every N questions/turns"
            freq_match = re.search(
                r"ask\s+(?:about\s+)?(.+?)\s+every\s+(\d+)\s*(?:question|turn|q)?s?",
                low,
            )
            if freq_match:
                topic = freq_match.group(1).strip().title()
                every = int(freq_match.group(2))
                result["frequency_rules"].append({"topic": topic, "every": every})
                continue

            # Must-topic: "must ask about X" / "always ask about X"
            must_match = re.search(
                r"(?:must|always|ensure|required?|mandatory)\s+(?:ask|cover|include|mention)\s+(?:about\s+)?(.+)",
                low,
            )
            if must_match:
                topic = must_match.group(1).strip().rstrip(".!,;").title()
                result["must_topics"].append(topic)
                continue

            # Custom question: ends with "?"
            if line.endswith("?") and len(line) > 15:
                result["custom_questions"].append(line)
                continue

        logger.info(
            f"[INSTRUCTIONS] Parsed: {len(result['must_topics'])} must-topics, "
            f"{len(result['frequency_rules'])} freq-rules, "
            f"{len(result['custom_questions'])} custom-Qs"
        )
    except Exception as e:
        logger.warning(f"[INSTRUCTIONS] Parse failed, using raw fallback: {e}")

    return result


# ---------------------------------------------------------------------------
# STEP 3: INTERVIEW STATE TRACKING
# ---------------------------------------------------------------------------


def load_instruction_state(interview_log: list) -> dict:
    """
    Rebuild instruction-tracking state from the existing interview log.
    Looks for a special sentinel message appended by update_instruction_state().
    """
    default = {
        "question_index": 0,
        "covered_topics": [],
        "instruction_usage": {"must_topics_covered": [], "frequency_hits": {}},
    }
    for msg in reversed(interview_log or []):
        if msg.get("role") == "__state__":
            try:
                return json.loads(msg["content"])
            except Exception:
                pass
    return default


def save_instruction_state(interview_log: list, state: dict) -> list:
    """
    Persist the updated state back into the interview_log as a sentinel message.
    Replaces any previous sentinel.
    """
    log = [m for m in (interview_log or []) if m.get("role") != "__state__"]
    log.append({"role": "__state__", "content": json.dumps(state)})
    return log


# ---------------------------------------------------------------------------
# STEP 4: PRIORITY-BASED FOCUS SELECTION
# ---------------------------------------------------------------------------


def compute_difficulty_band(
    current_score: float, recent_history: list, q_index: int, total_questions: int
) -> str:
    """
    Compute the difficulty band for the next question based on candidate performance.
    Returns: 'Beginner' | 'Intermediate' | 'Advanced' | 'Expert'
    """
    # Normalize score
    score = float(current_score or 75.0)

    # Progress ratio — ramp difficulty as interview progresses
    progress = q_index / max(total_questions, 1)

    # Recency penalty: if last 2 answers were weak, don't increase difficulty
    if len(recent_history) >= 2:
        recent_ai = [m for m in recent_history[-4:] if m.get("role") == "assistant"]
        # Simple heuristic: more messages = more engagement
        if len(recent_ai) == 0:
            score = max(score - 5, 0)

    # Map score + progress to difficulty band
    if score >= 85 and progress >= 0.4:
        return "Expert"
    elif score >= 70 and progress >= 0.25:
        return "Advanced"
    elif score >= 50:
        return "Intermediate"
    else:
        return "Beginner"


def select_focus(
    cv_terms: list,
    skill_scores: dict,
    instructions: dict,
    state: dict,
    declared_role: str,
    rubric_categories: list = None,
) -> str:
    """
    Priority-based focus selector for the interview engine.
    Priority order:
      1. Mandatory topics from recruiter instructions (not yet covered)
      2. Frequency-rule topics (due this turn)
      3. Rubric skills (required first, then optional) not yet covered
      4. Must-probe skills from CV with low scores
      5. Untested CV terms
      6. Role fallback
    """
    must_covered = set(
        state.get("instruction_usage", {}).get("must_topics_covered", [])
    )
    q_index = state.get("question_index", 0)

    # 1. Mandatory recruiter topics not yet covered
    must_topics = instructions.get("must_topics", [])
    remaining_must = [t for t in must_topics if t not in must_covered]
    if remaining_must:
        logger.info(f"[SELECT_FOCUS] Using must-topic: {remaining_must[0]}")
        return remaining_must[0]

    # 2. Frequency-rule topics due this turn
    for rule in instructions.get("frequency_rules", []):
        every = rule.get("every", 99)
        topic = rule.get("topic", "")
        if every > 0 and q_index > 0 and q_index % every == 0:
            logger.info(f"[SELECT_FOCUS] Frequency rule due: {topic}")
            return topic

    # 3. Rubric skills (required first, then optional) not yet covered
    if rubric_categories:
        covered_skills = set(state.get("covered_skills", []) if state else [])
        rubric_skills = []
        for cat in rubric_categories:
            for sub in (
                cat.subcategories
                if hasattr(cat, "subcategories")
                else cat.get("subcategories", [])
            ):
                for sk in (
                    sub.skills if hasattr(sub, "skills") else sub.get("skills", [])
                ):
                    rubric_skills.append(sk)

        required = [
            s
            for s in rubric_skills
            if (s.is_required if hasattr(s, "is_required") else s.get("is_required"))
        ]
        optional = [
            s
            for s in rubric_skills
            if not (
                s.is_required if hasattr(s, "is_required") else s.get("is_required")
            )
        ]

        for pool in [required, optional]:
            for sk in pool:
                name = sk.name if hasattr(sk, "name") else sk.get("name", "")
                if name.lower() not in covered_skills:
                    logger.info(f"[SELECT_FOCUS] Using rubric skill: {name}")
                    return name

    # 4. Weakest CV skill (score < 60)
    # Map CV terms to skill category keys for comparison
    CV_TO_SKILL_MAP = {
        "python": "Technical",
        "javascript": "Technical",
        "java": "Technical",
        "react": "Technical",
        "angular": "Technical",
        "vue": "Technical",
        "node": "Technical",
        "django": "Technical",
        "flask": "Technical",
        "fastapi": "Technical",
        "spring": "Technical",
        "ruby": "Technical",
        "go": "Technical",
        "rust": "Technical",
        "c++": "Technical",
        "csharp": "Technical",
        "typescript": "Technical",
        "php": "Technical",
        "sql": "Technical",
        "postgresql": "Technical",
        "mysql": "Technical",
        "mongodb": "Technical",
        "redis": "Technical",
        "docker": "Technical",
        "kubernetes": "Technical",
        "aws": "Technical",
        "azure": "Technical",
        "gcp": "Technical",
        "terraform": "Technical",
        "git": "Technical",
        "html": "Technical",
        "css": "Technical",
        "tailwind": "Technical",
        "machine learning": "Technical",
        "ml": "Technical",
        "ai": "Technical",
        "tensorflow": "Technical",
        "pytorch": "Technical",
        "pandas": "Technical",
        "rest": "Technical",
        "graphql": "Technical",
        "api": "Technical",
        "microservices": "Technical",
        "devops": "Technical",
        "ci/cd": "Technical",
        "linux": "Technical",
        "bash": "Technical",
        "shell": "Technical",
        "communication": "Communication",
        "presentation": "Communication",
        "writing": "Communication",
        "public speaking": "Communication",
        "problem solving": "Problem Solving",
        "analytical": "Problem Solving",
        "debugging": "Problem Solving",
        "troubleshooting": "Problem Solving",
        "adaptability": "Adaptability",
        "agile": "Adaptability",
        "flexible": "Adaptability",
        "confidence": "Confidence",
        "leadership": "Confidence",
        "mentoring": "Confidence",
    }

    if skill_scores and cv_terms:
        weak = []
        for t in cv_terms:
            t_lower = t.lower()
            # Direct match (CV term is a skill category key)
            if t in skill_scores and float(skill_scores.get(t, 75)) < 60:
                weak.append(t)
            # Mapped match (CV term maps to a skill category)
            elif t_lower in CV_TO_SKILL_MAP:
                mapped = CV_TO_SKILL_MAP[t_lower]
                if mapped in skill_scores and float(skill_scores.get(mapped, 75)) < 60:
                    weak.append(t)
            # Partial match: check if any skill_scores key contains the CV term
            else:
                for skill_key in skill_scores:
                    if (
                        t_lower in skill_key.lower()
                        and float(skill_scores.get(skill_key, 75)) < 60
                    ):
                        weak.append(t)
                        break
        if weak:
            worst = min(
                weak,
                key=lambda t: float(
                    skill_scores.get(
                        t, skill_scores.get(CV_TO_SKILL_MAP.get(t.lower(), t), 75)
                    )
                ),
            )
            logger.info(f"[SELECT_FOCUS] Targeting weak skill: {worst}")
            return worst

    # 5. Untested CV terms
    covered = set(state.get("covered_topics", []))
    untested = [t for t in (cv_terms or []) if t not in covered]
    if untested:
        logger.info(f"[SELECT_FOCUS] Using untested CV term: {untested[0]}")
        return untested[0]

    # 6. Role fallback
    return declared_role or "General Reasoning"


def select_next_focus(
    state: dict,
    declared_role: str,
    rubric_categories: list = None,
    seniority: str = "mid",
) -> SkillFocus:
    """
    Selects the next topic focus (v3.1 Hardened).
    Returns a SkillFocus with rubric context when a rubric skill is chosen.
    Priority:
    1. Rubric skills (required first, then optional) not yet covered
    2. Weakness Reinforcement: Re-test skills with lowest weighted scores.
    3. Discovery: Move to unverified/untested skills if performance is stable.
    4. Fallback: Role or "General Reasoning".
    """
    # 0. Rubric skills (required first, then optional) not yet covered
    if rubric_categories:
        covered_skills = {s.lower() for s in (state.get("covered_skills", []) if state else [])}
        rubric_skills = []
        for cat in rubric_categories:
            for sub in (
                cat.subcategories
                if hasattr(cat, "subcategories")
                else cat.get("subcategories", [])
            ):
                for sk in (
                    sub.skills if hasattr(sub, "skills") else sub.get("skills", [])
                ):
                    rubric_skills.append(sk)

        required = [
            s
            for s in rubric_skills
            if (s.is_required if hasattr(s, "is_required") else s.get("is_required"))
        ]
        optional = [
            s
            for s in rubric_skills
            if not (
                s.is_required if hasattr(s, "is_required") else s.get("is_required")
            )
        ]

        for pool in [required, optional]:
            for sk in pool:
                name = sk.name if hasattr(sk, "name") else sk.get("name", "")
                lower_name = name.lower()
                if lower_name not in covered_skills:
                    logger.info(f"[SELECT_NEXT_FOCUS] Using rubric skill: {name}")

                    desc = (
                        sk.description
                        if hasattr(sk, "description")
                        else sk.get("description", "")
                    )
                    kw = (
                        sk.keywords
                        if hasattr(sk, "keywords")
                        else sk.get("keywords", [])
                    )
                    is_req = (
                        sk.is_required
                        if hasattr(sk, "is_required")
                        else sk.get("is_required", False)
                    )

                    levels = (
                        sk.levels if hasattr(sk, "levels") else sk.get("levels", {})
                    )
                    level_list = (
                        levels.get(seniority, []) if isinstance(levels, dict) else []
                    )
                    level_text = level_list[0].description if level_list else ""

                    # Coverage context: how many required skills have been tested
                    required_covered = sum(
                        1
                        for s in required
                        if (s.name if hasattr(s, "name") else s.get("name", "")).lower()
                        in covered_skills
                    )
                    total_required = len(required)
                    coverage = (
                        f"tested {required_covered} of {total_required} required skills"
                        if total_required
                        else ""
                    )

                    return SkillFocus(
                        name=name,
                        description=desc,
                        keywords=kw if isinstance(kw, list) else [],
                        level_text=level_text,
                        is_required=is_req,
                        coverage_context=coverage,
                    )

    strategy = state.get("strategy")
    pool = state.get("focus_pool", [])
    skill_scores = state.get("skill_scores", {})
    verified = state.get("verified_skills", [])

    # 1. IDENTIFY WEAKNESSES (Weighted sort)
    def _get_weight_val(skill):
        scores = skill_scores.get(skill, [])
        if not scores:
            return 101  # Move untested to end of weakness list
        weights = [i + 1 for i in range(len(scores))]
        return sum(s * w for s, w in zip(scores, weights)) / sum(weights)

    # Skills we have tested at least once
    tested = [s for s in pool if len(skill_scores.get(s, [])) > 0]

    # If we have weak skills (score < 60), hunt them!
    weak_skills = sorted(
        [s for s in tested if _get_weight_val(s) < 60], key=_get_weight_val
    )
    if weak_skills and state.get("turn", 0) % 2 == 1:  # Every other turn, hunt weakness
        return SkillFocus(name=weak_skills[0])

    # 2. DISCOVERY (Untested or Unverified)
    remaining = [s for s in pool if s not in verified]
    if strategy == "skill-driven" and remaining:
        # Prioritize untested, then unverified
        untested = [s for s in remaining if s not in tested]
        if untested:
            return SkillFocus(name=untested[0])
        return SkillFocus(name=remaining[0])

    if strategy == "role-driven":
        return SkillFocus(name=declared_role)

    return SkillFocus(name=declared_role or "General Reasoning")


def update_engine_state(
    state: dict, last_focus: str, last_score: float, category_scores: dict = None
) -> dict:
    """
    Updates the engine state after a turn (v3.0 Decision Intelligence).
    Logic:
    - V3 Dual-State: Competence + Sigma (Uncertainty)
    - Momentum tracking (slope of last 3 turns)
    - Confidence score (inverse of sigma)
    - Live Skill Blending (Talent Graph)
    """
    state["turn"] = state.get("turn", 0) + 1

    # V3 Initialization
    if "sigma" not in state:
        state["sigma"] = 25.0  # Initial high uncertainty
    if "momentum" not in state:
        state["momentum"] = 0.0

    # 0. DUAL-STATE UPDATE (Sigma & Score)
    prev_score = state.get("last_overall_score", 50.0)
    alpha = 0.3  # Learning rate for uncertainty

    # sigma_t = sigma_{t-1} * (1 - alpha) + alpha * abs(G_t - S_{t-1})
    current_sigma = state.get("sigma", 25.0)
    new_sigma = (current_sigma * (1 - alpha)) + (alpha * abs(last_score - prev_score))
    state["sigma"] = round(new_sigma, 2)
    state["last_overall_score"] = last_score

    # Confidence = 100 - beta * sigma
    beta = 1.2
    state["confidence_score"] = max(
        0, min(100, round(100 - (beta * state["sigma"]), 1))
    )

    # 3. LIVE SKILL BLENDING (Talent Graph V3 Upgrade)
    # Moved OUTSIDE the skill_scores gate so rubric skills (which may not
    # exist in skill_scores) can still update live_skill_metrics.
    if category_scores:
        live = state.get("live_skill_metrics", {})
        live_conf = state.get("live_skill_confidence", {})

        # Build a case-insensitive lookup of existing live keys
        _live_lower = {k.lower(): k for k in live}

        for cat, new_val in category_scores.items():
            # Resolve to the existing title-case key if present
            resolved = _live_lower.get(cat.lower(), cat)

            if resolved not in live:
                live[resolved] = 0.0
                live_conf[resolved] = 25.0
                if "live_skill_history" not in state:
                    state["live_skill_history"] = {}
                state["live_skill_history"][resolved] = []

            cat = resolved  # use the canonical key for the rest of this iteration
            if cat in live:
                clamped_val = float(new_val)

                # Rolling median of last N values per dimension
                if "live_skill_history" not in state:
                    state["live_skill_history"] = {}
                if cat not in state["live_skill_history"]:
                    state["live_skill_history"][cat] = []
                hist = state["live_skill_history"][cat]

                # Outlier rejection: only clamp after first observation
                # First assessment sets the baseline directly
                current = live[cat]
                if len(hist) > 0:
                    delta = clamped_val - current
                    if delta > 15:
                        clamped_val = current + 15
                    elif delta < -15:
                        clamped_val = current - 15

                hist.append(clamped_val)
                if len(hist) > 5:
                    hist.pop(0)
                median_val = sorted(hist)[len(hist) // 2]

                # First observation: set directly; subsequent: blend 40/60
                update_weight = 1.0 if len(hist) == 1 else (0.4 if len(hist) >= 3 else 0.5)
                live[cat] = round(
                    (live[cat] * (1 - update_weight))
                    + (median_val * update_weight),
                    1,
                )

                # Update skill-specific confidence
                turn_variance = abs(clamped_val - live[cat])
                cat_sigma = live_conf.get(cat, 25.0)
                new_cat_sigma = (cat_sigma * 0.7) + (0.3 * turn_variance)
                live_conf[cat] = round(
                    max(0, min(100, 100 - (1.2 * new_cat_sigma))), 1
                )

        state["live_skill_metrics"] = live
        state["live_skill_confidence"] = live_conf

    if last_focus and last_focus in state["skill_scores"]:
        # Record Score & Attempt
        state["skill_scores"][last_focus].append(last_score)
        state["skill_attempts"][last_focus] = (
            state["skill_attempts"].get(last_focus, 0) + 1
        )

        # 1. MOMENTUM TRACKING (Last 3 turns)
        all_turn_scores = []
        for s_list in state["skill_scores"].values():
            all_turn_scores.extend(s_list)

        if len(all_turn_scores) >= 3:
            recent = all_turn_scores[-3:]
            # Simple slope: (y3 - y1) / 2
            state["momentum"] = round((recent[2] - recent[0]) / 2, 1)

        # 2. STREAK & DEPTH (V2 Legacy Preserved)
        if last_score >= 70:
            state["success_streak"][last_focus] += 1
        else:
            state["success_streak"][last_focus] = 0

        current_depth = state["skill_depth"].get(last_focus, 0)
        if state["success_streak"][last_focus] >= 2 and current_depth < 2:
            state["skill_depth"][last_focus] += 1
            logger.info(
                f"[V3] Depth for '{last_focus}' ADVANCED to level {state['skill_depth'][last_focus]}"
            )

        # 4. MULTI-SIGNAL VERIFICATION
        scores = state["skill_scores"][last_focus]
        weights = [i + 1 for i in range(len(scores))]
        weighted_avg = sum(s * w for s, w in zip(scores, weights)) / sum(weights)

        if weighted_avg >= 65 and len(scores) >= 2:
            if last_focus not in state["verified_skills"]:
                state["verified_skills"].append(last_focus)
                logger.info(f"[V3] Skill '{last_focus}' VERIFIED")

    return state


def should_early_exit(state: dict) -> bool:
    """
    Check if the interview should end early.
    Triggers when: >=3 answers, weighted avg < 35, no upward trend.
    """
    all_scores = []
    for s_list in state.get("skill_scores", {}).values():
        all_scores.extend(s_list)
    if len(all_scores) < 3:
        return False

    avg = sum(all_scores) / len(all_scores)
    if avg >= 35:
        return False

    recent = all_scores[-3:]
    if recent[2] > recent[0] + 5:
        return False

    return True


# ---------------------------------------------------------------------------
# STEP 5: PROMPT INJECTION HELPERS
# ---------------------------------------------------------------------------


def build_recruiter_instructions_block(instructions: dict, state: dict) -> str:
    """
    Build the <recruiter_instructions> block to inject into the prompt.
    Omits already-fulfilled instructions to avoid repetition.
    """
    if not instructions or not instructions.get("raw"):
        return ""

    must_covered = set(state["instruction_usage"].get("must_topics_covered", []))
    remaining_must = [
        t for t in instructions.get("must_topics", []) if t not in must_covered
    ]

    parts = ["<recruiter_instructions>"]
    parts.append("⚠️ RECRUITER DEFINED: Follow these instructions when relevant.")
    parts.append(
        "Do NOT break interview coherence. Do NOT repeat fulfilled instructions."
    )

    if remaining_must:
        parts.append(f"MANDATORY TOPICS (not yet covered): {', '.join(remaining_must)}")

    for rule in instructions.get("frequency_rules", []):
        parts.append(
            f"FREQUENCY RULE: Ask about '{rule['topic']}' every {rule['every']} questions."
        )

    if instructions.get("custom_questions"):
        parts.append("CUSTOM QUESTIONS POOL (use verbatim or adapt naturally):")
        for q in instructions["custom_questions"]:
            parts.append(f"  - {q}")

    if (
        instructions.get("raw")
        and not remaining_must
        and not instructions.get("frequency_rules")
    ):
        parts.append(f"GENERAL GUIDANCE: {instructions['raw'][:500]}")

    parts.append("</recruiter_instructions>")
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# STEP 6: POST-GENERATION VALIDATION
# ---------------------------------------------------------------------------


def validate_question(
    question: str, focus: str, instructions: dict, state: dict
) -> bool:
    """
    Returns True if the generated question satisfies active instruction constraints.
    """
    if not question:
        return False

    q_lower = question.lower()
    must_covered = set(state["instruction_usage"].get("must_topics_covered", []))

    # If current focus is a must-topic, the question must mention it
    must_topics = instructions.get("must_topics", [])
    if focus in must_topics and focus not in must_covered:
        if focus.lower() not in q_lower:
            logger.warning(
                f"[VALIDATE] Must-topic '{focus}' missing from question. Retrying..."
            )
            return False

    # Check frequency rule topic is included when triggered
    q_index = state.get("question_index", 0)
    for rule in instructions.get("frequency_rules", []):
        every = rule.get("every", 99)
        topic = rule.get("topic", "")
        if every > 0 and q_index > 0 and q_index % every == 0:
            if topic.lower() not in q_lower:
                logger.warning(
                    f"[VALIDATE] Frequency topic '{topic}' missing from question. Retrying..."
                )
                return False

    return True


# ---------------------------------------------------------------------------
# STEP 7: STATE UPDATE
# ---------------------------------------------------------------------------


def update_instruction_state(state: dict, focus: str, instructions: dict) -> dict:
    """
    Mark focus as covered and update must_topics_covered.
    """
    covered = set(state.get("covered_topics", []))
    covered.add(focus)
    state["covered_topics"] = list(covered)
    state["question_index"] = state.get("question_index", 0) + 1

    if focus in instructions.get("must_topics", []):
        must_covered = set(state["instruction_usage"].get("must_topics_covered", []))
        must_covered.add(focus)
        state["instruction_usage"]["must_topics_covered"] = list(must_covered)
        logger.info(f"[STATE] Must-topic '{focus}' marked as covered.")

    return state
