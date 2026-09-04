import hashlib
import json
import os

from backend.ai.llm import call_groq_cascade
from backend.ai.privacy import audit_ai_call, count_pii_categories
from backend.ai.prompts import (
    _escape_prompt_text,
    get_cv_extraction_prompt,
    get_cv_extraction_prompt_with_rubric,
    get_skills_extraction_prompt,
)
from backend.logger import logger

# Redis cache for CV analysis results
from backend.redis_manager import redis_manager


async def _get_redis():
    return await redis_manager.get_client()


def _normalize_advanced_output(advanced: dict, declared_role: str) -> dict:
    score = float(advanced.get("overall_score", 0) or 0)
    verdict = (
        "Qualified" if score >= 70 else "Incomplete" if score >= 40 else "Irrelevant"
    )

    # Harden summary extraction: avoid indexing into strings (which causes "R" instead of "Rayen")
    raw_insights = advanced.get("key_insights", [])
    if isinstance(raw_insights, list) and len(raw_insights) > 0:
        summary = raw_insights[0]
    elif isinstance(raw_insights, str) and len(raw_insights) > 1:
        summary = raw_insights
    else:
        summary = (
            advanced.get("summary") or "Profile analyzed with semantic extraction."
        )

    # Force summary to be a string
    summary = str(summary)

    skills = advanced.get("skills", [])
    timeline = advanced.get("experience_timeline", [])

    # Harden strengths/weaknesses to always be lists of strings
    def ensure_list_of_strings(val):
        if not val:
            return []
        if isinstance(val, list):
            return [str(x) for x in val if x]
        if isinstance(val, str):
            return [val]
        return []

    strengths = ensure_list_of_strings(advanced.get("strengths"))
    if not strengths and isinstance(skills, list):
        strengths = [
            s.get("name", "")
            for s in skills[:5]
            if isinstance(s, dict) and s.get("name")
        ]

    weaknesses = ensure_list_of_strings(advanced.get("weaknesses"))
    if not weaknesses:
        weaknesses = (
            []
            if score >= 70
            else ["Needs deeper role-aligned evidence and measurable outcomes."]
        )

    # --- Weaknesses / Gaps Extraction ---
    gaps = (
        advanced.get("ai_analysis", {}).get("critical_gaps")
        or advanced.get("critical_gaps")
        or advanced.get("weaknesses")
        or []
    )

    # --- Skill Metrics Mapping ---
    raw_metrics = (
        advanced.get("ai_analysis", {}).get("skill_metrics")
        or advanced.get("skill_metrics")
        or {}
    )

    # Map new lowercase keys to dashboard uppercase keys
    tech_score = (
        raw_metrics.get("technical", {}).get("score")
        if isinstance(raw_metrics.get("technical"), dict)
        else raw_metrics.get("technical")
    )
    comm_score = (
        raw_metrics.get("communication", {}).get("score")
        if isinstance(raw_metrics.get("communication"), dict)
        else raw_metrics.get("communication")
    )
    exp_score = (
        raw_metrics.get("experience", {}).get("score")
        if isinstance(raw_metrics.get("experience"), dict)
        else raw_metrics.get("experience")
    )

    # Final Normalized Metrics
    skill_metrics = {
        "Technical": int(tech_score) if tech_score is not None else int(score),
        "Communication": int(comm_score) if comm_score is not None else int(score),
        "Problem Solving": int(exp_score) if exp_score is not None else int(score),
        "Adaptability": int(score),
        "Confidence": int(score),
        "Consistency": 100,  # Initial baseline consistency is 100%
        "Soft Skills": int(comm_score) if comm_score is not None else int(score),
    }

    # --- Derived Market Positioning & Explainability ---
    market_pos = advanced.get("market_positioning") or (
        f"Highly competitive fit for {declared_role} in the MENA market."
        if score > 75
        else f"Developing profile with foundational alignment to {declared_role} standards."
    )

    why_this_score = (
        advanced.get("explainability", {}).get("why_this_score") or summary[:200]
        if len(summary) > 50
        else f"Based on evidence-based analysis of {declared_role} core competencies."
    )

    # ─── SEMANTIC SKILL CLUSTERING ───
    semantic_clusters = _compute_semantic_clusters(skills, raw_metrics)

    # ─── AI CONFIDENCE SCORING ───
    ai_confidence = _compute_ai_confidence(advanced, score, skills, raw_metrics)

    # ─── INDUSTRY BENCHMARKING ───
    industry_benchmarks = _compute_industry_benchmarks(
        declared_role, score, skill_metrics
    )

    # ─── ROLE COMPATIBILITY SCORING ───
    role_compatibility = _compute_role_compatibility(declared_role, skills, score)

    return {
        "detected_role": declared_role,
        "seniority_level": advanced.get("seniority_level", "Junior"),
        "summary": summary,
        "score": score,
        "verdict": verdict,
        "ai_confidence": ai_confidence,
        "skill_metrics": skill_metrics,
        "semantic_clusters": semantic_clusters,
        "industry_benchmarks": industry_benchmarks,
        "role_compatibility": role_compatibility,
        "strengths": strengths,
        "weaknesses": gaps,
        "gaps": gaps,
        "interview_focus_areas": advanced.get("ai_analysis", {}).get(
            "interview_focus_areas"
        )
        or advanced.get("interview_focus_areas")
        or [],
        "market_positioning": market_pos,
        "explainability": {
            "why_this_score": why_this_score,
            "gap_analysis": advanced.get("explainability", {}).get("gap_analysis")
            or gaps,
            "fastest_impact": advanced.get("explainability", {}).get("fastest_impact")
            or "Immediate focus on technical evidence and project-based results.",
        },
        "experience": advanced.get("experience")
        or [
            {
                "title": item.get("role", ""),
                "company": item.get("company", ""),
                "duration": f"{item.get('duration_months', 0)} months",
                "description": f"Level: {item.get('progression_level', 2.0)}",
            }
            for item in timeline
        ],
        "education": advanced.get("education") or [],
        "skills": advanced.get("skills") or [],
        "role_confidence": advanced.get("role_confidence")
        or advanced.get("ai_analysis", {}).get("role_confidence", 0.5),
        "advanced_analysis": advanced,
    }


async def analyze_cv(
    text_anonymized: str, declared_role: str, security_context: str = ""
):
    """
    Standardized CV Analysis using AI Cascade with Redis caching.
    """
    # Validate input text
    if not text_anonymized or len(text_anonymized.strip()) < 50:
        return {
            "error": "CV text too short or empty. Please use a text-based PDF (not a scanned image).",
            "score": 0,
            "verdict": "Incomplete",
            "detected_role": declared_role,
        }

    # Truncate text if too long to prevent token overflow (Standardized to 6k to match prompts)
    text_anonymized = text_anonymized.strip()
    if len(text_anonymized) > 6000:
        logger.warning(
            f"CV Text too long ({len(text_anonymized)} chars), truncating to 6000..."
        )
        text_anonymized = text_anonymized[:6000]

    # Generate cache key from content hash and role
    content_hash = hashlib.sha256(
        f"{text_anonymized[:2000]}:{declared_role}:{security_context}".encode()
    ).hexdigest()[:16]
    cache_key = f"cv_analysis:{content_hash}"

    # Bypass cache for testing to ensure fresh insights
    redis = None  # await _get_redis() if _get_redis else None
    if redis:
        try:
            cached = await redis.get(cache_key)
            if cached:
                logger.info(
                    f"CV Analysis cache hit for {declared_role} (hash: {content_hash})"
                )
                return json.loads(cached)
        except Exception as e:
            logger.warning(f"Redis cache read error: {e}")

    # Phase-1 analyzer integration (enabled by default, safe fallback to legacy).
    result = None
    if os.getenv("ADVANCED_CV_ANALYZER_ENABLED", "1") == "1":
        try:
            from backend.ai.advanced_cv_analyzer import AdvancedCVAnalyzer

            digest = hashlib.sha1(text_anonymized.encode("utf-8")).hexdigest()[:12]
            analyzer = AdvancedCVAnalyzer()
            advanced = await analyzer.analyze_cv(
                cv_content=text_anonymized,
                user_id=f"cv_{digest}",
                job_context=declared_role,
            )
            if isinstance(advanced, dict) and not advanced.get("error"):
                result = _normalize_advanced_output(advanced, declared_role)
        except Exception as e:
            error_msg = str(e).lower()
            # Handle image-related errors gracefully
            if "image" in error_msg and (
                "does not support" in error_msg or "vision" in error_msg
            ):
                result = {
                    "error": "Le fichier semble être une image convertie en PDF. Veuillez utiliser un PDF avec du texte sélectionnable.",
                    "score": 0,
                    "verdict": "Incomplete",
                    "detected_role": declared_role,
                }
            logger.warning(
                f"Advanced CV analyzer unavailable, falling back to legacy path: {e}"
            )

    # Fallback to legacy analysis if advanced analyzer failed or disabled
    if not result:
        from backend.ai.prompts import get_cv_analysis_prompt

        # Get versioned prompt with A/B testing support
        prompt, prompt_info = get_cv_analysis_prompt(
            declared_role,
            text_anonymized,
            security_context,
            user_id=getattr(security_context, "user_id", None),
        )
        logger.info(
            f"Starting CV Analysis for '{declared_role}'. "
            f"Prompt v{prompt_info['version']} ({prompt_info['variant']}). "
            f"Size: {len(prompt)} chars."
        )

        try:
            result = await call_groq_cascade(
                [
                    {"role": "system", "content": prompt},
                    {
                        "role": "user",
                        "content": (
                            "Analyze the CV text described in the system instructions "
                            "and return the requested JSON analysis."
                        ),
                    },
                ],
                temperature=0.3,
            )

            # Track successful prompt usage
            from backend.ai.prompts import track_prompt_usage

            track_prompt_usage(
                "cv_analysis",
                prompt_info["version"],
                prompt_info["variant"],
                success=True,
            )
        except Exception as e:
            logger.error(f"AI Analysis Failed: {e}")
            result = {
                "error": "CV analysis failed",
                "score": 0,
                "verdict": "Error",
                "summary": "CV analysis failed due to an unexpected error",
                "skill_metrics": {
                    "Technical": 0,
                    "Communication": 0,
                    "Problem Solving": 0,
                    "Adaptability": 0,
                    "Confidence": 0,
                },
                "explainability": {
                    "why_this_score": "Service unavailable",
                    "gap_analysis": [],
                },
                "strengths": [],
                "weaknesses": ["System temporarily unavailable during processing."],
            }

            # Track failed prompt usage
            from backend.ai.prompts import track_prompt_usage

            track_prompt_usage(
                "cv_analysis",
                prompt_info["version"],
                prompt_info["variant"],
                success=False,
            )

    # PII Compliance Audit — log what PII categories were detected (never raw values)
    pii_count, pii_cats = count_pii_categories(text_anonymized)
    if pii_count:
        audit_ai_call(
            pipeline_stage="cv_analysis",
            application_id=0,
            pii_count=pii_count,
            pii_categories=pii_cats,
            success="error" not in (result or {}),
        )

    # Add prompt version info to result for tracking
    if result and "error" not in result:
        from backend.ai.prompts import get_prompt_variant, get_prompt_version

        result["_prompt_info"] = {
            "version": get_prompt_version("cv_analysis"),
            "variant": get_prompt_variant(
                getattr(security_context, "user_id", None), "cv_analysis"
            ),
        }

    # Cache the result (24 hours = 86400 seconds)
    if redis and result and "error" not in result:
        try:
            await redis.setex(cache_key, 3600, json.dumps(result))
            logger.info(
                f"CV Analysis cached for {declared_role} (hash: {content_hash})"
            )
        except Exception as e:
            logger.warning(f"Redis cache write error: {e}")

    return result


async def extract_cv_details(
    cv_text: str, job_description: str = "", rubric_context: str = ""
):
    """
    Extracts structured candidate info from CV text.
    Used for Bulk Uploads.
    """
    if rubric_context:
        prompt = get_cv_extraction_prompt_with_rubric(
            cv_text, job_description, rubric_context
        )
    else:
        prompt = get_cv_extraction_prompt(cv_text, job_description)

    try:
        messages = [{"role": "system", "content": prompt}]
        # Use our robust cascade (Local -> Groq -> DeepSeek -> Gemini)
        result = await call_groq_cascade(messages, temperature=0.1)
        if result is None:
            logger.error("Extraction returned None (all AI providers failed)")
            return {
                "name": "Unknown Candidate",
                "email": None,
                "role": "General",
                "skills": [],
                "summary": "Failed to extract details.",
                "score": 0,
            }
        return result
    except Exception as e:
        logger.error(f"Extraction Failed: {e}")
        return {
            "name": "Unknown Candidate",
            "email": None,
            "role": "General",
            "skills": [],
            "summary": "Failed to extract details.",
            "score": 0,
        }


async def extract_skills_from_cv(cv_text: str, declared_role: str) -> dict:
    """
    Extracts ONLY skills explicitly mentioned in CV text.
    Uses strict NLP rules - no guessing or inference.
    """
    if not cv_text or len(cv_text.strip()) < 20:
        return {
            "extracted_skills": {
                "technical": [],
                "tools": [],
                "databases": [],
                "domains": [],
            }
        }

    # Truncate if too long
    cv_text = cv_text.strip()[:8000]

    prompt = get_skills_extraction_prompt(cv_text, declared_role)

    try:
        result = await call_groq_cascade(
            [{"role": "system", "content": prompt}], temperature=0.1, json_mode=True
        )

        # PII Compliance Audit
        pii_count, pii_cats = count_pii_categories(cv_text)
        if pii_count:
            audit_ai_call(
                pipeline_stage="skill_extraction",
                application_id=0,
                pii_count=pii_count,
                pii_categories=pii_cats,
                success=isinstance(result, dict),
            )

        if isinstance(result, dict):
            return result
    except Exception as e:
        logger.warning(f"Skills extraction failed: {e}")

    return {
        "extracted_skills": {
            "technical": [],
            "tools": [],
            "databases": [],
            "domains": [],
        }
    }


async def extract_skills_with_confidence(cv_text: str, declared_role: str) -> dict:
    """
    Enhanced skill extraction with confidence scores and evidence from CV.
    Each skill includes:
    - skill: the skill name
    - confidence: 0-100 score based on how clearly mentioned
    - evidence: the CV text line where skill was found
    """
    if not cv_text or len(cv_text.strip()) < 50:
        return {
            "skills_with_confidence": [],
            "technical": [],
            "tools": [],
            "databases": [],
            "soft": [],
        }

    cv_text = cv_text.strip()[:6000]
    _cv = _escape_prompt_text(cv_text)
    _role = _escape_prompt_text(declared_role)

    prompt = f"""You are a CV Analysis Expert. Extract skills from this CV with CONFIDENCE SCORES and EVIDENCE.

CV TEXT:
{_cv}

ROLE: {_role}

TASK: For each skill found, provide:
1. skill: the exact skill name
2. confidence: 0-100 score (higher = clearer mention with context)
3. evidence: the EXACT line from CV where skill appears

CATEGORIES TO EXTRACT:
- technical: Python, Java, React, SQL, JavaScript...
- tools: Docker, AWS, Figma, Git, Jira...
- databases: PostgreSQL, MongoDB, Redis...
- soft: Leadership, Management, Communication...

OUTPUT (JSON ONLY):
{{
  "skills_with_confidence": [
    {{"skill": "Python", "confidence": 95, "evidence": "3 years experience with Python", "category": "technical"}},
    {{"skill": "Docker", "confidence": 70, "evidence": "familiar with Docker containers", "category": "tools"}}
  ],
  "technical": ["Python", "Java"],
  "tools": ["Docker", "AWS"],
  "soft": []
}}

RULES:
- evidence MUST be exact text from CV (quote it)
- confidence 90-100: clear mention with context (e.g., "3 years Python")
- confidence 70-89: mentioned but vague (e.g., "familiar with")
- confidence below 70: uncertain, only mentioned once
- Only extract what IS in the CV text"""

    try:
        result = await call_groq_cascade(
            [{"role": "system", "content": prompt}], temperature=0.1, json_mode=True
        )

        if result and isinstance(result, dict):
            # Flatten for easier access
            technical = result.get("technical", [])
            tools = result.get("tools", [])
            databases = result.get("databases", [])
            soft = result.get("soft", [])

            all_skills_raw = technical + tools + databases + soft
            all_skills_strings = []
            for s in all_skills_raw:
                if isinstance(s, str):
                    all_skills_strings.append(s)
                elif isinstance(s, dict):
                    name = s.get("name") or s.get("skill") or str(s)
                    all_skills_strings.append(name)

            return {
                "skills_with_confidence": result.get("skills_with_confidence", []),
                "technical": technical,
                "tools": tools,
                "databases": databases,
                "soft": soft,
                "all": all_skills_strings,
            }
    except Exception as e:
        logger.warning(f"Enhanced skills extraction failed: {e}")

    return {
        "skills_with_confidence": [],
        "technical": [],
        "tools": [],
        "databases": [],
        "soft": [],
        "all": [],
    }


def _compute_semantic_clusters(skills_list: list, raw_metrics: dict) -> dict:
    """Build semantic skill clusters from extracted skills."""
    if not skills_list and not raw_metrics:
        return {"clusters": [], "relationships": []}

    # Normalize skills list
    all_skills = []
    if isinstance(skills_list, list):
        for s in skills_list:
            if isinstance(s, str):
                all_skills.append(s)
            elif isinstance(s, dict):
                all_skills.append(s.get("name", "") or s.get("skill", ""))
    if isinstance(raw_metrics, dict):
        all_skills.extend(list(raw_metrics.keys()))

    # Deduplicate
    seen = set()
    unique_skills = []
    for s in all_skills:
        if s and s.lower() not in seen:
            seen.add(s.lower())
            unique_skills.append(s)

    # Group into clusters
    cluster_map = {
        "Frontend": [
            "react",
            "angular",
            "vue",
            "html",
            "css",
            "javascript",
            "typescript",
            "frontend",
            "ui",
            "ux",
        ],
        "Backend": [
            "python",
            "java",
            "node",
            "go",
            "rust",
            "c#",
            "backend",
            "api",
            "microservices",
            "graphql",
            "rest",
        ],
        "Data & AI": [
            "machine learning",
            "deep learning",
            "tensorflow",
            "pytorch",
            "pandas",
            "numpy",
            "data",
            "sql",
            "analytics",
        ],
        "DevOps & Cloud": [
            "docker",
            "kubernetes",
            "aws",
            "gcp",
            "azure",
            "ci/cd",
            "devops",
            "terraform",
            "jenkins",
            "gitlab",
        ],
        "Soft Skills": [
            "communication",
            "leadership",
            "teamwork",
            "problem solving",
            "critical thinking",
            "adaptability",
        ],
        "Design": [
            "figma",
            "sketch",
            "photoshop",
            "illustrator",
            "design",
            "prototyping",
            "wireframing",
        ],
    }

    clusters = []
    for cluster_name, keywords in cluster_map.items():
        matching = [s for s in unique_skills if any(kw in s.lower() for kw in keywords)]
        if matching:
            score = (
                sum(1 for m in matching) / len(unique_skills) * 100
                if unique_skills
                else 0
            )
            clusters.append(
                {
                    "name": cluster_name,
                    "skills": matching[:10],
                    "strength": min(100, int(score)),
                    "count": len(matching),
                }
            )

    # Build relationships (edges between skills in same cluster)
    relationships = []
    for cluster in clusters:
        skills = cluster["skills"]
        for i in range(len(skills)):
            for j in range(i + 1, len(skills)):
                relationships.append(
                    {
                        "source": skills[i],
                        "target": skills[j],
                        "strength": cluster["strength"],
                    }
                )

    return {"clusters": clusters, "relationships": relationships[:30]}


def _compute_ai_confidence(
    advanced: dict, score: float, skills: list, raw_metrics: dict
) -> float:
    """Compute AI confidence score for the analysis results."""
    confidence = 0.85  # base

    # Factor 1: Score reliability
    if score > 0:
        confidence += 0.05
    if score >= 70:
        confidence += 0.03

    # Factor 2: Skills depth
    skills_count = (
        len(skills)
        if isinstance(skills, list)
        else len(raw_metrics)
        if isinstance(raw_metrics, dict)
        else 0
    )
    if skills_count >= 10:
        confidence += 0.05
    elif skills_count >= 5:
        confidence += 0.02

    # Factor 3: Advanced analysis presence
    if advanced.get("ai_analysis") or advanced.get("explainability"):
        confidence += 0.05

    # Factor 4: Experience timeline
    if advanced.get("experience") or advanced.get("experience_timeline"):
        confidence += 0.02

    return round(min(0.99, max(0.5, confidence)), 3)


def _compute_industry_benchmarks(
    declared_role: str, score: float, skill_metrics: dict
) -> dict:
    """Compare candidate against industry standards."""
    role_lower = declared_role.lower()

    benchmarks = {
        "software engineer": {"avg_score": 72, "top_percentile": 88, "competitive": 80},
        "data scientist": {"avg_score": 70, "top_percentile": 86, "competitive": 78},
        "product manager": {"avg_score": 68, "top_percentile": 85, "competitive": 76},
        "designer": {"avg_score": 74, "top_percentile": 89, "competitive": 82},
        "devops": {"avg_score": 71, "top_percentile": 87, "competitive": 79},
        "general": {"avg_score": 65, "top_percentile": 82, "competitive": 74},
    }

    benchmark = benchmarks.get("general", {})
    for role_key, bm in benchmarks.items():
        if role_key in role_lower:
            benchmark = bm
            break

    percentile_estimate = min(
        99, int((score / benchmark.get("top_percentile", 85)) * 100)
    )
    gap_to_competitive = max(0, benchmark.get("competitive", 75) - score)

    return {
        "industry_average": benchmark["avg_score"],
        "top_percentile_threshold": benchmark["top_percentile"],
        "competitive_threshold": benchmark["competitive"],
        "candidate_percentile": percentile_estimate,
        "gap_to_competitive": gap_to_competitive,
        "rating": "Top Tier"
        if score >= benchmark["top_percentile"]
        else "Competitive"
        if score >= benchmark["competitive"]
        else "Developing"
        if score >= benchmark["avg_score"]
        else "Needs Improvement",
    }


def _compute_role_compatibility(declared_role: str, skills: list, score: float) -> dict:
    """Score how well the candidate fits the declared role."""
    role_lower = declared_role.lower()

    # Role-skill mapping
    role_skills = {
        "software engineer": [
            "python",
            "java",
            "javascript",
            "algorithms",
            "data structures",
            "system design",
            "git",
            "sql",
        ],
        "frontend developer": [
            "html",
            "css",
            "javascript",
            "typescript",
            "react",
            "angular",
            "vue",
            "responsive design",
        ],
        "backend developer": [
            "python",
            "java",
            "node",
            "api",
            "database",
            "sql",
            "microservices",
            "docker",
        ],
        "data scientist": [
            "python",
            "machine learning",
            "statistics",
            "sql",
            "pandas",
            "tensorflow",
            "data visualization",
        ],
        "devops engineer": [
            "docker",
            "kubernetes",
            "aws",
            "ci/cd",
            "terraform",
            "linux",
            "scripting",
        ],
        "product manager": [
            "roadmap",
            "user research",
            "analytics",
            "agile",
            "stakeholder",
            "a/b testing",
        ],
        "designer": [
            "figma",
            "ui",
            "ux",
            "prototyping",
            "user research",
            "design systems",
            "wireframing",
        ],
    }

    expected_skills = role_skills.get("software engineer", [])
    for role_key, rskills in role_skills.items():
        if role_key in role_lower:
            expected_skills = rskills
            break

    # Match skills
    skill_texts = []
    if isinstance(skills, list):
        for s in skills:
            if isinstance(s, str):
                skill_texts.append(s.lower())
            elif isinstance(s, dict):
                skill_texts.append((s.get("name", "") or s.get("skill", "")).lower())

    matches = sum(1 for es in expected_skills if any(es in st for st in skill_texts))
    total = len(expected_skills)
    compatibility_score = int((matches / total) * 100) if total > 0 else 50

    missing = [es for es in expected_skills if not any(es in st for st in skill_texts)]

    return {
        "compatibility_score": min(100, max(0, compatibility_score)),
        "matching_skills_count": matches,
        "total_expected_skills": total,
        "missing_key_skills": missing[:8],
        "skill_gap_percentage": 100 - min(100, int((matches / total) * 100))
        if total > 0
        else 50,
    }
