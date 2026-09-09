"""Security contracts for immutable external GitHub Actions references."""

from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import yaml

_REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
_COMMIT_SHA_RE = re.compile(r"^[^@\s]+@[0-9a-f]{40}$")


def _external_action_references(value: Any) -> Iterator[str]:
    """Yield external-action references from a parsed GitHub YAML document."""
    if isinstance(value, dict):
        reference = value.get("uses")
        if isinstance(reference, str):
            yield reference
        for child in value.values():
            yield from _external_action_references(child)
    elif isinstance(value, list):
        for child in value:
            yield from _external_action_references(child)


def test_quoted_uses_key_is_checked() -> None:
    """Treat quoted YAML keys exactly like the unquoted ``uses`` key."""
    document = yaml.safe_load('"uses": actions/checkout@v5')

    assert list(_external_action_references(document)) == ["actions/checkout@v5"]


def test_external_github_actions_are_pinned_to_immutable_commits() -> None:
    """Keep mutable third-party action tags out of trusted automation."""
    offenders: list[str] = []
    for path in sorted((_REPOSITORY_ROOT / ".github").rglob("*.y*ml")):
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
        for reference in _external_action_references(document):
            if reference.startswith("./") or _COMMIT_SHA_RE.fullmatch(reference):
                continue
            offenders.append(f"{path.relative_to(_REPOSITORY_ROOT)}: {reference}")

    assert not offenders, "External actions must use full commit SHAs:\n" + "\n".join(offenders)
