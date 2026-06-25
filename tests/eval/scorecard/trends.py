from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from tests.eval.scorecard.types import RunScorecard

TRENDS_PATH = Path("docs/eval/scorecard-trends.jsonl")
LATEST_MD_PATH = Path("docs/eval/scorecard-latest.md")


def append_trend_row(scorecard: RunScorecard, *, git_sha: str) -> dict[str, object]:
    row = {
        "date": datetime.now(UTC).date().isoformat(),
        "tier": scorecard.tier,
        "git_sha": git_sha,
        "precision_at_1": round(scorecard.aggregate.precision_at_1, 4),
        "top3_recall": round(scorecard.aggregate.top3_recall, 4),
        "evidence_grounding_rate": round(scorecard.aggregate.evidence_grounding_rate, 4),
        "false_confidence_rate": round(scorecard.aggregate.false_confidence_rate, 4),
        "actionability_rate": round(scorecard.aggregate.actionability_rate, 4),
        "case_count": scorecard.aggregate.case_count,
        "thresholds_passed": scorecard.thresholds.passed,
    }
    TRENDS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with TRENDS_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row) + "\n")
    return row


def render_latest_markdown(scorecard: RunScorecard) -> str:
    agg = scorecard.aggregate
    lines = [
        "# Investigation Quality Scorecard — Latest",
        "",
        f"- **Tier:** `{scorecard.tier}`",
        f"- **Git SHA:** `{scorecard.git_sha}`",
        f"- **Cases:** {agg.case_count}",
        f"- **Thresholds:** {'PASS' if scorecard.thresholds.passed else 'FAIL'}",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
        f"| precision_at_1 | {agg.precision_at_1:.1%} |",
        f"| top3_recall | {agg.top3_recall:.1%} |",
        f"| evidence_grounding_rate | {agg.evidence_grounding_rate:.1%} |",
        f"| false_confidence_rate | {agg.false_confidence_rate:.1%} |",
        f"| actionability_rate | {agg.actionability_rate:.1%} |",
        "",
    ]
    if scorecard.thresholds.failures:
        lines.extend(["## Threshold failures", ""])
        for failure in scorecard.thresholds.failures:
            lines.append(f"- {failure}")
        lines.append("")
    return "\n".join(lines)


def write_latest_markdown(scorecard: RunScorecard) -> Path:
    LATEST_MD_PATH.parent.mkdir(parents=True, exist_ok=True)
    LATEST_MD_PATH.write_text(render_latest_markdown(scorecard), encoding="utf-8")
    return LATEST_MD_PATH
