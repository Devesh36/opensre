"""Scan orchestration, refactor task building, and report formatting."""

from __future__ import annotations

from typing import Any

from tools.architecture_issue_tool.models import (
    ArchitectureViolation,
    RefactorPriority,
    RefactorTask,
)
from tools.architecture_issue_tool.scanners import (
    resolve_repo_root,
    scan_compatibility_shims,
    scan_dependency_violations,
    scan_misplaced_modules,
    scan_oversized_files,
)

_GITHUB_ISSUE_GUIDANCE = (
    "Use propose_github_issue_mutation_from_slack + execute_github_issue_mutation "
    "per task; the scanner does not create GitHub issues automatically."
)

_VIOLATION_TYPE_ORDER = (
    "dependency_direction",
    "compatibility_shim",
    "misplaced_module",
    "oversized_file",
)

_SECTION_LABELS: dict[str, str] = {
    "dependency_direction": "Dependency direction",
    "compatibility_shim": "Compatibility shims",
    "misplaced_module": "Misplaced modules",
    "oversized_file": "Oversized files",
}


def _priority_for(violation: ArchitectureViolation) -> RefactorPriority:
    if violation.type == "dependency_direction":
        return "high"
    if violation.type == "compatibility_shim":
        return "medium"
    if violation.type == "oversized_file":
        line_count = int(violation.details.get("line_count", 0))
        return "medium" if line_count > 800 else "low"
    return "medium"


def _title_for(violation: ArchitectureViolation) -> str:
    if violation.type == "dependency_direction":
        return f"Fix dependency direction violation in {violation.file_path}"
    if violation.type == "compatibility_shim":
        return f"Remove compatibility forwarding module {violation.file_path}"
    if violation.type == "oversized_file":
        return f"Split oversized module {violation.file_path}"
    return f"Relocate misplaced module {violation.file_path}"


def _description_for(violation: ArchitectureViolation) -> str:
    if violation.type == "dependency_direction":
        return (
            f"{violation.description} Resolve by moving shared logic to a lower layer "
            "or introducing a port/adapter. See AGENTS.md layering rules."
        )
    if violation.type == "compatibility_shim":
        module = violation.details.get("module", violation.file_path)
        return (
            f"The module '{module}' is a compatibility-only forwarding module. "
            "Migrate remaining import sites to the canonical path and delete this file."
        )
    if violation.type == "oversized_file":
        return (
            f"{violation.description} Extract validation, transport, and formatting "
            "into focused sibling modules."
        )
    return (
        f"{violation.description} Keep agent-callable tools under 'tools/' and "
        "integration clients/config under 'integrations/'."
    )


def build_refactor_tasks(violations: list[ArchitectureViolation]) -> list[RefactorTask]:
    return [
        RefactorTask(
            title=_title_for(violation),
            description=_description_for(violation),
            target_file=violation.file_path,
            violation_type=violation.type,
            priority=_priority_for(violation),
        )
        for violation in violations
    ]


def build_summary(violations: list[ArchitectureViolation]) -> dict[str, object]:
    by_type: dict[str, int] = {}
    for violation in violations:
        by_type[violation.type] = by_type.get(violation.type, 0) + 1
    return {"total": len(violations), "by_type": by_type}


def format_architecture_scan_report(scan_result: dict[str, Any]) -> str:
    """Render a deterministic text report shared by CLI, REPL, and tool output."""
    error = scan_result.get("error")
    if isinstance(error, str) and error:
        return f"Architecture violation scan failed: {error}"

    summary = scan_result.get("summary", {})
    by_type = summary.get("by_type", {})
    total = summary.get("total", 0)
    violations = scan_result.get("violations", [])

    lines = [
        "Architecture violation scan",
        f"Total: {total}",
        "",
        "Summary by type:",
    ]
    for violation_type in _VIOLATION_TYPE_ORDER:
        count = by_type.get(violation_type, 0)
        lines.append(f"  {violation_type}: {count}")

    grouped: dict[str, list[dict[str, Any]]] = {key: [] for key in _VIOLATION_TYPE_ORDER}
    for violation in violations:
        if not isinstance(violation, dict):
            continue
        item_type = violation.get("type")
        if isinstance(item_type, str) and item_type in grouped:
            grouped[item_type].append(violation)

    for violation_type in _VIOLATION_TYPE_ORDER:
        items = grouped[violation_type]
        if not items:
            continue
        label = _SECTION_LABELS[violation_type]
        lines.extend(("", f"=== {label} ({len(items)}) ==="))
        for violation in items:
            file_path = str(violation.get("file_path", ""))
            description = str(violation.get("description", "")).strip()
            details = violation.get("details", {})
            if violation_type == "oversized_file" and isinstance(details, dict):
                line_count = details.get("line_count", "?")
                lines.append(f"  {file_path} ({line_count} lines)")
            else:
                lines.append(f"  {file_path}")
                if description:
                    lines.append(f"    {description}")

    guidance = scan_result.get("github_issue_creation")
    if isinstance(guidance, str) and guidance:
        lines.extend(("", f"GitHub issues: {guidance}"))

    return "\n".join(lines)


def run_architecture_scan(
    *,
    repo_root: str | None = None,
    max_file_lines: int = 500,
    include_baselines: bool = False,
) -> dict[str, Any]:
    root = resolve_repo_root(repo_root)
    if not root.is_dir():
        return {"error": f"Repository root does not exist: {root}"}

    violations: list[ArchitectureViolation] = []
    violations.extend(scan_dependency_violations(root, include_baselines=include_baselines))
    violations.extend(scan_oversized_files(root, max_file_lines=max_file_lines))
    violations.extend(scan_compatibility_shims(root))
    violations.extend(scan_misplaced_modules(root))

    tasks = build_refactor_tasks(violations)
    payload = {
        "violations": [v.to_dict() for v in violations],
        "proposed_refactor_tasks": [t.to_dict() for t in tasks],
        "summary": build_summary(violations),
        "github_issue_creation": _GITHUB_ISSUE_GUIDANCE,
    }
    payload["report"] = format_architecture_scan_report(payload)
    return payload
