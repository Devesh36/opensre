"""Scrollable inline picker for recent shell sessions."""

from __future__ import annotations

import shutil
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from infrastructure.terminal import theme as ui_theme
from surfaces.shared.terminal.components.choice_menu import (
    enter_inline_menu,
    erase_menu_lines,
    leave_inline_menu,
    menu_columns,
    read_menu_action,
    repl_tty_interactive,
    write_menu_line,
)
from surfaces.shared.terminal.prompt_layout import clip_prompt_text, prompt_text_width

_MAX_VISIBLE_ROWS = 15
_CHROME_ROWS = 5
_MAX_WIDTH = 104


@dataclass(frozen=True)
class SessionMenuItem:
    session_id: str
    title: str
    started: str
    duration: str
    turns: str
    is_current: bool = False
    started_full: str = ""


def _visible_row_count(max_visible_rows: int, chrome_rows: int) -> int:
    rows = shutil.get_terminal_size(fallback=(80, 24)).lines
    return min(max_visible_rows, max(1, rows - chrome_rows - 1))


def _row(item: SessionMenuItem, *, selected: bool, index: int, width: int) -> str:
    prefix = clip_prompt_text(f"  {'›' if selected else ' '}  ", width)
    when = f"  {clip_prompt_text(item.started, 11)}" if width >= 48 else ""
    title_width = max(0, width - prompt_text_width(prefix + when))
    title = f"● current  {item.title}" if item.is_current else item.title
    title = clip_prompt_text(title, title_width)
    padding = " " * max(0, title_width - prompt_text_width(title))
    content = f"{prefix}{title}{padding}{when}"
    if selected:
        return f"{ui_theme.prominent_menu_selection_ansi()}{content}{ui_theme.ANSI_RESET}"
    background = ui_theme.INPUT_SURFACE_BG_ANSI if index % 2 else ui_theme.SURFACE_BG_ANSI
    title_style = ui_theme.HIGHLIGHT_ANSI if item.is_current else ui_theme.TEXT_ANSI
    return (
        f"{background}{ui_theme.DIM_COUNTER_ANSI}{prefix}"
        f"{title_style}{title}{padding}"
        f"{ui_theme.DIM_COUNTER_ANSI}{when}{ui_theme.ANSI_RESET}"
    )


def _draw(
    items: Sequence[SessionMenuItem],
    *,
    selected: int,
    top: int,
    visible_rows: int,
    erase_lines: int,
) -> int:
    width = min(menu_columns(), _MAX_WIDTH)
    if erase_lines:
        erase_menu_lines(erase_lines)
    write_menu_line()
    heading = f"  Sessions  ·  {len(items)} recent"
    write_menu_line(
        f"{ui_theme.PROMPT_ACCENT_ANSI}{clip_prompt_text(heading, width)}{ui_theme.ANSI_RESET}"
    )
    write_menu_line(f"{ui_theme.DIM_COUNTER_ANSI}{'─' * width}{ui_theme.ANSI_RESET}")
    end = min(len(items), top + visible_rows)
    for index in range(top, end):
        write_menu_line(_row(items[index], selected=index == selected, index=index, width=width))
    for _ in range(visible_rows - (end - top)):
        write_menu_line()

    item = items[selected]
    detail = (
        f"  {item.session_id[:8]}  ·  {item.started}  ·  {item.duration}  ·  {item.turns} turns"
    )
    write_menu_line(
        f"{ui_theme.DIM_COUNTER_ANSI}{clip_prompt_text(detail, width)}{ui_theme.ANSI_RESET}"
    )
    action = "Enter already here" if item.is_current else "Enter resume"
    position = f"{selected + 1}/{len(items)}"
    hint = f"  ↑↓ move   {action}   Esc close"
    hint += " " * max(0, width - prompt_text_width(hint) - len(position) - 2)
    hint += f"{position}  "
    write_menu_line(
        f"{ui_theme.DIM_COUNTER_ANSI}{clip_prompt_text(hint, width)}{ui_theme.ANSI_RESET}"
    )
    sys.stdout.flush()
    return visible_rows + _CHROME_ROWS


def _choose_scrollable[T](
    items: Sequence[T],
    *,
    draw: Callable[..., int],
    max_visible_rows: int,
    chrome_rows: int,
    selected: int = 0,
) -> T | None:
    """Run a bounded inline picker and return its selected item."""
    if not items or not repl_tty_interactive():
        return None
    top = 0
    drawn_height = 0
    enter_inline_menu()
    try:
        while True:
            visible_rows = _visible_row_count(max_visible_rows, chrome_rows)
            top = min(top, max(0, len(items) - visible_rows))
            if selected < top:
                top = selected
            elif selected >= top + visible_rows:
                top = selected - visible_rows + 1
            drawn_height = draw(
                items,
                selected=selected,
                top=top,
                visible_rows=visible_rows,
                erase_lines=drawn_height,
            )
            action = read_menu_action()
            if action == "up":
                selected = (selected - 1) % len(items)
            elif action == "down":
                selected = (selected + 1) % len(items)
            elif action == "enter":
                return items[selected]
            elif action in ("cancel", "eof"):
                return None
    finally:
        erase_menu_lines(drawn_height, delete=True)
        leave_inline_menu()


def choose_recent_session(items: Sequence[SessionMenuItem]) -> str | None:
    """Return the highlighted session ID when Enter is pressed."""
    selected = next((index for index, item in enumerate(items) if not item.is_current), 0)
    picked = _choose_scrollable(
        items,
        draw=_draw,
        max_visible_rows=_MAX_VISIBLE_ROWS,
        chrome_rows=_CHROME_ROWS,
        selected=selected,
    )
    return picked.session_id if picked is not None else None
