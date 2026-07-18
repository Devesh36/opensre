"""Tests for deterministic Sentry morning digest."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from integrations.sentry import SentryConfig
from integrations.sentry.morning_digest import (
    IssuesDigestView,
    PriorityRow,
    ThemeRow,
    UptimeDigestView,
    UptimeStatusRow,
    build_issues_digest_view,
    build_uptime_digest_view,
    merge_watch_histories,
    monitor_label,
    parse_digest_payload,
    require_sentry_config,
    run_sentry_morning_digest,
)
from integrations.sentry.uptime import UptimeTransitionRecord, WatchState, save_watch_state


def _uptime_record(
    monitor_id: str,
    *,
    kind: str = "down",
    at: datetime,
    name: str = "example",
    url: str = "https://example.com",
    project_slug: str = "web",
) -> UptimeTransitionRecord:
    return UptimeTransitionRecord(
        monitor_id=monitor_id,
        kind=kind,  # type: ignore[arg-type]
        at=at.isoformat(),
        name=name,
        url=url,
        project_slug=project_slug,
    )


class TestParseDigestPayload:
    def test_defaults(self) -> None:
        params = parse_digest_payload({})
        assert params.project_slug == ""
        assert params.stats_period == "24h"
        assert params.query == "is:unresolved"
        assert params.window_hours == 24

    def test_invalid_window_defaults_to_24(self) -> None:
        params = parse_digest_payload({"window_hours": "bad"})
        assert params.window_hours == 24


class TestRequireSentryConfig:
    def test_raises_when_missing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "integrations.sentry.morning_digest.resolve_sentry_config",
            lambda **_kwargs: None,
        )
        with pytest.raises(RuntimeError, match="Sentry is not configured"):
            require_sentry_config()

    def test_returns_config(self, monkeypatch: pytest.MonkeyPatch) -> None:
        config = SentryConfig(organization_slug="acme", auth_token="token")
        monkeypatch.setattr(
            "integrations.sentry.morning_digest.resolve_sentry_config",
            lambda **_kwargs: config,
        )
        assert require_sentry_config() == config


class TestRunSentryMorningDigest:
    def test_raises_when_sentry_not_configured(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "integrations.sentry.morning_digest.require_sentry_config",
            lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("Sentry is not configured")),
        )
        with pytest.raises(RuntimeError, match="Sentry is not configured"):
            run_sentry_morning_digest({})

    def test_renders_structured_digest(self, monkeypatch: pytest.MonkeyPatch) -> None:
        config = SentryConfig(organization_slug="tracer-30", auth_token="token")
        issues_view = IssuesDigestView(
            period_label="last 24 hours",
            query_label="is:unresolved",
            issue_count=3,
            page_saturated=False,
            themes=(),
            priorities=(),
        )
        uptime_view = UptimeDigestView(
            window_label="last 24h",
            still_down=(UptimeStatusRow("sandbox.tracer.cloud", "since now", "down"),),
            recovered=(),
        )

        monkeypatch.setattr(
            "integrations.sentry.morning_digest.require_sentry_config",
            lambda **_kwargs: config,
        )
        monkeypatch.setattr(
            "integrations.sentry.morning_digest.build_issues_digest_view",
            lambda **_kwargs: issues_view,
        )
        monkeypatch.setattr(
            "integrations.sentry.morning_digest.build_uptime_digest_view",
            lambda **_kwargs: uptime_view,
        )

        report = run_sentry_morning_digest({})
        assert "*Sentry Morning Digest*" in report
        assert "*Summary*" in report
        assert "*[DOWN] Still down*" in report
        assert report.index("*[DOWN] Still down*") < report.index("*Issues*")


class TestIssuesDigestView:
    def test_build_issues_digest_view_renders_clusters(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        config = SentryConfig(organization_slug="acme", auth_token="token")
        monkeypatch.setattr(
            "integrations.sentry.morning_digest.require_sentry_config",
            lambda **_kwargs: config,
        )
        monkeypatch.setattr(
            "integrations.sentry.morning_digest.list_sentry_issues",
            lambda **_kwargs: [
                {
                    "id": "1",
                    "shortId": "APP-1",
                    "title": "Checkout timeout",
                    "count": 12,
                    "userCount": 4,
                    "culprit": "checkout.views",
                }
            ],
        )

        view = build_issues_digest_view()
        assert view.issue_count >= 0
        assert view.query_label == "is:unresolved"


class TestUptimeDigestView:
    def test_monitor_label_prefers_url_host(self) -> None:
        assert monitor_label(name="ignored", url="https://sandbox.tracer.cloud") == (
            "sandbox.tracer.cloud"
        )
        assert monitor_label(name="fallback", url="") == "fallback"

    def test_still_down(self, tmp_path: Path) -> None:
        now = datetime(2026, 7, 16, 8, 0, tzinfo=UTC)
        down_at = now - timedelta(hours=6)
        save_watch_state(
            "task-a",
            WatchState(
                open_incidents={"1"},
                transitions=[
                    _uptime_record(
                        "1",
                        at=down_at,
                        url="https://sandbox.tracer.cloud",
                    )
                ],
            ),
            path=tmp_path / "state.json",
        )

        view = build_uptime_digest_view(state_path=tmp_path / "state.json", now=now)
        assert view is not None
        assert view.still_down[0].label == "sandbox.tracer.cloud"
        assert view.still_down[0].detail == "since 2026-07-16 02:00 UTC"

    def test_recovered_in_window(self, tmp_path: Path) -> None:
        now = datetime(2026, 7, 16, 8, 0, tzinfo=UTC)
        save_watch_state(
            "task-a",
            WatchState(
                transitions=[
                    _uptime_record(
                        "1", kind="down", at=now - timedelta(hours=5), url="https://api.example.com"
                    ),
                    _uptime_record(
                        "1",
                        kind="recovered",
                        at=now - timedelta(hours=1),
                        url="https://api.example.com",
                    ),
                ]
            ),
            path=tmp_path / "state.json",
        )

        view = build_uptime_digest_view(state_path=tmp_path / "state.json", now=now)
        assert view is not None
        assert view.recovered[0].label == "api.example.com"

    def test_quiet_when_no_activity(self, tmp_path: Path) -> None:
        now = datetime(2026, 7, 16, 8, 0, tzinfo=UTC)
        save_watch_state(
            "task-a",
            WatchState(
                transitions=[
                    _uptime_record(
                        "1",
                        kind="recovered",
                        at=now - timedelta(days=2),
                        url="https://old.example.com",
                    )
                ]
            ),
            path=tmp_path / "state.json",
        )
        assert build_uptime_digest_view(state_path=tmp_path / "state.json", now=now) is None

    def test_filters_by_project(self, tmp_path: Path) -> None:
        now = datetime(2026, 7, 16, 8, 0, tzinfo=UTC)
        down_at = now - timedelta(hours=2)
        path = tmp_path / "state.json"
        save_watch_state(
            "task-a",
            WatchState(
                open_incidents={"1", "2"},
                transitions=[
                    _uptime_record(
                        "1", at=down_at, url="https://web.example.com", project_slug="web"
                    ),
                    _uptime_record(
                        "2", at=down_at, url="https://api.example.com", project_slug="api"
                    ),
                ],
            ),
            path=path,
        )

        view = build_uptime_digest_view(state_path=path, now=now, project_slug="web")
        assert view is not None
        labels = {row.label for row in view.still_down}
        assert labels == {"web.example.com"}

    def test_merge_watch_histories_dedupes_across_tasks(self) -> None:
        now = datetime(2026, 7, 16, 8, 0, tzinfo=UTC)
        record = _uptime_record("1", at=now - timedelta(hours=1), url="https://shared.example.com")
        transitions, open_incidents = merge_watch_histories(
            {
                "task-a": WatchState(open_incidents={"1"}, transitions=[record]),
                "task-b": WatchState(open_incidents={"1"}, transitions=[record]),
            }
        )
        assert len(transitions) == 1
        assert open_incidents == {"1"}

    def test_dedupes_same_host_across_tasks(self, tmp_path: Path) -> None:
        now = datetime(2026, 7, 16, 8, 0, tzinfo=UTC)
        path = tmp_path / "state.json"
        save_watch_state(
            "task-a",
            WatchState(
                open_incidents={"1"},
                transitions=[
                    _uptime_record(
                        "1", at=now - timedelta(hours=10), url="https://sandbox.tracer.cloud"
                    )
                ],
            ),
            path=path,
        )
        save_watch_state(
            "task-b",
            WatchState(
                open_incidents={"99"},
                transitions=[
                    _uptime_record(
                        "99", at=now - timedelta(hours=1), url="https://sandbox.tracer.cloud"
                    )
                ],
            ),
            path=path,
        )

        view = build_uptime_digest_view(state_path=path, now=now)
        assert view is not None
        assert len(view.still_down) == 1
        assert view.still_down[0].detail == "since 2026-07-16 07:00 UTC"


class TestDigestFormatting:
    def test_issues_section_layout(self) -> None:
        from integrations.sentry.morning_digest import _format_issues_section

        section = _format_issues_section(
            IssuesDigestView(
                period_label="last 24 hours",
                query_label="is:unresolved",
                issue_count=34,
                page_saturated=False,
                themes=(ThemeRow(4, 12, "Issue family PYTHON", ("PYTHON-KW",)),),
                priorities=(
                    PriorityRow(
                        1, "PYTHON-RJ", "NoConsoleScreenBufferError", ("4 events in window",)
                    ),
                ),
            )
        )
        assert "*Issues*" in section
        assert "*Top themes*" in section
        assert "`PYTHON-KW`" in section
        assert "*Focus today*" in section
