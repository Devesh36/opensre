"""Tests for the interactive-shell launch banner."""

from __future__ import annotations

import io

from rich.console import Console

from app.cli.interactive_shell.ui import banner as banner_module


def test_banner_shows_ollama_model(monkeypatch: object) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    monkeypatch.setenv("OLLAMA_MODEL", "qwen2.5:7b")
    console_file = io.StringIO()
    console = Console(file=console_file, force_terminal=False, highlight=False)

    banner_module.render_banner(console)

    output = console_file.getvalue()
    assert "ollama" in output
    assert "qwen2.5:7b" in output
    assert "ollama · default" not in output


def test_ready_box_uses_active_theme_palette() -> None:
    from app.cli.interactive_shell.ui.theme import set_active_theme

    set_active_theme("pink")
    pink_rgb = "255;179;217"
    green_rgb = "185;237;175"

    console = Console(record=True, width=120)
    console.print(banner_module.build_ready_panel(console))

    styled = console.export_text(styles=True)
    assert pink_rgb in styled
    assert green_rgb not in styled


def test_refresh_welcome_poster_uses_repl_safe_render(monkeypatch: object) -> None:
    console = Console(record=True, width=120)
    render_calls: list[dict[str, object | None]] = []

    monkeypatch.setattr(
        "app.cli.interactive_shell.ui.rendering.repl_clear_screen",
        lambda: None,
    )

    def _fake_render(
        _console: Console,
        *,
        session: object = None,
        theme_notice: str | None = None,
    ) -> None:
        render_calls.append({"session": session, "theme_notice": theme_notice})

    monkeypatch.setattr(
        "app.cli.interactive_shell.ui.rendering.repl_render_launch_poster",
        _fake_render,
    )

    banner_module.refresh_welcome_poster(console, session="sess", theme_notice="pink")

    assert render_calls == [{"session": "sess", "theme_notice": "pink"}]


def test_ready_box_expands_to_console_width() -> None:
    console_file = io.StringIO()
    console = Console(file=console_file, force_terminal=False, highlight=False, width=120)

    banner_module.render_ready_box(console)

    lines = [
        line for line in console_file.getvalue().splitlines() if line.startswith(("╭", "╰", "│"))
    ]
    assert lines
    assert max(len(line) for line in lines) == 120
