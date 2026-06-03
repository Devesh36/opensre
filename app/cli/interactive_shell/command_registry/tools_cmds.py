"""Slash command /tools."""

from __future__ import annotations

from rich.console import Console
from rich.markup import escape

from app.cli.interactive_shell.command_registry.types import ExecutionTier, SlashCommand
from app.cli.interactive_shell.config.tool_catalog import build_tool_catalog
from app.cli.interactive_shell.runtime import ReplSession
from app.cli.interactive_shell.ui import ERROR, render_tools_table


def _cmd_tools(session: ReplSession, console: Console, args: list[str]) -> bool:
    sub = (args[0].lower() if args else "list").strip()
    if sub in ("list", "ls", "tool", "tools"):
        render_tools_table(console, build_tool_catalog())
        return True

    console.print(f"[{ERROR}]unknown subcommand:[/] {escape(sub)}  (try [bold]/tools list[/bold])")
    session.mark_latest(ok=False, kind="slash")
    return True


_TOOLS_FIRST_ARGS: tuple[tuple[str, str], ...] = (
    ("list", "list registered tools (investigation + chat surfaces)"),
)

COMMANDS: list[SlashCommand] = [
    SlashCommand(
        "/tools",
        "List registered tools.",
        _cmd_tools,
        usage=("/tools", "/tools list"),
        first_arg_completions=_TOOLS_FIRST_ARGS,
        execution_tier=ExecutionTier.SAFE,
    )
]

__all__ = ["COMMANDS", "_TOOLS_FIRST_ARGS"]
