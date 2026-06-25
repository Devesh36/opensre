from __future__ import annotations

from collections.abc import Callable

from tests.eval.scorecard.metrics import build_gold_final_state, metrics_from_final_state
from tests.eval.scorecard.types import CaseMetrics
from tests.synthetic.hermes_rca.scenario_loader import SUITE_DIR as HERMES_SUITE_DIR
from tests.synthetic.hermes_rca.scenario_loader import load_scenario as load_hermes_scenario
from tests.synthetic.rds_postgres.scenario_loader import SUITE_DIR as RDS_SUITE_DIR
from tests.synthetic.rds_postgres.scenario_loader import load_scenario as load_rds_scenario
from tests.synthetic.rds_postgres.scoring import _accepted_root_cause_categories


def _resolve_rds_fixture(case_id: str):
    scenario_id = case_id.split("/", 1)[-1]
    return load_rds_scenario(RDS_SUITE_DIR / scenario_id)


def _resolve_hermes_fixture(case_id: str):
    scenario_id = case_id.split("/", 1)[-1]
    return load_hermes_scenario(HERMES_SUITE_DIR / scenario_id)


def score_rds_offline(case_id: str) -> CaseMetrics:
    fixture = _resolve_rds_fixture(case_id)
    key = fixture.answer_key
    accepted = _accepted_root_cause_categories(fixture)
    gold_state = build_gold_final_state(
        root_cause_category=key.root_cause_category,
        model_response=key.model_response,
        required_evidence_sources=key.required_evidence_sources,
        canonical_root_cause=key.canonical_root_cause,
        suite="rds",
    )
    return metrics_from_final_state(
        case_id=case_id,
        adapter="synthetic_rds_offline",
        final_state=gold_state,
        accepted_categories=accepted,
        contributing_factors=key.contributing_factors,
        canonical_root_cause=key.canonical_root_cause,
        required_evidence_sources=tuple(key.required_evidence_sources),
        required_keywords=tuple(key.required_keywords),
        min_actionability_keywords=key.min_actionability_keywords,
    )


def score_hermes_offline(case_id: str) -> CaseMetrics:
    fixture = _resolve_hermes_fixture(case_id)
    key = fixture.answer_key
    required_sources = list(key.required_evidence_sources)
    available = set(fixture.metadata.available_evidence)
    missing = sorted(set(required_sources) - available)
    if missing:
        return CaseMetrics(
            case_id=case_id,
            adapter="hermes_offline",
            precision_at_1=0.0,
            top3_recall=0.0,
            evidence_grounding_rate=0.0,
            false_confidence_rate=0.0,
            actionability_rate=0.0,
            passed=False,
            detail=f"missing required evidence sources: {missing}",
        )

    gold_state = build_gold_final_state(
        root_cause_category=key.root_cause_category,
        model_response=key.model_response,
        required_evidence_sources=required_sources,
        suite="hermes",
    )
    accepted = frozenset({key.root_cause_category.strip().lower()})
    return metrics_from_final_state(
        case_id=case_id,
        adapter="hermes_offline",
        final_state=gold_state,
        accepted_categories=accepted,
        required_keywords=tuple(key.required_keywords),
    )


OFFLINE_ADAPTERS: dict[str, Callable[[str], CaseMetrics]] = {
    "synthetic_rds_offline": score_rds_offline,
    "hermes_offline": score_hermes_offline,
}


def score_rds_live(case_id: str) -> CaseMetrics:
    from tests.synthetic.rds_postgres.run_suite import run_scenario

    fixture = _resolve_rds_fixture(case_id)
    key = fixture.answer_key
    accepted = _accepted_root_cause_categories(fixture)
    final_state, scenario_score = run_scenario(fixture, use_mock_grafana=True)
    metrics = metrics_from_final_state(
        case_id=case_id,
        adapter="synthetic_rds_live",
        final_state=final_state,
        accepted_categories=accepted,
        contributing_factors=key.contributing_factors,
        canonical_root_cause=key.canonical_root_cause,
        required_evidence_sources=tuple(key.required_evidence_sources),
        required_keywords=tuple(key.required_keywords),
        min_actionability_keywords=key.min_actionability_keywords,
    )
    passed = scenario_score.passed and metrics.precision_at_1 >= 1.0
    return CaseMetrics(
        case_id=metrics.case_id,
        adapter=metrics.adapter,
        precision_at_1=metrics.precision_at_1,
        top3_recall=metrics.top3_recall,
        evidence_grounding_rate=metrics.evidence_grounding_rate,
        false_confidence_rate=metrics.false_confidence_rate,
        actionability_rate=metrics.actionability_rate,
        validity_score=metrics.validity_score,
        passed=passed,
        detail=scenario_score.failure_reason,
    )


def score_hermes_live(case_id: str) -> CaseMetrics:
    from tests.synthetic.hermes_rca.run_suite import run_scenario

    fixture = _resolve_hermes_fixture(case_id)
    key = fixture.answer_key
    final_state, scenario_score = run_scenario(fixture)
    accepted = frozenset({key.root_cause_category.strip().lower()})
    metrics = metrics_from_final_state(
        case_id=case_id,
        adapter="hermes_live",
        final_state=final_state,
        accepted_categories=accepted,
        required_keywords=tuple(key.required_keywords),
    )
    return CaseMetrics(
        case_id=metrics.case_id,
        adapter=metrics.adapter,
        precision_at_1=metrics.precision_at_1,
        top3_recall=metrics.top3_recall,
        evidence_grounding_rate=metrics.evidence_grounding_rate,
        false_confidence_rate=metrics.false_confidence_rate,
        actionability_rate=metrics.actionability_rate,
        validity_score=metrics.validity_score,
        passed=scenario_score.passed,
        detail=scenario_score.failure_reason,
    )


LIVE_ADAPTERS: dict[str, Callable[[str], CaseMetrics]] = {
    "synthetic_rds_live": score_rds_live,
    "hermes_live": score_hermes_live,
}


def adapter_name_for_case(case_id: str, *, tier: str) -> str:
    prefix = case_id.split("/", 1)[0]
    suffix = "offline" if tier == "offline" else "live"
    mapping = {
        "rds": f"synthetic_rds_{suffix}",
        "hermes_rca": f"hermes_{suffix}",
        "cloudopsbench": f"cloudopsbench_{suffix}",
    }
    adapter = mapping.get(prefix)
    if adapter is None:
        raise KeyError(f"unknown suite prefix in {case_id!r}")
    return adapter


def score_offline_case(case_id: str) -> CaseMetrics:
    adapter = adapter_name_for_case(case_id, tier="offline")
    scorer = OFFLINE_ADAPTERS.get(adapter)
    if scorer is None:
        raise KeyError(f"offline adapter not implemented: {adapter!r}")
    return scorer(case_id)


def score_live_case(case_id: str) -> CaseMetrics:
    adapter = adapter_name_for_case(case_id, tier="live")
    scorer = LIVE_ADAPTERS.get(adapter)
    if scorer is None:
        raise KeyError(f"live adapter not implemented: {adapter!r}")
    return scorer(case_id)


def score_case(case_id: str, *, tier: str) -> CaseMetrics:
    if tier == "offline":
        return score_offline_case(case_id)
    return score_live_case(case_id)
