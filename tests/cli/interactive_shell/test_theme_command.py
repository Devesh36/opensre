from __future__ import annotations

import io

from rich.console import Console

from app.cli.interactive_shell.commands import SLASH_COMMANDS, dispatch_slash
from app.cli.interactive_shell.runtime.session import ReplSession
from app.cli.interactive_shell.ui.theme import get_active_theme_name, set_active_theme


def _capture() -> tuple[Console, io.StringIO]:
    buf = io.StringIO()
    return Console(file=buf, force_terminal=False, highlight=False), buf


def test_theme_command_is_registered() -> None:
    assert "/theme" in SLASH_COMMANDS


def test_theme_command_updates_active_theme_and_persists(monkeypatch) -> None:
    from app.cli.interactive_shell.command_registry import theme as theme_cmd

    monkeypatch.setattr(theme_cmd, "repl_tty_interactive", lambda: True)
    monkeypatch.setattr(theme_cmd, "repl_choose_one", lambda **_kwargs: "blue")
    monkeypatch.setattr(theme_cmd, "_refresh_prompt_style", lambda _session: None)
    repaint_calls: list[int] = []
    monkeypatch.setattr(theme_cmd, "_repaint_terminal", lambda _console: repaint_calls.append(1))

    saved_payloads: list[dict[str, object]] = []
    monkeypatch.setattr(theme_cmd, "_load_config", lambda: {})
    monkeypatch.setattr(theme_cmd, "_save_config", lambda data: saved_payloads.append(dict(data)))

    set_active_theme("green")
    session = ReplSession()
    console, _buf = _capture()

    assert dispatch_slash("/theme", session, console) is True
    assert get_active_theme_name() == "blue"
    assert saved_payloads
    assert repaint_calls == [1]
    interactive = saved_payloads[-1].get("interactive")
    assert isinstance(interactive, dict)
    assert interactive.get("theme") == "blue"


def test_theme_command_escape_keeps_current_theme(monkeypatch) -> None:
    from app.cli.interactive_shell.command_registry import theme as theme_cmd

    monkeypatch.setattr(theme_cmd, "repl_tty_interactive", lambda: True)
    monkeypatch.setattr(theme_cmd, "repl_choose_one", lambda **_kwargs: None)

    set_active_theme("amber")
    session = ReplSession()
    console, buf = _capture()

    assert dispatch_slash("/theme", session, console) is True
    assert get_active_theme_name() == "amber"
    assert "theme unchanged" in buf.getvalue()


def test_theme_set_message_uses_active_theme_color(monkeypatch) -> None:
    from app.cli.interactive_shell.command_registry import theme as theme_cmd

    monkeypatch.setattr(theme_cmd, "repl_tty_interactive", lambda: True)
    monkeypatch.setattr(theme_cmd, "repl_choose_one", lambda **_kwargs: "blue")
    monkeypatch.setattr(theme_cmd, "_refresh_prompt_style", lambda _session: None)
    monkeypatch.setattr(theme_cmd, "_repaint_terminal", lambda _console: None)
    monkeypatch.setattr(theme_cmd, "_load_config", lambda: {})
    monkeypatch.setattr(theme_cmd, "_save_config", lambda _data: None)

    set_active_theme("green")
    session = ReplSession()
    console, buf = _capture()

    assert dispatch_slash("/theme", session, console) is True
    output = buf.getvalue()
    assert "theme set: blue" in output
    assert "#A8D4FF" not in output
