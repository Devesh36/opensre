"""Architecture violation scanner tool registration."""

from __future__ import annotations

from typing import Any

from core.tool_framework.tool_decorator import tool
from tools.architecture_issue_tool.scan import (
    propose_github_issues_from_tasks,
    run_architecture_scan,
)


@tool(
    name="find_architecture_violations",
    display_name="Architecture violation scan",
    source="knowledge",
    description=(
        "Scan the repository for architecture violations: dependency direction "
        "problems, oversized files, compatibility shims, and misplaced modules. "
        "Returns proposed refactor tasks plus a deterministic `report` text field "
        "listing every violation type; does not modify code or create GitHub issues. "
        "For identical CLI/REPL output without summarization, use "
        "`opensre architecture-scan` or `/architecture-scan`."
    ),
    use_cases=[
        "Auditing layering violations before a refactor PR",
        "Finding compatibility-only forwarding modules to remove",
        "Identifying oversized modules that should be split into sibling files",
        "Detecting agent tools or integration clients in the wrong package layer",
        "Generating atomic refactor task proposals for maintainers",
    ],
    tags=("safe", "fast", "no-credentials"),
    cost_tier="cheap",
    side_effect_level="read_only",
    surfaces=("investigation", "chat"),
    input_schema={
        "type": "object",
        "properties": {
            "repo_root": {
                "type": "string",
                "description": "Optional absolute path to the repository root.",
            },
            "max_file_lines": {
                "type": "integer",
                "description": "Non-blank line limit for oversized file detection.",
                "default": 500,
            },
            "include_baselines": {
                "type": "boolean",
                "description": ("When true, include known baseline dependency debt tracked in CI."),
                "default": False,
            },
        },
        "required": [],
    },
)
def find_architecture_violations(
    repo_root: str | None = None,
    max_file_lines: int = 500,
    include_baselines: bool = False,
) -> dict[str, Any]:
    """Scan the repository for architecture violations and propose refactor tasks."""
    return run_architecture_scan(
        repo_root=repo_root,
        max_file_lines=max_file_lines,
        include_baselines=include_baselines,
    )


@tool(
    name="propose_github_issues_from_architecture_tasks",
    display_name="Propose GitHub issues from architecture tasks",
    source="knowledge",
    description=(
        "Build read-only GitHub create-issue proposals from proposed_refactor_tasks "
        "returned by find_architecture_violations. Does not call GitHub or create "
        "issues; execute each approved proposal with execute_github_issue_mutation."
    ),
    use_cases=[
        "Turning architecture scan refactor tasks into GitHub issue proposals",
        "Preparing maintainer review packets before filing architecture debt issues",
    ],
    anti_examples=[
        "Creating GitHub issues without human approval",
        "Running during investigations that should stay read-only end-to-end",
    ],
    tags=("safe", "no-credentials"),
    cost_tier="cheap",
    side_effect_level="read_only",
    surfaces=("chat",),
    input_schema={
        "type": "object",
        "properties": {
            "owner": {"type": "string", "description": "GitHub repository owner."},
            "repo": {"type": "string", "description": "GitHub repository name."},
            "proposed_refactor_tasks": {
                "type": "array",
                "description": (
                    "proposed_refactor_tasks array from find_architecture_violations output."
                ),
                "items": {"type": "object"},
            },
            "task_indices": {
                "type": "array",
                "description": (
                    "Optional 0-based indices into proposed_refactor_tasks. "
                    "Omit to propose issues for every task."
                ),
                "items": {"type": "integer"},
            },
        },
        "required": ["owner", "repo", "proposed_refactor_tasks"],
    },
)
def propose_github_issues_from_architecture_tasks(
    owner: str,
    repo: str,
    proposed_refactor_tasks: list[dict[str, Any]],
    task_indices: list[int] | None = None,
) -> dict[str, Any]:
    """Build GitHub issue mutation proposals for architecture refactor tasks."""
    return propose_github_issues_from_tasks(
        owner=owner,
        repo=repo,
        proposed_refactor_tasks=proposed_refactor_tasks,
        task_indices=task_indices,
    )
