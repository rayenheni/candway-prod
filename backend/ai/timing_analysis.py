"""
Timing Analysis for Anti-Cheat
================================

Detects suspicious answer timing patterns:
- Too-fast answers (reading from notes/AI)
- Inconsistent timing (copy-paste bursts)
- Perfect timing (automated submission)
- Temporal anomalies (impossible response times)

Author: Candway Engineering
"""

import statistics
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class TimingAnalysis:
    """Complete timing analysis for cheat detection"""

    avg_response_time: float
    min_response_time: float
    max_response_time: float
    std_dev: float
    too_fast_count: int
    too_fast_threshold: float
    consistency_score: float
    anomaly_flags: List[str] = field(default_factory=list)
    risk_level: str = "Low"
    detailed_timings: List[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "avg_response_time_sec": round(self.avg_response_time, 1),
            "min_response_time_sec": round(self.min_response_time, 1),
            "max_response_time_sec": round(self.max_response_time, 1),
            "std_dev_sec": round(self.std_dev, 1),
            "too_fast_count": self.too_fast_count,
            "too_fast_threshold_sec": round(self.too_fast_threshold, 1),
            "consistency_score": round(self.consistency_score, 1),
            "anomaly_flags": self.anomaly_flags,
            "risk_level": self.risk_level,
            "detailed_timings": self.detailed_timings,
        }


def analyze_response_timing(
    response_times: List[float],
    question_complexities: Optional[List[str]] = None,
    expected_read_time_wpm: int = 200,
) -> TimingAnalysis:
    """
    Analyze response times for cheat detection.

    Args:
        response_times: List of response times in seconds
        question_complexities: Optional list of complexity levels ("basic", "intermediate", "advanced")
        expected_read_time_wpm: Expected reading speed in words per minute

    Returns:
        TimingAnalysis with cheat indicators
    """
    if not response_times:
        return TimingAnalysis(
            avg_response_time=0,
            min_response_time=0,
            max_response_time=0,
            std_dev=0,
            too_fast_count=0,
            too_fast_threshold=0,
            consistency_score=100,
            risk_level="Low",
        )

    n = len(response_times)
    avg = statistics.mean(response_times)
    min_time = min(response_times)
    max_time = max(response_times)
    std_dev = statistics.stdev(response_times) if n > 1 else 0.0

    # Dynamic threshold: too fast depends on question complexity
    too_fast_thresholds = []
    if question_complexities:
        for complexity in question_complexities:
            if complexity == "basic":
                too_fast_thresholds.append(15.0)  # 15 seconds minimum
            elif complexity == "intermediate":
                too_fast_thresholds.append(25.0)  # 25 seconds minimum
            elif complexity == "advanced":
                too_fast_thresholds.append(40.0)  # 40 seconds minimum
            else:
                too_fast_thresholds.append(20.0)
    else:
        too_fast_thresholds = [20.0] * n  # Default 20 seconds

    avg_threshold = statistics.mean(too_fast_thresholds)
    too_fast_count = sum(
        1 for t, threshold in zip(response_times, too_fast_thresholds) if t < threshold
    )

    # Consistency score: low variance = suspicious (possibly automated)
    # High variance = natural human behavior
    cv = std_dev / avg if avg > 0 else 0  # Coefficient of variation
    consistency_score = min(100, cv * 100)  # Scale to 0-100

    # Anomaly detection
    anomaly_flags = []

    # 1. Too-fast detection
    if too_fast_count >= 3:
        anomaly_flags.append(
            f"{too_fast_count} answers submitted impossibly fast (likely reading from notes or AI)"
        )
    elif too_fast_count >= 1:
        anomaly_flags.append(f"{too_fast_count} answer(s) submitted suspiciously fast")

    # 2. Perfect timing detection (automated)
    if std_dev < 2.0 and n >= 3:
        anomaly_flags.append(
            "Near-perfect timing consistency — possible automated submission"
        )

    # 3. Burst detection (multiple answers in rapid succession)
    if n >= 3:
        rapid_pairs = sum(
            1
            for i in range(1, n)
            if response_times[i] < 10 and response_times[i - 1] < 10
        )
        if rapid_pairs >= 2:
            anomaly_flags.append(
                "Burst pattern detected — multiple rapid answers suggest copy-paste behavior"
            )

    # 4. Impossible speed (faster than reading the question)
    impossible_count = sum(1 for t in response_times if t < 5)
    if impossible_count >= 1:
        anomaly_flags.append(
            f"{impossible_count} answer(s) submitted faster than humanly possible to read the question"
        )

    # 5. Declining time pattern (getting faster unnaturally)
    if n >= 4:
        first_half_avg = statistics.mean(response_times[: n // 2])
        second_half_avg = statistics.mean(response_times[n // 2 :])
        if second_half_avg < first_half_avg * 0.3:
            anomaly_flags.append(
                "Response time decreased unnaturally — possible external assistance escalation"
            )

    # Risk level
    if len(anomaly_flags) >= 3:
        risk_level = "High"
    elif len(anomaly_flags) >= 1:
        risk_level = "Medium"
    else:
        risk_level = "Low"

    # Detailed timings
    detailed = []
    for i, (t, threshold) in enumerate(zip(response_times, too_fast_thresholds)):
        detailed.append(
            {
                "question_index": i + 1,
                "response_time_sec": round(t, 1),
                "threshold_sec": round(threshold, 1),
                "flagged": t < threshold,
            }
        )

    return TimingAnalysis(
        avg_response_time=avg,
        min_response_time=min_time,
        max_response_time=max_time,
        std_dev=std_dev,
        too_fast_count=too_fast_count,
        too_fast_threshold=avg_threshold,
        consistency_score=consistency_score,
        anomaly_flags=anomaly_flags,
        risk_level=risk_level,
        detailed_timings=detailed,
    )


def compute_timing_penalty(timing_analysis: TimingAnalysis) -> float:
    """
    Compute score penalty based on timing analysis.
    Returns 0-15 penalty points.
    """
    penalty = 0.0

    if timing_analysis.risk_level == "High":
        penalty += 10.0
    elif timing_analysis.risk_level == "Medium":
        penalty += 5.0

    # Additional penalty for impossible speeds
    impossible = sum(
        1 for d in timing_analysis.detailed_timings if d["response_time_sec"] < 5
    )
    penalty += impossible * 2.0

    # Cap at 15
    return min(15.0, penalty)


def estimate_answer_quality_from_timing(
    response_time: float,
    question_complexity: str = "intermediate",
    answer_length_words: int = 0,
) -> Dict[str, any]:
    """
    Estimate if the answer quality is plausible given the response time.
    Returns assessment with flags.
    """
    # Expected time ranges by complexity (seconds)
    expectations = {
        "basic": {"min": 15, "typical": 60, "max": 300},
        "intermediate": {"min": 25, "typical": 120, "max": 600},
        "advanced": {"min": 40, "typical": 180, "max": 900},
    }

    exp = expectations.get(question_complexity, expectations["intermediate"])

    flags = []
    quality_estimate = "plausible"

    if response_time < exp["min"]:
        quality_estimate = "suspicious"
        flags.append(f"Response too fast for {question_complexity} question")

    if answer_length_words > 0:
        words_per_second = (
            answer_length_words / response_time if response_time > 0 else 0
        )
        if words_per_second > 5:
            quality_estimate = "suspicious"
            flags.append(f"Typing speed implausible ({words_per_second:.1f} words/sec)")
        elif words_per_second < 0.1 and response_time > 60:
            flags.append("Very slow typing — possible copy-paste with editing")

    if response_time > exp["max"]:
        flags.append("Response time unusually long — may indicate external research")

    return {
        "quality_estimate": quality_estimate,
        "response_time_sec": response_time,
        "expected_range": f"{exp['min']}-{exp['max']} seconds",
        "flags": flags,
    }
