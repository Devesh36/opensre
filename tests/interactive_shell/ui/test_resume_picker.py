"""Tests for the scrollable conversation picker."""

from __future__ import annotations

import importlib
from datetime import UTC, datetime
from io import StringIO
from types import SimpleNamespace
from typing import Any

from rich.console import Console

from surfaces.interactive_shell.ui import resume_picker


def test_draw_starts_with_blank_line_and_counts_it(monkeypatch: Any, capsys: Any) -> None:
    monkeypatch.setattr(resume_picker, "menu_columns", lambda: 80)

    height = resume_picker._draw(
        [
            resume_picker.ResumeMenuItem(
                session_id="session-a",
                title="Investigate latency",
                activity_at=datetime.now(UTC),
            )
        ],
        selected=0,
        top=0,
        visible_rows=1,
        erase_lines=0,
        now=datetime.now(UTC),
    )

    assert capsys.readouterr().out.startswith("\r\n")
    assert height == 7


def test_interactive_resume_separates_picker_from_result(monkeypatch: Any) -> None:
    resume_command = importlib.import_module(
        "surfaces.interactive_shell.command_registry.session_cmds.resume"
    )
    events: list[str] = []
    resumed: dict[str, Any] = {}
    repo = SimpleNamespace(
        load_recent=lambda _limit: [
            {
                "session_id": "target-session",
                "conversation_title": "Investigate latency",
                "activity_at": "2026-09-25T12:00:00+00:00",
            }
        ]
    )

    def _prepare_output() -> None:
        events.append("gap")

    def _do_resume(
        prefix: str,
        session: Any,
        console: Console,
        *,
        slash_command: str | None = None,
    ) -> bool:
        events.append("resume")
        resumed.update(prefix=prefix, slash_command=slash_command)
        return True

    monkeypatch.setattr(resume_command, "default_session_repo", lambda: repo)
    monkeypatch.setattr(
        resume_command,
        "choose_resume_session",
        lambda _items: "target-session",
    )
    monkeypatch.setattr(resume_command, "prepare_repl_output_line", _prepare_output)
    monkeypatch.setattr(resume_command, "_do_resume", _do_resume)

    handled = resume_command._interactive_resume_menu(
        SimpleNamespace(session_id="current-session"),
        Console(file=StringIO()),
    )

    assert handled is True
    assert events == ["gap", "resume"]
    assert resumed == {
        "prefix": "target-session",
        "slash_command": "/resume target-s",
    }
