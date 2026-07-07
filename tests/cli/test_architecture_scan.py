from __future__ import annotations

from click.testing import CliRunner

from surfaces.cli.__main__ import cli

_GITHUB_REPO = "https://github.com/Tracer-Cloud/opensre"


def test_architecture_scan_command_prints_report(tmp_path) -> None:
    integrations_dir = tmp_path / "integrations"
    integrations_dir.mkdir()
    (integrations_dir / "shim.py").write_text(
        'from core.module import foo\n__all__ = ["foo"]\n',
        encoding="utf-8",
    )

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["architecture-scan", "--repo-root", str(tmp_path), "--max-file-lines", "50"],
    )

    assert result.exit_code == 0
    assert "Architecture violation scan" in result.output
    assert "Summary by type:" in result.output
    assert "compatibility_shim:" in result.output


def test_architecture_scan_command_json_output(tmp_path) -> None:
    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["--json", "architecture-scan", "--repo-root", str(tmp_path)],
    )

    assert result.exit_code == 0
    assert '"violations"' in result.output
    assert '"report"' in result.output


def test_architecture_scan_missing_repo_root_exits_error(tmp_path) -> None:
    missing = tmp_path / "missing"
    runner = CliRunner()
    result = runner.invoke(cli, ["architecture-scan", "--repo-root", str(missing)])

    assert result.exit_code != 0
    assert "does not exist" in result.output


def test_architecture_scan_propose_subcommand(tmp_path) -> None:
    integrations_dir = tmp_path / "integrations"
    integrations_dir.mkdir()
    (integrations_dir / "shim.py").write_text(
        'from core.module import foo\n__all__ = ["foo"]\n',
        encoding="utf-8",
    )

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "architecture-scan",
            "propose",
            _GITHUB_REPO,
            "--repo-root",
            str(tmp_path),
            "--issue-numbers",
            "0",
        ],
    )

    assert result.exit_code == 0
    assert "Architecture violation scan: 1 total" in result.output
    assert "GitHub issue proposals: 1" in result.output
    assert "Remove compatibility forwarding module" in result.output


def test_architecture_scan_propose_accepts_owner_repo_slug(tmp_path) -> None:
    integrations_dir = tmp_path / "integrations"
    integrations_dir.mkdir()
    (integrations_dir / "shim.py").write_text(
        'from core.module import foo\n__all__ = ["foo"]\n',
        encoding="utf-8",
    )

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "architecture-scan",
            "propose",
            "Tracer-Cloud/opensre",
            "--repo-root",
            str(tmp_path),
            "--issue-numbers",
            "0",
        ],
    )

    assert result.exit_code == 0
    assert "GitHub issue proposals: 1" in result.output


def test_architecture_scan_subcommand_inherits_group_scan_options(tmp_path) -> None:
    integrations_dir = tmp_path / "integrations"
    integrations_dir.mkdir()
    (integrations_dir / "shim.py").write_text(
        'from core.module import foo\n__all__ = ["foo"]\n',
        encoding="utf-8",
    )

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "architecture-scan",
            "--repo-root",
            str(tmp_path),
            "--max-file-lines",
            "50",
            "propose",
            _GITHUB_REPO,
            "--issue-numbers",
            "0",
        ],
    )

    assert result.exit_code == 0
    assert "Architecture violation scan: 1 total" in result.output
    assert "GitHub issue proposals: 1" in result.output


def test_architecture_scan_subcommand_prefers_explicit_scan_option_over_group(
    tmp_path,
) -> None:
    integrations_dir = tmp_path / "integrations"
    integrations_dir.mkdir()
    (integrations_dir / "shim.py").write_text(
        'from core.module import foo\n__all__ = ["foo"]\n',
        encoding="utf-8",
    )

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "architecture-scan",
            "--max-file-lines",
            "5000",
            "propose",
            _GITHUB_REPO,
            "--repo-root",
            str(tmp_path),
            "--max-file-lines",
            "50",
            "--issue-numbers",
            "0",
        ],
    )

    assert result.exit_code == 0
    assert "Architecture violation scan: 1 total" in result.output


def test_architecture_scan_propose_without_github_url(tmp_path) -> None:
    integrations_dir = tmp_path / "integrations"
    integrations_dir.mkdir()
    (integrations_dir / "shim.py").write_text(
        'from core.module import foo\n__all__ = ["foo"]\n',
        encoding="utf-8",
    )

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "architecture-scan",
            "propose",
            "--repo-root",
            str(tmp_path),
            "--issue-numbers",
            "0",
        ],
    )

    assert result.exit_code == 0
    assert "GitHub issue proposals: 1" in result.output


def test_architecture_scan_propose_rejects_invalid_github_repo(tmp_path) -> None:
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "architecture-scan",
            "propose",
            "not-a-valid-repo",
            "--repo-root",
            str(tmp_path),
        ],
    )

    assert result.exit_code != 0
    assert "Invalid GitHub repository" in result.output


def test_architecture_scan_file_issues_subcommand(tmp_path, monkeypatch) -> None:
    integrations_dir = tmp_path / "integrations"
    integrations_dir.mkdir()
    (integrations_dir / "shim.py").write_text(
        'from core.module import foo\n__all__ = ["foo"]\n',
        encoding="utf-8",
    )
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")

    def _fake_execute(owner: str, repo: str, proposal: dict) -> dict:
        return {
            "source": "github",
            "available": True,
            "executed": True,
            "side_effect": "created_github_issue",
            "issue": {
                "number": 1234,
                "html_url": f"https://github.com/{owner}/{repo}/issues/1234",
                "title": proposal.get("payload", {}).get("title", ""),
            },
        }

    monkeypatch.setattr(
        "integrations.github.tools.work_status.execute_github_issue_mutation",
        _fake_execute,
    )

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "architecture-scan",
            "file-issues",
            _GITHUB_REPO,
            "--repo-root",
            str(tmp_path),
            "--issue-numbers",
            "0",
        ],
    )

    assert result.exit_code == 0
    assert "created #1234" in result.output
    assert "https://github.com/Tracer-Cloud/opensre/issues/1234" in result.output


def test_architecture_scan_file_issues_uses_integration_store_token(tmp_path, monkeypatch) -> None:
    from integrations.github import mcp as github_mcp_module

    integrations_dir = tmp_path / "integrations"
    integrations_dir.mkdir()
    (integrations_dir / "shim.py").write_text(
        'from core.module import foo\n__all__ = ["foo"]\n',
        encoding="utf-8",
    )
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GH_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_MCP_AUTH_TOKEN", raising=False)
    monkeypatch.setattr(
        "integrations.store.get_integration",
        lambda service: (
            {
                "credentials": {
                    "mode": "streamable-http",
                    "url": github_mcp_module.DEFAULT_GITHUB_MCP_URL,
                    "auth_token": "store-token",
                }
            }
            if service == "github"
            else None
        ),
    )

    def _fake_execute(
        owner: str, repo: str, proposal: dict, github_token: str | None = None
    ) -> dict:
        assert github_token is None or github_token == "store-token"
        return {
            "source": "github",
            "available": True,
            "executed": True,
            "side_effect": "created_github_issue",
            "issue": {
                "number": 99,
                "html_url": f"https://github.com/{owner}/{repo}/issues/99",
                "title": proposal.get("payload", {}).get("title", ""),
            },
        }

    monkeypatch.setattr(
        "integrations.github.tools.work_status.execute_github_issue_mutation",
        _fake_execute,
    )

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "architecture-scan",
            "file-issues",
            _GITHUB_REPO,
            "--repo-root",
            str(tmp_path),
            "--issue-numbers",
            "0",
        ],
    )

    assert result.exit_code == 0
    assert "created #99" in result.output


def test_architecture_scan_file_issues_without_token_exits_once(tmp_path, monkeypatch) -> None:
    integrations_dir = tmp_path / "integrations"
    integrations_dir.mkdir()
    (integrations_dir / "shim.py").write_text(
        'from core.module import foo\n__all__ = ["foo"]\n',
        encoding="utf-8",
    )
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GH_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_MCP_AUTH_TOKEN", raising=False)
    monkeypatch.setattr("integrations.store.get_integration", lambda _service: None)

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "architecture-scan",
            "file-issues",
            _GITHUB_REPO,
            "--repo-root",
            str(tmp_path),
            "--issue-numbers",
            "0",
        ],
    )

    assert result.exit_code != 0
    assert result.output.count("GitHub token is required") == 1
    assert "integrations setup github" in result.output
    assert "GitHub issue results:" not in result.output


def test_architecture_scan_invalid_issue_numbers(tmp_path) -> None:
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "architecture-scan",
            "propose",
            _GITHUB_REPO,
            "--repo-root",
            str(tmp_path),
            "--issue-numbers",
            "abc",
        ],
    )

    assert result.exit_code != 0
    assert "Invalid issue number 'abc': must be an integer." in result.output


def test_architecture_scan_file_issues_exits_error_when_mutation_fails(
    tmp_path, monkeypatch
) -> None:
    integrations_dir = tmp_path / "integrations"
    integrations_dir.mkdir()
    (integrations_dir / "shim.py").write_text(
        'from core.module import foo\n__all__ = ["foo"]\n',
        encoding="utf-8",
    )
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")

    def _failing_execute(owner: str, repo: str, proposal: dict) -> dict:  # noqa: ARG001
        return {"error": "GitHub API error 403: forbidden"}

    monkeypatch.setattr(
        "integrations.github.tools.work_status.execute_github_issue_mutation",
        _failing_execute,
    )

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "architecture-scan",
            "file-issues",
            _GITHUB_REPO,
            "--repo-root",
            str(tmp_path),
            "--issue-numbers",
            "0",
        ],
    )

    assert result.exit_code != 0
    assert "failed: GitHub API error 403: forbidden" in result.output


def test_architecture_scan_propose_succeeds_with_no_violations(tmp_path) -> None:
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "architecture-scan",
            "propose",
            _GITHUB_REPO,
            "--repo-root",
            str(tmp_path),
        ],
    )

    assert result.exit_code == 0
    assert "Architecture violation scan: 0 total" in result.output
    assert "GitHub issue proposals: 0" in result.output
    assert "proposed_refactor_tasks is empty" not in result.output


def test_architecture_scan_file_issues_succeeds_with_no_violations(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "architecture-scan",
            "file-issues",
            _GITHUB_REPO,
            "--repo-root",
            str(tmp_path),
        ],
    )

    assert result.exit_code == 0
    assert "Architecture violation scan: 0 total" in result.output
    assert "GitHub issue proposals: 0" in result.output
    assert "no issues filed" in result.output


def test_architecture_scan_file_issues_no_violations_without_token(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GH_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_MCP_AUTH_TOKEN", raising=False)
    monkeypatch.setattr("integrations.store.get_integration", lambda _service: None)

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "architecture-scan",
            "file-issues",
            _GITHUB_REPO,
            "--repo-root",
            str(tmp_path),
        ],
    )

    assert result.exit_code == 0
    assert "Architecture violation scan: 0 total" in result.output
    assert "GitHub issue proposals: 0" in result.output
    assert "GitHub token is required" not in result.output
