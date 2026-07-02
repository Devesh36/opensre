"""Repository path helpers shared by architecture scanners."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

# Keep skip list aligned with .github/ci/check_import_cycles.py.
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
