"""Tests for find_architecture_violations tool."""

from __future__ import annotations

import sys
from pathlib import Path

from tests.tools.conftest import BaseToolContract
from tools.architecture_issue_tool.paths import default_repo_root, resolve_repo_root
from tools.architecture_issue_tool.scan import run_architecture_scan
from tools.architecture_issue_tool.scanners.dependencies import (
    _matches_prefix,
    scan_dependency_violations,
)
from tools.architecture_issue_tool.scanners.shims import scan_compatibility_shims
from tools.architecture_issue_tool.tool import find_architecture_violations

_CI_DIR = Path(__file__).resolve().parents[2] / ".github" / "ci"
if str(_CI_DIR) not in sys.path:
    sys.path.insert(0, str(_CI_DIR))

from check_direct_imports import find_direct_violations  # noqa: E402


class TestArchitectureIssueToolContract(BaseToolContract):
    def get_tool_under_test(self):
        return find_architecture_violations.__opensre_registered_tool__


def test_find_architecture_violations_mock_project(tmp_path: Path) -> None:
    core_domain = tmp_path / "core" / "domain"
    core_domain.mkdir(parents=True)
    integrations_dir = tmp_path / "integrations"
    integrations_dir.mkdir()
    tools_dir = tmp_path / "tools"
    tools_dir.mkdir()

    (core_domain / "module.py").write_text(
        "from integrations.some_integration import helper\n",
        encoding="utf-8",
    )
    (core_domain / "big.py").write_text("\n".join(["line"] * 10) + "\n", encoding="utf-8")
    (integrations_dir / "shim.py").write_text(
        '"""Forwarding shim."""\nfrom core.module import foo\n__all__ = ["foo"]\n',
        encoding="utf-8",
    )
    (core_domain / "misplaced_tool.py").write_text(
        "from core.tool_framework.tool_decorator import tool\n"
        '@tool(name="bad_tool", source="knowledge")\n'
        "def run_tool():\n"
        "    pass\n",
        encoding="utf-8",
    )
    (tools_dir / "my_client.py").write_text("class MyClient:\n    pass\n", encoding="utf-8")

    result = find_architecture_violations(repo_root=str(tmp_path), max_file_lines=4)

    violations = result["violations"]
    proposed_tasks = result["proposed_refactor_tasks"]

    dep_violations = [v for v in violations if v["type"] == "dependency_direction"]
    assert dep_violations
    assert any(
        "core-to-integration" in v["description"]
        or "integrations.some_integration" in v["description"]
        for v in dep_violations
    )

    oversized = [v for v in violations if v["type"] == "oversized_file"]
    assert oversized
    assert oversized[0]["details"]["line_count"] == 10

    shims = [v for v in violations if v["type"] == "compatibility_shim"]
    assert shims

    misplaced = [v for v in violations if v["type"] == "misplaced_module"]
    assert len(misplaced) >= 2

    assert len(proposed_tasks) == len(violations)
    assert result["summary"]["total"] == len(violations)
    assert "github_issue_creation" in result


def test_shim_scanner_skips_substantive_init(tmp_path: Path) -> None:
    pkg = tmp_path / "tools" / "sample_tool"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text(
        '"""Public facade."""\nfrom tools.sample_tool.tool import SampleTool\n\n'
        "def helper() -> str:\n"
        '    return "ok"\n',
        encoding="utf-8",
    )
    violations = scan_compatibility_shims(tmp_path)
    assert violations == []


def test_baseline_prefix_does_not_suppress_distinct_module() -> None:
    graph = {
        "integrations.client.module": {"tools.registry"},
    }
    violations = find_direct_violations(
        graph,
        baseline_ignores=frozenset({"integrations.cli.module -> tools.registry"}),
    )
    edges = {v.edge for v in violations}
    assert "integrations.client.module -> tools.registry" in edges


def test_matches_prefix_requires_dot_boundary() -> None:
    assert _matches_prefix("integrations.client", "integrations.cli") is False
    assert _matches_prefix("integrations.cli.module", "integrations.cli") is True


def test_find_direct_violations_flags_forbidden_edge() -> None:
    graph = {
        "integrations.grafana.tools": {"tools.registry"},
        "tools.fleet_monitoring": {"surfaces.cli.commands.doctor"},
    }
    violations = find_direct_violations(graph, baseline_ignores=frozenset())
    edges = {v.edge for v in violations}
    assert "integrations.grafana.tools -> tools.registry" in edges
    assert "tools.fleet_monitoring -> surfaces.cli.commands.doctor" in edges


def test_include_baselines_reports_known_debt(tmp_path: Path) -> None:
    tools_dir = tmp_path / "tools"
    tools_dir.mkdir()
    (tools_dir / "sample.py").write_text("pass\n", encoding="utf-8")

    without = scan_dependency_violations(tmp_path, include_baselines=False)
    with_baselines = scan_dependency_violations(tmp_path, include_baselines=True)
    assert len(with_baselines) >= len(without)


def test_dogfood_scan_on_repo_root() -> None:
    repo_root = default_repo_root()
    result = run_architecture_scan(repo_root=str(repo_root), max_file_lines=500)
    assert isinstance(result["violations"], list)
    assert isinstance(result["proposed_refactor_tasks"], list)
    assert "total" in result["summary"]
    assert result["summary"]["total"] == len(result["violations"])


def test_tool_discovered_on_investigation_surface() -> None:
    from tools.registry import clear_tool_registry_cache, get_registered_tools

    clear_tool_registry_cache()
    names = {t.name for t in get_registered_tools("investigation")}
    assert "find_architecture_violations" in names


def test_resolve_repo_root_uses_checkout_when_none() -> None:
    assert resolve_repo_root(None) == default_repo_root()


def test_missing_repo_root_returns_error(tmp_path: Path) -> None:
    missing = tmp_path / "missing"
    result = find_architecture_violations(repo_root=str(missing))
    assert "error" in result
