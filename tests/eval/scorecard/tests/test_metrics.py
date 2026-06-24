from __future__ import annotations

import pytest

from tests.eval.scorecard.metrics import (
    compute_actionability_rate,
    compute_evidence_grounding_rate,
    compute_false_confidence,
    compute_precision_at_1,
    compute_top3_recall,
)
from tests.eval.scorecard.runner import aggregate_cases, check_thresholds, load_baseline
from tests.eval.scorecard.types import AggregateMetrics, CaseMetrics, ThresholdSpec


def test_precision_at_1_true_positive() -> None:
    assert (
        compute_precision_at_1(
            actual_category="replication_lag",
            accepted_categories=frozenset({"replication_lag"}),
            root_cause_present=True,
        )
        == 1.0
    )


def test_false_confidence_high_validity_wrong_answer() -> None:
    assert compute_false_confidence(validity_score=0.85, precision_at_1=0.0) == 1.0
    assert compute_false_confidence(validity_score=0.85, precision_at_1=1.0) == 0.0


def test_evidence_grounding_requires_linked_sources() -> None:
    rate = compute_evidence_grounding_rate(
        validated_claims=[
            {"claim": "lag high", "evidence_source": "aws_cloudwatch_metrics"},
            {"claim": "wal spike", "evidence_source": "aws_performance_insights"},
        ],
        evidence={"aws_cloudwatch_metrics": {"x": 1}},
        required_evidence_sources=("aws_cloudwatch_metrics", "aws_performance_insights"),
    )
    assert rate == 0.5


def test_top3_recall_matches_contributing_factor() -> None:
    assert (
        compute_top3_recall(
            contributing_factors=("replication lag", "wal"),
            top_hypotheses=["cpu saturation", "replication lag on replica"],
            precision_at_1=0.0,
        )
        == 1.0
    )


def test_actionability_rate_keyword_coverage() -> None:
    rate = compute_actionability_rate(
        report="Reduce batch size on the replica and monitor lag.",
        remediation_steps=[],
        required_keywords=("replica",),
        min_actionability_keywords=("reduce batch", "replica"),
    )
    assert rate == 1.0


def test_threshold_regression_fails_on_precision_drop() -> None:
    aggregate = AggregateMetrics(0.90, 1.0, 0.95, 0.0, 0.80, 10)
    baseline = {
        "precision_at_1": 1.0,
        "top3_recall": 1.0,
        "evidence_grounding_rate": 0.95,
        "false_confidence_rate": 0.0,
        "actionability_rate": 0.80,
    }
    result = check_thresholds(aggregate, tier="offline", baseline=baseline, spec=ThresholdSpec())
    assert not result.passed
    assert any("precision_at_1 regression" in failure for failure in result.failures)


def test_offline_baseline_file_loads() -> None:
    baseline = load_baseline()
    assert baseline["precision_at_1"] >= 0.99


def test_aggregate_cases_mean() -> None:
    cases = (
        CaseMetrics("a", "test", 1.0, 1.0, 1.0, 0.0, 0.5),
        CaseMetrics("b", "test", 0.0, 0.0, 0.0, 1.0, 1.0),
    )
    aggregate = aggregate_cases(cases)
    assert aggregate.precision_at_1 == pytest.approx(0.5)
    assert aggregate.actionability_rate == pytest.approx(0.75)
