"""Shared Rich loaders for interactive-shell LLM calls.

A theme-accented spinner shows that an LLM call is in flight. Centralized so
every LLM-backed surface in the interactive shell (``cli_agent``, ``cli_help``,
``follow_up``) shares the same look.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from rich.console import Console

from app.cli.interactive_shell.ui import theme as ui_theme

_LOADER_SPINNER = "dots"

DEFAULT_LOADER_LABEL = "thinking"


@contextmanager
def llm_loader(console: Console, label: str = DEFAULT_LOADER_LABEL) -> Iterator[None]:
    """Show a themed spinner while an LLM call is in flight.

    On non-terminal consoles (CI, captured output, piped stdout), the spinner is
    skipped so captured logs stay clean — the wrapped call still runs unchanged.
    """
    if not console.is_terminal:
        yield
        return

    loader_color = ui_theme.HIGHLIGHT
    console.print()
    text = f"[{loader_color}]{label}…[/{loader_color}]"
    with console.status(text, spinner=_LOADER_SPINNER, spinner_style=loader_color):
        yield


__all__ = ["DEFAULT_LOADER_LABEL", "llm_loader"]
