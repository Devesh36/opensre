"""Orchestrate architecture violation scans."""

from __future__ import annotations

from typing import Any

from tools.architecture_issue_tool.models import ArchitectureViolation
from tools.architecture_issue_tool.paths import resolve_repo_root
from tools.architecture_issue_tool.scanners.dependencies import scan_dependency_violations
from tools.architecture_issue_tool.scanners.misplaced import scan_misplaced_modules
from tools.architecture_issue_tool.scanners.oversized import scan_oversized_files
from tools.architecture_issue_tool.scanners.shims import scan_compatibility_shims
from tools.architecture_issue_tool.task_builder import (
    build_refactor_tasks,
    build_summary,
    github_issue_creation_guidance,
)


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
    return {
        "violations": [v.to_dict() for v in violations],
        "proposed_refactor_tasks": [t.to_dict() for t in tasks],
        "summary": build_summary(violations),
        "github_issue_creation": github_issue_creation_guidance(),
    }
