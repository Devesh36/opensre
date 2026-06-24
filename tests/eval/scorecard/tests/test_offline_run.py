from __future__ import annotations

from tests.eval.scorecard.adapters import score_rds_offline
from tests.eval.scorecard.runner import run_tier


def test_offline_smoke_run_passes_thresholds() -> None:
    scorecard = run_tier(tier="offline", git_sha="test")
    assert scorecard.aggregate.case_count >= 10
    assert scorecard.thresholds.passed


def test_rds_offline_gold_case_scores_perfectly() -> None:
    metrics = score_rds_offline("rds/001-replication-lag")
    assert metrics.precision_at_1 == 1.0
    assert metrics.evidence_grounding_rate >= 0.85
