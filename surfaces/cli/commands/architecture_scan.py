"""``opensre architecture-scan`` — deterministic architecture violation report."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

import click

from platform.common.exit_codes import ERROR, SUCCESS
from platform.common.runtime_flags import is_json_output
from tools.architecture_issue_tool.scan import (
    format_file_issues_report_text,
    format_propose_report_text,
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


def _scan_kwargs(ctx: click.Context) -> dict[str, Any]:
    obj = ctx.obj if isinstance(ctx.obj, dict) else {}
    return {
        "repo_root": obj.get("repo_root"),
        "max_file_lines": int(obj.get("max_file_lines", 500)),
        "include_baselines": bool(obj.get("include_baselines", False)),
    }


def _store_scan_options(
    ctx: click.Context,
    repo_root: str | None,
    max_file_lines: int,
    include_baselines: bool,
) -> None:
    ctx.obj = {
        "repo_root": repo_root,
        "max_file_lines": max_file_lines,
        "include_baselines": include_baselines,
    }


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
@click.argument("owner")
@click.argument("repo")
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
    owner: str,
    repo: str,
    task_indices: str | None,
) -> None:
    """Scan, then build read-only GitHub create-issue proposals."""
    _store_scan_options(ctx, repo_root, max_file_lines, include_baselines)
    result = run_architecture_scan_and_propose_github_issues(
        owner=owner,
        repo=repo,
        task_indices=parse_task_indices(task_indices),
        **_scan_kwargs(ctx),
    )
    _emit_text_or_json(result, formatter=format_propose_report_text)
    _exit_for_scan_error(result)


@architecture_scan_group.command(name="file-issues")
@_scan_options
@click.argument("owner")
@click.argument("repo")
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
    owner: str,
    repo: str,
    task_indices: str | None,
) -> None:
    """Scan, propose GitHub issues, and create them on GitHub."""
    _store_scan_options(ctx, repo_root, max_file_lines, include_baselines)
    result = run_architecture_scan_and_file_github_issues(
        owner=owner,
        repo=repo,
        task_indices=parse_task_indices(task_indices),
        **_scan_kwargs(ctx),
    )
    _emit_text_or_json(result, formatter=format_file_issues_report_text)
    _exit_for_issue_results(result)


architecture_scan_command = architecture_scan_group
