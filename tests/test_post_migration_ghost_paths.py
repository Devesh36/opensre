"""Regression guard: post-V0.2 migration ghost directories must not reappear.

After vendor tools moved to ``integrations/<vendor>/tools/`` and system tools to
``tools/system/``, several empty ``tools/`` stubs and pre-refactor ``tests/``
namespaces were left behind with only ``__pycache__``. Those paths are not
imported and confuse contributors; keep the canonical locations only.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Empty stubs from tools/ → integrations/ or tools/system/ migration.
REMOVED_TOOLS_PATHS = (
    "tools/architecture_issue_tool",
    "tools/fix_sentry_issue",
    "tools/fleet_monitoring",
    "tools/python_execution_tool",
    "tools/sre_guidance_tool",
    "tools/watch_dog",
    "tools/utils",
    "tools/github",
    "tools/github_actions_tool",
    "tools/github_commits_tool",
    "tools/github_file_contents_tool",
    "tools/github_issues_tool",
    "tools/github_repository_tree_tool",
    "tools/github_search_code_tool",
)

# Legacy pre-refactor test namespaces (replaced by tests/core/, tests/tools/, etc.).
REMOVED_TESTS_PATHS = (
    "tests/app",
    "tests/nodes",
    "tests/services",
    "tests/agents",
)

# Collapsed into core/state/ during the state-package refactor.
REMOVED_CORE_PATHS = ("core/context",)


def test_post_migration_ghost_paths_do_not_exist() -> None:
    offenders = [
        rel
        for rel in (*REMOVED_TOOLS_PATHS, *REMOVED_TESTS_PATHS, *REMOVED_CORE_PATHS)
        if (ROOT / rel).exists()
    ]
    assert offenders == [], (
        "Post-migration ghost paths must not exist. Remove these directories "
        f"(they only contained stale __pycache__): {offenders}"
    )
