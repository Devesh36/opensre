"""Dependency direction violation scanner."""

from __future__ import annotations

import ast
from pathlib import Path

from tools.architecture_issue_tool.ci_bridge import (
    _BASELINE_IGNORES,
    DirectViolation,
    _build_graph,
    find_direct_violations,
)
from tools.architecture_issue_tool.models import ArchitectureViolation
from tools.architecture_issue_tool.paths import (
    discover_first_party_roots_cached,
    file_path_from_module,
    module_path_from_file,
)

# Mirrors tests/test_core_layering.py forbidden prefixes for core-facing packages.
_CORE_SCAN_ROOTS: tuple[str, ...] = (
    "core/domain",
    "tools/investigation",
    "platform/observability",
)
_CORE_ONLY_ROOTS: tuple[str, ...] = ("core/domain",)
_CORE_RUNTIME_FILES: tuple[str, ...] = (
    "core/__init__.py",
    "core/agent.py",
    "core/context_budget.py",
    "core/events.py",
    "core/execution.py",
    "core/llm_invoke_errors.py",
    "core/messages/__init__.py",
    "core/messages/message_formatter.py",
    "core/messages/runtime_message_types.py",
    "core/provider.py",
    "core/types.py",
)
_FORBIDDEN_CORE_PREFIXES: tuple[str, ...] = (
    "cli",
    "integrations.tracer",
)
_INVESTIGATION_TOOL_PREFIX = "tools.investigation"
_ALLOWED_CORE_INTEGRATION_PREFIXES: tuple[str, ...] = ("integrations.port",)


def _matches_prefix(module: str, prefix: str) -> bool:
    return module == prefix or module.startswith(f"{prefix}.")


def _core_scan_files(repo_root: Path) -> list[Path]:
    files: list[Path] = []
    for rel in _CORE_SCAN_ROOTS:
        root = repo_root / rel
        if root.is_dir():
            files.extend(p for p in root.rglob("*.py") if "__pycache__" not in p.parts)
    for rel in _CORE_RUNTIME_FILES:
        candidate = repo_root / rel
        if candidate.is_file():
            files.append(candidate)
    return sorted(set(files))


def _core_only_scan_files(repo_root: Path) -> list[Path]:
    files: list[Path] = []
    for rel in _CORE_ONLY_ROOTS:
        root = repo_root / rel
        if root.is_dir():
            files.extend(p for p in root.rglob("*.py") if "__pycache__" not in p.parts)
    for rel in _CORE_RUNTIME_FILES:
        candidate = repo_root / rel
        if candidate.is_file():
            files.append(candidate)
    return sorted(set(files))


def _imported_modules_with_lines(source: str) -> list[tuple[str, int]]:
    tree = ast.parse(source)
    imports: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append((alias.name, node.lineno))
        elif isinstance(node, ast.ImportFrom):
            if node.level or not node.module:
                continue
            imports.append((node.module, node.lineno))
    return imports


def _violation_from_direct(
    repo_root: Path,
    violation: DirectViolation,
    *,
    is_baseline_ignore: bool,
) -> ArchitectureViolation:
    file_path = file_path_from_module(repo_root, violation.source)
    return ArchitectureViolation(
        type="dependency_direction",
        file_path=file_path,
        description=(
            f"Module '{violation.source}' imports '{violation.target}', "
            f"violating the '{violation.source.split('.', 1)[0]} -> "
            f"{violation.target.split('.', 1)[0]}' dependency restriction."
        ),
        details={
            "source_module": violation.source,
            "imported_module": violation.target,
            "is_baseline_ignore": is_baseline_ignore,
        },
    )


def _scan_core_prefix_violations(repo_root: Path) -> list[ArchitectureViolation]:
    violations: list[ArchitectureViolation] = []
    core_only_files = {str(p.relative_to(repo_root)) for p in _core_only_scan_files(repo_root)}

    for py_file in _core_scan_files(repo_root):
        rel_path = str(py_file.relative_to(repo_root))
        source = py_file.read_text(encoding="utf-8")
        module = module_path_from_file(repo_root, py_file)
        is_core_only = rel_path in core_only_files

        for imported, line_number in _imported_modules_with_lines(source):
            for prefix in _FORBIDDEN_CORE_PREFIXES:
                if not _matches_prefix(imported, prefix):
                    continue
                violations.append(
                    ArchitectureViolation(
                        type="dependency_direction",
                        file_path=rel_path,
                        description=(
                            f"Module '{module}' imports '{imported}', which violates the "
                            f"core layering rule forbidding imports from '{prefix}'."
                        ),
                        details={
                            "source_module": module,
                            "imported_module": imported,
                            "line_number": line_number,
                            "is_baseline_ignore": False,
                        },
                    )
                )
            if is_core_only and _matches_prefix(imported, _INVESTIGATION_TOOL_PREFIX):
                violations.append(
                    ArchitectureViolation(
                        type="dependency_direction",
                        file_path=rel_path,
                        description=(
                            f"Module '{module}' imports '{imported}', which violates the "
                            "core layering rule forbidding imports from 'tools.investigation'."
                        ),
                        details={
                            "source_module": module,
                            "imported_module": imported,
                            "line_number": line_number,
                            "is_baseline_ignore": False,
                        },
                    )
                )
            if (
                is_core_only
                and imported.startswith("integrations.")
                and not any(
                    _matches_prefix(imported, allowed)
                    for allowed in _ALLOWED_CORE_INTEGRATION_PREFIXES
                )
            ):
                violations.append(
                    ArchitectureViolation(
                        type="dependency_direction",
                        file_path=rel_path,
                        description=(
                            f"Module '{module}' imports '{imported}', violating the "
                            "core-to-integration boundary. Route through "
                            "'integrations.port' or a core port instead."
                        ),
                        details={
                            "source_module": module,
                            "imported_module": imported,
                            "line_number": line_number,
                            "is_baseline_ignore": False,
                        },
                    )
                )
    return violations


def scan_dependency_violations(
    repo_root: Path,
    *,
    include_baselines: bool = False,
) -> list[ArchitectureViolation]:
    roots = discover_first_party_roots_cached(str(repo_root))
    graph = _build_graph(repo_root, roots)

    baseline_ignores = frozenset() if include_baselines else _BASELINE_IGNORES
    direct_violations = find_direct_violations(graph, baseline_ignores=baseline_ignores)

    violations: list[ArchitectureViolation] = []
    for direct in direct_violations:
        is_baseline = direct.edge in _BASELINE_IGNORES
        if not include_baselines and is_baseline:
            continue
        violations.append(_violation_from_direct(repo_root, direct, is_baseline_ignore=is_baseline))

    violations.extend(_scan_core_prefix_violations(repo_root))
    return violations
