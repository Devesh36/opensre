"""Argument parsing helpers for ``opensre architecture-scan``."""

from __future__ import annotations

from pathlib import Path

import click

from tools.architecture_issue_tool.scan import (
    CANONICAL_OPENSRE_GITHUB_REPO,
    format_github_repo_url,
    parse_github_repo_argument,
    parse_issue_numbers,
    resolve_architecture_scan_github_repo_scope,
)

ARCHITECTURE_SCAN_GITHUB_SUBCOMMANDS = frozenset({"propose", "file-issues"})
SCAN_OPTION_FLAGS = frozenset({"--repo-root", "--max-file-lines", "--issue-numbers"})
SCAN_FLAG_ONLY = frozenset({"--include-baselines"})


def architecture_scan_github_subcommand(args: list[str]) -> str | None:
    """Return ``propose``/``file-issues`` when present, skipping scan-only flags."""
    index = 0
    while index < len(args):
        token = args[index]
        if token in SCAN_OPTION_FLAGS:
            index += 2
            continue
        if token in SCAN_FLAG_ONLY:
            index += 1
            continue
        if any(token.startswith(f"{flag}=") for flag in SCAN_OPTION_FLAGS):
            index += 1
            continue
        if token.startswith("-"):
            index += 1
            continue
        lowered = token.lower()
        if lowered in ARCHITECTURE_SCAN_GITHUB_SUBCOMMANDS:
            return lowered
        return None
    return None


def architecture_scan_github_repo_argument(scan_args: list[str]) -> str | None:
    """Return explicit ``GITHUB_REPO`` positional from scan args when present."""
    saw_subcommand = False
    index = 0
    while index < len(scan_args):
        token = scan_args[index]
        if token in SCAN_OPTION_FLAGS:
            index += 2
            continue
        if token in SCAN_FLAG_ONLY:
            index += 1
            continue
        if any(token.startswith(f"{flag}=") for flag in SCAN_OPTION_FLAGS):
            index += 1
            continue
        if token.startswith("-"):
            index += 1
            continue
        lowered = token.lower()
        if lowered in ARCHITECTURE_SCAN_GITHUB_SUBCOMMANDS:
            saw_subcommand = True
            index += 1
            continue
        if saw_subcommand:
            stripped = token.strip()
            return stripped or None
        return None
    return None


def resolve_architecture_scan_repo_scope_from_args(scan_args: list[str]) -> tuple[str, str]:
    """Resolve target GitHub repo from explicit args, git remote, or canonical default."""
    explicit = architecture_scan_github_repo_argument(scan_args)
    if explicit:
        return parse_github_repo_argument(explicit)
    scope = resolve_architecture_scan_github_repo_scope(cwd=architecture_scan_repo_root(scan_args))
    return scope or CANONICAL_OPENSRE_GITHUB_REPO


def architecture_scan_repo_root(scan_args: list[str]) -> Path | None:
    """Parse ``--repo-root`` from architecture-scan args when provided."""
    for index, arg in enumerate(scan_args):
        if arg == "--repo-root":
            if index + 1 < len(scan_args):
                value = scan_args[index + 1].strip()
                if value:
                    return Path(value).expanduser()
            return None
        if arg.startswith("--repo-root="):
            value = arg.split("=", 1)[1].strip()
            if value:
                return Path(value).expanduser()
            return None
    return None


def architecture_scan_args_include_issue_numbers(scan_args: list[str]) -> bool:
    return any(arg == "--issue-numbers" or arg.startswith("--issue-numbers=") for arg in scan_args)


def architecture_scan_follow_up_cli_args(
    choice: str,
    scan_args: list[str],
) -> list[str]:
    """Build follow-up CLI args, preserving scan flags and explicit repo from the original run."""
    owner, repo = resolve_architecture_scan_repo_scope_from_args(scan_args)
    follow_up = ["architecture-scan", choice, format_github_repo_url(owner, repo)]
    index = 0
    while index < len(scan_args):
        arg = scan_args[index]
        if arg in {"--repo-root", "--max-file-lines"}:
            if index + 1 < len(scan_args):
                follow_up.extend([arg, scan_args[index + 1]])
            index += 2
            continue
        if arg == "--include-baselines":
            follow_up.append(arg)
            index += 1
            continue
        if arg.startswith("--repo-root=") or arg.startswith("--max-file-lines="):
            follow_up.append(arg)
            index += 1
            continue
        index += 1
    return follow_up


def parse_issue_numbers_option(issue_numbers: str | None) -> list[int] | None:
    try:
        return parse_issue_numbers(issue_numbers)
    except ValueError as exc:
        raise click.BadParameter(str(exc), param_hint="'--issue-numbers'") from None


def parse_github_repo_option(value: str) -> tuple[str, str]:
    try:
        return parse_github_repo_argument(value)
    except ValueError as exc:
        raise click.BadParameter(str(exc), param_hint="'GITHUB_REPO'") from None


def resolve_github_repo_for_subcommand(
    github_repo: str | None,
    repo_root: str | None,
) -> tuple[str, str]:
    if github_repo and github_repo.strip():
        return parse_github_repo_option(github_repo.strip())
    scope = resolve_architecture_scan_github_repo_scope(repo_root)
    if scope:
        return scope
    return CANONICAL_OPENSRE_GITHUB_REPO
