from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

ScorecardTier = Literal["offline", "live"]


@dataclass(frozen=True)
class CaseMetrics:
    case_id: str
    adapter: str
    precision_at_1: float
    top3_recall: float
    evidence_grounding_rate: float
    false_confidence_rate: float
    actionability_rate: float
    validity_score: float | None = None
    passed: bool = True
    detail: str = ""


@dataclass(frozen=True)
class AggregateMetrics:
    precision_at_1: float
    top3_recall: float
    evidence_grounding_rate: float
    false_confidence_rate: float
    actionability_rate: float
    case_count: int


@dataclass(frozen=True)
class ThresholdSpec:
    evidence_grounding_rate_min: float = 0.85
    actionability_rate_min: float = 0.70
    precision_at_1_regression_pp: float = 0.02
    top3_recall_regression_pp: float = 0.05


@dataclass(frozen=True)
class ThresholdResult:
    passed: bool
    failures: tuple[str, ...] = ()


@dataclass(frozen=True)
class RunScorecard:
    tier: ScorecardTier
    git_sha: str
    aggregate: AggregateMetrics
    cases: tuple[CaseMetrics, ...]
    thresholds: ThresholdResult
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["cases"] = [asdict(case) for case in self.cases]
        return payload
