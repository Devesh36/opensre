"""Architecture violation scanner tool registration."""

from __future__ import annotations

from typing import Any

from core.tool_framework.tool_decorator import tool
from tools.architecture_issue_tool.scan import run_architecture_scan


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
