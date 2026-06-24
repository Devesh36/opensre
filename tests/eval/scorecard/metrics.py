from __future__ import annotations

import re
from typing import Any

from tests.eval.scorecard.types import CaseMetrics

FALSE_CONFIDENCE_THRESHOLD = 0.70

_RE_ROOT_CAUSE = re.compile(r"^ROOT_CAUSE:\s*(.+)$", re.MULTILINE | re.IGNORECASE)
_RE_CATEGORY = re.compile(r"^ROOT_CAUSE_CATEGORY:\s*(.+)$", re.MULTILINE | re.IGNORECASE)
_RE_CLAIM = re.compile(
    r"^- (.+?) \.\s*\[evidence:\s*([^\]]+)\]",
    re.MULTILINE | re.IGNORECASE,
)
_RE_REMEDIATION = re.compile(r"^REMEDIATION(?:_STEPS)?:\s*(.+)$", re.MULTILINE | re.IGNORECASE)


def _normalize(text: str) -> str:
    return " ".join(text.lower().split())


def parse_rds_model_response(text: str) -> dict[str, Any]:
    root_cause_match = _RE_ROOT_CAUSE.search(text)
    category_match = _RE_CATEGORY.search(text)
    validated_claims: list[dict[str, str]] = []
    for claim_match in _RE_CLAIM.finditer(text):
        validated_claims.append(
            {
                "claim": claim_match.group(1).strip(),
                "evidence_source": claim_match.group(2).strip(),
            }
        )

    remediation_steps: list[str] = []
    for rem_match in _RE_REMEDIATION.finditer(text):
        remediation_steps.append(rem_match.group(1).strip())

    return {
        "root_cause": (root_cause_match.group(1).strip() if root_cause_match else text.strip()),
        "root_cause_category": (
            category_match.group(1).strip().lower() if category_match else "unknown"
        ),
        "validated_claims": validated_claims,
        "remediation_steps": remediation_steps,
        "report": text.strip(),
    }


def build_gold_final_state(
    *,
    root_cause_category: str,
    model_response: str,
    required_evidence_sources: list[str] | tuple[str, ...],
    canonical_root_cause: str = "",
    suite: str = "rds",
) -> dict[str, Any]:
    if suite == "rds":
        parsed = parse_rds_model_response(model_response)
        root_cause = canonical_root_cause or str(parsed.get("root_cause", ""))
        category = parsed.get("root_cause_category") or root_cause_category
        validated_claims = parsed.get("validated_claims") or []
        remediation_steps = parsed.get("remediation_steps") or []
        report = parsed.get("report") or model_response
    else:
        root_cause = canonical_root_cause or model_response.strip()
        category = root_cause_category
        validated_claims = []
        remediation_steps = []
        report = model_response

    evidence = {
        source: {"present": True, "summary": "gold fixture"} for source in required_evidence_sources
    }

    return {
        "root_cause": root_cause,
        "root_cause_category": str(category).strip().lower(),
        "validated_claims": validated_claims,
        "non_validated_claims": [],
        "remediation_steps": remediation_steps,
        "report": report,
        "evidence": evidence,
        "validity_score": 0.85,
        "top_hypotheses": [],
    }


def compute_precision_at_1(
    *,
    actual_category: str,
    accepted_categories: frozenset[str],
    root_cause_present: bool,
    canonical_root_cause: str = "",
    actual_root_cause: str = "",
) -> float:
    if not root_cause_present:
        return 0.0
    category = actual_category.strip().lower()
    if category not in accepted_categories:
        return 0.0
    if canonical_root_cause:
        normalized_gold = _normalize(canonical_root_cause)
        normalized_actual = _normalize(actual_root_cause)
        if normalized_gold and normalized_gold not in normalized_actual:
            return 0.0
    return 1.0


def compute_top3_recall(
    *,
    contributing_factors: tuple[str, ...],
    top_hypotheses: list[str],
    precision_at_1: float,
) -> float:
    if not contributing_factors:
        return precision_at_1
    normalized_top = [_normalize(item) for item in top_hypotheses[:3]]
    if not normalized_top and precision_at_1 >= 1.0:
        normalized_top = [_normalize(item) for item in contributing_factors[:1]]
    for factor in contributing_factors:
        token = _normalize(factor)
        if any(token in hypothesis or hypothesis in token for hypothesis in normalized_top):
            return 1.0
    return 0.0


def compute_evidence_grounding_rate(
    *,
    validated_claims: list[dict[str, Any]],
    evidence: dict[str, Any],
    required_evidence_sources: tuple[str, ...] | list[str],
) -> float:
    if not validated_claims:
        if required_evidence_sources:
            present = sum(1 for source in required_evidence_sources if evidence.get(source))
            return present / len(required_evidence_sources)
        return 1.0

    grounded = 0
    for claim in validated_claims:
        source = str(
            claim.get("evidence_source") or claim.get("source") or claim.get("evidence") or ""
        ).strip()
        if source and evidence.get(source):
            grounded += 1
    return grounded / len(validated_claims)


def compute_false_confidence(*, validity_score: float | None, precision_at_1: float) -> float:
    if validity_score is None:
        return 0.0
    if validity_score >= FALSE_CONFIDENCE_THRESHOLD and precision_at_1 < 1.0:
        return 1.0
    return 0.0


def compute_actionability_rate(
    *,
    report: str,
    remediation_steps: list[str] | tuple[str, ...],
    required_keywords: tuple[str, ...] | list[str],
    min_actionability_keywords: tuple[str, ...] | list[str],
) -> float:
    keywords = tuple(min_actionability_keywords) or tuple(required_keywords)
    if not keywords:
        return 1.0
    haystack = _normalize(" ".join([report, " ".join(str(step) for step in remediation_steps)]))
    matched = sum(1 for keyword in keywords if _normalize(keyword) in haystack)
    return matched / len(keywords)


def metrics_from_final_state(
    *,
    case_id: str,
    adapter: str,
    final_state: dict[str, Any],
    accepted_categories: frozenset[str],
    contributing_factors: tuple[str, ...] = (),
    canonical_root_cause: str = "",
    required_evidence_sources: tuple[str, ...] = (),
    required_keywords: tuple[str, ...] = (),
    min_actionability_keywords: tuple[str, ...] = (),
) -> CaseMetrics:
    root_cause = str(final_state.get("root_cause") or "").strip()
    root_cause_present = bool(root_cause and root_cause.lower() != "unable to determine root cause")
    actual_category = str(final_state.get("root_cause_category") or "unknown").strip().lower()
    validated_claims = list(final_state.get("validated_claims") or [])
    evidence = dict(final_state.get("evidence") or {})
    top_hypotheses = [str(item) for item in (final_state.get("top_hypotheses") or [])]
    validity_raw = final_state.get("validity_score")
    validity_score = float(validity_raw) if isinstance(validity_raw, (int, float)) else None

    precision = compute_precision_at_1(
        actual_category=actual_category,
        accepted_categories=accepted_categories,
        root_cause_present=root_cause_present,
        canonical_root_cause=canonical_root_cause,
        actual_root_cause=root_cause,
    )
    top3 = compute_top3_recall(
        contributing_factors=contributing_factors,
        top_hypotheses=top_hypotheses,
        precision_at_1=precision,
    )
    grounding = compute_evidence_grounding_rate(
        validated_claims=validated_claims,
        evidence=evidence,
        required_evidence_sources=required_evidence_sources,
    )
    false_conf = compute_false_confidence(validity_score=validity_score, precision_at_1=precision)
    actionability = compute_actionability_rate(
        report=str(final_state.get("report") or ""),
        remediation_steps=list(final_state.get("remediation_steps") or []),
        required_keywords=required_keywords,
        min_actionability_keywords=min_actionability_keywords,
    )

    return CaseMetrics(
        case_id=case_id,
        adapter=adapter,
        precision_at_1=precision,
        top3_recall=top3,
        evidence_grounding_rate=grounding,
        false_confidence_rate=false_conf,
        actionability_rate=actionability,
        validity_score=validity_score,
        passed=precision >= 1.0 and grounding >= 0.85 and actionability >= 0.70,
    )
