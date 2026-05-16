from __future__ import annotations

from app.cli.interactive_shell.ui.theme import (
    DEFAULT_THEME_NAME,
    get_active_theme,
    get_theme,
    list_theme_names,
    set_active_theme,
)


def test_theme_registry_contains_expected_builtin_names() -> None:
    assert list_theme_names() == (
        "green",
        "blue",
        "amber",
        "mono",
        "red",
        "pink",
        "purple",
        "orange",
        "teal",
    )


def test_theme_registry_entries_include_required_semantic_tokens() -> None:
    required = (
        "HIGHLIGHT",
        "BRAND",
        "TEXT",
        "SECONDARY",
        "DIM",
        "WARNING",
        "ERROR",
        "BG",
        "INPUT_SURFACE",
    )
    for name in list_theme_names():
        theme = get_theme(name)
        for token in required:
            value = getattr(theme, token)
            assert isinstance(value, str)
            assert value.startswith("#")
            assert len(value) == 7


def test_set_active_theme_falls_back_to_default_for_unknown_name() -> None:
    active = set_active_theme("does-not-exist")
    assert active.name == DEFAULT_THEME_NAME
    assert get_active_theme().name == DEFAULT_THEME_NAME
