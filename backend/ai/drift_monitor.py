"""
Model Drift Monitoring
========================

Tracks AI model behavior over time to detect:
- Score distribution drift
- Evaluation consistency changes
- Response time degradation
- Prompt injection pattern evolution
- Model version changes

Author: Candway Engineering
"""

import statistics
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Dict, List, Optional


def _parse_timestamp(value: str) -> datetime:
    """Parse an ISO-8601 timestamp and always return a
    timezone-aware datetime. If the input is naive (no offset
    suffix), assume UTC — this is the safe default for our
    snapshot pipeline.

    The previous implementation used ``datetime.fromisoformat``
    directly, which returns a naive datetime for naive strings
    and then crashes when compared against the UTC-aware
    ``cutoff`` returned by ``datetime.now(UTC)``.
    """
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed


@dataclass
class DriftMetric:
    """A single drift measurement"""

    metric_name: str
    current_value: float
    baseline_value: float
    drift_amount: float
    drift_percentage: float
    timestamp: str
    severity: str = "none"  # none, low, medium, high, critical

    def to_dict(self) -> dict:
        return {
            "metric_name": self.metric_name,
            "current_value": round(self.current_value, 2),
            "baseline_value": round(self.baseline_value, 2),
            "drift_amount": round(self.drift_amount, 2),
            "drift_percentage": round(self.drift_percentage, 1),
            "timestamp": self.timestamp,
            "severity": self.severity,
        }


@dataclass
class ModelSnapshot:
    """Snapshot of model behavior at a point in time"""

    timestamp: str
    model_version: str
    sample_count: int
    mean_score: float
    std_dev: float
    median_score: float
    p25_score: float
    p75_score: float
    avg_response_time: float
    error_rate: float
    dimension_averages: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "model_version": self.model_version,
            "sample_count": self.sample_count,
            "mean_score": round(self.mean_score, 1),
            "std_dev": round(self.std_dev, 1),
            "median_score": round(self.median_score, 1),
            "percentiles": {
                "p25": round(self.p25_score, 1),
                "p75": round(self.p75_score, 1),
            },
            "avg_response_time_sec": round(self.avg_response_time, 1),
            "error_rate": round(self.error_rate, 2),
            "dimension_averages": {
                k: round(v, 1) for k, v in self.dimension_averages.items()
            },
        }


@dataclass
class DriftReport:
    """Complete drift analysis report"""

    baseline_period: str
    current_period: str
    metrics: List[DriftMetric] = field(default_factory=list)
    alerts: List[str] = field(default_factory=list)
    overall_drift_score: float = 0.0
    recommendation: str = ""

    def to_dict(self) -> dict:
        return {
            "baseline_period": self.baseline_period,
            "current_period": self.current_period,
            "metrics": [m.to_dict() for m in self.metrics],
            "alerts": self.alerts,
            "overall_drift_score": round(self.overall_drift_score, 2),
            "recommendation": self.recommendation,
            "status": "healthy"
            if self.overall_drift_score < 0.1
            else "warning"
            if self.overall_drift_score < 0.25
            else "critical",
        }


class DriftMonitor:
    """
    Monitors AI model behavior for drift over time.
    """

    def __init__(self, baseline_window_days: int = 30):
        self.baseline_window = timedelta(days=baseline_window_days)
        self.snapshots: List[ModelSnapshot] = []
        self.baseline: Optional[ModelSnapshot] = None

    def record_snapshot(self, snapshot: ModelSnapshot):
        """Record a new model behavior snapshot"""
        self.snapshots.append(snapshot)
        self.snapshots.sort(key=lambda s: s.timestamp)

        # Update baseline if needed
        if not self.baseline or self._should_update_baseline():
            self._compute_baseline()

    def _should_update_baseline(self) -> bool:
        """Check if baseline should be recomputed"""
        if not self.baseline:
            return True

        cutoff = datetime.now(UTC) - self.baseline_window
        baseline_time = _parse_timestamp(self.baseline.timestamp)
        return baseline_time < cutoff

    def _compute_baseline(self):
        """Compute baseline from recent snapshots"""
        cutoff = datetime.now(UTC) - self.baseline_window
        recent = [s for s in self.snapshots if _parse_timestamp(s.timestamp) >= cutoff]

        if not recent:
            return

        # Aggregate recent snapshots into baseline
        all_scores = []
        all_times = []
        all_errors = []
        dim_totals: Dict[str, List[float]] = {}

        for snapshot in recent:
            all_scores.append(snapshot.mean_score)
            all_times.append(snapshot.avg_response_time)
            all_errors.append(snapshot.error_rate)

            for dim, val in snapshot.dimension_averages.items():
                if dim not in dim_totals:
                    dim_totals[dim] = []
                dim_totals[dim].append(val)

        self.baseline = ModelSnapshot(
            timestamp=datetime.now(UTC).isoformat(),
            model_version=recent[-1].model_version,
            sample_count=sum(s.sample_count for s in recent),
            mean_score=statistics.mean(all_scores),
            std_dev=statistics.stdev(all_scores) if len(all_scores) > 1 else 0,
            median_score=statistics.median(all_scores),
            p25_score=sorted(all_scores)[len(all_scores) // 4]
            if len(all_scores) >= 4
            else all_scores[0],
            p75_score=sorted(all_scores)[3 * len(all_scores) // 4]
            if len(all_scores) >= 4
            else all_scores[-1],
            avg_response_time=statistics.mean(all_times),
            error_rate=statistics.mean(all_errors),
            dimension_averages={
                dim: statistics.mean(vals) for dim, vals in dim_totals.items()
            },
        )

    def detect_drift(self, current: ModelSnapshot) -> DriftReport:
        """
        Detect drift between baseline and current snapshot.
        """
        if not self.baseline:
            return DriftReport(
                baseline_period="No baseline established",
                current_period=current.timestamp,
                recommendation="Collect more data to establish baseline",
            )

        report = DriftReport(
            baseline_period=self.baseline.timestamp, current_period=current.timestamp
        )

        # 1. Score distribution drift
        score_drift = abs(current.mean_score - self.baseline.mean_score)
        score_drift_pct = (
            (score_drift / self.baseline.mean_score * 100)
            if self.baseline.mean_score > 0
            else 0
        )

        severity = "none"
        if score_drift_pct >= 15:
            severity = "critical"
        elif score_drift_pct >= 10:
            severity = "high"
        elif score_drift_pct >= 5:
            severity = "medium"
        elif score_drift_pct >= 2:
            severity = "low"

        report.metrics.append(
            DriftMetric(
                metric_name="mean_score",
                current_value=current.mean_score,
                baseline_value=self.baseline.mean_score,
                drift_amount=score_drift,
                drift_percentage=score_drift_pct,
                timestamp=current.timestamp,
                severity=severity,
            )
        )

        if severity in ["high", "critical"]:
            report.alerts.append(
                f"Score drift detected: {score_drift_pct:.1f}% change from baseline"
            )

        # 2. Variance drift
        if self.baseline.std_dev > 0:
            var_drift = (
                abs(current.std_dev - self.baseline.std_dev) / self.baseline.std_dev
            )
            var_severity = (
                "high"
                if var_drift > 0.5
                else "medium"
                if var_drift > 0.3
                else "low"
                if var_drift > 0.1
                else "none"
            )

            report.metrics.append(
                DriftMetric(
                    metric_name="score_variance",
                    current_value=current.std_dev,
                    baseline_value=self.baseline.std_dev,
                    drift_amount=var_drift * self.baseline.std_dev,
                    drift_percentage=var_drift * 100,
                    timestamp=current.timestamp,
                    severity=var_severity,
                )
            )

            if var_severity in ["high", "critical"]:
                report.alerts.append(
                    f"Score variance changed significantly: {var_drift * 100:.0f}%"
                )

        # 3. Response time drift
        if self.baseline.avg_response_time > 0:
            time_drift = (
                current.avg_response_time - self.baseline.avg_response_time
            ) / self.baseline.avg_response_time
            time_severity = (
                "high"
                if time_drift > 0.5
                else "medium"
                if time_drift > 0.2
                else "low"
                if time_drift > 0.1
                else "none"
            )

            report.metrics.append(
                DriftMetric(
                    metric_name="response_time",
                    current_value=current.avg_response_time,
                    baseline_value=self.baseline.avg_response_time,
                    drift_amount=current.avg_response_time
                    - self.baseline.avg_response_time,
                    drift_percentage=time_drift * 100,
                    timestamp=current.timestamp,
                    severity=time_severity,
                )
            )

            if time_severity == "high":
                report.alerts.append(
                    f"Response time degraded: {time_drift * 100:.0f}% slower"
                )

        # 4. Error rate drift
        if current.error_rate > self.baseline.error_rate * 2:
            report.metrics.append(
                DriftMetric(
                    metric_name="error_rate",
                    current_value=current.error_rate,
                    baseline_value=self.baseline.error_rate,
                    drift_amount=current.error_rate - self.baseline.error_rate,
                    drift_percentage=(
                        (current.error_rate - self.baseline.error_rate)
                        / self.baseline.error_rate
                        * 100
                    )
                    if self.baseline.error_rate > 0
                    else 0,
                    timestamp=current.timestamp,
                    severity="high",
                )
            )
            report.alerts.append(
                f"Error rate increased: {current.error_rate:.1%} vs {self.baseline.error_rate:.1%} baseline"
            )

        # 5. Dimension drift
        for dim in set(
            list(current.dimension_averages.keys())
            + list(self.baseline.dimension_averages.keys())
        ):
            current_val = current.dimension_averages.get(dim, 50)
            baseline_val = self.baseline.dimension_averages.get(dim, 50)

            if baseline_val > 0:
                dim_drift = abs(current_val - baseline_val) / baseline_val * 100
                dim_severity = (
                    "high"
                    if dim_drift > 15
                    else "medium"
                    if dim_drift > 10
                    else "low"
                    if dim_drift > 5
                    else "none"
                )

                report.metrics.append(
                    DriftMetric(
                        metric_name=f"dimension_{dim}",
                        current_value=current_val,
                        baseline_value=baseline_val,
                        drift_amount=current_val - baseline_val,
                        drift_percentage=dim_drift,
                        timestamp=current.timestamp,
                        severity=dim_severity,
                    )
                )

        # Overall drift score
        severities = {"none": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}
        total_severity = sum(severities.get(m.severity, 0) for m in report.metrics)
        max_possible = len(report.metrics) * 4
        report.overall_drift_score = (
            total_severity / max_possible if max_possible > 0 else 0
        )

        # Recommendation
        if report.overall_drift_score >= 0.5:
            report.recommendation = "CRITICAL: Model behavior has drifted significantly. Recalibrate scoring system and review prompt templates."
        elif report.overall_drift_score >= 0.25:
            report.recommendation = "WARNING: Moderate drift detected. Monitor closely and consider recalibration."
        elif report.overall_drift_score >= 0.1:
            report.recommendation = "Minor drift detected. Continue monitoring."
        else:
            report.recommendation = "Model behavior is stable. No action needed."

        return report

    def get_drift_history(self, days: int = 30) -> List[dict]:
        """Get drift history over time"""
        cutoff = datetime.now(UTC) - timedelta(days=days)
        recent = [s for s in self.snapshots if _parse_timestamp(s.timestamp) >= cutoff]

        return [s.to_dict() for s in recent]


# Global monitor instance
drift_monitor = DriftMonitor()


def create_snapshot_from_interviews(
    interviews: List[dict], model_version: str, timestamp: str = None
) -> ModelSnapshot:
    """
    Create a model snapshot from a batch of interview results.

    Args:
        interviews: List of {score, dimension_scores, response_time, error}
        model_version: Current model version string
        timestamp: ISO timestamp

    Returns:
        ModelSnapshot
    """
    if not interviews:
        return ModelSnapshot(
            timestamp=timestamp or datetime.now(UTC).isoformat(),
            model_version=model_version,
            sample_count=0,
            mean_score=0,
            std_dev=0,
            median_score=0,
            p25_score=0,
            p75_score=0,
            avg_response_time=0,
            error_rate=0,
        )

    scores = [i.get("score", 50) for i in interviews]
    times = [i.get("response_time", 0) for i in interviews]
    errors = sum(1 for i in interviews if i.get("error"))

    # Dimension averages
    dim_totals: Dict[str, List[float]] = {}
    for interview in interviews:
        dims = interview.get("dimension_scores", {})
        for dim, val in dims.items():
            if dim not in dim_totals:
                dim_totals[dim] = []
            dim_totals[dim].append(val)

    dim_averages = {dim: statistics.mean(vals) for dim, vals in dim_totals.items()}

    sorted_scores = sorted(scores)
    n = len(sorted_scores)

    return ModelSnapshot(
        timestamp=timestamp or datetime.now(UTC).isoformat(),
        model_version=model_version,
        sample_count=len(interviews),
        mean_score=statistics.mean(scores),
        std_dev=statistics.stdev(scores) if n > 1 else 0,
        median_score=statistics.median(scores),
        p25_score=sorted_scores[n // 4] if n >= 4 else sorted_scores[0],
        p75_score=sorted_scores[3 * n // 4] if n >= 4 else sorted_scores[-1],
        avg_response_time=statistics.mean(times) if times else 0,
        error_rate=errors / len(interviews),
        dimension_averages=dim_averages,
    )
