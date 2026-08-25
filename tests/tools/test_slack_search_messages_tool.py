"""Pins #5660: search.messages rejects bot tokens; hint instead of opaque error."""

from __future__ import annotations

import pytest

from integrations.slack.tools.slack_search_messages_tool.tool import SlackSearchMessagesTool
from integrations.slack.web_client import SlackBotTarget, _api_error_hint, search_messages


def test_description_does_not_claim_a_bot_search_scope() -> None:
    assert "bot scope" not in SlackSearchMessagesTool().description
    assert "xoxp-" in SlackSearchMessagesTool().description


def test_bot_token_is_rejected_with_a_clear_hint(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-x")
    matches, error = search_messages(SlackBotTarget(bot_token="xoxb-x"), query="timeout")
    assert matches is None
    assert "user token" in error
    result = SlackSearchMessagesTool().run(query="timeout")
    assert result["status"] == "failed"
    assert result["error"] == error


def test_not_allowed_token_type_maps_to_the_same_hint() -> None:
    assert "user token" in _api_error_hint("not_allowed_token_type", context="search")
