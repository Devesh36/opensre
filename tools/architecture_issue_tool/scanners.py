"""Path helpers, CI bridge, AST utilities, and architecture violation scanners."""

from __future__ import annotations

import ast
import importlib
import re
import sys
from collections import defaultdict
from functools import lru_cache
from pathlib import Path
from typing import Any, Protocol, cast

from tools.architecture_issue_tool.models import ArchitectureViolation

# ---------------------------------------------------------------------------
# Repository paths (aligned with .github/ci/check_import_cycles.py)
# ---------------------------------------------------------------------------

_SKIP_ROOT_DIRS = frozenset(
    {
        ".git",
        ".github",
        ".pytest_cache",
        ".ruff_cache",
        ".venv",
        "__pycache__",
        "docs",
        "opensre.egg-info",
        "packaging",
        "tests",
        "venv",
    }
)


def default_repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def resolve_repo_root(repo_root: str | None) -> Path:
    if repo_root:
        return Path(repo_root).resolve()
    return default_repo_root()


@lru_cache(maxsize=32)
def discover_first_party_roots_cached(repo_root_str: str) -> tuple[str, ...]:
    root = Path(repo_root_str)
    names: list[str] = []
    if not root.is_dir():
        return ()
    for child in sorted(root.iterdir()):
        if not child.is_dir() or child.name.startswith("."):
            continue
        if child.name in _SKIP_ROOT_DIRS:
            continue
        if not any(child.rglob("*.py")):
            continue
        names.append(child.name)
    return tuple(names)


def iter_python_files(repo_root: Path, first_party_roots: tuple[str, ...]) -> list[Path]:
    files: list[Path] = []
    for pkg in first_party_roots:
        pkg_path = repo_root / pkg
        if not pkg_path.exists():
            continue
        for py in pkg_path.rglob("*.py"):
            if "__pycache__" in py.parts:
                continue
            files.append(py)
    return sorted(files)


def module_path_from_file(repo_root: Path, py_file: Path) -> str:
    rel = py_file.with_suffix("").relative_to(repo_root)
    parts = rel.parts
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def file_path_from_module(repo_root: Path, module: str) -> str:
    parts = module.split(".")
    candidate = repo_root.joinpath(*parts).with_suffix(".py")
    if candidate.is_file():
        return str(candidate.relative_to(repo_root))
    package_init = repo_root.joinpath(*parts, "__init__.py")
    if package_init.is_file():
        return str(package_init.relative_to(repo_root))
    return "/".join(parts) + ".py"


# ---------------------------------------------------------------------------
# AST helpers
# ---------------------------------------------------------------------------


def read_source_safe(py_file: Path) -> str | None:
    try:
        return py_file.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return None


def parse_module(source: str) -> ast.Module | None:
    try:
        return ast.parse(source)
    except SyntaxError:
        return None


def class_base_names(node: ast.ClassDef) -> set[str]:
    names: set[str] = set()
    for base in node.bases:
        if isinstance(base, ast.Name):
            names.add(base.id)
        elif isinstance(base, ast.Attribute):
            names.add(base.attr)
    return names


def inherits_from(node: ast.ClassDef, base_names: set[str]) -> bool:
    return bool(class_base_names(node) & base_names)


# ---------------------------------------------------------------------------
# CI import-graph bridge
# ---------------------------------------------------------------------------

_CI_DIR = Path(__file__).resolve().parents[2] / ".github" / "ci"
if str(_CI_DIR) not in sys.path:
    sys.path.insert(0, str(_CI_DIR))

_check_direct_imports = importlib.import_module("check_direct_imports")
_check_import_cycles = importlib.import_module("check_import_cycles")

for symbol in ("_BASELINE_IGNORES", "DirectViolation", "find_direct_violations"):
    if not hasattr(_check_direct_imports, symbol):
        msg = f"check_direct_imports is missing required symbol {symbol!r}"
        raise ImportError(msg)

for symbol in ("_build_graph", "_top_level_imports"):
    if not hasattr(_check_import_cycles, symbol):
        msg = f"check_import_cycles is missing required symbol {symbol!r}"
        raise ImportError(msg)

_BASELINE_IGNORES = cast(Any, _check_direct_imports._BASELINE_IGNORES)
find_direct_violations = cast(Any, _check_direct_imports.find_direct_violations)
_top_level_imports = cast(Any, _check_import_cycles._top_level_imports)


class _DirectViolationLike(Protocol):
    source: str
    target: str


def build_import_graph(root: Path, first_party_roots: tuple[str, ...]) -> dict[str, set[str]]:
    roots = frozenset(first_party_roots)
    graph: dict[str, set[str]] = defaultdict(set)
    for pkg in first_party_roots:
        pkg_path = root / pkg
        if not pkg_path.exists():
            continue
        for py in pkg_path.rglob("*.py"):
            if "__pycache__" in py.parts:
                continue
            module = ".".join(py.with_suffix("").relative_to(root).parts)
            module = module.removesuffix(".__init__")
            source = read_source_safe(py)
            if source is None:
                continue
            graph[module].update(_top_level_imports(source, first_party_roots=roots))
    return graph


# ---------------------------------------------------------------------------
# Dependency direction scanner
# ---------------------------------------------------------------------------

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
_FORBIDDEN_CORE_PREFIXES: tuple[str, ...] = ("cli", "integrations.tracer")
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
    tree = parse_module(source)
    if tree is None:
        return []
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
    violation: _DirectViolationLike,
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
        source = read_source_safe(py_file)
        if source is None:
            continue
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
    graph = build_import_graph(repo_root, roots)

    baseline_ignores = frozenset() if include_baselines else _BASELINE_IGNORES
    direct_violations = find_direct_violations(graph, baseline_ignores=baseline_ignores)

    violations: list[ArchitectureViolation] = []
    for direct in direct_violations:
        is_baseline = direct.edge in _BASELINE_IGNORES
        violations.append(_violation_from_direct(repo_root, direct, is_baseline_ignore=is_baseline))

    violations.extend(_scan_core_prefix_violations(repo_root))
    return violations


# ---------------------------------------------------------------------------
# Oversized file scanner
# ---------------------------------------------------------------------------


def _non_blank_line_count(source: str) -> int:
    return sum(1 for line in source.splitlines() if line.strip())


def scan_oversized_files(
    repo_root: Path,
    *,
    max_file_lines: int = 500,
) -> list[ArchitectureViolation]:
    roots = discover_first_party_roots_cached(str(repo_root))
    violations: list[ArchitectureViolation] = []
    for py_file in iter_python_files(repo_root, roots):
        rel_path = str(py_file.relative_to(repo_root))
        source = read_source_safe(py_file)
        if source is None:
            continue
        line_count = _non_blank_line_count(source)
        if line_count <= max_file_lines:
            continue
        violations.append(
            ArchitectureViolation(
                type="oversized_file",
                file_path=rel_path,
                description=(
                    f"File has {line_count} non-blank lines, exceeding the limit of "
                    f"{max_file_lines}. Consider extracting focused sibling modules."
                ),
                details={"line_count": line_count, "max_file_lines": max_file_lines},
            )
        )
    return violations


# ---------------------------------------------------------------------------
# Compatibility shim scanner
# ---------------------------------------------------------------------------


def _is_reexport_value(node: ast.expr | None) -> bool:
    return isinstance(node, (ast.Name, ast.Attribute))


def _is_simple_alias(node: ast.stmt) -> bool:
    if isinstance(node, ast.Assign):
        return all(isinstance(target, ast.Name) for target in node.targets)
    if isinstance(node, ast.AnnAssign):
        return isinstance(node.target, ast.Name)
    return False


def _has_real_import(body: list[ast.stmt]) -> bool:
    for node in body:
        if isinstance(node, ast.ImportFrom):
            if node.module and node.module != "__future__":
                return True
        elif isinstance(node, ast.Import) and any(
            alias.name != "__future__" for alias in node.names
        ):
            return True
    return False


def _is_allowed_shim_statement(node: ast.stmt) -> bool:
    if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant):
        return isinstance(node.value.value, str)
    if isinstance(node, (ast.Import, ast.ImportFrom)):
        return True
    if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
        if node.targets[0].id == "__all__":
            return True
        return _is_simple_alias(node) and _is_reexport_value(node.value)
    if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
        return node.value is not None and _is_reexport_value(node.value)
    return isinstance(node, ast.FunctionDef) and node.name == "__getattr__"


def _is_compatibility_shim(source: str) -> bool:
    tree = parse_module(source)
    if tree is None:
        return False
    body = tree.body
    if not body or not _has_real_import(body):
        return False
    return all(_is_allowed_shim_statement(node) for node in body)


def scan_compatibility_shims(repo_root: Path) -> list[ArchitectureViolation]:
    roots = discover_first_party_roots_cached(str(repo_root))
    violations: list[ArchitectureViolation] = []
    for py_file in iter_python_files(repo_root, roots):
        if py_file.name == "__init__.py":
            continue
        rel_path = str(py_file.relative_to(repo_root))
        source = read_source_safe(py_file)
        if source is None:
            continue
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


# ---------------------------------------------------------------------------
# Misplaced module scanner
# ---------------------------------------------------------------------------

_TOOL_DECORATOR_NAMES = {"tool"}
_BASE_TOOL_NAMES = {"BaseTool"}
_CLIENT_FILE_NAMES = frozenset({"client.py", "verifier.py"})
_CLIENT_CLASS_PATTERN = re.compile(r"^class\s+(\w+(Client|Verifier))\b", re.MULTILINE)
_ALLOWED_TOOL_FRAMEWORK_PREFIXES = ("core/tool_framework/",)


def _is_tool_definition(tree: ast.Module) -> bool:
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and inherits_from(node, _BASE_TOOL_NAMES):
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
    if any(rel_path.startswith(prefix) for prefix in _ALLOWED_TOOL_FRAMEWORK_PREFIXES):
        return True
    if rel_path.startswith("tools/"):
        return True
    return "/tools/" in rel_path and rel_path.startswith("integrations/")


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
        source = read_source_safe(py_file)
        if source is None:
            continue
        module = module_path_from_file(repo_root, py_file)
        tree = parse_module(source)
        if tree is None:
            continue

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
