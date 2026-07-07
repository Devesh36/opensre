from __future__ import annotations

from pathlib import Path

import click
import pytest

from surfaces.cli.commands.architecture_scan_parsing import (
    architecture_scan_args_include_issue_numbers,
    architecture_scan_follow_up_cli_args,
    architecture_scan_github_repo_argument,
    architecture_scan_github_subcommand,
    architecture_scan_repo_root,
    parse_github_repo_option,
    parse_issue_numbers_option,
    resolve_architecture_scan_repo_scope_from_args,
    resolve_github_repo_for_subcommand,
)

_GITHUB_REPO = "https://github.com/Tracer-Cloud/opensre"
_EXTERNAL_REPO = "https://github.com/example/external"


@pytest.mark.parametrize(
    ("args", "expected"),
    [
        (["--include-baselines", "propose", _GITHUB_REPO], "propose"),
        (["--repo-root", "/tmp", "file-issues"], "file-issues"),
        (["--repo-root=/tmp", "propose"], "propose"),
        (["--issue-numbers=0,1", "file-issues", _GITHUB_REPO], "file-issues"),
        (["--include-baselines"], None),
        (["scan"], None),
        (["--repo-root", "/tmp", "scan"], None),
        ([], None),
    ],
)
def test_architecture_scan_github_subcommand(args: list[str], expected: str | None) -> None:
    assert architecture_scan_github_subcommand(args) == expected


def test_architecture_scan_github_subcommand_is_case_insensitive() -> None:
    assert architecture_scan_github_subcommand(["PROPOSE", _GITHUB_REPO]) == "propose"


def test_architecture_scan_repo_root_parses_flag_and_equals_form(tmp_path: Path) -> None:
    assert architecture_scan_repo_root(["--repo-root", str(tmp_path)]) == tmp_path
    assert architecture_scan_repo_root([f"--repo-root={tmp_path}"]) == tmp_path


def test_architecture_scan_repo_root_rejects_empty_value() -> None:
    assert architecture_scan_repo_root(["--repo-root", ""]) is None
    assert architecture_scan_repo_root(["--repo-root="]) is None


@pytest.mark.parametrize(
    ("args", "expected"),
    [
        (["--issue-numbers", "0"], True),
        (["--issue-numbers=0,1"], True),
        (["propose"], False),
    ],
)
def test_architecture_scan_args_include_issue_numbers(args: list[str], expected: bool) -> None:
    assert architecture_scan_args_include_issue_numbers(args) is expected


def test_architecture_scan_github_repo_argument_extracts_explicit_repo() -> None:
    assert (
        architecture_scan_github_repo_argument(["propose", _EXTERNAL_REPO, "--repo-root", "/tmp"])
        == _EXTERNAL_REPO
    )
    assert (
        architecture_scan_github_repo_argument(
            ["--repo-root", "/tmp", "file-issues", "example/external"]
        )
        == "example/external"
    )


def test_architecture_scan_github_repo_argument_returns_none_without_repo() -> None:
    assert architecture_scan_github_repo_argument(["propose"]) is None
    assert architecture_scan_github_repo_argument(["--include-baselines"]) is None


def test_resolve_architecture_scan_repo_scope_from_args_prefers_explicit_repo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tools.architecture_issue_tool import scan as scan_module

    monkeypatch.setattr(
        scan_module,
        "resolve_architecture_scan_github_repo_scope",
        lambda cwd=None: ("Tracer-Cloud", "opensre"),  # noqa: ARG005
    )

    scope = resolve_architecture_scan_repo_scope_from_args(
        ["propose", _EXTERNAL_REPO, "--repo-root", "/tmp"]
    )
    assert scope == ("example", "external")


def test_architecture_scan_follow_up_cli_args_preserves_scan_flags(tmp_path: Path) -> None:
    scan_args = [
        "propose",
        _EXTERNAL_REPO,
        "--repo-root",
        str(tmp_path),
        "--max-file-lines",
        "50",
        "--include-baselines",
    ]
    cli_args = architecture_scan_follow_up_cli_args("propose", scan_args)
    assert cli_args == [
        "architecture-scan",
        "propose",
        _EXTERNAL_REPO,
        "--repo-root",
        str(tmp_path),
        "--max-file-lines",
        "50",
        "--include-baselines",
    ]


def test_parse_issue_numbers_option_wraps_invalid_input() -> None:
    with pytest.raises(click.BadParameter, match="Invalid issue number 'abc'"):
        parse_issue_numbers_option("abc")


def test_parse_github_repo_option_wraps_invalid_input() -> None:
    with pytest.raises(click.BadParameter, match="Invalid GitHub repository"):
        parse_github_repo_option("not-a-valid-repo")


def test_resolve_github_repo_for_subcommand_uses_explicit_repo() -> None:
    assert resolve_github_repo_for_subcommand("Tracer-Cloud/opensre", None) == (
        "Tracer-Cloud",
        "opensre",
    )


def test_resolve_github_repo_for_subcommand_falls_back_to_canonical() -> None:
    assert resolve_github_repo_for_subcommand(None, None) == ("Tracer-Cloud", "opensre")
