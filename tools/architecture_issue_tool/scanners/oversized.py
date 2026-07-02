"""Oversized Python file scanner."""

from __future__ import annotations

from pathlib import Path

from tools.architecture_issue_tool.models import ArchitectureViolation
from tools.architecture_issue_tool.paths import discover_first_party_roots_cached, iter_python_files


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
        source = py_file.read_text(encoding="utf-8")
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
