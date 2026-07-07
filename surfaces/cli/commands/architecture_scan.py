"""``opensre architecture-scan`` — deterministic architecture violation report."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

import click
from click.core import ParameterSource

from platform.common.exit_codes import ERROR, SUCCESS
from platform.common.runtime_flags import is_json_output
from surfaces.cli.commands.architecture_scan_parsing import (
    parse_issue_numbers_option,
    resolve_github_repo_for_subcommand,
)
from tools.architecture_issue_tool.scan import (
    format_file_issues_report_text,
    format_propose_report_text,
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
@_scan_options
@click.argument("github_repo", required=False, default=None)
@click.option(
    "--issue-numbers",
    default=None,
    help=(
        "Comma-separated issue numbers from the scan (0-based, default: all). Not GitHub issue IDs."
    ),
)
@click.pass_context
def architecture_scan_propose_command(
    ctx: click.Context,
    repo_root: str | None,
    max_file_lines: int,
    include_baselines: bool,
    github_repo: str | None,
    issue_numbers: str | None,
) -> None:
    """Scan, then build read-only GitHub create-issue proposals."""
    owner, repo = resolve_github_repo_for_subcommand(github_repo, repo_root)
    result = run_architecture_scan_and_propose_github_issues(
        owner=owner,
        repo=repo,
        issue_numbers=parse_issue_numbers_option(issue_numbers),
        **_merged_scan_kwargs(ctx, repo_root, max_file_lines, include_baselines),
    )
    _emit_text_or_json(result, formatter=format_propose_report_text)
    _exit_for_scan_error(result)


@architecture_scan_group.command(name="file-issues")
@_scan_options
@click.argument("github_repo", required=False, default=None)
@click.option(
    "--issue-numbers",
    default=None,
    help=(
        "Comma-separated issue numbers from the scan (0-based, default: all). Not GitHub issue IDs."
    ),
)
@click.pass_context
def architecture_scan_file_issues_command(
    ctx: click.Context,
    repo_root: str | None,
    max_file_lines: int,
    include_baselines: bool,
    github_repo: str | None,
    issue_numbers: str | None,
) -> None:
    """Scan, propose GitHub issues, and create them on GitHub."""
    owner, repo = resolve_github_repo_for_subcommand(github_repo, repo_root)
    result = run_architecture_scan_and_file_github_issues(
        owner=owner,
        repo=repo,
        issue_numbers=parse_issue_numbers_option(issue_numbers),
        **_merged_scan_kwargs(ctx, repo_root, max_file_lines, include_baselines),
    )
    _emit_text_or_json(result, formatter=format_file_issues_report_text)
    _exit_for_issue_results(result)


architecture_scan_command = architecture_scan_group
