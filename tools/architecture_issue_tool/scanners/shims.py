"""Compatibility shim / forwarding module scanner."""

from __future__ import annotations

import ast
from pathlib import Path

from tools.architecture_issue_tool.models import ArchitectureViolation
from tools.architecture_issue_tool.paths import (
    discover_first_party_roots_cached,
    iter_python_files,
    module_path_from_file,
)


def _is_simple_alias(node: ast.stmt) -> bool:
    if isinstance(node, ast.Assign):
        return all(isinstance(target, ast.Name) for target in node.targets)
    if isinstance(node, ast.AnnAssign):
        return isinstance(node.target, ast.Name)
    return False


def _is_allowed_statement(node: ast.stmt) -> bool:
    if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant):
        return isinstance(node.value.value, str)
    if isinstance(node, (ast.Import, ast.ImportFrom)):
        return True
    if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
        if node.targets[0].id == "__all__":
            return True
        return _is_simple_alias(node)
    if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
        return _is_simple_alias(node)
    return isinstance(node, ast.FunctionDef) and node.name == "__getattr__"


def _is_compatibility_shim(source: str) -> bool:
    tree = ast.parse(source)
    body = tree.body
    if not body:
        return False
    if any(not _is_allowed_statement(node) for node in body):
        return False
    has_import = any(isinstance(node, (ast.Import, ast.ImportFrom)) for node in body)
    return has_import


def scan_compatibility_shims(repo_root: Path) -> list[ArchitectureViolation]:
    roots = discover_first_party_roots_cached(str(repo_root))
    violations: list[ArchitectureViolation] = []
    for py_file in iter_python_files(repo_root, roots):
        if py_file.name == "__init__.py":
            continue
        rel_path = str(py_file.relative_to(repo_root))
        source = py_file.read_text(encoding="utf-8")
        if "# architecture:facade" in source:
            continue
        if not _is_compatibility_shim(source):
            continue
        module = module_path_from_file(repo_root, py_file)
        violations.append(
            ArchitectureViolation(
                type="compatibility_shim",
                file_path=rel_path,
                description=(
                    f"Module '{module}' appears to be a compatibility-only forwarding module."
                ),
                details={"module": module},
            )
        )
    return violations
