"""Deterministic Sentry morning digest: Issues + uptime rollup (#4070)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

from integrations.sentry import SentryConfig, list_sentry_issues
from integrations.sentry.issue_digest import build_sentry_issue_digest
from integrations.sentry.project_scope import payload_project_slug
from integrations.sentry.uptime import (
    UptimeTransitionRecord,
    WatchState,
    load_all_watch_states,
    parse_transition_at,
    resolve_sentry_config,
)
from platform.scheduler.agent_runner import AgentPayload

SENTRY_NOT_CONFIGURED_ERROR = (
    "Sentry is not configured. Run `opensre integrations setup` and verify "
    "with `opensre integrations verify sentry` before scheduling a digest."
)

_SECTION_RULE = "────────────────────────"
_DEFAULT_STATS_PERIOD = "24h"
_DEFAULT_QUERY = "is:unresolved"
_DEFAULT_WINDOW_HOURS = 24


@dataclass(frozen=True)
class DigestRunParams:
    """Normalized scheduler/CLI payload for one morning digest run."""

    project_slug: str
    stats_period: str
    query: str
    window_hours: int


@dataclass(frozen=True)
class ThemeRow:
    issue_count: int
    percent: int
    label: str
    sample_ids: tuple[str, ...]


@dataclass(frozen=True)
class PriorityRow:
    rank: int
    short_id: str
    title: str
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class IssuesDigestView:
    period_label: str
    query_label: str
    issue_count: int
    page_saturated: bool
    themes: tuple[ThemeRow, ...]
    priorities: tuple[PriorityRow, ...]


@dataclass(frozen=True)
class UptimeStatusRow:
    label: str
    detail: str
    status: Literal["down", "recovered"]


@dataclass(frozen=True)
class UptimeDigestView:
    window_label: str
    still_down: tuple[UptimeStatusRow, ...]
    recovered: tuple[UptimeStatusRow, ...]


def parse_digest_payload(payload: AgentPayload) -> DigestRunParams:
    """Parse digest run fields from a scheduler or CLI payload."""
    window_hours = payload.get("window_hours")
    try:
        parsed_window = int(window_hours) if window_hours is not None else _DEFAULT_WINDOW_HOURS
    except (TypeError, ValueError):
        parsed_window = _DEFAULT_WINDOW_HOURS

    stats_period = str(payload.get("stats_period") or _DEFAULT_STATS_PERIOD).strip()
    query = str(payload.get("query") or _DEFAULT_QUERY).strip()
    return DigestRunParams(
        project_slug=payload_project_slug(payload) or "",
        stats_period=stats_period or _DEFAULT_STATS_PERIOD,
        query=query or _DEFAULT_QUERY,
        window_hours=max(parsed_window, 1),
    )


def require_sentry_config(*, project_slug: str = "") -> SentryConfig:
    """Return Sentry REST config or raise when integration is missing."""
    config = resolve_sentry_config(project_slug=project_slug)
    if config is None:
        raise RuntimeError(SENTRY_NOT_CONFIGURED_ERROR)
    return config


def _truncate(text: str, limit: int) -> str:
    cleaned = text.strip()
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 1].rstrip() + "…"


def _format_digest_header(
    *,
    generated_at: datetime | None,
    period_label: str,
    organization_slug: str,
    project_slug: str,
) -> str:
    timestamp = (generated_at or datetime.now(UTC)).astimezone(UTC).strftime("%Y-%m-%d %H:%M UTC")
    scope_bits = [bit for bit in (organization_slug.strip(), project_slug.strip()) if bit]
    scope = f" · {' / '.join(scope_bits)}" if scope_bits else ""
    return "\n".join(
        [
            "*Sentry Morning Digest*",
            f"_{timestamp} · {period_label}{scope}_",
        ]
    )


def _format_digest_summary(
    *,
    issue_count: int,
    still_down_count: int,
    recovered_count: int,
) -> str:
    uptime_bits: list[str] = []
    if still_down_count:
        uptime_bits.append(
            f"{still_down_count} monitor{'s' if still_down_count != 1 else ''} still down"
        )
    if recovered_count:
        uptime_bits.append(f"{recovered_count} recovered in window")
    uptime_line = " · ".join(uptime_bits) if uptime_bits else "no uptime incidents in window"
    return "\n".join(
        [
            "*Summary*",
            f"• Issues: {issue_count} unresolved group{'s' if issue_count != 1 else ''}",
            f"• Uptime: {uptime_line}",
        ]
    )


def _theme_display_label(label: str) -> str:
    return _truncate(label.split(" — e.g. ", 1)[0].strip(), 72)


def _format_issues_section(view: IssuesDigestView) -> str:
    lines = [
        _SECTION_RULE,
        f"*Issues* ({view.issue_count} unresolved · {view.period_label})",
        f"_Filter: `{view.query_label}`_",
    ]
    if view.page_saturated:
        lines.append("_Note: first page only (100+ may exist in this window)._")

    if view.themes:
        lines.extend(["", "*Top themes*"])
        for theme in view.themes[:8]:
            ids = ", ".join(f"`{item}`" for item in theme.sample_ids)
            ids_suffix = f" — {ids}" if ids else ""
            lines.append(
                f"• {theme.percent:>2}% · {_theme_display_label(theme.label)} "
                f"(×{theme.issue_count}){ids_suffix}"
            )

    if view.priorities:
        lines.extend(["", "*Focus today*"])
        for row in view.priorities[:5]:
            title = _truncate(row.title, 90)
            reason_bits = f" _({'; '.join(row.reasons)})_" if row.reasons else ""
            lines.append(f"{row.rank}. `{row.short_id}` — {title}{reason_bits}")

    return "\n".join(lines)


def _format_uptime_section(view: UptimeDigestView) -> str:
    lines = [_SECTION_RULE, f"*Uptime / downtime* ({view.window_label})"]
    if view.still_down:
        lines.extend(["", "*[DOWN] Still down*"])
        for row in view.still_down:
            lines.append(f"• `{row.label}` — {row.detail}")
    if view.recovered:
        lines.extend(["", "*[RECOVERED] In window*"])
        for row in view.recovered:
            lines.append(f"• `{row.label}` — {row.detail}")
    return "\n".join(lines)


def _compose_digest(
    *,
    header: str,
    summary: str,
    uptime: UptimeDigestView | None,
    issues: str,
) -> str:
    blocks: list[str] = [header, "", summary]
    if uptime is not None and uptime.still_down:
        blocks.extend(["", _format_uptime_section(uptime)])
    blocks.extend(["", issues])
    if uptime is not None and not uptime.still_down and uptime.recovered:
        blocks.extend(["", _format_uptime_section(uptime)])
    return "\n".join(blocks).strip()


def build_issues_digest_view(
    *,
    stats_period: str = "24h",
    query: str = "is:unresolved",
    project_slug: str = "",
) -> IssuesDigestView:
    """Fetch unresolved issues and build a structured digest view."""
    config = require_sentry_config(project_slug=project_slug)
    normalized_query = query.strip() or _DEFAULT_QUERY
    digest = build_sentry_issue_digest(
        list_sentry_issues(
            config=config,
            query=normalized_query,
            stats_period=stats_period,
        ),
        stats_period=stats_period,
        query=normalized_query,
    )

    themes = tuple(
        ThemeRow(
            issue_count=int(cluster.get("issue_count") or 0),
            percent=int(cluster.get("percent") or 0),
            label=str(cluster.get("label") or "Unknown"),
            sample_ids=tuple(str(item) for item in (cluster.get("sample_short_ids") or [])),
        )
        for cluster in (digest.get("structural_clusters") or [])
        if isinstance(cluster, dict)
    )
    priorities = tuple(
        PriorityRow(
            rank=index,
            short_id=str(candidate.get("short_id") or "unknown"),
            title=str(candidate.get("title") or "Untitled issue"),
            reasons=tuple(str(item) for item in (candidate.get("impact_reasons") or [])),
        )
        for index, candidate in enumerate(digest.get("priority_candidates") or [], start=1)
        if isinstance(candidate, dict)
    )[:5]

    return IssuesDigestView(
        period_label=str(digest.get("stats_period_label") or stats_period),
        query_label=normalized_query,
        issue_count=int(digest.get("issue_count") or 0),
        page_saturated=bool(digest.get("page_saturated")),
        themes=themes,
        priorities=priorities,
    )


def monitor_label(*, name: str, url: str) -> str:
    """Prefer URL host for display; fall back to monitor name."""
    candidate = url.strip()
    if candidate:
        parsed = urlparse(candidate if "://" in candidate else f"https://{candidate}")
        host = (parsed.hostname or parsed.path or "").strip()
        if host:
            return host
    return name.strip() or "unknown monitor"


def merge_watch_histories(
    states: dict[str, WatchState],
    *,
    project_slug: str = "",
) -> tuple[list[UptimeTransitionRecord], set[str]]:
    """Merge transition logs and open incidents from all uptime watch tasks."""
    scope = project_slug.strip()
    transitions: list[UptimeTransitionRecord] = []
    open_incidents: set[str] = set()
    seen: set[tuple[str, str, str]] = set()
    monitor_projects: dict[str, set[str]] = {}

    for state in states.values():
        for record in state.transitions:
            if record.project_slug:
                monitor_projects.setdefault(record.monitor_id, set()).add(record.project_slug)
            if scope and record.project_slug != scope:
                continue
            key = (record.monitor_id, record.kind, record.at)
            if key in seen:
                continue
            seen.add(key)
            transitions.append(record)
        for monitor_id in state.open_incidents:
            if scope:
                projects = monitor_projects.get(monitor_id, set())
                if not projects or scope not in projects:
                    continue
            open_incidents.add(str(monitor_id))

    transitions.sort(key=lambda record: record.at)
    return transitions, open_incidents


def _label_for_records(records: list[UptimeTransitionRecord]) -> str:
    for record in reversed(records):
        label = monitor_label(name=record.name, url=record.url)
        if label != "unknown monitor":
            return label
    return "unknown monitor"


def _earliest_down_at(records: list[UptimeTransitionRecord]) -> datetime | None:
    earliest: datetime | None = None
    for record in records:
        if record.kind != "down":
            continue
        parsed = parse_transition_at(record)
        if parsed is None:
            continue
        if earliest is None or parsed < earliest:
            earliest = parsed
    return earliest


def _scan_timeline(
    records: list[UptimeTransitionRecord],
    *,
    window_start: datetime,
) -> tuple[datetime | None, datetime | None]:
    open_down_at: datetime | None = None
    recovered_at: datetime | None = None

    for record in records:
        parsed = parse_transition_at(record)
        if parsed is None:
            continue
        if record.kind == "down":
            open_down_at = parsed
            continue
        if record.kind == "recovered":
            if parsed >= window_start:
                recovered_at = parsed
            open_down_at = None

    return open_down_at, recovered_at


@dataclass(frozen=True)
class _MonitorTimeline:
    monitor_id: str
    label: str
    open_down_at: datetime | None
    recovered_at: datetime | None
    ongoing_without_timestamp: bool = False


def _build_monitor_timelines(
    *,
    grouped: dict[str, list[UptimeTransitionRecord]],
    open_incidents: set[str],
    window_start: datetime,
) -> list[_MonitorTimeline]:
    timelines: list[_MonitorTimeline] = []

    for monitor_id in open_incidents:
        records = grouped.get(monitor_id, [])
        open_down_at, _ = _scan_timeline(records, window_start=window_start)
        ongoing_without_timestamp = False
        if open_down_at is None:
            open_down_at = _earliest_down_at(records)
        if open_down_at is None:
            ongoing_without_timestamp = True
        timelines.append(
            _MonitorTimeline(
                monitor_id=monitor_id,
                label=_label_for_records(records),
                open_down_at=open_down_at,
                recovered_at=None,
                ongoing_without_timestamp=ongoing_without_timestamp,
            )
        )

    seen_labels = {timeline.label.lower() for timeline in timelines}
    for monitor_id, records in grouped.items():
        if monitor_id in open_incidents:
            continue
        _open_down_at, recovered_at = _scan_timeline(records, window_start=window_start)
        if recovered_at is None:
            continue
        label = _label_for_records(records)
        label_key = label.lower()
        if label_key in seen_labels:
            continue
        timelines.append(
            _MonitorTimeline(
                monitor_id=monitor_id,
                label=label,
                open_down_at=None,
                recovered_at=recovered_at,
            )
        )
        seen_labels.add(label_key)

    return timelines


def _prefer_still_down_timeline(
    candidate: _MonitorTimeline,
    current: _MonitorTimeline,
) -> bool:
    if candidate.open_down_at is None:
        return False
    if current.open_down_at is None:
        return True
    return candidate.open_down_at > current.open_down_at


def _dedupe_open_timelines(timelines: list[_MonitorTimeline]) -> list[_MonitorTimeline]:
    open_by_label: dict[str, _MonitorTimeline] = {}
    recovered: list[_MonitorTimeline] = []

    for timeline in timelines:
        if timeline.recovered_at is not None:
            recovered.append(timeline)
            continue
        if timeline.open_down_at is None and not timeline.ongoing_without_timestamp:
            continue
        key = timeline.label.lower()
        existing = open_by_label.get(key)
        if existing is None or _prefer_still_down_timeline(timeline, existing):
            open_by_label[key] = timeline

    return sorted(open_by_label.values(), key=lambda item: item.label) + sorted(
        recovered,
        key=lambda item: item.label,
    )


def build_uptime_digest_view(
    *,
    window_hours: int = 24,
    project_slug: str = "",
    state_path: Path | None = None,
    now: datetime | None = None,
) -> UptimeDigestView | None:
    """Build structured uptime digest data or None when quiet."""
    current = now or datetime.now(UTC)
    window_start = current - timedelta(hours=max(window_hours, 1))
    transitions, open_incidents = merge_watch_histories(
        load_all_watch_states(path=state_path),
        project_slug=project_slug,
    )
    if not transitions and not open_incidents:
        return None

    grouped: dict[str, list[UptimeTransitionRecord]] = {}
    for record in transitions:
        grouped.setdefault(record.monitor_id, []).append(record)

    still_down: list[UptimeStatusRow] = []
    recovered: list[UptimeStatusRow] = []

    for timeline in _dedupe_open_timelines(
        _build_monitor_timelines(
            grouped=grouped,
            open_incidents=open_incidents,
            window_start=window_start,
        )
    ):
        if timeline.recovered_at is None and (
            timeline.open_down_at is not None or timeline.ongoing_without_timestamp
        ):
            if timeline.open_down_at is not None:
                since = timeline.open_down_at.astimezone(UTC).strftime("%Y-%m-%d %H:%M UTC")
                detail = f"since {since}"
            else:
                detail = "ongoing (start time unavailable)"
            still_down.append(UptimeStatusRow(label=timeline.label, detail=detail, status="down"))
        elif timeline.recovered_at is not None:
            stamp = timeline.recovered_at.astimezone(UTC).strftime("%Y-%m-%d %H:%M UTC")
            recovered.append(
                UptimeStatusRow(
                    label=timeline.label, detail=f"recovered {stamp}", status="recovered"
                )
            )

    if not still_down and not recovered:
        return None

    window_label = f"last {window_hours}h" if window_hours != 24 else "last 24h"
    return UptimeDigestView(
        window_label=window_label,
        still_down=tuple(still_down),
        recovered=tuple(recovered),
    )


def run_sentry_morning_digest(payload: AgentPayload) -> str:
    """Build the scheduled morning digest from deterministic Sentry sections."""
    params = parse_digest_payload(payload)
    config = require_sentry_config(project_slug=params.project_slug)

    issues_view = build_issues_digest_view(
        stats_period=params.stats_period,
        query=params.query,
        project_slug=params.project_slug,
    )
    uptime_view = build_uptime_digest_view(
        window_hours=params.window_hours,
        project_slug=params.project_slug,
    )

    return _compose_digest(
        header=_format_digest_header(
            generated_at=None,
            period_label=issues_view.period_label,
            organization_slug=config.organization_slug,
            project_slug=params.project_slug,
        ),
        summary=_format_digest_summary(
            issue_count=issues_view.issue_count,
            still_down_count=len(uptime_view.still_down) if uptime_view else 0,
            recovered_count=len(uptime_view.recovered) if uptime_view else 0,
        ),
        uptime=uptime_view,
        issues=_format_issues_section(issues_view),
    )


__all__ = [
    "DigestRunParams",
    "IssuesDigestView",
    "PriorityRow",
    "SENTRY_NOT_CONFIGURED_ERROR",
    "ThemeRow",
    "UptimeDigestView",
    "UptimeStatusRow",
    "build_issues_digest_view",
    "build_uptime_digest_view",
    "merge_watch_histories",
    "monitor_label",
    "parse_digest_payload",
    "require_sentry_config",
    "run_sentry_morning_digest",
]
