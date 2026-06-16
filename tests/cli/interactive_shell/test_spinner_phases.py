"""Unit tests for REPL spinner phase labels."""

from __future__ import annotations

from app.cli.interactive_shell.runtime.spinner_phases import (
    SPINNER_PHASE_RUNNING_INVESTIGATION,
    slash_command_phase,
    spinner_phase_for_action,
)


def test_slash_command_phase_normalizes_missing_slash_prefix() -> None:
    assert slash_command_phase("health") == "running /health"
    assert slash_command_phase("/integrations list") == "running /integrations"


def test_spinner_phase_for_action_covers_common_kinds() -> None:
    assert spinner_phase_for_action(kind="slash", content="/health") == "running /health"
    assert (
        spinner_phase_for_action(kind="cli_command", content="integrations list")
        == "running integrations"
    )
    assert (
        spinner_phase_for_action(kind="investigation", content="CPU spike on orders-api")
        == SPINNER_PHASE_RUNNING_INVESTIGATION
    )
    assert (
        spinner_phase_for_action(kind="llm_provider", content="anthropic")
        == "running /model anthropic"
    )
    assert spinner_phase_for_action(kind="unknown_kind", content="") == "running action"
