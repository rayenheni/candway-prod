"""
Metrics and Monitoring Module for Interview System
Tracks key performance indicators and system health.
Uses prometheus_client for production-grade metrics collection,
while maintaining backward compatibility with the existing
InterviewMetrics singleton interface.
"""

import threading
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List

from backend.logger import logger

# --- Prometheus Metrics (production-grade) ---
try:
    from prometheus_client import Counter, Gauge, Histogram

    _PROMETHEUS_AVAILABLE = True
except ImportError:
    _PROMETHEUS_AVAILABLE = False
    logger.warning(
        "[METRICS] prometheus_client not installed — using in-process counters only"
    )

if _PROMETHEUS_AVAILABLE:
    prom_interviews_started = Counter(
        "candway_interviews_started_total", "Total interviews started"
    )
    prom_interviews_completed = Counter(
        "candway_interviews_completed_total", "Total interviews completed"
    )
    prom_interviews_failed = Counter(
        "candway_interviews_failed_total", "Total interviews failed", ["error_type"]
    )
    prom_ai_calls_total = Counter(
        "candway_ai_calls_total", "Total AI API calls", ["status"]
    )
    prom_ai_response_time = Histogram(
        "candway_ai_response_seconds",
        "AI API response time in seconds",
        buckets=(0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0, float("inf")),
    )
    prom_interview_duration = Histogram(
        "candway_interview_duration_seconds",
        "Interview duration in seconds",
        buckets=(60, 180, 300, 600, 900, 1800, 3600, float("inf")),
    )
    prom_ai_timeouts = Counter("candway_ai_timeouts_total", "Total AI API timeouts")
    prom_scores = Gauge(
        "candway_current_score", "Latest overall score", ["application_id"]
    )
    prom_active_interviews = Gauge(
        "candway_active_interviews", "Number of currently active interviews"
    )
else:
    prom_interviews_started = prom_interviews_completed = prom_interviews_failed = None
    prom_ai_calls_total = prom_ai_response_time = prom_interview_duration = None
    prom_ai_timeouts = prom_scores = prom_active_interviews = None


@dataclass
class InterviewMetrics:
    """Thread-safe metrics collector for interview system"""

    # Counters
    interviews_started: int = 0
    interviews_completed: int = 0
    interviews_failed: int = 0

    # AI API Metrics
    ai_calls_total: int = 0
    ai_calls_success: int = 0
    ai_calls_failed: int = 0
    ai_timeouts: int = 0

    # Response Times (in seconds)
    ai_response_times: List[float] = field(default_factory=list)
    interview_durations: List[float] = field(default_factory=list)

    # Error Tracking
    errors_by_type: Dict[str, int] = field(default_factory=lambda: defaultdict(int))

    # Score Distribution
    scores: List[float] = field(default_factory=list)

    # Thread lock for concurrent access
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def record_interview_start(self):
        """Record interview start event"""
        with self._lock:
            self.interviews_started += 1
        if prom_interviews_started:
            prom_interviews_started.inc()
        if prom_active_interviews:
            prom_active_interviews.inc()

    def record_interview_complete(self, duration_seconds: float, final_score: float):
        """Record successful interview completion"""
        with self._lock:
            self.interviews_completed += 1
            self.interview_durations.append(duration_seconds)
            self.scores.append(final_score)
        if prom_interviews_completed:
            prom_interviews_completed.inc()
        if prom_interview_duration:
            prom_interview_duration.observe(duration_seconds)
        if prom_active_interviews:
            prom_active_interviews.dec()

    def record_interview_failure(self, error_type: str):
        """Record interview failure"""
        with self._lock:
            self.interviews_failed += 1
            self.errors_by_type[error_type] += 1
        if prom_interviews_failed:
            prom_interviews_failed.labels(error_type=error_type).inc()
        if prom_active_interviews:
            prom_active_interviews.dec()

    def record_ai_call(
        self, success: bool, response_time: float = None, timeout: bool = False
    ):
        """Record AI API call"""
        with self._lock:
            self.ai_calls_total += 1
            if success:
                self.ai_calls_success += 1
                if response_time:
                    self.ai_response_times.append(response_time)
            else:
                self.ai_calls_failed += 1
            if timeout:
                self.ai_timeouts += 1
        status = "success" if success else "failure"
        if prom_ai_calls_total:
            prom_ai_calls_total.labels(status=status).inc()
        if success and response_time and prom_ai_response_time:
            prom_ai_response_time.observe(response_time)
        if timeout and prom_ai_timeouts:
            prom_ai_timeouts.inc()

    def get_summary(self) -> dict:
        """Get metrics summary (thread-safe)"""
        with self._lock:
            return {
                "interviews": {
                    "started": self.interviews_started,
                    "completed": self.interviews_completed,
                    "failed": self.interviews_failed,
                    "completion_rate": (
                        self.interviews_completed / self.interviews_started * 100
                        if self.interviews_started > 0
                        else 0
                    ),
                },
                "ai_api": {
                    "total_calls": self.ai_calls_total,
                    "success_rate": (
                        self.ai_calls_success / self.ai_calls_total * 100
                        if self.ai_calls_total > 0
                        else 0
                    ),
                    "timeout_rate": (
                        self.ai_timeouts / self.ai_calls_total * 100
                        if self.ai_calls_total > 0
                        else 0
                    ),
                    "avg_response_time": (
                        sum(self.ai_response_times) / len(self.ai_response_times)
                        if self.ai_response_times
                        else 0
                    ),
                },
                "performance": {
                    "avg_interview_duration": (
                        sum(self.interview_durations) / len(self.interview_durations)
                        if self.interview_durations
                        else 0
                    ),
                    "avg_score": (
                        sum(self.scores) / len(self.scores) if self.scores else 0
                    ),
                },
                "errors": dict(self.errors_by_type),
            }

    def reset(self):
        """Reset all metrics (for testing or periodic reset)"""
        with self._lock:
            self.interviews_started = 0
            self.interviews_completed = 0
            self.interviews_failed = 0
            self.ai_calls_total = 0
            self.ai_calls_success = 0
            self.ai_calls_failed = 0
            self.ai_timeouts = 0
            self.ai_response_times.clear()
            self.interview_durations.clear()
            self.errors_by_type.clear()
            self.scores.clear()


# Global metrics instance
interview_metrics = InterviewMetrics()


# Convenience functions for easy access
def record_interview_start():
    interview_metrics.record_interview_start()


def record_interview_complete(duration: float, score: float):
    interview_metrics.record_interview_complete(duration, score)


def record_interview_failure(error_type: str):
    interview_metrics.record_interview_failure(error_type)


def record_ai_call(success: bool, response_time: float = None, timeout: bool = False):
    interview_metrics.record_ai_call(success, response_time, timeout)


def get_metrics_summary() -> dict:
    return interview_metrics.get_summary()
