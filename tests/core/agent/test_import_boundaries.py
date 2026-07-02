"""Import-boundary tests for the surface-agnostic agent engine."""

from __future__ import annotations

import ast
from pathlib import Path


def _repo_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "pyproject.toml").is_file():
            return parent
    return Path(__file__).resolve().parents[3]


def _collect_surface_import_offenders(
    root: Path,
    *,
    package_root: Path,
    forbidden_modules: frozenset[str],
    forbidden_prefixes: tuple[str, ...],
) -> list[str]:
    offenders: list[str] = []
    for path in sorted(package_root.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    name = alias.name
                    if name in forbidden_modules or any(
                        name.startswith(prefix) for prefix in forbidden_prefixes
                    ):
                        offenders.append(str(path.relative_to(root)))
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if module in forbidden_modules or any(
                    module.startswith(prefix) for prefix in forbidden_prefixes
                ):
                    offenders.append(str(path.relative_to(root)))
    return offenders


def test_core_agent_harness_does_not_import_interactive_shell() -> None:
    root = _repo_root()
    offenders = _collect_surface_import_offenders(
        root,
        package_root=root / "core" / "agent_harness",
        forbidden_modules=frozenset({"interactive_shell", "surfaces.interactive_shell"}),
        forbidden_prefixes=("surfaces.interactive_shell.",),
    )
    assert not offenders, "\n".join(offenders)


def test_core_agent_harness_does_not_import_surfaces_cli() -> None:
    root = _repo_root()
    offenders = _collect_surface_import_offenders(
        root,
        package_root=root / "core" / "agent_harness",
        forbidden_modules=frozenset({"surfaces.cli"}),
        forbidden_prefixes=("surfaces.cli.",),
    )
    assert not offenders, "\n".join(offenders)
