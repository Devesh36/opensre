from __future__ import annotations

import json
from pathlib import Path

import yaml

from tests.eval.scorecard.adapters import score_case
from tests.eval.scorecard.types import (
    AggregateMetrics,
    CaseMetrics,
    RunScorecard,
    ScorecardTier,
    ThresholdResult,
    ThresholdSpec,
)

MANIFEST_PATH = Path(__file__).resolve().parents[1] / "manifest.yml"
BASELINE_PATH = Path(__file__).resolve().parent / "baselines" / "smoke_offline.json"


def load_manifest(path: Path | None = None) -> dict[str, object]:
    manifest_path = path or MANIFEST_PATH
    raw = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"{manifest_path}: manifest must be a mapping")
    return raw


def case_ids_for_tier(manifest: dict[str, object], tier: ScorecardTier) -> tuple[str, ...]:
    key = "smoke_offline" if tier == "offline" else "smoke_live"
    entries = manifest.get(key) or []
    if not isinstance(entries, list):
        raise ValueError(f"manifest {key} must be a list")
    return tuple(str(entry).strip() for entry in entries)


def aggregate_cases(cases: tuple[CaseMetrics, ...]) -> AggregateMetrics:
    if not cases:
        return AggregateMetrics(0.0, 0.0, 0.0, 0.0, 0.0, 0)

    count = len(cases)
    return AggregateMetrics(
        precision_at_1=sum(case.precision_at_1 for case in cases) / count,
        top3_recall=sum(case.top3_recall for case in cases) / count,
        evidence_grounding_rate=sum(case.evidence_grounding_rate for case in cases) / count,
        false_confidence_rate=sum(case.false_confidence_rate for case in cases) / count,
        actionability_rate=sum(case.actionability_rate for case in cases) / count,
        case_count=count,
    )


def load_baseline(path: Path | None = None) -> dict[str, float]:
    baseline_path = path or BASELINE_PATH
    if not baseline_path.exists():
        return {}
    payload = json.loads(baseline_path.read_text(encoding="utf-8"))
    aggregate = payload.get("aggregate") or payload
    return {
        "precision_at_1": float(aggregate.get("precision_at_1", 0.0)),
        "top3_recall": float(aggregate.get("top3_recall", 0.0)),
        "evidence_grounding_rate": float(aggregate.get("evidence_grounding_rate", 0.0)),
        "false_confidence_rate": float(aggregate.get("false_confidence_rate", 0.0)),
        "actionability_rate": float(aggregate.get("actionability_rate", 0.0)),
    }


def write_baseline(scorecard: RunScorecard, path: Path | None = None) -> Path:
    baseline_path = path or BASELINE_PATH
    baseline_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "tier": scorecard.tier,
        "git_sha": scorecard.git_sha,
        "aggregate": {
            "precision_at_1": scorecard.aggregate.precision_at_1,
            "top3_recall": scorecard.aggregate.top3_recall,
            "evidence_grounding_rate": scorecard.aggregate.evidence_grounding_rate,
            "false_confidence_rate": scorecard.aggregate.false_confidence_rate,
            "actionability_rate": scorecard.aggregate.actionability_rate,
            "case_count": scorecard.aggregate.case_count,
        },
    }
    baseline_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return baseline_path


def check_thresholds(
    aggregate: AggregateMetrics,
    *,
    tier: ScorecardTier,
    baseline: dict[str, float] | None = None,
    spec: ThresholdSpec | None = None,
) -> ThresholdResult:
    thresholds = spec or ThresholdSpec()
    failures: list[str] = []

    if tier == "offline":
        if aggregate.evidence_grounding_rate < thresholds.evidence_grounding_rate_min:
            failures.append(
                "evidence_grounding_rate "
                f"{aggregate.evidence_grounding_rate:.3f} < {thresholds.evidence_grounding_rate_min:.3f}"
            )
        if aggregate.actionability_rate < thresholds.actionability_rate_min:
            failures.append(
                "actionability_rate "
                f"{aggregate.actionability_rate:.3f} < {thresholds.actionability_rate_min:.3f}"
            )

        if baseline:
            precision_floor = baseline["precision_at_1"] - thresholds.precision_at_1_regression_pp
            if aggregate.precision_at_1 + 1e-9 < precision_floor:
                failures.append(
                    "precision_at_1 regression: "
                    f"{aggregate.precision_at_1:.3f} < baseline {baseline['precision_at_1']:.3f} "
                    f"- {thresholds.precision_at_1_regression_pp:.2f}"
                )
            top3_floor = baseline["top3_recall"] - thresholds.top3_recall_regression_pp
            if aggregate.top3_recall + 1e-9 < top3_floor:
                failures.append(
                    "top3_recall regression: "
                    f"{aggregate.top3_recall:.3f} < baseline {baseline['top3_recall']:.3f} "
                    f"- {thresholds.top3_recall_regression_pp:.2f}"
                )
    else:
        if aggregate.evidence_grounding_rate < thresholds.live_evidence_grounding_rate_min:
            failures.append(
                "evidence_grounding_rate "
                f"{aggregate.evidence_grounding_rate:.3f} < "
                f"{thresholds.live_evidence_grounding_rate_min:.3f} (live target)"
            )
        if aggregate.false_confidence_rate > thresholds.false_confidence_rate_max:
            failures.append(
                "false_confidence_rate "
                f"{aggregate.false_confidence_rate:.3f} > {thresholds.false_confidence_rate_max:.3f}"
            )

    return ThresholdResult(passed=not failures, failures=tuple(failures))


def run_tier(
    *,
    tier: ScorecardTier,
    manifest_path: Path | None = None,
    git_sha: str = "local",
) -> RunScorecard:
    manifest = load_manifest(manifest_path)
    cases = tuple(score_case(case_id, tier=tier) for case_id in case_ids_for_tier(manifest, tier))
    aggregate = aggregate_cases(cases)
    baseline = load_baseline() if tier == "offline" else None
    thresholds = check_thresholds(aggregate, tier=tier, baseline=baseline)
    return RunScorecard(
        tier=tier,
        git_sha=git_sha,
        aggregate=aggregate,
        cases=cases,
        thresholds=thresholds,
        metadata={
            "manifest_version": int(manifest.get("version", 1)),
            "owner": str(manifest.get("owner", "")),
        },
    )
