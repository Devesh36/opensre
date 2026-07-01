"""Tests for the ``opensre watchdog`` CLI command."""

from __future__ import annotations

import pytest
from click.testing import CliRunner

from platform.common.errors import OpenSREError
from surfaces.cli.__main__ import cli
from surfaces.cli.commands.watchdog import watchdog_command
from tools.watch_dog.config import WatchdogConfig


def test_watchdog_help_lists_expected_flags() -> None:
    result = CliRunner().invoke(watchdog_command, ["--help"])

    assert result.exit_code == 0
    for flag in (
        "--pid",
        "--name",
        "--pick-first",
        "--max-cpu",
        "--cpu-window",
        "--max-runtime",
        "--max-rss",
        "--interval",
        "--cooldown",
        "--once",
        "--chat-id",
        "--verbose",
    ):
        assert flag in result.output


def test_watchdog_cli_maps_flags_to_config(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, WatchdogConfig] = {}

    def _fake_run(config: WatchdogConfig, **kwargs: object) -> int:
        captured["config"] = config
        return 0

    monkeypatch.setattr("surfaces.cli.commands.watchdog.run_watchdog", _fake_run)
    monkeypatch.setattr("surfaces.cli.commands.watchdog.load_credentials_from_env", lambda **_: {})

    result = CliRunner().invoke(
        watchdog_command,
        [
            "--pid",
            "123",
            "--max-cpu",
            "90",
            "--cpu-window",
            "30",
            "--max-runtime",
            "30m",
            "--max-rss",
            "4G",
            "--interval",
            "5",
            "--cooldown",
            "5m",
            "--once",
            "--chat-id",
            "chat-1",
            "--verbose",
        ],
    )

    assert result.exit_code == 0
    config = captured["config"]
    assert config.pid == 123
    assert config.max_cpu == 90
    assert config.cpu_window == 30
    assert config.max_runtime == 1800
    assert config.max_rss == 4 * 1024**3
    assert config.interval == 5
    assert config.cooldown == 300
    assert config.once is True
    assert config.chat_id == "chat-1"
    assert config.verbose is True


def test_watchdog_cli_rejects_invalid_selector() -> None:
    result = CliRunner().invoke(
        watchdog_command,
        ["--pid", "123", "--name", "python", "--max-cpu", "90"],
    )

    assert result.exit_code != 0
    assert "Invalid watchdog configuration" in result.output


def test_missing_credentials_fail_fast_before_sampling(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _raise_missing_credentials(*, chat_id_override: str | None = None) -> dict:
        raise OpenSREError("missing telegram credentials")

    monkeypatch.setattr(
        "surfaces.cli.commands.watchdog.load_credentials_from_env",
        _raise_missing_credentials,
    )

    with pytest.raises(OpenSREError, match="missing telegram credentials"):
        watchdog_command.callback(
            pid=123,
            process_name=None,
            pick_first=False,
            max_cpu=90,
            cpu_window="30",
            max_runtime=None,
            max_rss=None,
            interval=5,
            cooldown="5m",
            once=False,
            chat_id=None,
            verbose=False,
        )


def test_root_cli_registers_watchdog_command() -> None:
    result = CliRunner().invoke(cli, ["watchdog", "--help"])

    assert result.exit_code == 0
    assert "--max-runtime" in result.output
