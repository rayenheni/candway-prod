"""
Tests for Advanced Scoring Features
=====================================

Tests for:
- Explainable scoring layer
- Confidence intervals
- Timing analysis
- Knowledge graph
- Bias detection
- Calibration infrastructure
- A/B testing framework
- Drift monitoring

Author: Candway Engineering
"""

import statistics
from datetime import UTC, datetime

import pytest

from backend.ai.ab_testing import (
    ABExperiment,
    ABTestManager,
    ExperimentResult,
    ExperimentVariant,
)
from backend.ai.bias_detection import (
    BiasAuditReport,
    compute_statistical_parity,
    detect_cultural_bias,
    detect_language_bias,
    detect_length_bias,
    detect_style_bias,
    run_bias_audit,
)
from backend.ai.calibration import (
    CalibrationDataset,
    CalibrationSample,
    CalibrationStore,
    create_calibration_sample,
)
from backend.ai.drift_monitor import (
    DriftMonitor,
    ModelSnapshot,
    create_snapshot_from_interviews,
)
from backend.ai.explainable_scoring import (
    ExplainableScore,
    analyze_dimension_performance,
    compute_confidence_interval,
    generate_explainable_score,
)
from backend.ai.knowledge_graph import (
    MasteryLevel,
    assess_mastery_level,
    build_knowledge_graph,
    extract_concepts_from_answer,
    get_concept_mastery_report,
)
from backend.ai.timing_analysis import (
    TimingAnalysis,
    analyze_response_timing,
    compute_timing_penalty,
    estimate_answer_quality_from_timing,
)
from backend.scoring_transparent import (
    calculate_overall_score,
    get_recommendation,
    get_score_label,
)

# =============================================================================
# EXPLAINABLE SCORING TESTS
# =============================================================================


class TestExplainableScoring:
    def test_confidence_interval_narrow_with_many_samples(self):
        """More samples = narrower confidence interval"""
        scores = [70, 72, 68, 71, 69, 73, 70, 72, 68, 71, 69, 73, 70, 72, 68]
        ci = compute_confidence_interval(scores)

        assert ci.point_estimate == pytest.approx(statistics.mean(scores), abs=0.1)
        assert ci.lower_bound <= ci.point_estimate
        assert ci.upper_bound >= ci.point_estimate
        assert ci.margin_of_error < 5  # Should be narrow with 15 samples

    def test_confidence_interval_wide_with_few_samples(self):
        """Few samples = wider confidence interval"""
        scores = [60, 80]
        ci = compute_confidence_interval(scores)

        assert ci.margin_of_error > 10  # Should be wide with only 2 samples

    def test_confidence_interval_with_single_sample(self):
        """Single sample should have maximum uncertainty"""
        ci = compute_confidence_interval([75])

        assert ci.point_estimate == 75
        assert ci.lower_bound == 0.0
        assert ci.upper_bound == 100.0

    def test_explainable_score_generation(self):
        """Test full explainable score generation"""
        explainable = generate_explainable_score(
            final_score=75.0,
            dimension_scores={
                "Technical": 80,
                "Communication": 70,
                "Problem Solving": 75,
                "Adaptability": 65,
                "Confidence": 70,
            },
            question_scores=[70, 72, 68, 75, 78, 80],
            role="Python Developer",
            seniority="Mid",
        )

        assert isinstance(explainable, ExplainableScore)
        assert explainable.final_score == 75.0
        assert explainable.why_this_score != ""
        assert explainable.confidence_interval is not None
        assert len(explainable.dimension_explanations) == 5

    def test_explainable_score_identifies_strengths(self):
        """Should identify dimensions that exceed expectations"""
        explainable = generate_explainable_score(
            final_score=85.0,
            dimension_scores={
                "Technical": 95,
                "Communication": 80,
                "Problem Solving": 90,
                "Adaptability": 85,
                "Confidence": 80,
            },
            question_scores=[80, 85, 88, 90, 92],
            role="Senior Engineer",
            seniority="Senior",
        )

        assert len(explainable.strengths) > 0
        assert any("Technical" in s for s in explainable.strengths)

    def test_explainable_score_identifies_weaknesses(self):
        """Should identify dimensions below expectations"""
        explainable = generate_explainable_score(
            final_score=55.0,
            dimension_scores={
                "Technical": 45,
                "Communication": 60,
                "Problem Solving": 50,
                "Adaptability": 55,
                "Confidence": 65,
            },
            question_scores=[50, 48, 52, 55, 60],
            role="Python Developer",
            seniority="Senior",
        )

        assert len(explainable.weaknesses) > 0
        assert len(explainable.gaps) > 0

    def test_explainable_score_risk_factors(self):
        """Should identify risk factors"""
        explainable = generate_explainable_score(
            final_score=60.0,
            dimension_scores={
                "Technical": 65,
                "Communication": 60,
                "Problem Solving": 55,
                "Adaptability": 60,
                "Confidence": 60,
            },
            question_scores=[60, 58, 62, 55, 65],
            role="Developer",
            seniority="Mid",
            violations=[
                {"type": "tab_switch"},
                {"type": "tab_switch"},
                {"type": "tab_switch"},
            ],
            answer_times=[5, 6, 7, 8, 9],
        )

        assert len(explainable.risk_factors) > 0

    def test_dimension_performance_analysis(self):
        """Test dimension-specific analysis"""
        explanation, evidence, expected = analyze_dimension_performance(
            "Technical", 85, [80, 82, 88, 90], "Python Developer", "Mid"
        )

        assert explanation != ""
        assert expected == 75  # Mid-level expectation
        assert "exceeds" in explanation.lower()

    def test_explainable_score_to_dict(self):
        """Test serialization"""
        explainable = generate_explainable_score(
            final_score=70.0,
            dimension_scores={
                "Technical": 75,
                "Communication": 70,
                "Problem Solving": 65,
                "Adaptability": 70,
                "Confidence": 70,
            },
            question_scores=[65, 68, 70, 72, 75],
            role="Developer",
            seniority="Mid",
        )

        result = explainable.to_dict()
        assert "final_score" in result
        assert "confidence_interval" in result
        assert "why_this_score" in result
        assert "strengths" in result
        assert "weaknesses" in result
        assert "gaps" in result


# =============================================================================
# TIMING ANALYSIS TESTS
# =============================================================================


class TestTimingAnalysis:
    def test_normal_timing_pattern(self):
        """Normal human timing should not trigger flags"""
        times = [45, 60, 90, 75, 120, 85]
        analysis = analyze_response_timing(times)

        assert analysis.risk_level == "Low"
        assert analysis.too_fast_count == 0
        assert len(analysis.anomaly_flags) == 0

    def test_too_fast_detection(self):
        """Very fast answers should be flagged"""
        times = [5, 8, 10, 6, 7, 9]
        analysis = analyze_response_timing(times)

        assert analysis.risk_level in ["Medium", "High"]
        assert analysis.too_fast_count >= 3

    def test_perfect_timing_detection(self):
        """Suspiciously consistent timing should be flagged"""
        times = [60, 60, 60, 60, 60, 60]
        analysis = analyze_response_timing(times)

        assert len(analysis.anomaly_flags) > 0
        assert (
            "perfect" in " ".join(analysis.anomaly_flags).lower()
            or "automated" in " ".join(analysis.anomaly_flags).lower()
        )

    def test_impossible_speed_detection(self):
        """Answers faster than reading time should be flagged"""
        times = [2, 3, 4, 60, 90]
        analysis = analyze_response_timing(times)

        assert any(
            "impossible" in flag.lower() or "faster" in flag.lower()
            for flag in analysis.anomaly_flags
        )

    def test_burst_pattern_detection(self):
        """Multiple rapid answers in succession should be flagged"""
        times = [60, 5, 6, 7, 8, 90]
        analysis = analyze_response_timing(times)

        assert len(analysis.anomaly_flags) > 0

    def test_timing_penalty_computation(self):
        """High risk should result in higher penalty"""
        high_risk = TimingAnalysis(
            avg_response_time=5,
            min_response_time=2,
            max_response_time=10,
            std_dev=2,
            too_fast_count=5,
            too_fast_threshold=20,
            consistency_score=10,
            anomaly_flags=["too fast", "impossible speed", "burst pattern"],
            risk_level="High",
        )

        low_risk = TimingAnalysis(
            avg_response_time=60,
            min_response_time=30,
            max_response_time=120,
            std_dev=20,
            too_fast_count=0,
            too_fast_threshold=20,
            consistency_score=50,
            anomaly_flags=[],
            risk_level="Low",
        )

        high_penalty = compute_timing_penalty(high_risk)
        low_penalty = compute_timing_penalty(low_risk)

        assert high_penalty > low_penalty
        assert high_penalty <= 15  # Cap at 15

    def test_answer_quality_estimation(self):
        """Estimate if answer quality is plausible given timing"""
        result = estimate_answer_quality_from_timing(
            response_time=5, question_complexity="advanced", answer_length_words=100
        )

        assert result["quality_estimate"] == "suspicious"
        assert len(result["flags"]) > 0

    def test_empty_timing_data(self):
        """Should handle empty input gracefully"""
        analysis = analyze_response_timing([])

        assert analysis.avg_response_time == 0
        assert analysis.risk_level == "Low"


# =============================================================================
# KNOWLEDGE GRAPH TESTS
# =============================================================================


class TestKnowledgeGraph:
    def test_concept_extraction_python(self):
        """Should extract Python concepts from answer"""
        answer = "I use Python decorators to implement caching and error handling in my FastAPI applications."
        concepts = extract_concepts_from_answer(answer, "Python Developer")

        assert len(concepts) > 0
        assert any(c.lower() in ["python", "decorators", "fastapi"] for c in concepts)

    def test_concept_extraction_frontend(self):
        """Should extract frontend concepts"""
        answer = "I use React with TypeScript and manage state with Redux. I also write unit tests with Jest."
        concepts = extract_concepts_from_answer(answer, "Frontend Developer")

        assert len(concepts) > 0
        assert any(
            c.lower() in ["react", "typescript", "redux", "jest"] for c in concepts
        )

    def test_mastery_assessment_deep(self):
        """High score with deep signals should indicate deep mastery"""
        answer = "The trade-off between consistency and availability depends on your use case. In my experience, for financial systems, I prefer strong consistency because data integrity is critical. However, for social media feeds, eventual consistency is acceptable."
        level, confidence = assess_mastery_level(
            "distributed systems", answer, 85, "advanced"
        )

        assert level in [MasteryLevel.DEEP, MasteryLevel.EXPERT]
        assert confidence > 0.7

    def test_mastery_assessment_surface(self):
        """Low score with surface signals should indicate surface knowledge"""
        answer = "It's basically used for caching. It's simple and easy."
        level, confidence = assess_mastery_level("Redis", answer, 40, "basic")

        assert level in [MasteryLevel.SURFACE, MasteryLevel.NONE]

    def test_knowledge_graph_construction(self):
        """Should build graph from Q&A pairs"""
        qa_pairs = [
            {
                "question": "How do you handle errors in Python?",
                "answer": "I use try/except blocks and custom exceptions. I also implement logging for production systems.",
                "score": 75,
                "focus": "Python",
                "complexity": "intermediate",
            },
            {
                "question": "Explain REST API design",
                "answer": "REST uses HTTP methods like GET, POST, PUT, DELETE. I design resources with proper status codes and versioning.",
                "score": 70,
                "focus": "API",
                "complexity": "intermediate",
            },
        ]

        graph = build_knowledge_graph(qa_pairs, "Python Developer")

        assert len(graph.concepts) > 0
        assert graph.overall_coverage >= 0
        assert graph.depth_score >= 0

    def test_knowledge_graph_gaps(self):
        """Should identify gaps when expected concepts are missing"""
        qa_pairs = [
            {
                "question": "Basic Python question",
                "answer": "I know Python basics.",
                "score": 60,
                "focus": "Python",
                "complexity": "basic",
            }
        ]

        expected = ["Python", "Django", "SQLAlchemy", "pytest", "Docker"]
        graph = build_knowledge_graph(
            qa_pairs, "Python Developer", expected_concepts=expected
        )

        assert len(graph.gaps) > 0
        assert graph.overall_coverage < 1.0

    def test_mastery_report(self):
        """Should generate human-readable report"""
        qa_pairs = [
            {
                "question": "Python question",
                "answer": "I use Python for data analysis with pandas and numpy.",
                "score": 70,
                "focus": "Python",
                "complexity": "intermediate",
            }
        ]

        graph = build_knowledge_graph(qa_pairs, "Python Developer")
        report = get_concept_mastery_report(graph)

        assert "total_concepts" in report
        assert "coverage" in report
        assert "depth_score" in report
        assert "by_category" in report


# =============================================================================
# BIAS DETECTION TESTS
# =============================================================================


class TestBiasDetection:
    def test_language_bias_detection_complex_vocab(self):
        """Should detect language bias for non-native with very complex vocabulary and low score"""
        indicator = detect_language_bias(
            answer="Notwithstanding the aforementioned paradigm shift, the synergistic implementation of core competencies requires rigorous due diligence and comprehensive stakeholder alignment to achieve optimal outcomes.",
            score=45,
            candidate_language="French",
            is_native=False,
        )

        assert indicator is not None
        assert indicator.type == "language"

    def test_language_bias_idiom_detection(self):
        """Should detect language bias when non-native overuses idioms"""
        indicator = detect_language_bias(
            answer="We need to hit the ground running, think outside the box, and move the needle on this game plan. Also need to deep dive into low-hanging fruit before touching base.",
            score=50,
            candidate_language="Arabic",
            is_native=False,
        )

        assert indicator is not None
        assert indicator.type == "language"

    def test_no_language_bias_for_native(self):
        """Native speakers should not trigger language bias"""
        indicator = detect_language_bias(
            answer="Python is excellent for software development.",
            score=80,
            candidate_language="English",
            is_native=True,
        )

        assert indicator is None

    def test_no_language_bias_informal_style(self):
        """Informal writing style should not be penalized (style bias removed)"""
        indicator = detect_language_bias(
            answer="python is good for coding i use it everyday very useful and also many times",
            score=45,
            candidate_language="English",
            is_native=False,
        )

        assert indicator is None

    def test_length_bias_short_answer(self):
        """Short answers with technical content should be flagged"""
        indicator = detect_length_bias(
            answer="FastAPI async PostgreSQL Redis Docker",
            score=40,
            avg_answer_length=80,
        )

        assert indicator is not None
        assert indicator.type == "length"

    def test_length_bias_verbose_answer(self):
        """Very long answers with low diversity should be flagged"""
        long_answer = (
            "good code good code good code good code good code good code good code good code good code good code "
            * 40
        )
        indicator = detect_length_bias(
            answer=long_answer, score=80, avg_answer_length=80
        )

        assert indicator is not None
        assert indicator.type == "length"

    def test_cultural_bias_detection(self):
        """Regional references should be checked for bias"""
        indicator = detect_cultural_bias(
            answer="I worked on projects in Tunisia using local tech stacks",
            score=45,
            candidate_region="Tunisia",
        )

        assert indicator is not None
        assert indicator.type == "cultural"

    def test_style_bias_detection(self):
        """Informal style shouldn't override technical competence"""
        indicator = detect_style_bias(
            answer="yeah i use the function to call the api and it works kinda well for the database stuff lol",
            score=50,
        )

        assert indicator is not None
        assert indicator.type == "style"

    def test_full_bias_audit(self):
        """Run comprehensive bias audit"""
        qa_pairs = [
            {"answer": "Python is good for coding", "score": 60},
            {"answer": "I use fastapi and databases", "score": 55},
            {"answer": "Testing is important", "score": 65},
        ]

        report = run_bias_audit(
            qa_pairs,
            candidate_language="English",
            is_native_speaker=False,
            candidate_region="Tunisia",
        )

        assert isinstance(report, BiasAuditReport)
        assert 0 <= report.fairness_score <= 100
        assert report.risk_level in ["Low", "Medium", "High"]

    def test_statistical_parity(self):
        """Test group comparison"""
        group_a = [70, 72, 68, 75, 71]
        group_b = [71, 69, 73, 70, 72]

        result = compute_statistical_parity(group_a, group_b)

        assert "test" in result
        assert "parity" in result
        assert result["parity"]  # Similar groups should show parity

    def test_statistical_parity_different_groups(self):
        """Different groups should show disparity"""
        group_a = [80, 82, 85, 83, 81]
        group_b = [50, 52, 48, 55, 51]

        result = compute_statistical_parity(group_a, group_b)

        assert not result["parity"]  # Different groups should show disparity


# =============================================================================
# CALIBRATION TESTS
# =============================================================================


class TestCalibration:
    def test_create_calibration_sample(self):
        """Test sample creation"""
        sample = create_calibration_sample(
            sample_id="test_001",
            role="Python Developer",
            seniority="Mid",
            qa_pairs=[{"question": "Q1", "answer": "A1"}],
            human_ratings={
                "rater_1": {"Technical": 75, "Communication": 70},
                "rater_2": {"Technical": 78, "Communication": 72},
            },
            ai_scores={"Technical": 76, "Communication": 71},
        )

        assert sample.sample_id == "test_001"
        assert len(sample.human_scores) == 2
        assert sample.human_consensus["Technical"] == pytest.approx(76.5, abs=0.1)

    def test_inter_rater_reliability(self):
        """High agreement should yield high IRR"""
        sample = CalibrationSample(
            sample_id="irr_test",
            role="Developer",
            seniority="Mid",
            qa_pairs=[],
            human_scores={
                "rater_1": {"Technical": 80, "Communication": 75},
                "rater_2": {"Technical": 81, "Communication": 76},
            },
            ai_scores={"Technical": 80, "Communication": 75},
        )

        assert sample.inter_rater_reliability > 0.9

    def test_calibration_dataset(self):
        """Test dataset management"""
        dataset = CalibrationDataset(name="test_dataset")

        sample1 = create_calibration_sample(
            "s1",
            "Python Developer",
            "Mid",
            [],
            {"r1": {"Technical": 75}},
            {"Technical": 76},
        )
        sample2 = create_calibration_sample(
            "s2",
            "Python Developer",
            "Mid",
            [],
            {"r1": {"Technical": 80}},
            {"Technical": 78},
        )

        dataset.add_sample(sample1)
        dataset.add_sample(sample2)

        assert len(dataset.samples) == 2
        assert len(dataset.get_by_role("Python Developer")) == 2

    def test_calibration_store(self):
        """Test store operations"""
        store = CalibrationStore()
        store.create_dataset("production")

        sample = create_calibration_sample(
            "s1", "Developer", "Mid", [], {"r1": {"Technical": 75}}, {"Technical": 76}
        )
        store.add_sample("production", sample)

        assert len(store.list_datasets()) == 1
        assert store.get_dataset("production").samples[0].sample_id == "s1"

    def test_calibration_report(self):
        """Test report generation"""
        store = CalibrationStore()
        store.create_dataset("test")

        for i in range(5):
            sample = create_calibration_sample(
                f"s{i}",
                "Developer",
                "Mid",
                [],
                {"r1": {"Technical": 70 + i}},
                {"Technical": 71 + i},
            )
            store.add_sample("test", sample)

        report = store.get_calibration_report("test")

        assert "sample_count" in report
        assert report["sample_count"] == 5


# =============================================================================
# A/B TESTING TESTS
# =============================================================================


class TestABTesting:
    def test_variant_assignment(self):
        """Should deterministically assign variants"""
        variants = [
            ExperimentVariant(name="control", prompt_template="prompt A"),
            ExperimentVariant(name="treatment", prompt_template="prompt B"),
        ]

        experiment = ABExperiment(
            id="exp1",
            name="Test",
            description="Test",
            variants=variants,
            traffic_split={"control": 0.5, "treatment": 0.5},
            start_time=datetime.now(UTC).isoformat(),
        )

        # Same candidate should always get same variant
        variant1 = experiment.assign_variant("candidate_123")
        variant2 = experiment.assign_variant("candidate_123")
        assert variant1 == variant2

    def test_experiment_statistics(self):
        """Should compute statistics correctly"""
        variants = [
            ExperimentVariant(name="control", prompt_template="A"),
            ExperimentVariant(name="treatment", prompt_template="B"),
        ]

        experiment = ABExperiment(
            id="exp1",
            name="Test",
            description="Test",
            variants=variants,
            traffic_split={"control": 0.5, "treatment": 0.5},
            start_time=datetime.now(UTC).isoformat(),
            min_sample_size=3,
        )

        # Add results
        for i in range(5):
            experiment.add_result(
                ExperimentResult(
                    experiment_id="exp1",
                    variant_name="control",
                    candidate_id=f"c{i}",
                    score=70 + i,
                    dimension_scores={"Technical": 70 + i},
                    duration_seconds=300,
                )
            )

        for i in range(5):
            experiment.add_result(
                ExperimentResult(
                    experiment_id="exp1",
                    variant_name="treatment",
                    candidate_id=f"t{i}",
                    score=75 + i,
                    dimension_scores={"Technical": 75 + i},
                    duration_seconds=300,
                )
            )

        stats = experiment.compute_statistics()

        assert "control" in stats
        assert "treatment" in stats
        assert stats["control"]["sample_count"] == 5
        assert stats["treatment"]["sample_count"] == 5

    def test_ab_test_manager(self):
        """Test manager operations"""
        manager = ABTestManager()

        variants = [
            ExperimentVariant(name="control", prompt_template="A"),
            ExperimentVariant(name="treatment", prompt_template="B"),
        ]

        exp = manager.create_experiment(
            name="Prompt Test", description="Testing prompt variants", variants=variants
        )

        assert exp.id in manager.experiments
        assert len(manager.get_active_experiments()) == 1

        manager.complete_experiment(exp.id)
        assert manager.get_experiment(exp.id).status == "completed"


# =============================================================================
# DRIFT MONITORING TESTS
# =============================================================================


class TestDriftMonitoring:
    def test_snapshot_creation(self):
        """Test snapshot creation from interviews"""
        interviews = [
            {
                "score": 70,
                "dimension_scores": {"Technical": 75},
                "response_time": 60,
                "error": False,
            },
            {
                "score": 75,
                "dimension_scores": {"Technical": 80},
                "response_time": 90,
                "error": False,
            },
            {
                "score": 65,
                "dimension_scores": {"Technical": 70},
                "response_time": 45,
                "error": False,
            },
        ]

        snapshot = create_snapshot_from_interviews(interviews, "gpt-4o-2024-05-13")

        assert snapshot.sample_count == 3
        assert snapshot.mean_score == pytest.approx(70, abs=0.1)

    def test_drift_detection_no_drift(self):
        """Similar snapshots should show no drift"""
        monitor = DriftMonitor()

        baseline = ModelSnapshot(
            timestamp=datetime.now(UTC).isoformat(),
            model_version="v1",
            sample_count=100,
            mean_score=70,
            std_dev=10,
            median_score=70,
            p25_score=60,
            p75_score=80,
            avg_response_time=60,
            error_rate=0.02,
            dimension_averages={"Technical": 72},
        )
        monitor.baseline = baseline

        current = ModelSnapshot(
            timestamp=datetime.now(UTC).isoformat(),
            model_version="v1",
            sample_count=100,
            mean_score=71,
            std_dev=10,
            median_score=71,
            p25_score=61,
            p75_score=81,
            avg_response_time=62,
            error_rate=0.02,
            dimension_averages={"Technical": 73},
        )

        report = monitor.detect_drift(current)

        assert report.overall_drift_score < 0.1
        assert (
            "stable" in report.recommendation.lower()
            or "no action" in report.recommendation.lower()
        )

    def test_drift_detection_score_shift(self):
        """Significant score shift should be detected"""
        monitor = DriftMonitor()

        baseline = ModelSnapshot(
            timestamp=datetime.now(UTC).isoformat(),
            model_version="v1",
            sample_count=100,
            mean_score=70,
            std_dev=10,
            median_score=70,
            p25_score=60,
            p75_score=80,
            avg_response_time=60,
            error_rate=0.02,
            dimension_averages={"Technical": 72},
        )
        monitor.baseline = baseline

        current = ModelSnapshot(
            timestamp=datetime.now(UTC).isoformat(),
            model_version="v2",
            sample_count=100,
            mean_score=50,  # 20 point drop!
            std_dev=15,
            median_score=50,
            p25_score=40,
            p75_score=60,
            avg_response_time=90,
            error_rate=0.05,
            dimension_averages={"Technical": 52},
        )

        report = monitor.detect_drift(current)

        assert report.overall_drift_score > 0.25
        assert len(report.alerts) > 0

    def test_drift_history(self):
        """Test drift history retrieval"""
        monitor = DriftMonitor()

        for i in range(5):
            snapshot = ModelSnapshot(
                timestamp=datetime.now(UTC).isoformat(),
                model_version="v1",
                sample_count=20,
                mean_score=70 + i,
                std_dev=10,
                median_score=70 + i,
                p25_score=60,
                p75_score=80,
                avg_response_time=60,
                error_rate=0.02,
                dimension_averages={"Technical": 72},
            )
            monitor.record_snapshot(snapshot)

        history = monitor.get_drift_history(days=30)
        assert len(history) == 5


# =============================================================================
# INTEGRATION TESTS
# =============================================================================


class TestScoringIntegration:
    def test_full_scoring_with_explainability(self):
        """Test complete scoring pipeline with explainability"""
        breakdown = calculate_overall_score(
            skill_metrics={
                "Technical": 80,
                "Communication": 70,
                "Problem Solving": 75,
                "Adaptability": 65,
                "Confidence": 70,
            },
            question_scores=[70, 72, 68, 75, 78, 80],
            answered=6,
            total=6,
            violations=[],
            gaming_detected=False,
            role="Python Developer",
            seniority="Mid",
            answer_times=[45, 60, 90, 75, 120, 85],
        )

        assert 0 <= breakdown.final_score <= 100
        assert breakdown.confidence_interval is not None
        assert breakdown.why_this_score != ""
        assert "explainability" in breakdown.to_dict()

    def test_scoring_with_violations(self):
        """Test scoring with integrity violations"""
        breakdown = calculate_overall_score(
            skill_metrics={
                "Technical": 80,
                "Communication": 70,
                "Problem Solving": 75,
                "Adaptability": 65,
                "Confidence": 70,
            },
            question_scores=[70, 72, 68, 75, 78, 80],
            answered=6,
            total=6,
            violations=[
                {"type": "tab_switch"},
                {"type": "tab_switch"},
                {"type": "tab_switch"},
                {"type": "copy_paste"},
            ],
            role="Developer",
            seniority="Mid",
        )

        assert breakdown.integrity_penalty > 0
        assert len(breakdown.risk_factors) > 0

    def test_scoring_with_timing_penalty(self):
        """Test scoring with timing analysis"""
        breakdown = calculate_overall_score(
            skill_metrics={
                "Technical": 80,
                "Communication": 70,
                "Problem Solving": 75,
                "Adaptability": 65,
                "Confidence": 70,
            },
            question_scores=[70, 72, 68, 75, 78, 80],
            answered=6,
            total=6,
            answer_times=[5, 6, 7, 8, 9, 10],  # Suspiciously fast
            role="Developer",
            seniority="Mid",
        )

        assert breakdown.timing_penalty > 0

    def test_score_label(self):
        """Test score labels"""
        assert get_score_label(90) == "Exceptional"
        assert get_score_label(75) == "Strong"
        assert get_score_label(60) == "Competent"
        assert get_score_label(45) == "Developing"
        assert get_score_label(30) == "Needs Improvement"

    def test_recommendation(self):
        """Test hiring recommendations"""
        assert get_recommendation(85, 0) == "Strong Hire"
        assert get_recommendation(70, 0) == "Recommended"
        assert get_recommendation(55, 0) == "Consider"
        assert get_recommendation(40, 0) == "Not Recommended"
        assert get_recommendation(80, 20) == "Manual Review Required"
