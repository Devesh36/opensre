"""Convert architecture violations into atomic refactor task proposals."""

from __future__ import annotations

from tools.architecture_issue_tool.models import (
    ArchitectureViolation,
    RefactorPriority,
    RefactorTask,
)

_GITHUB_ISSUE_GUIDANCE = (
    "Use propose_github_issue_mutation_from_slack + execute_github_issue_mutation "
    "per task; the scanner does not create GitHub issues automatically."
)


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
    tasks: list[RefactorTask] = []
    for violation in violations:
        tasks.append(
            RefactorTask(
                title=_title_for(violation),
                description=_description_for(violation),
                target_file=violation.file_path,
                violation_type=violation.type,
                priority=_priority_for(violation),
            )
        )
    return tasks


def build_summary(violations: list[ArchitectureViolation]) -> dict[str, object]:
    by_type: dict[str, int] = {}
    for violation in violations:
        by_type[violation.type] = by_type.get(violation.type, 0) + 1
    return {"total": len(violations), "by_type": by_type}


def github_issue_creation_guidance() -> str:
    return _GITHUB_ISSUE_GUIDANCE
