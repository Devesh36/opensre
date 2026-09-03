"""Tests for the scheduled recurring skill runner tool filter."""

from __future__ import annotations

from core.agent_harness.tools.tool_provider import tool_allowed_for_unattended_run
from core.tool import SideEffectLevel


class _FakeTool:
    def __init__(self, name: str, level: SideEffectLevel | None) -> None:
        self.name = name
        self.side_effect_level = level


def test_unattended_run_allows_read_only_tools_only() -> None:
    assert (
        tool_allowed_for_unattended_run(_FakeTool("shell_run", SideEffectLevel.MUTATING)) is False
    )
    assert (
        tool_allowed_for_unattended_run(_FakeTool("slack_read_messages", SideEffectLevel.READ_ONLY))
        is True
    )
    assert (
        tool_allowed_for_unattended_run(_FakeTool("slack_add_reaction", SideEffectLevel.EXTERNAL))
        is False
    )
    assert (
        tool_allowed_for_unattended_run(_FakeTool("slack_send_message", SideEffectLevel.EXTERNAL))
        is False
    )
    assert (
        tool_allowed_for_unattended_run(
            _FakeTool("execute_github_issue_mutation", SideEffectLevel.MUTATING)
        )
        is False
    )
    assert (
        tool_allowed_for_unattended_run(_FakeTool("cli_command", SideEffectLevel.MUTATING)) is False
    )
    assert (
        tool_allowed_for_unattended_run(
            _FakeTool("propose_scheduled_delivery", SideEffectLevel.MUTATING)
        )
        is False
    )
    assert tool_allowed_for_unattended_run(_FakeTool("undeclared", None)) is False
