"""Tests for the scheduled recurring skill runner."""

from __future__ import annotations

from integrations.scheduled_skill_runner import (
    _BLOCKED_TOOL_NAMES,
    _DeliveryStrippedToolProvider,
)


class _FakeTool:
    def __init__(self, name: str) -> None:
        self.name = name


class _FakeInnerProvider:
    def action_tools(self, **_kwargs: object) -> list[_FakeTool]:
        return [
            _FakeTool("shell_run"),
            _FakeTool("slack_send_message"),
            _FakeTool("propose_scheduled_delivery"),
        ]

    def tool_resources(self) -> dict[str, object]:
        return {}

    def observer(self, *, message: str) -> object:
        _ = message
        return lambda _kind, _data: None


def test_delivery_stripped_provider_removes_send_and_schedule_tools() -> None:
    provider = _DeliveryStrippedToolProvider(_FakeInnerProvider())
    names = {tool.name for tool in provider.action_tools(confirm_fn=None, is_tty=False)}
    assert names == {"shell_run"}
    assert _BLOCKED_TOOL_NAMES >= {
        "slack_send_message",
        "telegram_send_message",
        "propose_scheduled_delivery",
    }
