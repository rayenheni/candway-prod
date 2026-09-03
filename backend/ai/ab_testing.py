"""
A/B Testing Framework for Prompt Variants
===========================================

Enables controlled experiments on prompt variations.
Tracks:
- Score distribution differences
- Candidate experience metrics
- Evaluation consistency
- Statistical significance

Author: Candway Engineering
"""

import hashlib
import math
import statistics
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Dict, List, Optional


@dataclass
class ExperimentVariant:
    """A single variant in an A/B test"""

    name: str
    prompt_template: str
    temperature: float = 0.1
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "prompt_template": self.prompt_template[:100] + "...",
            "temperature": self.temperature,
            "metadata": self.metadata,
        }


@dataclass
class ExperimentResult:
    """Result from a single interview in an experiment"""

    experiment_id: str
    variant_name: str
    candidate_id: str
    score: float
    dimension_scores: Dict[str, float]
    duration_seconds: float
    metadata: dict = field(default_factory=dict)
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(UTC).isoformat()

    def to_dict(self) -> dict:
        return {
            "experiment_id": self.experiment_id,
            "variant_name": self.variant_name,
            "candidate_id": self.candidate_id,
            "score": round(self.score, 1),
            "dimension_scores": {
                k: round(v, 1) for k, v in self.dimension_scores.items()
            },
            "duration_seconds": round(self.duration_seconds, 1),
            "metadata": self.metadata,
            "timestamp": self.timestamp,
        }


@dataclass
class ABExperiment:
    """An active A/B test experiment"""

    id: str
    name: str
    description: str
    variants: List[ExperimentVariant]
    traffic_split: Dict[str, float]  # variant_name -> probability
    start_time: str
    end_time: Optional[str] = None
    results: List[ExperimentResult] = field(default_factory=list)
    status: str = "active"  # active, paused, completed
    min_sample_size: int = 30
    significance_level: float = 0.05

    def assign_variant(self, candidate_id: str) -> str:
        """Deterministically assign a variant based on candidate ID"""
        hash_val = int(hashlib.md5(candidate_id.encode()).hexdigest(), 16)
        normalized = hash_val % 1000 / 1000.0

        cumulative = 0
        for variant_name, probability in self.traffic_split.items():
            cumulative += probability
            if normalized < cumulative:
                return variant_name

        return list(self.traffic_split.keys())[-1]

    def add_result(self, result: ExperimentResult):
        self.results.append(result)

    def get_variant_results(self, variant_name: str) -> List[ExperimentResult]:
        return [r for r in self.results if r.variant_name == variant_name]

    def is_significant(self) -> bool:
        """Check if we have enough samples for statistical significance"""
        for variant in self.variants:
            results = self.get_variant_results(variant.name)
            if len(results) < self.min_sample_size:
                return False
        return True

    def compute_statistics(self) -> Dict[str, dict]:
        """Compute statistical comparison between variants"""
        stats = {}

        for variant in self.variants:
            results = self.get_variant_results(variant.name)
            if not results:
                stats[variant.name] = {"sample_count": 0}
                continue

            scores = [r.score for r in results]
            stats[variant.name] = {
                "sample_count": len(results),
                "mean_score": round(statistics.mean(scores), 1),
                "median_score": round(statistics.median(scores), 1),
                "std_dev": round(statistics.stdev(scores), 1) if len(scores) > 1 else 0,
                "min_score": round(min(scores), 1),
                "max_score": round(max(scores), 1),
                "score_distribution": self._compute_distribution(scores),
            }

        # Pairwise comparisons
        if len(self.variants) == 2:
            v1_results = self.get_variant_results(self.variants[0].name)
            v2_results = self.get_variant_results(self.variants[1].name)

            if len(v1_results) >= 10 and len(v2_results) >= 10:
                v1_scores = [r.score for r in v1_results]
                v2_scores = [r.score for r in v2_results]

                stats["comparison"] = {
                    "mean_difference": round(
                        statistics.mean(v1_scores) - statistics.mean(v2_scores), 1
                    ),
                    "p_value_approx": _approximate_p_value(v1_scores, v2_scores),
                    "significant": _approximate_p_value(v1_scores, v2_scores)
                    < self.significance_level,
                    "effect_size": _cohens_d(v1_scores, v2_scores),
                }

        return stats

    def _compute_distribution(self, scores: List[float]) -> dict:
        """Compute score distribution buckets"""
        buckets = {"0-20": 0, "21-40": 0, "41-60": 0, "61-80": 0, "81-100": 0}
        for score in scores:
            if score <= 20:
                buckets["0-20"] += 1
            elif score <= 40:
                buckets["21-40"] += 1
            elif score <= 60:
                buckets["41-60"] += 1
            elif score <= 80:
                buckets["61-80"] += 1
            else:
                buckets["81-100"] += 1

        total = len(scores)
        return {k: round(v / total * 100, 1) for k, v in buckets.items()}

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "variants": [v.to_dict() for v in self.variants],
            "traffic_split": self.traffic_split,
            "status": self.status,
            "total_results": len(self.results),
            "statistics": self.compute_statistics(),
            "is_significant": self.is_significant(),
            "start_time": self.start_time,
            "end_time": self.end_time,
        }


class ABTestManager:
    """Manages A/B test experiments"""

    def __init__(self):
        self.experiments: Dict[str, ABExperiment] = {}

    def create_experiment(
        self,
        name: str,
        description: str,
        variants: List[ExperimentVariant],
        traffic_split: Optional[Dict[str, float]] = None,
        min_sample_size: int = 30,
    ) -> ABExperiment:
        """Create a new A/B test experiment"""
        exp_id = hashlib.md5(
            f"{name}{datetime.now(UTC).isoformat()}".encode()
        ).hexdigest()[:8]

        if traffic_split is None:
            # Equal split
            split = {v.name: 1.0 / len(variants) for v in variants}
        else:
            split = traffic_split

        experiment = ABExperiment(
            id=exp_id,
            name=name,
            description=description,
            variants=variants,
            traffic_split=split,
            start_time=datetime.now(UTC).isoformat(),
            min_sample_size=min_sample_size,
        )

        self.experiments[exp_id] = experiment
        return experiment

    def get_experiment(self, exp_id: str) -> Optional[ABExperiment]:
        return self.experiments.get(exp_id)

    def get_active_experiments(self) -> List[ABExperiment]:
        return [e for e in self.experiments.values() if e.status == "active"]

    def complete_experiment(self, exp_id: str):
        exp = self.get_experiment(exp_id)
        if exp:
            exp.status = "completed"
            exp.end_time = datetime.now(UTC).isoformat()

    def pause_experiment(self, exp_id: str):
        exp = self.get_experiment(exp_id)
        if exp:
            exp.status = "paused"

    def record_result(self, exp_id: str, result: ExperimentResult):
        exp = self.get_experiment(exp_id)
        if exp:
            exp.add_result(result)

    def get_experiment_report(self, exp_id: str) -> dict:
        exp = self.get_experiment(exp_id)
        if not exp:
            return {"error": "Experiment not found"}
        return exp.to_dict()

    def list_experiments(self) -> List[dict]:
        return [
            {
                "id": e.id,
                "name": e.name,
                "status": e.status,
                "results_count": len(e.results),
                "is_significant": e.is_significant(),
            }
            for e in self.experiments.values()
        ]


def _approximate_p_value(group_a: List[float], group_b: List[float]) -> float:
    """Approximate p-value using Welch's t-test"""
    n_a, n_b = len(group_a), len(group_b)
    if n_a < 2 or n_b < 2:
        return 1.0

    mean_a = statistics.mean(group_a)
    mean_b = statistics.mean(group_b)
    var_a = statistics.variance(group_a)
    var_b = statistics.variance(group_b)

    se = math.sqrt(var_a / n_a + var_b / n_b)
    if se == 0:
        return 1.0

    t_stat = abs(mean_a - mean_b) / se

    # Rough p-value approximation
    df = (var_a / n_a + var_b / n_b) ** 2 / (
        (var_a / n_a) ** 2 / (n_a - 1) + (var_b / n_b) ** 2 / (n_b - 1)
    )

    # Simplified: use t-stat to approximate p-value
    p_value = 2 * (1 - min(1, t_stat / (2 + df / 10)))
    return max(0.001, min(1.0, p_value))


def _cohens_d(group_a: List[float], group_b: List[float]) -> float:
    """Compute Cohen's d effect size"""
    n_a, n_b = len(group_a), len(group_b)
    if n_a < 2 or n_b < 2:
        return 0.0

    mean_a = statistics.mean(group_a)
    mean_b = statistics.mean(group_b)
    var_a = statistics.variance(group_a)
    var_b = statistics.variance(group_b)

    pooled_std = math.sqrt(((n_a - 1) * var_a + (n_b - 1) * var_b) / (n_a + n_b - 2))
    if pooled_std == 0:
        return 0.0

    return (mean_a - mean_b) / pooled_std


# Global manager instance
ab_test_manager = ABTestManager()
