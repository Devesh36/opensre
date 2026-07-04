"""``opensre architecture-scan`` — deterministic architecture violation report."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

import click
from click.core import ParameterSource

from platform.common.exit_codes import ERROR, SUCCESS
from platform.common.runtime_flags import is_json_output
from tools.architecture_issue_tool.scan import (
    format_file_issues_report_text,
    format_propose_report_text,
    parse_github_repo_argument,
    parse_task_indices,
    run_architecture_scan,
    run_architecture_scan_and_file_github_issues,
    run_architecture_scan_and_propose_github_issues,
)


def _scan_options(func: Any) -> Any:
    options = (
        click.option(
            "--repo-root",
            default=None,
            type=click.Path(exists=False, file_okay=False, dir_okay=True, resolve_path=True),
            help="Repository root to scan (default: current checkout).",
        ),
        click.option(
            "--max-file-lines",
            default=500,
            show_default=True,
            type=int,
            help="Non-blank line limit for oversized-file detection.",
        ),
        click.option(
            "--include-baselines",
            is_flag=True,
            help="Include known baseline dependency debt tracked in CI.",
        ),
    )
    decorated = func
    for option in reversed(options):
        decorated = option(decorated)
    return decorated


def _subcommand_scan_options(func: Any) -> Any:
    options = (
        click.option(
            "--repo-root",
            default=None,
            type=click.Path(exists=False, file_okay=False, dir_okay=True, resolve_path=True),
            help="Repository root to scan (default: current checkout).",
        ),
        click.option(
            "--max-file-lines",
            default=500,
            show_default=True,
            type=int,
            help="Non-blank line limit for oversized-file detection.",
        ),
        click.option(
            "--include-baselines",
            is_flag=True,
            help="Include known baseline dependency debt tracked in CI.",
        ),
    )
    decorated = func
    for option in reversed(options):
        decorated = option(decorated)
    return decorated


ARCHITECTURE_SCAN_GITHUB_SUBCOMMANDS = frozenset({"propose", "file-issues"})
_SCAN_OPTION_FLAGS = frozenset({"--repo-root", "--max-file-lines", "--task-indices"})
_SCAN_FLAG_ONLY = frozenset({"--include-baselines"})


def architecture_scan_github_subcommand(args: list[str]) -> str | None:
    """Return ``propose``/``file-issues`` when present, skipping scan-only flags."""
    i = 0
    while i < len(args):
        token = args[i]
        if token in _SCAN_OPTION_FLAGS:
            i += 2
            continue
        if token in _SCAN_FLAG_ONLY:
            i += 1
            continue
        if any(token.startswith(f"{flag}=") for flag in _SCAN_OPTION_FLAGS):
            i += 1
            continue
        if token.startswith("-"):
            i += 1
            continue
        lowered = token.lower()
        if lowered in ARCHITECTURE_SCAN_GITHUB_SUBCOMMANDS:
            return lowered
        return None
    return None


def _scan_kwargs(ctx: click.Context) -> dict[str, Any]:
    obj = ctx.obj if isinstance(ctx.obj, dict) else {}
    return {
        "repo_root": obj.get("repo_root"),
        "max_file_lines": int(obj.get("max_file_lines", 500)),
        "include_baselines": bool(obj.get("include_baselines", False)),
    }


def _merged_scan_kwargs(
    ctx: click.Context,
    repo_root: str | None,
    max_file_lines: int,
    include_baselines: bool,
) -> dict[str, Any]:
    """Merge group-level scan flags with subcommand overrides."""
    parent_ctx = ctx.parent
    group_kwargs = _scan_kwargs(parent_ctx) if parent_ctx is not None else _scan_kwargs(ctx)
    merged = dict(group_kwargs)
    for name, value in (
        ("repo_root", repo_root),
        ("max_file_lines", max_file_lines),
        ("include_baselines", include_baselines),
    ):
        if ctx.get_parameter_source(name) == ParameterSource.COMMANDLINE:
            merged[name] = value
    return merged


def _store_scan_options(
    ctx: click.Context,
    repo_root: str | None,
    max_file_lines: int,
    include_baselines: bool,
) -> None:
    if not isinstance(ctx.obj, dict):
        ctx.obj = {}
    for name, value in (
        ("repo_root", repo_root),
        ("max_file_lines", max_file_lines),
        ("include_baselines", include_baselines),
    ):
        if ctx.get_parameter_source(name) == ParameterSource.COMMANDLINE or name not in ctx.obj:
            ctx.obj[name] = value


def _emit_text_or_json(
    result: dict[str, Any], *, formatter: Callable[[dict[str, Any]], str]
) -> None:
    if is_json_output():
        click.echo(json.dumps(result, indent=2))
        return
    click.echo(formatter(result))


def _emit_scan_report(result: dict[str, Any]) -> None:
    if is_json_output():
        click.echo(json.dumps(result, indent=2))
        return
    report = result.get("report")
    if isinstance(report, str) and report:
        click.echo(report)
    elif isinstance(result.get("error"), str):
        click.echo(result["error"])


def _exit_for_scan_error(result: dict[str, Any]) -> None:
    if isinstance(result.get("error"), str) and result["error"]:
        raise SystemExit(ERROR)
    raise SystemExit(SUCCESS)


def _exit_for_issue_results(result: dict[str, Any]) -> None:
    if isinstance(result.get("error"), str) and result["error"]:
        raise SystemExit(ERROR)
    for item in result.get("issue_results", []):
        if isinstance(item, dict) and item.get("error"):
            raise SystemExit(ERROR)
    raise SystemExit(SUCCESS)


def _parse_task_indices_option(task_indices: str | None) -> list[int] | None:
    try:
        return parse_task_indices(task_indices)
    except ValueError as exc:
        raise click.BadParameter(str(exc), param_hint="'--task-indices'") from None


def _parse_github_repo_option(value: str) -> tuple[str, str]:
    try:
        return parse_github_repo_argument(value)
    except ValueError as exc:
        raise click.BadParameter(str(exc), param_hint="'GITHUB_REPO'") from None


@click.group(name="architecture-scan", invoke_without_command=True)
@_scan_options
@click.pass_context
def architecture_scan_group(
    ctx: click.Context,
    repo_root: str | None,
    max_file_lines: int,
    include_baselines: bool,
) -> None:
    """Scan the repository for architecture violations."""
    _store_scan_options(ctx, repo_root, max_file_lines, include_baselines)
    if ctx.invoked_subcommand is not None:
        return
    result = run_architecture_scan(**_scan_kwargs(ctx))
    _emit_scan_report(result)
    _exit_for_scan_error(result)


@architecture_scan_group.command(name="propose")
@_subcommand_scan_options
@click.argument("github_repo")
@click.option(
    "--task-indices",
    default=None,
    help="Comma-separated 0-based proposed_refactor_tasks indices (default: all).",
)
@click.pass_context
def architecture_scan_propose_command(
    ctx: click.Context,
    repo_root: str | None,
    max_file_lines: int,
    include_baselines: bool,
    github_repo: str,
    task_indices: str | None,
) -> None:
    """Scan, then build read-only GitHub create-issue proposals."""
    owner, repo = _parse_github_repo_option(github_repo)
    result = run_architecture_scan_and_propose_github_issues(
        owner=owner,
        repo=repo,
        task_indices=_parse_task_indices_option(task_indices),
        **_merged_scan_kwargs(ctx, repo_root, max_file_lines, include_baselines),
    )
    _emit_text_or_json(result, formatter=format_propose_report_text)
    _exit_for_scan_error(result)


@architecture_scan_group.command(name="file-issues")
@_subcommand_scan_options
@click.argument("github_repo")
@click.option(
    "--task-indices",
    default=None,
    help="Comma-separated 0-based proposed_refactor_tasks indices (default: all).",
)
@click.pass_context
def architecture_scan_file_issues_command(
    ctx: click.Context,
    repo_root: str | None,
    max_file_lines: int,
    include_baselines: bool,
    github_repo: str,
    task_indices: str | None,
) -> None:
    """Scan, propose GitHub issues, and create them on GitHub."""
    owner, repo = _parse_github_repo_option(github_repo)
    result = run_architecture_scan_and_file_github_issues(
        owner=owner,
        repo=repo,
        task_indices=_parse_task_indices_option(task_indices),
        **_merged_scan_kwargs(ctx, repo_root, max_file_lines, include_baselines),
    )
    _emit_text_or_json(result, formatter=format_file_issues_report_text)
    _exit_for_issue_results(result)


architecture_scan_command = architecture_scan_group
