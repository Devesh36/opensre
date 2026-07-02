from __future__ import annotations

from click.testing import CliRunner

from surfaces.cli.__main__ import cli


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
