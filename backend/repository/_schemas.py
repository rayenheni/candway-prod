"""Return-type schemas for metrics_repository functions.

Pure data containers — no logic. Every repository function returns one of these.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class DashboardMetrics:
    total_applications: int = 0
    total_candidates: int = 0
    hired: int = 0
    status_counts: dict = field(default_factory=dict)
    avg_score: Optional[float] = None
    ai_matches: int = 0
    flagged: int = 0
    avg_time_to_hire: Optional[float] = None
    sources: dict = field(default_factory=dict)
    active_jobs: int = 0


@dataclass
class FunnelMetrics:
    applied: int = 0
    screening: int = 0
    interview: int = 0
    offer: int = 0
    hired: int = 0
    rejected: int = 0


@dataclass
class ConversionRates:
    app_to_interview: float = 0.0
    interview_to_offer: float = 0.0
    offer_to_hired: float = 0.0
    overall: float = 0.0


@dataclass
class TrendPoint:
    date: str
    count: int


@dataclass
class InterviewMetrics:
    total: int = 0
    scheduled: int = 0
    completed: int = 0
    cancelled: int = 0
    today: int = 0
    no_show: int = 0


@dataclass
class CampaignStats:
    total_candidates: int = 0
    avg_cv_score: Optional[float] = None
    interviewed: int = 0
    invited: int = 0
    opened: int = 0
