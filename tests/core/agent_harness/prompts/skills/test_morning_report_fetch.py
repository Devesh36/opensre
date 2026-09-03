"""Tests for unattended morning-report data fetches."""

from __future__ import annotations

import pytest

from core.agent_harness.prompts.skills.morning_report import fetch as morning_fetch
from core.agent_harness.prompts.skills.schedule import scheduled_skill_context_block

_BBC_RSS = """\
<?xml version="1.0"?>
<rss version="2.0">
  <channel>
    <title>BBC News</title>
    <item><title>First headline</title></item>
    <item><title>Second headline</title></item>
  </channel>
</rss>
"""


def test_fetch_headlines_skips_channel_title(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(morning_fetch, "_get", lambda _url: _BBC_RSS)
    assert morning_fetch.fetch_headlines() == ["First headline", "Second headline"]


def test_format_fetched_briefing_inputs_uses_city(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(morning_fetch, "fetch_weather", lambda city="": f"{city}: sunny")
    monkeypatch.setattr(morning_fetch, "fetch_headlines", lambda: ["One"])
    block = morning_fetch.format_fetched_briefing_inputs({"city": "Amsterdam"})
    assert "Amsterdam: sunny" in block
    assert "- One" in block


def test_scheduled_skill_context_block_empty_for_other_skills() -> None:
    assert scheduled_skill_context_block("github-ci-fix", {}) == ""


def test_scheduled_skill_context_block_morning_report(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(morning_fetch, "fetch_weather", lambda _city="": "Paris: cloudy")
    monkeypatch.setattr(morning_fetch, "fetch_headlines", lambda: ["News"])
    block = scheduled_skill_context_block("morning-report", {"city": "Paris"})
    assert "Paris: cloudy" in block
    assert "- News" in block
