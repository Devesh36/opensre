"""Slash command: interactive theme selection and persistence."""

from __future__ import annotations

from contextlib import suppress
from typing import Any

from rich.console import Console

from app.cli.interactive_shell.command_registry.types import ExecutionTier, SlashCommand
from app.cli.interactive_shell.runtime import ReplSession
from app.cli.interactive_shell.ui import DIM, render_banner
from app.cli.interactive_shell.ui.choice_menu import repl_choose_one, repl_tty_interactive
from app.cli.interactive_shell.ui.theme import (
    get_active_theme,
    get_active_theme_name,
    list_theme_names,
    set_active_theme,
)


def _load_config() -> dict[str, Any]:
    from app.cli.commands.config import _load_config

    return _load_config()


def _save_config(data: dict[str, Any]) -> None:
    from app.cli.commands.config import _save_config

    _save_config(data)


def _set_nested_key(data: dict[str, Any], dotted_key: str, value: Any) -> dict[str, Any]:
    from app.cli.commands.config import _set_nested_key

    return _set_nested_key(data, dotted_key, value)


def _apply_new_prompt_style(session: ReplSession) -> None:
    """Update the running prompt-toolkit application's style in the main thread.

    Runs on the main asyncio thread via ``call_soon_threadsafe`` so
    ``get_app_or_none()`` returns the correct application (it returns
    ``None`` from worker threads because the ``_current_app`` ContextVar
    is only set on the main thread).
    """
    from app.cli.interactive_shell.prompting.prompt_surface import _build_prompt_style

    app = session.pt_style_app
    if app is None:
        return
    app.style = _build_prompt_style()
    if app.renderer is not None:
        with suppress(Exception):
            app.renderer.clear()
    app.invalidate()


def _refresh_prompt_style(session: ReplSession) -> None:
    """Schedule a prompt-toolkit style refresh on the main thread."""
    if session.main_loop is not None:
        session.main_loop.call_soon_threadsafe(_apply_new_prompt_style, session)


def _repaint_terminal(console: Console) -> None:
    """Clear and redraw shell chrome so the new theme is immediately visible."""
    console.clear()
    render_banner(console)


def _cmd_theme(session: ReplSession, console: Console, _args: list[str]) -> bool:
    if not repl_tty_interactive():
        console.print(f"[{DIM}]/theme requires an interactive TTY session.[/]")
        return True

    current = get_active_theme_name()
    choices = [
        (
            name,
            f"{name}{' (current)' if name == current else ''}",
        )
        for name in list_theme_names()
    ]
    selected = repl_choose_one(title="theme", breadcrumb="/theme", choices=choices)
    if selected is None:
        console.print(f"[{DIM}]theme unchanged.[/]")
        return True

    active = set_active_theme(selected)
    _refresh_prompt_style(session)
    _repaint_terminal(console)

    config_data = _load_config()
    updated = _set_nested_key(config_data, "interactive.theme", active.name)
    _save_config(updated)

    console.print(f"[{get_active_theme().HIGHLIGHT}]theme set:[/] {active.name}")
    return True


_THEME_FIRST_ARGS: tuple[tuple[str, str], ...] = tuple(
    (name, "interactive palette") for name in list_theme_names()
)

COMMANDS: list[SlashCommand] = [
    SlashCommand(
        "/theme",
        "choose and persist the interactive shell theme (TTY picker)",
        _cmd_theme,
        first_arg_completions=_THEME_FIRST_ARGS,
        execution_tier=ExecutionTier.SAFE,
    )
]

__all__ = ["COMMANDS"]
