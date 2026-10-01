"""Keyboard navigation and raw-terminal safety for the session picker."""

from __future__ import annotations

from os import terminal_size
from typing import Any

import pytest
from rich.text import Text

from surfaces.interactive_shell.ui import session_picker
from surfaces.shared.terminal.prompt_layout import prompt_text_width


def _items() -> list[session_picker.SessionMenuItem]:
    return [
        session_picker.SessionMenuItem("current", "Current work", "10-01 16:00", "7s", "2", True),
        session_picker.SessionMenuItem("past-a", "Investigate latency", "10-01 15:40", "11m", "4"),
        session_picker.SessionMenuItem("past-b", "Review alerts", "09-29 14:53", "2m", "8"),
    ]


def test_arrows_select_previous_session_and_restore_terminal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    selected_rows: list[int] = []
    events: list[str] = []
    actions = iter(("down", "enter"))

    monkeypatch.setattr(session_picker, "repl_tty_interactive", lambda: True)
    monkeypatch.setattr(
        session_picker.shutil,
        "get_terminal_size",
        lambda **_kwargs: terminal_size((80, 24)),
    )
    monkeypatch.setattr(session_picker, "enter_inline_menu", lambda: events.append("enter"))
    monkeypatch.setattr(session_picker, "leave_inline_menu", lambda: events.append("leave"))
    monkeypatch.setattr(
        session_picker,
        "erase_menu_lines",
        lambda _height, *, delete=False: events.append("erase" if delete else "redraw"),
    )
    monkeypatch.setattr(session_picker, "read_menu_action", lambda: next(actions))

    def _draw(_items: Any, **kwargs: Any) -> int:
        selected_rows.append(kwargs["selected"])
        return kwargs["visible_rows"] + session_picker._CHROME_ROWS

    monkeypatch.setattr(session_picker, "_draw", _draw)

    assert session_picker.choose_recent_session(_items()) == "past-b"
    assert selected_rows == [1, 2]
    assert events == ["enter", "erase", "leave"]


def test_picker_row_clips_untrusted_text_to_terminal_width() -> None:
    item = session_picker.SessionMenuItem(
        "past-a",
        "\x1b[31mVery long incident name with emoji 🔥 and more words",
        "10-01 15:40",
        "11m",
        "4",
    )

    row = session_picker._row(item, selected=False, index=0, width=40)

    assert "\x1b[31m" not in row
    assert prompt_text_width(Text.from_ansi(row).plain) == 40


def test_picker_scrolls_to_sessions_below_the_viewport(monkeypatch: pytest.MonkeyPatch) -> None:
    items = [
        session_picker.SessionMenuItem(
            f"session-{index}", f"Work {index}", "10-01 16:00", "1m", "2"
        )
        for index in range(20)
    ]
    actions = iter(["down"] * 17 + ["enter"])
    viewport_tops: list[int] = []
    monkeypatch.setattr(session_picker, "repl_tty_interactive", lambda: True)
    monkeypatch.setattr(
        session_picker.shutil,
        "get_terminal_size",
        lambda **_kwargs: terminal_size((80, 24)),
    )
    monkeypatch.setattr(session_picker, "enter_inline_menu", lambda: None)
    monkeypatch.setattr(session_picker, "leave_inline_menu", lambda: None)
    monkeypatch.setattr(session_picker, "erase_menu_lines", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(session_picker, "read_menu_action", lambda: next(actions))

    def _draw(_items: Any, **kwargs: Any) -> int:
        viewport_tops.append(kwargs["top"])
        return kwargs["visible_rows"] + session_picker._CHROME_ROWS

    monkeypatch.setattr(session_picker, "_draw", _draw)

    assert session_picker.choose_recent_session(items) == "session-17"
    assert viewport_tops[-1] > 0


def test_escape_closes_picker_and_restores_terminal(monkeypatch: pytest.MonkeyPatch) -> None:
    events: list[str] = []
    monkeypatch.setattr(session_picker, "repl_tty_interactive", lambda: True)
    monkeypatch.setattr(session_picker, "enter_inline_menu", lambda: events.append("enter"))
    monkeypatch.setattr(session_picker, "leave_inline_menu", lambda: events.append("leave"))
    monkeypatch.setattr(
        session_picker,
        "erase_menu_lines",
        lambda _height, *, delete=False: events.append("erase" if delete else "redraw"),
    )
    monkeypatch.setattr(session_picker, "read_menu_action", lambda: "cancel")
    monkeypatch.setattr(session_picker, "_draw", lambda *_args, **_kwargs: 7)

    assert session_picker.choose_recent_session(_items()) is None
    assert events == ["enter", "erase", "leave"]
