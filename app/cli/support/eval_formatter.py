"""Post-investigation eval formatting for CLI surfaces."""

from __future__ import annotations

from typing import Any


def _rubric_item_label(item: dict[str, Any]) -> str:
    return str(item.get("name") or item.get("criterion") or item.get("id") or "item")


def _rubric_item_passed(item: dict[str, Any]) -> bool | None:
    if "passed" in item:
        return bool(item.get("passed"))
    if "satisfied" in item:
        return bool(item.get("satisfied"))
    return None


def format_opensre_llm_eval(payload: dict[str, Any]) -> str:
    """Render ``opensre investigate --evaluate`` judge output as a short summary."""
    if payload.get("skipped"):
        return f"Evaluate skipped: {payload.get('reason', 'unknown')}"

    lines = ["OpenRCA LLM judge"]
    score = payload.get("score_0_100")
    if isinstance(score, (int, float)):
        lines.append(f"  score: {int(score)}/100")

    overall = payload.get("overall_pass")
    if overall is not None:
        lines.append(f"  overall_pass: {overall}")

    summary = payload.get("summary")
    if isinstance(summary, str) and summary.strip():
        lines.append(f"  summary: {summary.strip()}")

    rubric_items = payload.get("rubric_items")
    if isinstance(rubric_items, list) and rubric_items:
        lines.append("  rubric:")
        for item in rubric_items[:5]:
            if not isinstance(item, dict):
                continue
            label = _rubric_item_label(item)
            passed = _rubric_item_passed(item)
            if passed is None:
                lines.append(f"    - {label}")
            else:
                lines.append(f"    - {label}: {'pass' if passed else 'fail'}")
        if len(rubric_items) > 5:
            lines.append(f"    … {len(rubric_items) - 5} more item(s)")

    return "\n".join(lines)
