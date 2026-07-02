"""Misplaced module scanner for tools/ and integrations/ boundaries."""

from __future__ import annotations

import ast
import re
from pathlib import Path

from tools.architecture_issue_tool.models import ArchitectureViolation
from tools.architecture_issue_tool.paths import (
    discover_first_party_roots_cached,
    iter_python_files,
    module_path_from_file,
)

_TOOL_DECORATOR_NAMES = {"tool"}
_BASE_TOOL_NAMES = {"BaseTool"}
_CLIENT_FILE_NAMES = frozenset({"client.py", "verifier.py"})
_CLIENT_CLASS_PATTERN = re.compile(r"^class\s+(\w+(Client|Verifier))\b")


def _is_tool_definition(tree: ast.Module) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name in _BASE_TOOL_NAMES:
            return True
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for decorator in node.decorator_list:
                name = None
                if isinstance(decorator, ast.Name):
                    name = decorator.id
                elif isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Name):
                    name = decorator.func.id
                if name in _TOOL_DECORATOR_NAMES:
                    return True
    return False


def _is_allowed_tool_path(rel_path: str) -> bool:
    return rel_path.startswith("tools/") or (
        "/tools/" in rel_path and rel_path.startswith("integrations/")
    )


def _is_integration_client_file(rel_path: str, source: str) -> bool:
    if not rel_path.startswith("tools/"):
        return False
    file_name = Path(rel_path).name
    if file_name in _CLIENT_FILE_NAMES:
        return True
    return _CLIENT_CLASS_PATTERN.search(source) is not None


def scan_misplaced_modules(repo_root: Path) -> list[ArchitectureViolation]:
    roots = discover_first_party_roots_cached(str(repo_root))
    violations: list[ArchitectureViolation] = []
    for py_file in iter_python_files(repo_root, roots):
        rel_path = str(py_file.relative_to(repo_root))
        source = py_file.read_text(encoding="utf-8")
        module = module_path_from_file(repo_root, py_file)
        tree = ast.parse(source)

        if _is_tool_definition(tree) and not _is_allowed_tool_path(rel_path):
            violations.append(
                ArchitectureViolation(
                    type="misplaced_module",
                    file_path=rel_path,
                    description=(
                        f"Module '{module}' defines an agent tool but lives outside "
                        "'tools/' or 'integrations/*/tools/'."
                    ),
                    details={"module": module, "reason": "tool_outside_canonical_boundary"},
                )
            )

        if _is_integration_client_file(rel_path, source):
            violations.append(
                ArchitectureViolation(
                    type="misplaced_module",
                    file_path=rel_path,
                    description=(
                        f"Module '{module}' looks like integration client/verifier logic "
                        "inside 'tools/'. Move it to 'integrations/<vendor>/'."
                    ),
                    details={"module": module, "reason": "integration_logic_in_tools"},
                )
            )
    return violations
