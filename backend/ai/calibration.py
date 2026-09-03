"""
Calibration Dataset Infrastructure
====================================

Stores and manages human-annotated interview scores for AI calibration.
Enables:
- AI-to-human score comparison
- Calibration curve fitting
- Inter-rater reliability measurement
- Continuous model improvement tracking

Author: Candway Engineering
"""

import statistics
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Dict, List, Optional


@dataclass
class CalibrationSample:
    """A single human-annotated interview for calibration"""

    sample_id: str
    role: str
    seniority: str
    qa_pairs: List[dict]
    human_scores: Dict[str, float]  # Multiple human raters
    ai_scores: Dict[str, float]
    metadata: dict = field(default_factory=dict)
    created_at: str = ""

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now(UTC).isoformat()

    @property
    def human_consensus(self) -> Dict[str, float]:
        """Average of human scores across raters"""
        consensus = {}
        for dimension in set().union(*[s.keys() for s in self.human_scores.values()]):
            scores = [
                s[dimension] for s in self.human_scores.values() if dimension in s
            ]
            if scores:
                consensus[dimension] = statistics.mean(scores)
        return consensus

    @property
    def inter_rater_reliability(self) -> float:
        """Measure agreement between human raters (0-1)"""
        if len(self.human_scores) < 2:
            return 1.0

        all_scores = list(self.human_scores.values())
        dimensions = set().union(*[s.keys() for s in all_scores])

        reliabilities = []
        for dim in dimensions:
            dim_scores = [s[dim] for s in all_scores if dim in s]
            if len(dim_scores) >= 2:
                statistics.mean(dim_scores)
                variance = statistics.variance(dim_scores)
                # ICC-like metric: 1 - (variance / max_possible_variance)
                max_var = 2500  # (100/2)^2
                reliabilities.append(1 - min(1, variance / max_var))

        return statistics.mean(reliabilities) if reliabilities else 1.0

    def to_dict(self) -> dict:
        return {
            "sample_id": self.sample_id,
            "role": self.role,
            "seniority": self.seniority,
            "human_scores": self.human_scores,
            "ai_scores": self.ai_scores,
            "human_consensus": self.human_consensus,
            "inter_rater_reliability": round(self.inter_rater_reliability, 2),
            "metadata": self.metadata,
            "created_at": self.created_at,
        }


@dataclass
class CalibrationDataset:
    """Collection of calibration samples"""

    name: str
    samples: List[CalibrationSample] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now(UTC).isoformat()

    def add_sample(self, sample: CalibrationSample):
        self.samples.append(sample)
        self.updated_at = datetime.now(UTC).isoformat()

    def get_by_role(self, role: str) -> List[CalibrationSample]:
        return [s for s in self.samples if s.role.lower() == role.lower()]

    def get_by_seniority(self, seniority: str) -> List[CalibrationSample]:
        return [s for s in self.samples if s.seniority.lower() == seniority.lower()]

    @property
    def avg_inter_rater_reliability(self) -> float:
        """Average IRR across all samples"""
        if not self.samples:
            return 0.0
        return statistics.mean(s.inter_rater_reliability for s in self.samples)

    def compute_ai_human_correlation(self) -> Dict[str, float]:
        """
        Compute correlation between AI and human scores per dimension.
        Returns dict of dimension -> correlation coefficient.
        """
        if len(self.samples) < 3:
            return {}

        dimensions = set()
        for sample in self.samples:
            dimensions.update(sample.human_consensus.keys())
            dimensions.update(sample.ai_scores.keys())

        correlations = {}
        for dim in dimensions:
            human_scores = []
            ai_scores = []

            for sample in self.samples:
                h = sample.human_consensus.get(dim)
                a = sample.ai_scores.get(dim)
                if h is not None and a is not None:
                    human_scores.append(h)
                    ai_scores.append(a)

            if len(human_scores) >= 3:
                correlations[dim] = _pearson_correlation(human_scores, ai_scores)

        return correlations

    def compute_calibration_error(self) -> Dict[str, float]:
        """
        Compute mean absolute error between AI and human scores.
        """
        if not self.samples:
            return {}

        dimensions = set()
        for sample in self.samples:
            dimensions.update(sample.human_consensus.keys())
            dimensions.update(sample.ai_scores.keys())

        errors = {}
        for dim in dimensions:
            abs_errors = []
            for sample in self.samples:
                h = sample.human_consensus.get(dim)
                a = sample.ai_scores.get(dim)
                if h is not None and a is not None:
                    abs_errors.append(abs(h - a))

            if abs_errors:
                errors[dim] = statistics.mean(abs_errors)

        return errors

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "sample_count": len(self.samples),
            "avg_inter_rater_reliability": round(self.avg_inter_rater_reliability, 2),
            "ai_human_correlation": {
                k: round(v, 2) for k, v in self.compute_ai_human_correlation().items()
            },
            "calibration_error": {
                k: round(v, 1) for k, v in self.compute_calibration_error().items()
            },
            "samples": [s.to_dict() for s in self.samples],
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


def _pearson_correlation(x: List[float], y: List[float]) -> float:
    """Compute Pearson correlation coefficient"""
    n = len(x)
    if n < 2:
        return 0.0

    mean_x = statistics.mean(x)
    mean_y = statistics.mean(y)

    numerator = sum((xi - mean_x) * (yi - mean_y) for xi, yi in zip(x, y))
    denom_x = math.sqrt(sum((xi - mean_x) ** 2 for xi in x))
    denom_y = math.sqrt(sum((yi - mean_y) ** 2 for yi in y))

    if denom_x == 0 or denom_y == 0:
        return 0.0

    return numerator / (denom_x * denom_y)


import math  # noqa: E402


def create_calibration_sample(
    sample_id: str,
    role: str,
    seniority: str,
    qa_pairs: List[dict],
    human_ratings: Dict[str, Dict[str, float]],
    ai_scores: Dict[str, float],
    metadata: dict = None,
) -> CalibrationSample:
    """
    Factory function to create a calibration sample.

    Args:
        sample_id: Unique identifier
        role: Target role
        seniority: Seniority level
        qa_pairs: Interview Q&A pairs
        human_ratings: {"rater_1": {"Technical": 80, ...}, "rater_2": {...}}
        ai_scores: AI-generated scores
        metadata: Additional context

    Returns:
        CalibrationSample
    """
    return CalibrationSample(
        sample_id=sample_id,
        role=role,
        seniority=seniority,
        qa_pairs=qa_pairs,
        human_scores=human_ratings,
        ai_scores=ai_scores,
        metadata=metadata or {},
    )


class CalibrationStore:
    """
    In-memory store for calibration datasets.
    In production, this would be backed by a database.
    """

    def __init__(self):
        self.datasets: Dict[str, CalibrationDataset] = {}

    def create_dataset(self, name: str) -> CalibrationDataset:
        if name in self.datasets:
            return self.datasets[name]
        dataset = CalibrationDataset(name=name)
        self.datasets[name] = dataset
        return dataset

    def get_dataset(self, name: str) -> Optional[CalibrationDataset]:
        return self.datasets.get(name)

    def list_datasets(self) -> List[str]:
        return list(self.datasets.keys())

    def add_sample(self, dataset_name: str, sample: CalibrationSample):
        dataset = self.get_dataset(dataset_name)
        if dataset:
            dataset.add_sample(sample)

    def get_calibration_report(self, dataset_name: str) -> dict:
        """Generate comprehensive calibration report"""
        dataset = self.get_dataset(dataset_name)
        if not dataset:
            return {"error": "Dataset not found"}

        return {
            "dataset": dataset.name,
            "sample_count": len(dataset.samples),
            "avg_inter_rater_reliability": round(
                dataset.avg_inter_rater_reliability, 2
            ),
            "ai_human_correlation": {
                k: round(v, 2)
                for k, v in dataset.compute_ai_human_correlation().items()
            },
            "calibration_error": {
                k: round(v, 1) for k, v in dataset.compute_calibration_error().items()
            },
            "by_role": self._group_by_role(dataset),
            "by_seniority": self._group_by_seniority(dataset),
        }

    def _group_by_role(self, dataset: CalibrationDataset) -> dict:
        roles = set(s.role for s in dataset.samples)
        result = {}
        for role in roles:
            samples = dataset.get_by_role(role)
            if samples:
                avg_irr = statistics.mean(s.inter_rater_reliability for s in samples)
                result[role] = {
                    "sample_count": len(samples),
                    "avg_inter_rater_reliability": round(avg_irr, 2),
                }
        return result

    def _group_by_seniority(self, dataset: CalibrationDataset) -> dict:
        seniorities = set(s.seniority for s in dataset.samples)
        result = {}
        for seniority in seniorities:
            samples = dataset.get_by_seniority(seniority)
            if samples:
                avg_irr = statistics.mean(s.inter_rater_reliability for s in samples)
                result[seniority] = {
                    "sample_count": len(samples),
                    "avg_inter_rater_reliability": round(avg_irr, 2),
                }
        return result


# Global store instance
calibration_store = CalibrationStore()
