from __future__ import annotations

from tests.eval.scorecard.runner import check_thresholds
from tests.eval.scorecard.trends import append_trend_row, render_latest_markdown
from tests.eval.scorecard.types import (
    AggregateMetrics,
    RunScorecard,
    ThresholdResult,
    ThresholdSpec,
)


def test_live_threshold_fails_on_high_false_confidence() -> None:
    aggregate = AggregateMetrics(1.0, 1.0, 0.95, 0.25, 0.80, 4)
    result = check_thresholds(aggregate, tier="live", spec=ThresholdSpec())
    assert not result.passed
    assert any("false_confidence_rate" in failure for failure in result.failures)


def test_trends_append_and_render(tmp_path, monkeypatch) -> None:
    trends_path = tmp_path / "trends.jsonl"
    latest_path = tmp_path / "latest.md"
    monkeypatch.setattr("tests.eval.scorecard.trends.TRENDS_PATH", trends_path)
    monkeypatch.setattr("tests.eval.scorecard.trends.LATEST_MD_PATH", latest_path)

    scorecard = RunScorecard(
        tier="live",
        git_sha="abc123",
        aggregate=AggregateMetrics(0.9, 0.8, 0.91, 0.1, 0.75, 4),
        cases=(),
        thresholds=ThresholdResult(passed=True),
    )
    row = append_trend_row(scorecard, git_sha="abc123")
    assert row["tier"] == "live"
    assert trends_path.read_text(encoding="utf-8").strip()

    rendered = render_latest_markdown(scorecard)
    assert "precision_at_1" in rendered
    assert "91.0%" in rendered
