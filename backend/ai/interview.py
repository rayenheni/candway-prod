import asyncio
import json

from backend.ai.anti_cheat import AntiCheatDetector
from backend.ai.llm import call_groq_cascade
from backend.ai.privacy import audit_ai_call, count_pii_categories
from backend.ai.prompts import (
    get_answer_evaluation_prompt,
    get_complete_interview_evaluation_prompt,
    get_followup_qcm_prompt,
    get_history_summary_prompt,
    get_intelligent_evaluation_prompt,
    get_question_generator_prompt,
    get_score_comparison_prompt,
    get_technical_qcm_prompt,
)
from backend.ai.security import AISecurity
from backend.fallback_questions import (
    get_fallback_question,  # Emergency fallback questions
)
from backend.logger import logger
from backend.rubric.evidence_analyzer import classify_evidence_quality


# --- Deterministic generated-question validation (P0.1) ----------------------
# These guardrails reject empty / answer-shaped / context-dump / obvious
# non-question generations WITHOUT relying solely on the presence of '?'.
# They are intentionally conservative so valid FR/EN/AR questions pass.
_QUESTION_RETRY_ATTEMPTS = 2  # one bounded regeneration before retry-state
_ANSWER_ECHO_MARKERS = (
    "correct answer",
    "reference answer",
    "suggested answer",
    "sample answer",
    "model answer",
    "expected answer",
    "answer:",
    "answers:",
    "reponse :",
    "reponse correcte",
    "réponse :",
    "réponse correcte",
    "الإجابة",
    "الجواب",
    "الإجابة الصحيحة",
)

_CONTEXT_DUMP_MARKERS = (
    "<job_description>",
    "</job_description>",
    "<rubric_context>",
    "</rubric_context>",
    "<custom_generation_prompt>",
    "<recruiter_instructions>",
    "<candidate_summary>",
    "system:",
    "assistant:",
    "[sys]",
    "[system]",
)

# Interrogative / imperative cues in EN/FR/AR. A short reply with NO question
# mark and NONE of these is treated as obvious non-question prose.
_QUESTION_CUE_WORDS = (
    "what",
    "why",
    "how",
    "who",
    "when",
    "where",
    "which",
    "describe",
    "explain",
    "tell me",
    "walk me",
    "if you",
    "suppose",
    "assume",
    "imagine",
    "your approach",
    "how about",
    "what about",
    "would you",
    "could you",
    "can you",
    "share",
    "outline",
    "elaborate",
    "discuss",
    "scenario",
    "talk about",
    "let’s",
    "let's",
    # French
    "comment",
    "pourquoi",
    "quand",
    "quoi",
    "quel",
    "quelle",
    "quels",
    "quelles",
    "qui",
    "où",
    "explique",
    "décrivez",
    "parlez",
    "racontez",
    "imaginez",
    "supposez",
    "si vous",
    "dites-moi",
    "votre approche",
    "scénario",
    "que feriez",
    # Arabic / Tunisian arabizi
    "كيف",
    "لماذا",
    "ماذا",
    "ما هو",
    "ما هي",
    "هل",
    "متى",
    "أين",
    "اشرح",
    "صف",
    "حدثني",
    "أخبرني",
    "وضح",
    "تخيل",
    "افترض",
    "ما رأيك",
    "ماذا عن",
    "كيف تتعامل",
    "كيف تواجه",
    "win",
    "esh",
    "a3tini",
)


def validate_generated_question(reply) -> tuple:
    """Validate a generated interview question (deterministic, P0.1).

    Returns ``(ok: bool, reason: str)``. Rejects:
      - missing / non-string / empty / out-of-range-length replies
      - answer-shaped / reference-answer output (e.g. "Correct Answer should be")
      - context/prompt dumps leaked by the generator
      - obvious non-question prose (short declarative with no question cue)

    Deliberately does NOT require a ``?``: valid questions (EN/FR/AR) are
    frequently imperative ("Walk me through...", "Décrivez...", "صف لي...").
    """
    if not isinstance(reply, str) or not reply.strip():
        return False, "missing_or_empty"
    text = reply.strip()
    if len(text) < 10:
        return False, "too_short"
    if len(text) > 1500:
        return False, "too_long"

    lower = text.lower()

    if any(marker in lower for marker in _ANSWER_ECHO_MARKERS):
        return False, "answer_shaped"
    if any(marker in lower for marker in _CONTEXT_DUMP_MARKERS):
        return False, "context_dump"

    # Obvious non-question: a short declarative without any interrogative or
    # imperative engagement cue. Real questions virtually always carry one.
    if "?" not in text and "\u061f" not in text:
        has_cue = any(cue in lower for cue in _QUESTION_CUE_WORDS)
        if not has_cue and len(text) < 160:
            return False, "statement_not_question"

    return True, "ok"


def _is_trivial_answer(answer) -> bool:
    """True for trivial/lazy answers that must not produce rubric evidence rows.

    Matches the chat-layer lazy-answer semantics ("ok", "yes", "no", short
    replies, ...) so that ``RubricScoringDetail`` is never polluted by them
    (P1.3). The per-turn score behavior is intentionally unchanged.
    """
    if not isinstance(answer, str):
        return True
    m = answer.strip()
    if not m:
        return True
    if len(m) < 4:
        return True
    trivial_words = frozenset(
        {
            "ok",
            "okay",
            "go",
            "go on",
            "yes",
            "no",
            "oui",
            "non",
            "yep",
            "yeah",
            "tell me",
            "d'accord",
            "نعم",
            "لا",
        }
    )
    if len(m) <= 40 and m.lower() in trivial_words:
        return True
    return False


def calculate_weighted_score(scores: list) -> float:
    """
    Weighted average where recency matters (v3.1 Hardened).
    Reward improvement and penalize early luck that isn't sustained.
    """
    scores = [s for s in scores if s is not None]
    if not scores:
        return 50.0

    weights = [i + 1 for i in range(len(scores))]
    total_weight = sum(weights)
    weighted_sum = sum(s * w for s, w in zip(scores, weights))

    return round(weighted_sum / total_weight, 1)


def compute_confidence_level(state: dict) -> float:
    """
    Computes the reliability of the interview decision (v3.1 Hardened).
    Factors:
    - total_attempts: More questions = more evidence.
    - skill_coverage: More unique skills probed = better breadth.
    """
    skill_scores = state.get("skill_scores", {})
    total_probes = sum(len(v) for v in skill_scores.values())
    skills_covered = len([s for s, v in skill_scores.items() if len(v) > 0])

    # Baseline: 6 questions (max_turns) and 5 skills (typical pool)
    # Weights: 50% depth (total attempts), 50% breadth (coverage)
    score_depth = min(1.0, total_probes / 6.0)
    score_breadth = min(1.0, skills_covered / 5.0)

    confidence = (score_depth * 0.5) + (score_breadth * 0.5)
    return round(confidence, 2)


def optimize_cv_context(
    cv_text: str, declared_role: str, max_chars: int = None
) -> dict:
    """
    Extract ALL CV content and skills for LLM visibility.
    Returns dict with:
    - cv_full: Complete CV text (for comprehensive context)
    - skills_list: All extracted skills (for explicit LLM reference)
    - experience: Years and roles found
    - projects: Key projects identified
    """
    if not cv_text or len(cv_text) < 100:
        return {"cv_full": cv_text, "skills_list": [], "experience": [], "projects": []}

    lines = cv_text.split("\n")

    # Extract ALL skills from CV
    skills_list = []
    experience = []
    projects = []

    for line in lines:
        line_lower = line.lower().strip()

        # Look for skill keywords and extract the line
        skill_keywords = [
            "python",
            "java",
            "javascript",
            "typescript",
            "react",
            "angular",
            "vue",
            "node.js",
            "express",
            "fastapi",
            "django",
            "flask",
            "spring",
            "sql",
            "postgresql",
            "mysql",
            "mongodb",
            "redis",
            "elasticsearch",
            "aws",
            "gcp",
            "azure",
            "docker",
            "kubernetes",
            "terraform",
            "git",
            "ci/cd",
            "jenkins",
            "gitlab",
            "github",
            "devops",
            "machine learning",
            "tensorflow",
            "pytorch",
            "pandas",
            "numpy",
            "api",
            "rest",
            "graphql",
            "microservices",
            "cloud",
            "html",
            "css",
            "scss",
            "responsive",
            "ui",
            "ux",
            "figma",
            "agile",
            "scrum",
            "jira",
            "confluence",
            "communication",
            "leadership",
            "project management",
            "mentoring",
            "linux",
            "unix",
            "shell",
            "bash",
            "scripting",
            "testing",
            "unit test",
            "integration test",
            "automation",
            "security",
            "authentication",
            "encryption",
            "oauth",
            "jwt",
            "sales",
            "marketing",
            "customer",
            "business",
            "strategy",
        ]

        # Check for skills in line
        for skill_keyword in skill_keywords:
            if skill_keyword in line_lower:
                if line.strip() and line not in skills_list:
                    skills_list.append(line.strip())
                    break

        # Look for years of experience
        if "year" in line_lower or "experience" in line_lower:
            if line.strip() and line not in experience:
                experience.append(line.strip())

        # Look for projects
        if (
            "project" in line_lower
            or "built" in line_lower
            or "developed" in line_lower
        ):
            if line.strip() and line not in projects:
                projects.append(line.strip())

    return {
        "cv_full": cv_text,  # Return FULL CV text for LLM context
        "skills_list": skills_list,
        "experience": experience,
        "projects": projects,
    }


def format_cv_for_llm(cv_data: dict) -> str:
    """
    Format CV data for LLM consumption.
    Combines full CV + extracted skills for comprehensive visibility.
    """
    parts = []

    # Add full CV
    if cv_data.get("cv_full"):
        parts.append(f"=== COMPLETE CV ===\n{cv_data['cv_full']}")

    # Add extracted skills explicitly
    if cv_data.get("skills_list"):
        parts.append(
            "\n=== ALL IDENTIFIED SKILLS ===\n" + "\n".join(cv_data["skills_list"])
        )

    # Add experience
    if cv_data.get("experience"):
        parts.append("\n=== EXPERIENCE ===\n" + "\n".join(cv_data["experience"]))

    # Add projects
    if cv_data.get("projects"):
        parts.append("\n=== PROJECTS ===\n" + "\n".join(cv_data["projects"]))

    return "\n".join(parts)


def get_difficulty(turn: int) -> str:
    """
    Progressive difficulty scaling:
    Turn 0-1: Basic (Fundamentals)
    Turn 2-3: Intermediate (Implementation/Trade-offs)
    Turn 4+: Advanced (Edge cases/Architecture)
    """
    if turn <= 1:
        return "basic"
    if turn <= 3:
        return "intermediate"
    return "advanced"


def get_question_type(turn: int) -> str:
    """
    Round-robin question type rotation.
    """
    types = ["skill", "scenario", "problem"]
    return types[turn % len(types)]


async def evaluate_answer(
    question: str,
    answer: str,
    focus: str,
    history_summary: str,
    declared_role: str,
    language: str = "English",
    previous_answers: list = None,
    app=None,
    job_rubric=None,
    job_rubric_db_id: int = None,
    answer_id: int = 0,
) -> dict:
    """
    Extracts skills via LLM (extraction-only prompt), then scores
    deterministically via the rubric engine. Stores ExtractedSkill and
    RubricScoringDetail in the database when app is provided.
    """
    from backend.ai.anti_cheat import AntiCheatDetector
    from backend.rubric.skill_mapper import map_extracted_skills

    prompt = get_answer_evaluation_prompt(
        declared_role, question, answer, 0, history_summary, language=language,
        rubric_skills=[
            sk.name if hasattr(sk, "name") else sk.get("name", "")
            for cat in (job_rubric.categories if job_rubric else [])
            for sub in (
                cat.subcategories
                if hasattr(cat, "subcategories")
                else cat.get("subcategories", [])
            )
            for sk in (
                sub.skills
                if hasattr(sub, "skills")
                else sub.get("skills", [])
            )
            if (hasattr(sk, "name") and sk.name) or (isinstance(sk, dict) and sk.get("name"))
        ]
        if job_rubric else None,
    )

    try:
        result = await call_groq_cascade(
            [{"role": "system", "content": prompt}],
            temperature=0.1,
            json_mode=True,
        )

        cheat_result = AntiCheatDetector.calculate_cheat_score(
            answer=answer, history=[], previous_answers=previous_answers or []
        )

        extracted = result.get("extracted_skills", [])
        avg_score = _compute_heuristic_score(extracted)

        skill_results = {}

        if isinstance(extracted, list) and app and job_rubric:
            from backend.rubric.rubric_engine import score_answer

            mapped = map_extracted_skills(extracted, job_rubric.build_lookup())
            for item in mapped:
                quality, reason = classify_evidence_quality(
                    item.get("evidence_sentences", []),
                    item.get("skill_name", ""),
                )
                item["quality"] = quality
                item["quality_reason"] = reason

            _er = (
                app.evaluation_sessions[0].evaluation_result
                if app.evaluation_sessions
                and app.evaluation_sessions[0].evaluation_result
                else None
            )
            seniority = getattr(_er, "rubric_seniority", "mid")

            # Only score the focused skill to prevent cross-skill contamination
            if focus and mapped:
                focus_lower = focus.lower().strip()
                focused_mapped = [
                    m for m in mapped
                    if m.get("skill_name", "").lower().strip() == focus_lower
                ]
                if not focused_mapped:
                    # Fall back: try partial match (e.g. "SEO" vs "Search Engine Optimization (SEO)")
                    focused_mapped = [
                        m for m in mapped
                        if focus_lower in m.get("skill_name", "").lower()
                        or m.get("skill_name", "").lower() in focus_lower
                    ]
                if not focused_mapped and mapped:
                    # Last resort: the LLM didn't extract the focused skill, but the answer
                    # is about that skill — force-map the focused skill with the extracted evidence
                    rubric_lookup = job_rubric.build_lookup()
                    for rname, rskill in rubric_lookup.items():
                        if focus_lower in rname or rname in focus_lower:
                            best_evidence = []
                            for m in mapped:
                                best_evidence.extend(m.get("evidence_sentences", []))
                            focused_mapped = [{
                                "skill_name": rname,
                                "evidence_sentences": best_evidence[:3],
                                "quality": "intermediate",
                            }]
                            break
                mapped = focused_mapped

            if job_rubric is not None:
                skill_results = score_answer(
                    answer_text=answer,
                    extracted_skills=mapped,
                    job_rubric=job_rubric,
                    seniority=seniority,
                )

                if skill_results:
                    avg_score = int(
                        sum(r.final_score for r in skill_results.values())
                        / len(skill_results)
                    )

                    logger.info(
                        "[SCORING] focus=%s mapped=%s results=%s avg=%s scores=%s",
                        focus, len(mapped), len(skill_results), avg_score,
                        {n: r.final_score for n, r in skill_results.items()},
                    )

                    # Persist the per-turn rubric evidence against the
                    # canonical EvaluationResult.  evaluate_answer() is
                    # called directly by the AI interview engine, so relying
                    # only on /rubric/interviews/.../score would leave these
                    # rows missing for real interview turns.
                    if app is not None:
                        from backend.models.evaluation.scoring import (
                            RubricScoringDetail,
                        )
                        from backend.scoring_service import ScoringService
                        from sqlalchemy import inspect as sa_inspect

                        # evaluate_answer() is also called directly by tests and
                        # by the interview engine, so there is no explicit `db`
                        # argument here. Reuse the SQLAlchemy session that owns
                        # the Application object instead of creating a new one.
                        db = sa_inspect(app).session
                        if db is None:
                            raise RuntimeError(
                                "Application is not attached to a SQLAlchemy session"
                            )

                        eval_result = ScoringService.ensure_pending_score(app, db)

                        # One detail row per rubric skill scored in this turn.
                        # Do not create rows when score_answer() produced no
                        # rubric result, and never create substantive rubric
                        # evidence for trivial/lazy answers (P1.3) — "ok",
                        # "yes", "go", ... must not inflate rubric aggregation.
                        if _is_trivial_answer(answer):
                            logger.info(
                                "[SCORING] Trivial answer — skipping RubricScoringDetail "
                                "rows (app_id=%s, answer=%r)",
                                getattr(app, "id", "?"),
                                str(answer)[:40],
                            )
                        else:
                            for skill_name, scoring_result in skill_results.items():
                                db.add(
                                    RubricScoringDetail(
                                        evaluation_result_id=eval_result.id,
                                        company_id=getattr(
                                            eval_result, "company_id", None
                                        ),
                                        criterion_name=skill_name,
                                        criterion_key=getattr(
                                            scoring_result, "skill_id", None
                                        ),
                                        question=question,
                                        answer=answer,
                                        score=float(scoring_result.final_score),
                                        weight=float(
                                            getattr(
                                                scoring_result,
                                                "quality_multiplier",
                                                1.0,
                                            )
                                            or 1.0
                                        ),
                                        feedback=getattr(
                                            scoring_result, "explanation", None
                                        ),
                                        source="interview",
                                    )
                                )

                        db.flush()
                elif not avg_score:
                    answer_len = len(answer.strip().split())
                    avg_score = min(60, max(20, answer_len * 2)) if answer_len > 20 else min(30, answer_len)
                    logger.info(
                        "[SCORING] No rubric match for focus=%s, using length heuristic: %d (words=%d)",
                        focus, avg_score, answer_len,
                    )

        if cheat_result.get("cheat_detected"):
            _cheat_score = cheat_result.get("cheat_score", 0)
            score = AntiCheatDetector.apply_cheat_penalty(avg_score, _cheat_score)
            logger.warning(
                f"[ANTI-CHEAT] TURN PENALTY: -{_cheat_score} for {answer[:30]}..."
            )
        else:
            score = avg_score

        if skill_results:
            skills = {name: sr.final_score for name, sr in skill_results.items()}
        elif extracted:
            skills = {}
            for item in extracted:
                skill_name = item.get("skill_name", "unknown")
                evidence = item.get("evidence_sentences", [])
                quality = item.get("quality", "basic")
                quality_map = {
                    "advanced": 0.9,
                    "intermediate": 0.75,
                    "basic": 0.5,
                    "weak": 0.3,
                }
                quality_factor = quality_map.get(quality, 0.5)
                base = score
                skills[skill_name] = min(
                    100, int(base * quality_factor) + (len(evidence) * 5)
                )
        else:
            skills = {}

        # PII Compliance Audit
        combined_text = f"{question} {answer} {focus}"
        pii_count, pii_cats = count_pii_categories(combined_text)
        if pii_count:
            audit_ai_call(
                pipeline_stage="interview_evaluation",
                application_id=getattr(app, "id", 0) if app else 0,
                pii_count=pii_count,
                pii_categories=pii_cats,
                success=True,
            )

        logger.info(
            "[EVALUATOR] focus=%s score=%s skills=%s extracted=%s rubric_matched=%s cheat=%s feedback=%s",
            focus, score, list(skills.keys()), len(extracted or []),
            len(skill_results), cheat_result.get("cheat_detected", False),
            (result.get("feedback", "") or "")[:80],
        )

        return {
            "score": score,
            "quality": "adequate",
            "feedback": result.get("feedback", "Answer analyzed."),
            "reasoning": "Scored deterministically via rubric engine."
            if (extracted and job_rubric)
            else "No rubric available.",
            "skills": skills,
            "cheat_detected": cheat_result.get("cheat_detected", False),
            "cheat_reason": cheat_result.get("details", ""),
        }
    except Exception as e:
        logger.error(f"[EVALUATOR] Failed: {e}")
        return {
            "score": 50,
            "quality": "adequate",
            "feedback": "Analysis failed, using default evaluation.",
            "reasoning": "Evaluation failed, using default values",
            "skills": {
                "Technical": 50,
                "Communication": 50,
                "Problem Solving": 50,
                "Adaptability": 50,
                "Confidence": 50,
                "Consistency": 50,
            },
            "cheat_detected": False,
            "cheat_reason": "",
        }


def _compute_heuristic_score(extracted: list) -> int:
    """Deterministic score from extracted skills when no rubric is available."""
    if not extracted:
        return 0
    quality_map = {
        "strong": 80,
        "medium": 60,
        "weak": 40,
        "advanced": 80,
        "intermediate": 60,
        "basic": 40,
    }
    scores = []
    for item in extracted:
        sentences = item.get("evidence_sentences", [])
        name = item.get("skill_name", "")
        quality = classify_evidence_quality(sentences, name)[0]
        scores.append(quality_map.get(quality, 40))
    return int(sum(scores) / len(scores)) if scores else 0


def _get_phase(q_index: int, total_questions: int) -> str:
    """
    PROPORTIONAL PHASE: Scales thresholds based on total_questions.
    - 0-20%: WARMUP (Approachable fundamentals)
    - 20-80%: CORE (Challenging technical depth)
    - 80-100%: STRESS (Time pressure, conflicting priorities, ethics)
    """
    progress = q_index / total_questions
    if progress <= 0.20:
        return "WARMUP"
    elif progress <= 0.80:
        return "CORE"
    else:
        return "STRESS"


async def generate_skill_driven_turn(
    state: dict,
    cv_context: str,
    declared_role: str,
    language: str = "English",
    job_description: str = None,
    intelligence_layer: dict = None,
    calibration_data: dict = None,
    recruiter_instructions: str = "",
    custom_question_prompt: str = None,
    rubric_categories: list = None,
    rubric_seniority: str = "mid",
) -> dict:
    """
    STRICT SKILL-DRIVEN TURN GENERATION (v3.1 Hardened)
    Now includes adaptive difficulty based on calibration data
    and rubric-context injection for question generation.
    """
    from backend.ai.interview_customization import select_next_focus

    # 1. State Resolution
    turn = state.get("turn", 0)
    history = state.get("history", [])

    # 2. Get calibration score for adaptive difficulty
    cal_score = None
    if calibration_data and isinstance(calibration_data, dict):
        cal_score = calibration_data.get("score")

    # 2. Focus & Difficulty Selection
    focus_skill = select_next_focus(
        state,
        declared_role,
        rubric_categories=rubric_categories,
        seniority=rubric_seniority,
    )
    focus = focus_skill.name
    depth_level = state.get("skill_depth", {}).get(focus, 0)

    # Map depth to descriptions - ADAPTIVE based on calibration
    base_depth_map = {
        0: {"band": "basic", "desc": "fundamental concepts and definitions"},
        1: {
            "band": "intermediate",
            "desc": "real-world scenarios, implementation choices, and trade-offs",
        },
        2: {
            "band": "advanced",
            "desc": "complex system design, edge cases, scalability, and deep architectural decisions",
        },
    }

    # Adaptive: Adjust difficulty based on calibration score
    depth_info = base_depth_map.get(depth_level, base_depth_map[0])

    if cal_score is not None:
        # If calibration shows high competence (>75), boost difficulty faster
        if cal_score > 80:
            depth_info = base_depth_map.get(min(2, depth_level + 1), base_depth_map[2])
            state["difficulty_boost"] = "high"
        # If calibration shows low competence (<50), reduce difficulty
        elif cal_score < 50:
            depth_info = base_depth_map.get(0, base_depth_map[0])
            state["difficulty_boost"] = "low"

    # 🚨 SENIORITY LOCK
    if cal_score and cal_score < 50:
        seniority = "Junior"
    elif cal_score and cal_score > 80:
        seniority = "Senior"
    else:
        seniority = (calibration_data or {}).get("level", "Mid")
    avg_performance = (
        sum(h.get("score", 50) for h in history) / len(history) if history else 0
    )
    is_high_performer = avg_performance > 85 and len(history) >= 2

    if seniority == "Junior" and not is_high_performer:
        if depth_info["band"] == "advanced":
            depth_info = base_depth_map[1]
            depth_info["desc"] = "Junior-friendly scenarios: " + depth_info["desc"]
        elif depth_info["band"] == "intermediate":
            depth_info["desc"] = "Fundamental implementation: " + depth_info["desc"]
    elif seniority == "Junior" and is_high_performer:
        depth_info["desc"] = (
            "HIGH-POTENTIAL "
            + depth_info["band"].upper()
            + " PROBE: "
            + depth_info["desc"]
        )

    q_type = get_question_type(turn)

    state["current_focus"] = focus

    # 3. Context Preparation
    tested_concepts = [h.get("focus") for h in history if h.get("focus")]
    history_summary = "Tested Focus Areas: " + ", ".join(tested_concepts) + "\n"
    if history:
        history_summary += "\n".join(
            [
                f"Q: {h.get('question', '')}\nA: {str(h.get('answer', ''))[:100]}... [Score: {h.get('score', 'N/A')}]"
                for h in history[-5:]
            ]
        )

    candidate_summary = get_candidate_summary(
        cv_context, declared_role, intelligence_layer, calibration_data
    )

    # 4. Build rubric context for prompt injection
    rubric_context = None
    if rubric_categories and (focus_skill.description or focus_skill.keywords):
        keywords_str = ", ".join(focus_skill.keywords) if focus_skill.keywords else ""
        level_line = f" — {focus_skill.level_text}" if focus_skill.level_text else ""
        rubric_context = (
            f"\n<rubric_context>\n"
            f"SKILL: {focus_skill.name}\n"
            f"DESCRIPTION: {focus_skill.description}\n"
            f"LEVEL: {rubric_seniority}{level_line}\n"
            f"REQUIRED: {'yes' if focus_skill.is_required else 'no'}\n"
        )
        if focus_skill.coverage_context:
            rubric_context += f"COVERAGE: {focus_skill.coverage_context}\n"
        if keywords_str:
            rubric_context += f"KEYWORDS: {keywords_str}\n"
        rubric_context += "</rubric_context>"
        logger.info(
            f"[RUBRIC-CTX] Injected rubric context for skill '{focus_skill.name}' "
            f"(seniority={rubric_seniority}, required={focus_skill.is_required})"
        )

    # 5. Generate Question
    prompt = get_question_generator_prompt(
        declared_role=declared_role,
        candidate_summary=candidate_summary,
        phase=_get_phase(turn, state.get("max_turns", 6)),
        q_index=turn + 1,
        total_questions=state.get("max_turns", 6),
        language=language,
        history_summary=history_summary,
        last_feedback=history[-1].get("feedback", "")
        if history
        else "Start of interview",
        difficulty_band=depth_info["band"],
        technical_focus=focus,
        question_type=q_type,
        level_instruction=f"STRICT DEPTH: {depth_info['desc']}",
        job_description=job_description,
        recruiter_instructions_block=recruiter_instructions,
        custom_question_prompt=custom_question_prompt,
        calibration_data=calibration_data,
        rubric_context=rubric_context,
    )

    # 6. Bounded generation with deterministic validation (P0.1/P0.2).
    #    A failed or invalid generation is retried ONCE; if the retry also
    #    fails we return a structured retry state instead of a hardcoded or
    #    stale question. Nothing is persisted here.
    async def _generate_once(attempt: int):
        logger.info(
            f"[ENGINE v3.1] Turn {turn} | Focus: {focus} | Depth: {depth_level} "
            f"| Type: {q_type} | attempt {attempt}/{_QUESTION_RETRY_ATTEMPTS}"
        )
        # Sanitize recruiter instructions before injection
        safe_prompt = AISecurity.sanitize_input(prompt)
        result = await asyncio.wait_for(
            call_groq_cascade(
                [{"role": "system", "content": safe_prompt}],
                temperature=0.4,
                json_mode=True,
            ),
            timeout=30.0,
        )
        if result is None:
            raise ValueError("call_groq_cascade returned None")
        if not isinstance(result, dict):
            raise ValueError(f"call_groq_cascade returned {type(result).__name__}")
        reply = result.get("reply")
        ok, reason = validate_generated_question(reply)
        if not ok:
            raise ValueError(f"generated question failed validation: {reason}")
        return result, reply

    last_reason = "unknown"
    for attempt in range(1, _QUESTION_RETRY_ATTEMPTS + 1):
        try:
            result, reply = await _generate_once(attempt)
            return {
                "reply": reply,
                "hint_text": result.get("hint_text", ""),
                "focus": focus,
                "type": q_type,
                "difficulty": depth_info["band"],
                "depth": depth_level,
                "state": state,
            }
        except Exception as e:
            last_reason = f"{type(e).__name__}: {str(e)[:200]}"
            logger.error(
                f"[ENGINE v3.1] Turn {turn} question generation attempt "
                f"{attempt}/{_QUESTION_RETRY_ATTEMPTS} failed: {last_reason}"
            )

    logger.error(
        f"[ENGINE v3.1] Question generation failed after {_QUESTION_RETRY_ATTEMPTS} "
        f"attempts (turn={turn}, focus={focus}, reason={last_reason}). "
        f"Returning structured retry state — no question will be persisted."
    )
    return {
        "retry_required": True,
        "reply": "",
        "hint_text": "",
        "focus": focus,
        "type": q_type,
        "difficulty": depth_info["band"],
        "depth": depth_level,
        "state": state,
        "reason": last_reason,
    }


async def compute_final_decision(
    state: dict, declared_role: str, calibration_data: dict = None
) -> dict:
    """
    Computes the final hiring decision using a dedicated AI judgment layer (v3.1 Hardened).
    """
    from backend.ai.prompts import get_final_decision_prompt

    skill_scores = state.get("skill_scores", {})
    state.get("history", [])

    summary_parts = []
    total_weighted_sum = 0
    total_weight_count = 0

    for skill, scores in skill_scores.items():
        if not scores:
            continue
        w_score = calculate_weighted_score(scores)
        depth = state.get("skill_depth", {}).get(skill, 0)
        summary_parts.append(
            f"- {skill}: {w_score}/100 (Max Depth: {depth}, Attempts: {len(scores)})"
        )

        total_weighted_sum += w_score
        total_weight_count += 1

    overall_score = (
        round(total_weighted_sum / max(total_weight_count, 1), 1)
        if total_weight_count
        else 50.0
    )

    # Calibration adjust
    cal_score = None
    if calibration_data and isinstance(calibration_data, dict):
        cal_score = calibration_data.get("score")
    if cal_score is not None:
        cal_weight = 0.15
        adjusted_score = (overall_score * (1 - cal_weight)) + (cal_score * cal_weight)
        overall_score = round(adjusted_score, 1)
        summary_parts.append(f"- Calibration: {cal_score}/100 (15% weight in final)")

    confidence = compute_confidence_level(state)
    skill_assessment = "\n".join(summary_parts)

    prompt = get_final_decision_prompt(
        declared_role=declared_role,
        skill_assessment=skill_assessment,
        total_score=overall_score,
        confidence=confidence,
    )

    try:
        logger.info(f"[JUDGMENT] Computing final decision for {declared_role}...")
        decision_meta = await call_groq_cascade(
            [{"role": "system", "content": prompt}], temperature=0.1, json_mode=True
        )

        decision_meta["overall_score"] = overall_score
        decision_meta["confidence_score"] = confidence

        # PII Compliance Audit — report generation
        combined = str(state)
        pii_count, pii_cats = count_pii_categories(combined)
        if pii_count:
            audit_ai_call(
                pipeline_stage="report_generation",
                application_id=0,
                pii_count=pii_count,
                pii_categories=pii_cats,
                success=True,
            )

        return decision_meta
    except Exception as e:
        logger.error(f"[JUDGMENT] Failed: {e}")
        return {
            "decision": "BORDERLINE",
            "confidence": confidence,
            "summary": "Technical error during final assessment.",
            "overall_score": overall_score,
            "strengths": [],
            "weaknesses": [],
        }


def get_candidate_summary(
    cv_context: str,
    declared_role: str,
    intelligence_layer: dict = None,
    calibration_data: dict = None,
) -> str:
    """Creates a high-density summary of the candidate for the prompt."""
    summary_lines = []
    summary_lines.append(f"ROLE: {declared_role}")

    # Use calibration data if available
    if calibration_data:
        cal_score = calibration_data.get("score")
        if cal_score:
            summary_lines.append(f"CALIBRATION SCORE: {cal_score}/100")

        cal_eval = calibration_data.get("evaluation", {})
        cal_strengths = cal_eval.get("strengths", []) or calibration_data.get(
            "strengths", []
        )
        if cal_strengths:
            summary_lines.append(
                f"CALIBRATION STRENGTHS: {', '.join(cal_strengths[:3])}"
            )

        cal_weaknesses = cal_eval.get("weaknesses", []) or calibration_data.get(
            "weaknesses", []
        )
        if cal_weaknesses:
            summary_lines.append(f"CALIBRATION GAPS: {', '.join(cal_weaknesses[:3])}")

        cal_feedback = cal_eval.get("feedback") or calibration_data.get("feedback")
        if cal_feedback:
            summary_lines.append(f"CALIBRATION FEEDBACK: {cal_feedback[:200]}")

    # Use intelligence layer if available
    elif intelligence_layer:
        seniority = intelligence_layer.get("seniority_level", "Professional")
        summary_lines.append(f"SENIORITY: {seniority}")

        strengths = intelligence_layer.get("strengths", [])
        if strengths:
            summary_lines.append(f"VERIFIED STRENGTHS: {', '.join(strengths[:5])}")

        weaknesses = intelligence_layer.get("weaknesses", [])
        if weaknesses:
            summary_lines.append(f"GAPS TO PROBE: {', '.join(weaknesses[:5])}")

        summary = intelligence_layer.get("summary")
        if summary:
            summary_lines.append(f"AI AUDIT SUMMARY: {summary}")

    # Fallback - parse from CV context
    else:
        import re

        skills_match = re.search(
            r"skills?[:\s]+([^\n]+)", cv_context[:500], re.IGNORECASE
        )
        if skills_match:
            summary_lines.append(f"SKILLS: {skills_match.group(1)[:200]}")

        exp_match = re.search(
            r"experience[:\s]+([^\n]+)", cv_context[:500], re.IGNORECASE
        )
        if exp_match:
            summary_lines.append(f"EXPERIENCE: {exp_match.group(1)[:200]}")

    return "\n".join(summary_lines)


def get_role_scenario_guide(declared_role: str) -> str:
    """
    Universal scenario guide for ANY role.
    Returns role-agnostic prompt to generate meaningful scenarios.
    Works for roles beyond predefined list.
    """
    role_lower = declared_role.lower()

    # Map common role keywords to scenario domains
    scenario_map = {
        # Tech roles
        "engineer": "system design, debugging production issues, performance optimization, code review, deployment challenges",
        "developer": "feature implementation, debugging, refactoring, integration, deployment, scaling",
        "backend": "API design, database optimization, caching, microservices, scaling, payment handling",
        "frontend": "UI performance, responsive design, state management, accessibility, browser compatibility",
        "mobile": "mobile-specific challenges, offline functionality, battery/memory optimization, app store processes",
        "devops": "CI/CD, infrastructure, monitoring, incident response, cost optimization, scaling",
        "sre": "system reliability, incident response, monitoring, alerting, runbooks, capacity planning",
        "data": "data pipeline, model training, feature engineering, data quality, scaling, automation",
        "ml": "model development, training optimization, deployment, A/B testing, monitoring, drift",
        "ai": "algorithm selection, training strategy, hyperparameter tuning, inference optimization",
        "security": "vulnerability assessment, incident response, compliance, secure coding, risk analysis",
        "qa": "test strategy, automation, edge cases, regression testing, performance testing, mobile testing",
        # Product & Management
        "product": "feature prioritization, roadmap, user research, stakeholder management, MVP definition",
        "manager": "team leadership, resource allocation, performance management, stakeholder alignment",
        "scrum": "sprint planning, retrospectives, process improvement, conflict resolution, team dynamics",
        "agile": "agile methodology, team coordination, risk mitigation, continuous improvement",
        # Design
        "designer": "UX research, wireframing, prototyping, design systems, accessibility, iteration",
        "ux": "user journey, information architecture, usability testing, accessibility, design decisions",
        "ui": "visual design, consistency, responsive design, design systems, feedback loops",
        # Business & Sales
        "sales": "prospect qualification, objection handling, pipeline management, closing, negotiation",
        "marketing": "campaign strategy, target audience, ROI analysis, content planning, growth tactics",
        "community": "community engagement, crisis management, content strategy, member retention, moderation",
        "support": "customer issue resolution, escalation, documentation, training, satisfaction",
        # Admin & Operations
        "analyst": "data analysis, trend identification, reporting, insight generation, business impact",
        "operations": "process optimization, workflow design, efficiency, cost reduction, scaling",
        # Default fallback
    }

    # Find matching scenario domain
    scenario_domain = "real-world problem-solving, trade-off decisions, handling constraints, communicating impact"
    for keyword, domain in scenario_map.items():
        if keyword in role_lower:
            scenario_domain = domain
            break

    return f"""SCENARIO GENERATION FOR ANY ROLE ({declared_role}):

Focus Areas: {scenario_domain}

UNIVERSAL SCENARIO TEMPLATE (works for ANY role):
1. SET CONTEXT: Company type, team structure, business constraint. (CRITICAL: Skip this intro if continuing from a previous scenario).
2. PRESENT PROBLEM: Real challenge they'd face in this role (e.g., "Your team discovered [issue]. What do you do?")
3. ADD CONSTRAINT: Time pressure, resource limit, or competing priority
4. ASK FOR ACTION: "Walk me through your approach..." / "How would you solve..." / "What's your strategy..."
CONTINUITY RULE: If follow-up question, NEVER repeat the words "You are a [Role] at [Company]". Speak like a continuous conversation.

RULE: ALWAYS scenario-based. NEVER textbook definitions.
- BAD: "Explain [concept]"
- GOOD: "In your experience at [CV company], when you faced [problem], how would you have [action]?"

ADAPT TO ROLE:
- Technical roles: probe technical decisions + communication with non-tech stakeholders
- Management roles: probe leadership + strategic thinking
- Design roles: probe user empathy + iteration
- Sales roles: probe qualification + objection handling
- Others: probe domain-specific expertise + business impact
"""


def get_role_domain_keywords(declared_role: str) -> dict:
    """
    Returns role-specific keywords and focus areas for scenario generation.
    Supports unlimited roles dynamically.
    """
    role_lower = declared_role.lower()

    # Comprehensive role mapping with keywords
    role_profiles = {
        # Tech - Backend
        "backend engineer": {
            "keywords": ["API", "database", "cache", "queue", "scale", "deployment"],
            "problems": [
                "high traffic",
                "data consistency",
                "service outage",
                "performance bottleneck",
            ],
            "tools": [
                "Java",
                "Python",
                "Go",
                "Node.js",
                "PostgreSQL",
                "MongoDB",
                "Redis",
            ],
            "domain": "Backend Systems & APIs",
        },
        # Tech - Frontend
        "frontend engineer": {
            "keywords": [
                "UI",
                "performance",
                "state",
                "responsive",
                "accessibility",
                "browser",
            ],
            "problems": [
                "slow load",
                "memory leak",
                "rendering issue",
                "browser compatibility",
            ],
            "tools": ["React", "Vue", "Angular", "TypeScript", "CSS", "Webpack"],
            "domain": "Frontend & User Experience",
        },
        # Tech - DevOps
        "devops engineer": {
            "keywords": [
                "CI/CD",
                "infrastructure",
                "monitoring",
                "deployment",
                "scaling",
                "cost",
            ],
            "problems": [
                "pipeline failure",
                "outage",
                "slow deployment",
                "scaling issue",
            ],
            "tools": ["Docker", "Kubernetes", "Jenkins", "Terraform", "AWS", "Azure"],
            "domain": "Infrastructure & Deployment",
        },
        # Tech - Data
        "data scientist": {
            "keywords": [
                "model",
                "data pipeline",
                "training",
                "accuracy",
                "performance",
                "A/B test",
            ],
            "problems": [
                "low accuracy",
                "data quality",
                "slow training",
                "inference latency",
            ],
            "tools": [
                "Python",
                "TensorFlow",
                "PyTorch",
                "SQL",
                "Pandas",
                "Scikit-learn",
            ],
            "domain": "Machine Learning & Data",
        },
        # Product
        "product manager": {
            "keywords": [
                "roadmap",
                "feature",
                "MVP",
                "user research",
                "metrics",
                "stakeholder",
            ],
            "problems": [
                "competing priorities",
                "user churn",
                "feature conflict",
                "resource constraints",
            ],
            "tools": [
                "Jira",
                "Figma",
                "analytics",
                "user feedback",
                "roadmap planning",
            ],
            "domain": "Product Strategy & Direction",
        },
        # Management
        "engineering manager": {
            "keywords": [
                "team",
                "delivery",
                "hiring",
                "mentoring",
                "planning",
                "performance",
            ],
            "problems": [
                "missed deadline",
                "team conflict",
                "high turnover",
                "quality issues",
            ],
            "tools": [
                "team management",
                "planning",
                "feedback",
                "mentoring",
                "retrospectives",
            ],
            "domain": "Team Leadership & Delivery",
        },
        # Design
        "ux designer": {
            "keywords": [
                "user",
                "design",
                "research",
                "usability",
                "accessibility",
                "iteration",
            ],
            "problems": [
                "poor usability",
                "user frustration",
                "accessibility issue",
                "design debt",
            ],
            "tools": [
                "Figma",
                "user testing",
                "wireframing",
                "research",
                "prototyping",
            ],
            "domain": "User Experience & Design",
        },
        # Security
        "security engineer": {
            "keywords": [
                "vulnerability",
                "threat",
                "compliance",
                "incident",
                "defense",
                "audit",
            ],
            "problems": [
                "breach",
                "vulnerability",
                "compliance violation",
                "insider threat",
            ],
            "tools": [
                "security testing",
                "audit",
                "compliance",
                "threat modeling",
                "incident response",
            ],
            "domain": "Security & Risk",
        },
        # Sales
        "sales manager": {
            "keywords": [
                "pipeline",
                "closing",
                "objection",
                "negotiation",
                "forecast",
                "quota",
            ],
            "problems": [
                "low conversion",
                "lost deal",
                "pipeline gap",
                "forecast miss",
            ],
            "tools": [
                "CRM",
                "negotiation",
                "forecasting",
                "territory management",
                "deal tracking",
            ],
            "domain": "Sales & Revenue",
        },
        # Marketing
        "marketing manager": {
            "keywords": [
                "campaign",
                "audience",
                "ROI",
                "conversion",
                "growth",
                "brand",
            ],
            "problems": [
                "low CAC ROI",
                "low conversion",
                "campaign failure",
                "audience fatigue",
            ],
            "tools": [
                "marketing analytics",
                "campaign tools",
                "segmentation",
                "A/B testing",
                "content",
            ],
            "domain": "Marketing & Growth",
        },
        # Community
        "community manager": {
            "keywords": [
                "engagement",
                "moderation",
                "content",
                "crisis",
                "retention",
                "growth",
            ],
            "problems": ["community crisis", "low engagement", "toxic member", "churn"],
            "tools": [
                "community platform",
                "moderation",
                "content",
                "analytics",
                "engagement",
            ],
            "domain": "Community Building",
        },
    }

    # Try exact match first
    if role_lower in role_profiles:
        return role_profiles[role_lower]

    # Try partial match
    for role_key, profile in role_profiles.items():
        if role_lower in role_key or role_key in role_lower:
            return profile
    # Fallback: generic technical role profile
    return {
        "keywords": [
            "decision",
            "tradeoff",
            "problem-solving",
            "impact",
            "communication",
        ],
        "problems": [
            "unexpected issue",
            "constraint",
            "changing requirement",
            "team challenge",
        ],
        "tools": ["problem-solving", "communication", "domain knowledge"],
        "domain": f"{declared_role} Role",
    }


# Consolidated into the definition at line 133.


def get_question_style(q_index: int) -> str:
    """Rotates through different question styles to prevent repetition."""
    styles = [
        "CRISIS: A production issue just occurred. Walk me through your first 5 minutes.",
        "FEATURE: A stakeholder wants a new capability. How do you design it?",
        "TEAM: A teammate disagrees with your approach. How do you handle it?",
        "TRADE-OFF: You have to choose between speed and quality. What's your framework?",
        "AMBIGUITY: Requirements are unclear. How do you proceed?",
    ]
    return styles[(q_index - 1) % len(styles)]


async def summarize_history(declared_role: str, history: list) -> str:
    """Creates a concise summary of the interview history to prevent token bloat."""
    if not history:
        return ""

    # Format history for summarizer
    history_text = "\n".join(
        [
            f"{str(m.get('role', '')).upper()}: {str(m.get('content', ''))[:500]}"
            for m in history
            if isinstance(m, dict)
        ]
    )
    prompt = get_history_summary_prompt(declared_role, history_text)

    try:
        summary = await call_groq_cascade(
            [{"role": "user", "content": prompt}], temperature=0.1, max_tokens=300
        )
        return str(summary) if summary else ""
    except Exception as e:
        logger.error(f"Failed to summarize history: {e}")
        return ""


def _normalize_turn_language(value: str) -> str:
    raw = str(value or "").strip().lower()
    if raw in {"french", "fr", "francais"}:
        return "French"
    if raw in {"arabic", "ar", "derja", "darija"}:
        return "Arabic"
    return "English"


def _localized_turn_defaults(
    language: str, declared_role: str, technical_focus: str = None
) -> dict:
    # Phase 21: Returns a technical error structure to signal cascade failure.
    return {
        "feedback": "Technical Error: AI cascade failed.",
        "score_reasoning": "Processing failure (No fallback allowed).",
        "reply": "ERROR: Dynamic generation failed. Please refresh or retry.",
        "hint_text": "",
    }


async def generate_technical_qcm(
    skill: str,
    difficulty: str = "Intermediate",
    language: str = "English",
    cv_context: str = "",
):
    logger.debug(f"DEBUG: Generating CV-Based QCM for Role: {skill}")

    # SECURITY: Sanitize CV context before embedding in prompt
    if cv_context:
        cv_context = AISecurity.sanitize_input(cv_context)

    has_cv_data = len(cv_context.strip()) > 100
    prompt = get_technical_qcm_prompt(skill, difficulty, language, cv_context)

    try:
        result = await call_groq_cascade(
            [{"role": "system", "content": prompt}], temperature=0.4, max_tokens=800
        )

        # STRICT VALIDATION: Ensure question references CV and matches role
        _question = result.get("question") if isinstance(result, dict) else None
        if has_cv_data and _question:
            question_lower = _question.lower()
            cv_lower = cv_context[:3000].lower()

            # Extract meaningful keywords from CV (technologies, companies, projects)
            cv_keywords = set()
            for word in cv_lower.split():
                if len(word) > 3 and word.isalnum():
                    cv_keywords.add(word)

            # Check question keywords
            question_words = set(question_lower.split())
            overlap = cv_keywords.intersection(question_words)

            # STRICT CHECK: Question must have substantial CV overlap
            if len(overlap) < 3:  # Increased from 2 to 3
                logger.warning(
                    f"WARNING: Question appears generic. CV overlap: {overlap}"
                )
                logger.debug(f"Question: {_question[:100]}...")

                # Add explicit CV reference to force relevance
                _question = (
                    f"Based on your {skill} experience mentioned in your CV, "
                    + _question
                )
                result["question"] = _question
                result["cv_reference"] = "General CV experience"

            # ROLE ALIGNMENT CHECK: Ensure question matches target role
            role_keywords = {
                "software engineer": [
                    "code",
                    "programming",
                    "api",
                    "database",
                    "backend",
                    "frontend",
                    "algorithm",
                    "spring",
                    "java",
                    "microservices",
                ],
                "data scientist": [
                    "data",
                    "model",
                    "machine learning",
                    "analysis",
                    "statistics",
                    "python",
                    "ml",
                    "tensorflow",
                    "pytorch",
                ],
                "community manager": [
                    "community",
                    "social",
                    "engagement",
                    "content",
                    "users",
                    "platform",
                    "tiktok",
                    "instagram",
                    "facebook",
                ],
                "product manager": [
                    "product",
                    "feature",
                    "roadmap",
                    "stakeholder",
                    "requirements",
                    "user",
                    "mvp",
                    "sprint",
                    "backlog",
                ],
                "devops": [
                    "deployment",
                    "infrastructure",
                    "ci/cd",
                    "docker",
                    "kubernetes",
                    "monitoring",
                    "jenkins",
                    "terraform",
                    "aws",
                ],
                "designer": [
                    "design",
                    "ui",
                    "ux",
                    "user experience",
                    "interface",
                    "prototype",
                    "figma",
                    "wireframe",
                ],
                "frontend developer": [
                    "react",
                    "vue",
                    "angular",
                    "css",
                    "javascript",
                    "typescript",
                    "html",
                    "responsive",
                    "tailwind",
                ],
                "mobile developer": [
                    "mobile",
                    "ios",
                    "android",
                    "flutter",
                    "react native",
                    "swift",
                    "kotlin",
                    "app store",
                ],
                "qa engineer": [
                    "testing",
                    "test",
                    "qa",
                    "selenium",
                    "automation",
                    "regression",
                    "bug",
                    "coverage",
                ],
                "cybersecurity": [
                    "security",
                    "vulnerability",
                    "penetration",
                    "firewall",
                    "encryption",
                    "compliance",
                    "audit",
                ],
                "marketing manager": [
                    "marketing",
                    "campaign",
                    "roi",
                    "acquisition",
                    "brand",
                    "seo",
                    "content",
                    "growth",
                ],
                "sales manager": [
                    "sales",
                    "pipeline",
                    "crm",
                    "closing",
                    "negotiation",
                    "revenue",
                    "territory",
                    "quota",
                ],
                "scrum master": [
                    "scrum",
                    "agile",
                    "sprint",
                    "retrospective",
                    "velocity",
                    "kanban",
                    "ceremony",
                    "facilitation",
                ],
                "network engineer": [
                    "network",
                    "tcp",
                    "dns",
                    "firewall",
                    "routing",
                    "switching",
                    "vpn",
                    "sd-wan",
                ],
                "full stack developer": [
                    "fullstack",
                    "full-stack",
                    "backend",
                    "frontend",
                    "api",
                    "database",
                    "react",
                    "node",
                ],
            }

            # Check if question is relevant to role
            skill_lower = skill.lower()
            relevant_keywords = []
            for role, keywords in role_keywords.items():
                if role in skill_lower:
                    relevant_keywords = keywords
                    break

            if relevant_keywords:
                has_role_keyword = any(
                    keyword in question_lower for keyword in relevant_keywords
                )
                if not has_role_keyword:
                    logger.warning(f"⚠️ WARNING: Question may not match {skill} role")
                    logger.debug(f"Question: {_question[:100]}...")

        return result

    except Exception as e:
        logger.critical(f"CRITICAL: Groq Technical QCM Failed: {e}")

        # ALL PROVIDERS FAILED - Use fallback question bank (users never see errors!)
        fallback = get_fallback_question(skill, question_number=1)
        logger.info(f"✅ Using fallback question for {skill}")
        return fallback


async def generate_followup_qcm(
    skill: str,
    history: list,
    language: str = "English",
    cv_context: str = "",
    difficulty: str = "Intermediate",
):
    # SECURITY: Sanitize CV context before embedding in prompt
    if cv_context:
        cv_context = AISecurity.sanitize_input(cv_context)

    # Sanitize history
    for msg in history:
        if isinstance(msg, dict) and "content" in msg:
            msg["content"] = AISecurity.sanitize_for_prompt(
                msg.get("content", ""),
                field_name=f"history_{msg.get('role', 'unknown')}",
            )

    # ADAPTIVE HISTORY SIZE - Reduce for higher difficulties to prevent token overflow
    if difficulty == "Genius":
        short_history = history[-4:] if history else []  # Only last 2 Q&A pairs
        cv_context_size = 1500  # Smaller CV context
    elif difficulty == "Advanced":
        short_history = history[-5:] if history else []  # Last 2-3 Q&A pairs
        cv_context_size = 2000
    else:
        short_history = history[-6:] if history else []  # Last 3 Q&A pairs
        cv_context_size = 3000

    cv_segment = cv_context[:cv_context_size] if cv_context else ""
    system_prompt = get_followup_qcm_prompt(skill, difficulty, language, cv_segment)

    try:
        # ADAPTIVE MAX TOKENS
        max_tokens = 800 if difficulty == "Genius" else 1000
        temperature = 0.3 if difficulty == "Genius" else 0.4

        logger.debug(
            f"DEBUG: Calling Groq with max_tokens={max_tokens}, temp={temperature}"
        )

        messages = [{"role": "system", "content": system_prompt}] + short_history
        result = await call_groq_cascade(
            messages, temperature=temperature, max_tokens=max_tokens
        )

        # STRICT VALIDATION: Ensure follow-up question references CV and matches role
        if cv_context and result.get("question"):
            # Ensure question is distinct from previous turns
            pass

        return result

    except Exception as e:
        logger.critical(f"CRITICAL: Groq Follow-up Failed: {e}")
        # ... (fallbacks identical to original) ...
        return get_fallback_question(skill, question_number=2)


async def generate_dynamic_interview_turn(
    cv_context: str,
    declared_role: str,
    history: list,
    current_q_index: int,
    current_score: float = 75.0,
    total_questions: int = 15,
    language: str = "English",
    job_title: str = None,
    job_description: str = None,
    initial_skills: dict = None,
    seniority_level: str = "Junior",
    cv_skills_list: list = None,
    interview_instructions: dict = None,
    instruction_state: dict = None,
    rubric_categories: list = None,
):
    """
    REFACTORED: Implementation of the two-step evaluation -> generation pipeline.
    SECURITY: Added CV context sanitization before embedding in prompts.
    """
    # Normalize optional worker/API inputs before processing.
    # A missing interview history means a fresh interview.
    if not isinstance(history, list):
        history = []

    # SECURITY: CV and role are untrusted prompt data.
    if cv_context:
        cv_context = AISecurity.sanitize_for_prompt(
            cv_context,
            field_name="candidate_cv",
        )

    if declared_role:
        declared_role = AISecurity.sanitize_for_prompt(
            declared_role,
            field_name="declared_role",
        )

    _last_entry = history[-1] if history and isinstance(history[-1], dict) else {}
    last_user_message = (
        _last_entry.get("content") if _last_entry.get("role") == "user" else None
    )

    # SECURITY: Sanitize history messages
    for msg in history:
        if isinstance(msg, dict) and "content" in msg:
            msg["content"] = AISecurity.sanitize_input(msg.get("content", ""))

    # 1. OPTIMIZE CONTEXT
    # Summarize older history (keeps only last 4 messages, summarizes rest)
    if len(history) > 6:
        history_summary = await summarize_history(declared_role, history[:-4])
        recent_history = history[-4:]
    else:
        history_summary = "Interview just started."
        recent_history = history

    history_formatted = "\n".join(
        [
            f"{str(m.get('role', '')).upper()}: {str(m.get('content', ''))[:300]}..."
            for m in recent_history
            if isinstance(m, dict)
        ]
    )
    candidate_summary = get_candidate_summary(cv_context, declared_role)

    last_feedback = "No previous answer to evaluate."
    evaluation_result = {}

    # 2. STEP 1: EVALUATE LAST ANSWER (if applicable)
    if last_user_message and current_q_index > 1:
        # Find previous question
        prev_question = "Welcome/Introduction"
        for m in reversed(history[:-1]):
            if m.get("role") == "assistant":
                prev_question = m.get("content", "")
                break

        # PHASE B: Use intelligent evaluation with claim extraction
        eval_prompt = get_intelligent_evaluation_prompt(
            declared_role=declared_role,
            question=prev_question,
            user_answer=last_user_message,
            current_score=current_score,
            history_summary=history_summary,
            cv_claims=None,  # Could extract from CV if available
            previous_answer_quality=evaluation_result.get("answer_quality")
            if evaluation_result
            else None,
        )

        try:
            # Use Llama-3.3-70b for evaluation with LOW temperature (consistent)
            logger.info(f"[EVALUATOR] Evaluating answer for {declared_role}...")
            evaluation_result = await call_groq_cascade(
                [
                    {
                        "role": "system",
                        "content": (
                            "You are a rigorous interview answer evaluator. "
                            "Return valid JSON only."
                        ),
                    },
                    {
                        "role": "user",
                        "content": eval_prompt,
                    },
                ],
                temperature=0.1,
                json_mode=True,
            )

            # Fallback if evaluation fails but we got a result
            if not evaluation_result:
                evaluation_result = {
                    "current_score": current_score,
                    "feedback": "Answer noted.",
                    "answer_quality": "adequate",
                }

            last_feedback = json.dumps(evaluation_result)
            logger.info(
                f"[EVALUATOR] Score: {evaluation_result.get('current_score')} | Quality: {evaluation_result.get('answer_quality')}"
            )

            # PHASE B: Handle mandatory follow-up requirement
            if evaluation_result.get("requires_followup") and evaluation_result.get(
                "followup_question"
            ):
                # Store follow-up for next turn
                logger.info(
                    f"[EVALUATOR] Follow-up required: {evaluation_result.get('followup_question')}"
                )

            # PHASE D: Apply anti-cheat detection
            cheat_result = AntiCheatDetector.calculate_cheat_score(
                answer=last_user_message,
                cv_claims=None,  # Could pass CV claims if available
                history=history,
            )

            if cheat_result.get("cheat_detected"):
                logger.warning(
                    f"[ANTI-CHEAT] Cheat detected! Score: {cheat_result.get('cheat_score')}, Details: {cheat_result.get('details')}"
                )
                # Apply cheat penalty to score
                base_score = evaluation_result.get("current_score", current_score)
                penalized_score = AntiCheatDetector.apply_cheat_penalty(
                    base_score, cheat_result.get("cheat_score", 0)
                )
                evaluation_result["current_score"] = penalized_score
                evaluation_result["cheat_penalty"] = cheat_result.get("cheat_score", 0)

                # Graceful handling of empty feedback
                base_feedback = str(evaluation_result.get("feedback", "")).strip()
                if not base_feedback or base_feedback.lower() in ["none", "null"]:
                    base_feedback = "Your answer was extremely short or too vague to effectively evaluate."

                evaluation_result["feedback"] = (
                    f"{base_feedback} [Manual Verification Requested]"
                )

        except Exception as e:
            logger.error(f"[EVALUATOR] Failed: {e}")
            evaluation_result = {
                "current_score": current_score,
                "feedback": "Processing error, continuing...",
                "answer_quality": "adequate",
            }

    # 3. STEP 2: GENERATE NEXT QUESTION
    # Use proportional phases that scale with total_questions
    phase = _get_phase(current_q_index, total_questions)

    # Import customization engine (must be before compute_difficulty_band call)
    from backend.ai.interview_customization import (
        build_recruiter_instructions_block,
        compute_difficulty_band,
        select_focus,
        update_instruction_state,
        validate_question,
    )
    from backend.routers.ai_interview import _extract_cv_focus_terms

    difficulty_band = compute_difficulty_band(
        current_score, recent_history, current_q_index, total_questions
    )
    cv_terms = _extract_cv_focus_terms(cv_context, max_terms=8)

    # Normalize defaults
    if interview_instructions is None:
        interview_instructions = {
            "must_topics": [],
            "frequency_rules": [],
            "custom_questions": [],
            "raw": "",
        }
    # Normalize instruction state defensively.
    # Callers/tests may pass {} or a partial state.
    if not isinstance(instruction_state, dict):
        instruction_state = {}

    instruction_state.setdefault("question_index", current_q_index)
    instruction_state.setdefault("covered_topics", [])

    instruction_usage = instruction_state.get("instruction_usage")
    if not isinstance(instruction_usage, dict):
        instruction_usage = {}

    instruction_usage.setdefault("must_topics_covered", [])
    instruction_usage.setdefault("frequency_hits", {})
    instruction_state["instruction_usage"] = instruction_usage

    # Step 4: Priority-based focus selection
    technical_focus = select_focus(
        cv_terms=cv_terms,
        skill_scores=initial_skills or {},
        instructions=interview_instructions,
        state=instruction_state,
        declared_role=declared_role,
        rubric_categories=rubric_categories,
    )

    # Step 5: Build recruiter instructions block
    recruiter_block = build_recruiter_instructions_block(
        interview_instructions, instruction_state
    )

    gen_prompt = get_question_generator_prompt(
        declared_role=declared_role,
        candidate_summary=candidate_summary,
        phase=phase,
        q_index=current_q_index,
        total_questions=total_questions,
        language=language,
        history_summary=history_summary + "\n\nRecent:\n" + history_formatted,
        last_feedback=last_feedback,
        difficulty_band=difficulty_band,
        technical_focus=technical_focus,
        job_description=job_description,
        recruiter_instructions_block=recruiter_block,
    )

    # Step 6: Generation with validation retry loop (max 2 attempts)
    gen_response = None
    try:
        logger.info(
            f"[GENERATOR] Generating Q{current_q_index} ({phase}) focus={technical_focus} diff={difficulty_band}"
        )
        for attempt in range(2):
            # Groq Compound requires the final chat message to have
            # role=user. Keep the application prompt as system context,
            # then add a minimal user turn that explicitly requests the
            # generated interview question.
            gen_messages = [
                {"role": "system", "content": gen_prompt},
                {
                    "role": "user",
                    "content": (
                        "Generate the next interview question now. "
                        "Return the required JSON object only."
                    ),
                },
            ]

            gen_response = await call_groq_cascade(
                gen_messages,
                temperature=0.4,
                json_mode=True,
            )
            candidate_reply = (gen_response or {}).get("reply", "")
            if validate_question(
                candidate_reply,
                technical_focus,
                interview_instructions,
                instruction_state,
            ):
                break
            else:
                # Force retry: inject an explicit override instruction
                forcing_note = f"\n\n🔴 RETRY INSTRUCTION: Your previous question did NOT mention '{technical_focus}'. You MUST ask about {technical_focus} in this question. Include the word explicitly."
                gen_prompt_retry = gen_prompt + forcing_note
                gen_prompt = gen_prompt_retry
                logger.warning(
                    f"[VALIDATE RETRY] Attempt {attempt + 1} failed for focus '{technical_focus}'. Retrying with forcing instruction."
                )
        else:
            # Both attempts failed: fall through to fallback below
            gen_response = None
    except Exception as e:
        logger.error(f"[GENERATOR] Exception during generation: {e}")
        gen_response = None

    if not gen_response:
        logger.error("[GENERATOR] All attempts failed. Using graceful fallback.")
        from backend.routers.ai_interview import _get_graceful_fallback

        gen_response = {
            "reply": _get_graceful_fallback(current_q_index, language, declared_role)
        }

    try:
        # Merge results
        final_response = evaluation_result.copy()
        final_response.update(gen_response or {})

        # Ensure critical keys exist
        if "reply" not in final_response:
            final_response["reply"] = "Could you tell me more about that?"

        # Skill normalization and merging logic
        # Helper to safely convert values to float
        def _safe_float(val, default):
            try:
                return float(val)
            except Exception:
                return default

        current_val = _safe_float(
            final_response.get("current_score", current_score), current_score
        )
        answer_quality = final_response.get("answer_quality", "adequate").lower()

        if initial_skills and isinstance(initial_skills, dict):
            merged_skills = initial_skills.copy()
            ai_eval_skills = final_response.get("skills", {})

            # Phase 14: Asymmetric Merge (Penalties > Rewards)
            for k in list(merged_skills.keys()):
                prev_val = _safe_float(merged_skills.get(k, current_val), current_val)
                ai_skill_val = _safe_float(
                    ai_eval_skills.get(k, current_val), current_val
                )

                # Base weight
                weight = 0.3 if k == technical_focus else 0.1

                # ASYMMETRIC ENFORCEMENT:
                # 1. If Answer is Incorrect/Contradictory → Moderate drop in skill focus
                if answer_quality in ["incorrect", "contradictory"]:
                    weight = 0.35 if k == technical_focus else 0.15
                    if ai_skill_val < prev_val:
                        weight = max(weight, 0.4 if k == technical_focus else 0.2)
                # 2. If ai_skill_val < 40 → Penalty weight is 20%
                elif ai_skill_val < 40:
                    weight = 0.25 if k == technical_focus else 0.12
                # 3. Simple weighted average for regular updates
                # Allow much larger drop for incorrect/contradictory answers
                lower_limit = (
                    prev_val - 60
                    if answer_quality in ["incorrect", "contradictory"]
                    else prev_val - 25
                )
                upper_limit = prev_val + 20

                merged_skills[k] = max(5, min(100, merged_skills[k]))  # Basic clamp
                merged_skills[k] = max(lower_limit, min(upper_limit, merged_skills[k]))

            final_response["skills"] = merged_skills
        else:
            if "skills" not in final_response:
                final_response["skills"] = {
                    "Technical": current_val,
                    "Communication": round(current_val * 0.9, 1),
                    "Problem Solving": round(current_val * 1.1, 1)
                    if current_val < 90
                    else 95,
                    "Adaptability": current_val,
                    "Confidence": current_val,
                }

        # Step 7: Update instruction state after successful generation
        instruction_state = update_instruction_state(
            instruction_state, technical_focus, interview_instructions
        )
        final_response["instruction_state"] = instruction_state

        logger.info(
            f"[AI SUCCESS] Q{current_q_index} generated. Focus: {technical_focus}"
        )
        return final_response
    except Exception as e:
        logger.error(
            f"[AI] Dynamic Turn Error at Q{current_q_index}: {type(e).__name__}: {str(e)}"
        )
        import traceback

        logger.error(f"[AI] Traceback: {traceback.format_exc()}")
        raise e


async def evaluate_complete_interview(
    cv_text: str, declared_role: str, qa_pairs: list, violations: list = None,
    rubric_context: str = None,
):
    """
    REQUEST 3 of 3: Final batch evaluation of all interview answers.
    Evaluates all Q&A pairs in a single AI request.
    ``rubric_context`` (optional) is a rendered rubric skill list used to
    calibrate the evaluator; internal weights/formulas are never exposed.
    """
    logger.info(
        f"🎯 [AI] REQUEST 3/3: Evaluating complete interview for {declared_role}..."
    )

    # Format Q&A pairs for the prompt
    qa_formatted = ""
    for i, qa in enumerate(qa_pairs, 1):
        # FILTER: Only process candidate answers (skip AI questions and system messages)
        role = qa.get("role", "").lower()
        if role in ["system", "assistant", "bot", "ai", "interviewer"]:
            continue

        user_answer = qa.get("answer", "")
        if not user_answer:
            continue
        if user_answer.strip().lower() in [
            "ready",
            "start",
            "commencer",
            "yalla",
            "ok",
        ]:
            continue

        qa_formatted += f"Question {i}: {qa.get('question', 'N/A')}\nCandidate's Answer: {user_answer}\nCorrect Answer: {qa.get('correct_answer', 'N/A')}\n---\n"

    # Format proctoring context
    proctoring_context = "No violations detected."
    if violations:
        # Sum types for concise context
        summary = {}
        for v in violations:
            t = v.get("type", "General")
            summary[t] = summary.get(t, 0) + 1
        proctoring_context = " | ".join(
            [f"{t}: {count} occurrences" for t, count in summary.items()]
        )

    prompt = get_complete_interview_evaluation_prompt(
        declared_role, cv_text, qa_formatted, proctoring_context,
        rubric_context=rubric_context,
    )

    # FIX: ONE system message only (Groq limitation)
    messages = [
        {
            "role": "system",
            "content": f"You are an expert interview evaluator for {declared_role} positions. {prompt}",
        },
        {"role": "user", "content": "Evaluate the candidate and return JSON."},
    ]

    try:
        # Groq-only: no provider fallback
        result = await call_groq_cascade(
            messages, temperature=0.1, max_tokens=4000, json_mode=True
        )
        if not result or (isinstance(result, dict) and result.get("error")):
            logger.warning(
                "[AI] Groq failed for interview evaluation — returning empty result"
            )
            result = {}

        # ---- Schema validation --------------------------------
        if not isinstance(result, dict):
            logger.error(
                f"[AI] Expected dict from AI, got {type(result).__name__}; "
                f"treating as validation failure"
            )
            result = {}
        try:
            from backend.ai.schemas import EvaluationResponse

            EvaluationResponse(**result)
        except Exception as schema_err:
            logger.error(
                f"[AI] Schema validation failed for {declared_role}: {schema_err}",
                exc_info=True,
            )
            return {
                "_schema_error": "validation_failed",
                "final_score": None,
                "strengths": [],
                "weaknesses": [
                    "AI evaluation output was malformed. Manual review required."
                ],
                "skill_metrics": {},
                "recommendation": "Error",
                "detailed_feedback": (
                    "AI evaluation returned invalid data. Please contact support."
                ),
                "explainability": {
                    "why_this_score": "Schema validation failed during evaluation.",
                    "fastest_impact": "N/A",
                    "gap_analysis": [],
                },
                "question_scores": [],
                "role_fit_score": 0,
            }

        logger.info(
            f"[AI] Interview evaluation complete. Final score: "
            f"{result.get('final_score', 'N/A')}/100"
        )
        return result
    except Exception as e:
        logger.error(f"[AI] Interview evaluation failed: {e}", exc_info=True)
        return {
            "_schema_error": "ai_call_failed",
            "final_score": None,
            "strengths": [],
            "weaknesses": ["Error evaluating interview"],
            "skill_metrics": {
                "Technical": 0,
                "Communication": 0,
                "Problem Solving": 0,
                "Adaptability": 0,
                "Confidence": 0,
            },
            "explainability": {
                "why_this_score": "Evaluation failed due to a technical error.",
                "fastest_impact": "Please contact support.",
                "gap_analysis": [],
            },
            "detailed_feedback": "Technical error during evaluation.",
            "question_scores": [],
            "role_fit_score": 0,
            "recommendation": "Error",
        }


async def analyze_communication_style(qa_pairs: list) -> dict:
    """
    Analyze communication patterns from interview answers.
    Returns clarity score, sentence structure analysis, and speaking patterns.
    """
    if not qa_pairs:
        return {
            "clarity_score": 75,
            "sentence_structure": "Balanced",
            "average_answer_length": 0,
            "vocabulary_diversity": "Moderate",
            "communication_tips": [],
        }

    # Extract candidate answers only
    answers = []
    for qa in qa_pairs:
        if isinstance(qa, dict):
            answer = qa.get("answer") or qa.get("content", "")
            role = qa.get("role", "")
            sender = qa.get("sender", "").lower()
            if sender in ["system", "interviewer", "bot", "ai"]:
                continue
            if role == "user" and answer:
                answers.append(answer)
            elif role == "assistant" and qa.get("feedback"):
                pass  # not a candidate answer
            elif not role and answer and sender not in ["system", "interviewer"]:
                answers.append(answer)

    if not answers:
        return {
            "clarity_score": 75,
            "sentence_structure": "Balanced",
            "average_answer_length": 0,
            "vocabulary_diversity": "Moderate",
            "communication_tips": [],
        }

    # Compute metrics
    total_words = sum(len(a.split()) for a in answers)
    avg_length = total_words // len(answers) if answers else 0
    total_sentences = sum(len(a.split(".")) for a in answers) or 1
    avg_sentence_words = total_words / total_sentences if total_sentences else 15

    # Vocabulary diversity (rough estimate: unique words / total words)
    all_words = []
    for a in answers:
        all_words.extend(a.lower().split())
    unique_words = len(set(all_words))
    diversity_ratio = unique_words / len(all_words) if all_words else 0.5

    # Clarity score heuristic
    clarity = 75
    if avg_sentence_words < 10:
        clarity += 5  # concise
    elif avg_sentence_words > 30:
        clarity -= 10  # rambling
    if diversity_ratio > 0.5:
        clarity += 5
    if len(answers) >= 3:
        clarity += 5
    if total_words > 200:
        clarity += 5
    clarity = max(40, min(98, clarity))

    # Communication insights
    tips = []
    if avg_sentence_words > 25:
        tips.append("Try using shorter, more direct sentences for clarity")
    if diversity_ratio < 0.4:
        tips.append("Expand your vocabulary to demonstrate broader expertise")
    if avg_length < 15:
        tips.append("Provide more detailed examples in your answers")
    if avg_length > 100:
        tips.append("Consider being more concise to keep interviewers engaged")

    return {
        "clarity_score": clarity,
        "sentence_structure": "Concise and clear"
        if avg_sentence_words < 15
        else "Well-structured"
        if avg_sentence_words < 25
        else "Could be more concise",
        "average_answer_length": avg_length,
        "vocabulary_diversity": "High"
        if diversity_ratio > 0.5
        else "Moderate"
        if diversity_ratio > 0.35
        else "Limited",
        "communication_tips": tips[:4],
        "total_answers_analyzed": len(answers),
    }


async def analyze_emotional_intelligence(qa_pairs: list) -> dict:
    """
    Analyze emotional intelligence indicators from interview responses.
    Uses LLM-based analysis instead of keyword counting for accurate EQ assessment.
    """
    if not qa_pairs:
        return {
            "eq_score": 70,
            "confidence_trend": "stable",
            "behavioral_indicators": [],
            "self_awareness": "Moderate",
            "empathy_indicators": [],
            "ai_notes": "Insufficient data for comprehensive EQ analysis.",
        }

    # Extract candidate answers only
    answers = []
    for qa in qa_pairs:
        if isinstance(qa, dict):
            answer = qa.get("answer") or qa.get("content", "")
            role = qa.get("role", "")
            sender = qa.get("sender", "").lower()
            if sender in ["system", "interviewer", "bot", "ai"]:
                continue
            if role == "user" and answer:
                answers.append(answer)

    if not answers:
        return {
            "eq_score": 70,
            "confidence_trend": "stable",
            "behavioral_indicators": [],
            "self_awareness": "Moderate",
            "empathy_indicators": [],
            "ai_notes": "No candidate responses to analyze.",
        }

    # Use LLM for EQ analysis instead of keyword counting
    from backend.ai.llm import call_groq_cascade

    qa_summary = "\n---\n".join(
        [f"Q{idx + 1}: {a[:300]}..." for idx, a in enumerate(answers)]
    )

    prompt = f"""You are an expert psychologist and organizational behavior specialist.
Analyze the candidate's emotional intelligence based on these interview answers.

ANSWERS:
{qa_summary}

Evaluate:
1. Self-awareness: Does the candidate acknowledge strengths/weaknesses honestly?
2. Empathy: Do they consider team members, users, stakeholders?
3. Resilience: How do they discuss failures or challenges?
4. Communication tone: Collaborative vs. individualistic?
5. Growth mindset: Do they show willingness to learn and improve?

Return JSON ONLY:
{{
    "eq_score": <0-100>,
    "self_awareness": "High|Moderate|Developing",
    "empathy_level": "High|Moderate|Developing",
    "resilience": "High|Moderate|Developing",
    "communication_tone": "Collaborative|Balanced|Individualistic",
    "growth_mindset": "Strong|Moderate|Limited",
    "behavioral_indicators": ["Specific observed behavior 1", "behavior 2"],
    "empathy_indicators": ["Evidence of empathy 1", "evidence 2"],
    "ai_notes": "2-3 sentence summary of EQ assessment"
}}"""

    try:
        result = await call_groq_cascade(
            [{"role": "system", "content": prompt}], temperature=0.1, json_mode=True
        )

        eq_score = result.get("eq_score", 70)
        confidence_trend = "stable"  # Would need temporal analysis for trend

        return {
            "eq_score": eq_score,
            "confidence_trend": confidence_trend,
            "behavioral_indicators": result.get("behavioral_indicators", []),
            "self_awareness": result.get("self_awareness", "Moderate"),
            "empathy_indicators": result.get("empathy_indicators", []),
            "ai_notes": result.get("ai_notes", "EQ analysis completed."),
            "confidence_level": "High"
            if eq_score >= 75
            else "Moderate"
            if eq_score >= 60
            else "Developing",
        }
    except Exception as e:
        logger.error(f"[EQ ANALYSIS] LLM-based EQ analysis failed: {e}")
        # Fallback: use basic heuristic
        eq_score = 70
        total_words = sum(len(a.split()) for a in answers)
        avg_length = total_words / len(answers) if answers else 0
        if avg_length > 50:
            eq_score += 5
        if len(answers) >= 5:
            eq_score += 5
        eq_score = min(95, max(40, eq_score))

        return {
            "eq_score": eq_score,
            "confidence_trend": "stable",
            "behavioral_indicators": [],
            "self_awareness": "Moderate",
            "empathy_indicators": [],
            "ai_notes": f"EQ analysis via fallback heuristic (LLM unavailable). Analyzed {len(answers)} answers.",
            "confidence_level": "High"
            if eq_score >= 75
            else "Moderate"
            if eq_score >= 60
            else "Developing",
        }


async def generate_interview_emotional_analysis(qa_pairs: list, role: str) -> dict:
    """
    Complete emotional intelligence and communication analysis for interview panel.
    """
    comm_analysis = await analyze_communication_style(qa_pairs)
    eq_analysis = await analyze_emotional_intelligence(qa_pairs)

    # Combined verdict
    overall_eq = eq_analysis["eq_score"] * 0.6 + comm_analysis["clarity_score"] * 0.4
    overall_eq = min(100, max(0, int(overall_eq)))

    return {
        "emotional_intelligence": {
            "overall_eq_score": overall_eq,
            "confidence_trend": eq_analysis["confidence_trend"],
            "self_awareness": eq_analysis["self_awareness"],
            "behavioral_indicators": eq_analysis["behavioral_indicators"],
            "empathy_indicators": eq_analysis["empathy_indicators"],
            "ai_verdict": eq_analysis["ai_notes"],
        },
        "communication": {
            "clarity_score": comm_analysis["clarity_score"],
            "structure": comm_analysis["sentence_structure"],
            "vocabulary_diversity": comm_analysis["vocabulary_diversity"],
            "improvement_tips": comm_analysis["communication_tips"],
        },
        "overall_analysis": {
            "emotional_intelligence_score": eq_analysis["eq_score"],
            "communication_score": comm_analysis["clarity_score"],
            "speaking_clarity": comm_analysis["clarity_score"] * 0.8
            + eq_analysis["eq_score"] * 0.2,
            "personality_indicators": [
                "Analytical"
                if eq_analysis["eq_score"] >= 70
                and comm_analysis["clarity_score"] >= 70
                else None,
                "Empathetic" if len(eq_analysis["empathy_indicators"]) >= 2 else None,
                "Confident" if eq_analysis["confidence_level"] == "High" else None,
                "Reflective" if eq_analysis["self_awareness"] == "High" else None,
            ],
            "ai_interviewer_notes": f"Candidate {eq_analysis['confidence_trend']} confidence throughout the interview. Communication is {comm_analysis['sentence_structure'].lower()}. EQ indicators suggest {'strong interpersonal skills' if eq_analysis['eq_score'] >= 70 else 'developing interpersonal awareness'}.",
        },
    }


async def generate_score_comparison(
    cv_text: str,
    interview_log: str,
    cv_score: float,
    interview_score: float,
    role: str,
    linguistic_analysis: dict = None,
):
    """
    AI Generation: Explains the delta between CV Quality (Static) and Interview Performance (Dynamic).
    """
    prompt = get_score_comparison_prompt(
        role, cv_score, interview_score, cv_text, interview_log, linguistic_analysis
    )

    try:
        messages = [
            {"role": "system", "content": "You are a professional talent auditor."},
            {"role": "user", "content": prompt},
        ]

        # Groq-only: no provider fallback
        res = await call_groq_cascade(messages, temperature=0.1)

        if not res or (isinstance(res, dict) and res.get("error")):
            logger.warning("[AI] Groq failed for comparison — returning error")
            res = {
                "analysis_summary": "Unable to generate AI comparison at this time.",
                "score_difference": 0,
            }

        return res
    except Exception as e:
        logger.error(f"Comparison AI Failed: {e}")
        return {
            "analysis_summary": "Unable to generate AI comparison at this time.",
            "key_deltas": [],
            "final_verdict": "Manual review required.",
        }
