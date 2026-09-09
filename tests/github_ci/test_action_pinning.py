"""Security contracts for immutable external GitHub Actions references."""

from __future__ import annotations

import re
from pathlib import Path

_REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
_USES_RE = re.compile(r"^\s*(?:-\s+)?uses:\s*(?P<reference>\S+)")
_COMMIT_SHA_RE = re.compile(r"^[^@\s]+@[0-9a-f]{40}$")


def test_external_github_actions_are_pinned_to_immutable_commits() -> None:
    """Keep mutable third-party action tags out of trusted automation."""
    offenders: list[str] = []
    for path in sorted((_REPOSITORY_ROOT / ".github").rglob("*.y*ml")):
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            match = _USES_RE.match(line)
            if match is None or match["reference"].startswith("./"):
                continue
            reference = match.group("reference")
            if not _COMMIT_SHA_RE.fullmatch(reference):
                offenders.append(f"{path.relative_to(_REPOSITORY_ROOT)}:{line_number}: {reference}")

    assert not offenders, "External actions must use full commit SHAs:\n" + "\n".join(offenders)
