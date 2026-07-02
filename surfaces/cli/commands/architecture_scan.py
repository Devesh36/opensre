"""``opensre architecture-scan`` — deterministic architecture violation report."""

from __future__ import annotations

import json

import click

from platform.common.exit_codes import ERROR, SUCCESS
from platform.common.runtime_flags import is_json_output
from tools.architecture_issue_tool.scan import run_architecture_scan


@click.command(name="architecture-scan")
@click.option(
    "--repo-root",
    default=None,
    type=click.Path(exists=False, file_okay=False, dir_okay=True, resolve_path=True),
    help="Repository root to scan (default: current checkout).",
)
@click.option(
    "--max-file-lines",
    default=500,
    show_default=True,
    type=int,
    help="Non-blank line limit for oversized-file detection.",
)
@click.option(
    "--include-baselines",
    is_flag=True,
    help="Include known baseline dependency debt tracked in CI.",
)
def architecture_scan_command(
    repo_root: str | None,
    max_file_lines: int,
    include_baselines: bool,
) -> None:
    """Scan the repository for architecture violations and print a report."""
    result = run_architecture_scan(
        repo_root=repo_root,
        max_file_lines=max_file_lines,
        include_baselines=include_baselines,
    )

    if is_json_output():
        click.echo(json.dumps(result, indent=2))
    else:
        report = result.get("report")
        if isinstance(report, str) and report:
            click.echo(report)
        elif isinstance(result.get("error"), str):
            click.echo(result["error"])

    if isinstance(result.get("error"), str) and result["error"]:
        raise SystemExit(ERROR)
    raise SystemExit(SUCCESS)
