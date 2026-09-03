"""
Advanced Scoring Integration
==============================

Wires all new scoring features into the live interview pipeline:
- Answer time extraction and timing penalty
- Bias audit during final evaluation
- Knowledge graph construction
- Drift monitoring triggers
- Calibration sample creation

Author: Candway Engineering
"""

import logging
from datetime import UTC, datetime
from typing import Any, Dict, List

logger = logging.getLogger("candway_app")


def extract_answer_times(qa_pairs: List[dict]) -> List[float]:
    """
    Extract response times from structured QA pairs.
    Returns list of times in seconds.
    """
    times = []
    for qa in qa_pairs:
        if not isinstance(qa, dict):
            continue

        # Try response_time_seconds first
        rt = qa.get("response_time_seconds")
        if rt is not None:
            try:
                times.append(float(rt))
                continue
            except (ValueError, TypeError):
                pass

        # Fallback: compute from timestamps
        q_ts = qa.get("question_timestamp")
        a_ts = qa.get("answer_timestamp")
        if q_ts and a_ts:
            try:
                if isinstance(a_ts, (int, float)):
                    times.append(float(a_ts) - float(q_ts))
                elif isinstance(a_ts, str):
                    a_dt = datetime.fromisoformat(a_ts.replace("Z", "+00:00"))
                    times.append(a_dt.timestamp() - float(q_ts))
            except (ValueError, TypeError):
                pass

    return [t for t in times if t > 0]


def run_advanced_evaluation(
    qa_pairs: List[dict],
    skill_metrics: Dict[str, float],
    question_scores: List[float],
    violations: List[dict],
    role: str,
    seniority: str,
    cv_text: str = "",
    candidate_language: str = "English",
    is_native_speaker: bool = True,
    candidate_region: str = None,
) -> Dict[str, Any]:
    """
    Run all advanced scoring analyses and return consolidated results.

    Returns dict with:
    - answer_times: Extracted response times
    - timing_penalty: Computed penalty
    - bias_audit: Bias detection results
    - knowledge_graph: Concept mastery tracking
    - explainable_score: Full explainable scoring
    - drift_snapshot: Model behavior snapshot
    """
    results = {}

    # 1. Extract answer times
    answer_times = extract_answer_times(qa_pairs)
    results["answer_times"] = answer_times
    results["answer_time_stats"] = {
        "count": len(answer_times),
        "avg": round(sum(answer_times) / len(answer_times), 1) if answer_times else 0,
        "min": round(min(answer_times), 1) if answer_times else 0,
        "max": round(max(answer_times), 1) if answer_times else 0,
    }

    # 2. Timing analysis
    if answer_times:
        try:
            from backend.ai.timing_analysis import (
                analyze_response_timing,
                compute_timing_penalty,
            )

            timing = analyze_response_timing(answer_times)
            results["timing_analysis"] = timing.to_dict()
            results["timing_penalty"] = compute_timing_penalty(timing)
            results["timing_risk_level"] = timing.risk_level
        except Exception as e:
            logger.error(f"[ADVANCED SCORING] Timing analysis failed: {e}")
            results["timing_penalty"] = 0
            results["timing_risk_level"] = "Low"

    # 3. Bias audit
    try:
        from backend.ai.bias_detection import run_bias_audit

        bias_report = run_bias_audit(
            qa_pairs=qa_pairs,
            candidate_language=candidate_language,
            is_native_speaker=is_native_speaker,
            candidate_region=candidate_region,
        )
        results["bias_audit"] = bias_report.to_dict()
        results["bias_fairness_score"] = bias_report.fairness_score
        results["bias_risk_level"] = bias_report.risk_level
    except Exception as e:
        logger.error(f"[ADVANCED SCORING] Bias audit failed: {e}")
        results["bias_audit"] = {"error": "Analysis unavailable"}
        results["bias_fairness_score"] = 100
        results["bias_risk_level"] = "Low"

    # 4. Knowledge graph
    try:
        from backend.ai.knowledge_graph import (
            build_knowledge_graph,
            get_concept_mastery_report,
        )

        qa_for_graph = [
            {
                "question": qa.get("question", ""),
                "answer": qa.get("answer", ""),
                "score": qa.get("score", 50),
                "focus": qa.get("type", qa.get("focus", "")),
                "complexity": qa.get("difficulty", "intermediate"),
            }
            for qa in qa_pairs
            if isinstance(qa, dict)
        ]

        graph = build_knowledge_graph(qa_for_graph, role)
        results["knowledge_graph"] = graph.to_dict()
        results["knowledge_graph_report"] = get_concept_mastery_report(graph)
    except Exception as e:
        logger.error(f"[ADVANCED SCORING] Knowledge graph failed: {e}")
        results["knowledge_graph"] = {"error": "Analysis unavailable"}

    # 5. Explainable scoring (uses timing penalty if available)
    try:
        from backend.ai.explainable_scoring import generate_explainable_score

        results.get("timing_penalty", 0)

        # If timing penalty exists, we need to adjust the final score
        # This is handled by calculate_overall_score, but we generate explainability here
        explainable = generate_explainable_score(
            final_score=sum(question_scores) / len(question_scores)
            if question_scores
            else 50,
            dimension_scores=skill_metrics,
            question_scores=question_scores,
            role=role,
            seniority=seniority,
            violations=violations,
            answer_times=answer_times if answer_times else None,
            qa_pairs=qa_pairs,
        )

        results["explainable_score"] = explainable.to_dict()
    except Exception as e:
        logger.error(f"[ADVANCED SCORING] Explainable scoring failed: {e}")
        results["explainable_score"] = {"error": "Analysis unavailable"}

    # 6. Drift monitoring snapshot
    try:
        from backend.ai.drift_monitor import (
            create_snapshot_from_interviews,
            drift_monitor,
        )

        interviews = []
        for qa in qa_pairs:
            if isinstance(qa, dict):
                interviews.append(
                    {
                        "score": qa.get("score", 50),
                        "dimension_scores": skill_metrics,
                        "response_time": qa.get("response_time_seconds", 0),
                        "error": qa.get("status") == "error",
                    }
                )

        if interviews:
            snapshot = create_snapshot_from_interviews(interviews, "current")
            results["drift_snapshot"] = snapshot.to_dict()

            # Record and check for drift
            drift_monitor.record_snapshot(snapshot)
            drift_report = drift_monitor.detect_drift(snapshot)
            results["drift_report"] = drift_report.to_dict()
    except Exception as e:
        logger.error(f"[ADVANCED SCORING] Drift monitoring failed: {e}")
        results["drift_report"] = {"error": "Analysis unavailable"}

    return results


def integrate_into_analysis_json(
    analysis_data: dict, advanced_results: dict, breakdown: Any = None
) -> dict:
    """
    Merge advanced scoring results into the analysis_json structure.
    """
    analysis_data["advanced_scoring"] = {
        "answer_times": advanced_results.get("answer_times", []),
        "answer_time_stats": advanced_results.get("answer_time_stats", {}),
        "timing_analysis": advanced_results.get("timing_analysis", {}),
        "timing_penalty": advanced_results.get("timing_penalty", 0),
        "timing_risk_level": advanced_results.get("timing_risk_level", "Low"),
        "bias_audit": advanced_results.get("bias_audit", {}),
        "bias_fairness_score": advanced_results.get("bias_fairness_score", 100),
        "bias_risk_level": advanced_results.get("bias_risk_level", "Low"),
        "knowledge_graph": advanced_results.get("knowledge_graph", {}),
        "knowledge_graph_report": advanced_results.get("knowledge_graph_report", {}),
        "explainable_score": advanced_results.get("explainable_score", {}),
        "drift_report": advanced_results.get("drift_report", {}),
        "timestamp": datetime.now(UTC).isoformat(),
    }

    # Add breakdown explainability if available
    if breakdown and hasattr(breakdown, "to_dict"):
        breakdown_dict = breakdown.to_dict()
        if "explainability" in breakdown_dict:
            analysis_data["advanced_scoring"]["score_explainability"] = breakdown_dict[
                "explainability"
            ]

    return analysis_data
