from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from tests.eval.scorecard.runner import run_tier, write_baseline
from tests.eval.scorecard.trends import append_trend_row, write_latest_markdown
from tests.eval.scorecard.types import ScorecardTier


def _git_sha() -> str:
    try:
        return (
            subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()  # noqa: S603,S607
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the investigation quality scorecard.")
    parser.add_argument("command", choices=("run",), help="Run the scorecard for a tier.")
    parser.add_argument(
        "--tier",
        choices=("offline", "live"),
        default="offline",
        help="Eval tier: offline (PR gate) or live (LLM smoke).",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=None,
        help="Path to manifest.yml (defaults to tests/eval/manifest.yml).",
    )
    parser.add_argument(
        "--check-thresholds",
        action="store_true",
        help="Exit non-zero when thresholds fail.",
    )
    parser.add_argument(
        "--write-baseline",
        action="store_true",
        help="Write aggregate metrics to baselines/smoke_offline.json.",
    )
    parser.add_argument(
        "--write-trends",
        action="store_true",
        help="Append a trend row and regenerate docs/eval/scorecard-latest.md.",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=Path("scorecard-report.json"),
        help="Output path for the JSON report.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    tier: ScorecardTier = args.tier
    git_sha = _git_sha()
    scorecard = run_tier(tier=tier, manifest_path=args.manifest, git_sha=git_sha)

    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(scorecard.to_dict(), indent=2) + "\n", encoding="utf-8")

    if args.write_baseline:
        if tier != "offline":
            print("--write-baseline is only supported for offline tier", file=sys.stderr)
            return 2
        path = write_baseline(scorecard)
        print(f"Wrote baseline: {path}")

    if args.write_trends:
        if tier != "live":
            print("--write-trends is only supported for live tier", file=sys.stderr)
            return 2
        append_trend_row(scorecard, git_sha=git_sha)
        latest = write_latest_markdown(scorecard)
        print(f"Updated trends and {latest}")

    agg = scorecard.aggregate
    print(
        f"scorecard tier={tier} cases={agg.case_count} "
        f"precision_at_1={agg.precision_at_1:.3f} "
        f"grounding={agg.evidence_grounding_rate:.3f} "
        f"false_confidence={agg.false_confidence_rate:.3f} "
        f"actionability={agg.actionability_rate:.3f} "
        f"thresholds={'PASS' if scorecard.thresholds.passed else 'FAIL'}"
    )
    if scorecard.thresholds.failures:
        for failure in scorecard.thresholds.failures:
            print(f"  FAIL: {failure}", file=sys.stderr)

    if args.check_thresholds and not scorecard.thresholds.passed:
        return 1
    return 0
