"""Validated runtime context for interactive shell sessions."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Self

import click
from prompt_toolkit import PromptSession
from pydantic import BaseModel, ConfigDict, InstanceOf, model_validator

from core.agent_harness.session.bootstrap import ReplSessionBootstrapSpec
from core.agent_harness.session.state import ReplSession
from core.domain.alerts import inbox as _alert_inbox
from surfaces.interactive_shell.runtime.core.state import (
    ReplState,
    SpinnerState,
    create_repl_mutable_state,
)


class ReplRuntimeContext(BaseModel):
    """Validated bundle shared by REPL entrypoints and the controller."""

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        extra="forbid",
        validate_assignment=True,
    )

    session: InstanceOf[ReplSession]
    state: InstanceOf[ReplState]
    spinner: InstanceOf[SpinnerState]
    pt_session: PromptSession[str] | None = None
    inbox: _alert_inbox.AlertInbox | None = None

    @model_validator(mode="before")
    @classmethod
    def apply_initial_mutable_state(cls, data: object) -> object:
        """Set the paired mutable state defaults through one canonical factory."""
        if not isinstance(data, dict):
            return data
        if "state" in data and "spinner" in data:
            return data
        mutable_state = create_repl_mutable_state(
            state=data.get("state"),
            spinner=data.get("spinner"),
        )
        return {
            **data,
            "state": mutable_state.state,
            "spinner": mutable_state.spinner,
        }

    @model_validator(mode="after")
    def bind_prompt_history_backend(self) -> Self:
        """Keep session prompt-history state aligned with the prompt session."""
        if self.pt_session is not None:
            self.session.prompt_history_backend = self.pt_session.history
        return self


def _current_theme_name() -> str:
    from platform.terminal.theme import get_active_theme_name

    return get_active_theme_name()


def _bind_shell_grounding(session: ReplSession) -> None:
    def _slash_commands() -> Mapping[str, object]:
        from surfaces.interactive_shell.command_registry import SLASH_COMMANDS

        return SLASH_COMMANDS

    def _cli_command_group() -> click.Command | None:
        from surfaces.cli.__main__ import cli

        return cli

    session.grounding.set_slash_commands_provider(_slash_commands)
    session.grounding.set_command_group_provider(_cli_command_group)


def _validate_active_theme_name(active_theme_name: str | None) -> str | None:
    if active_theme_name is not None and not active_theme_name.strip():
        raise ValueError("active_theme_name must not be blank")
    return active_theme_name


def prepare_repl_session(
    session: ReplSession | None = None,
    *,
    pt_session: PromptSession[str] | None = None,
    active_theme_name: str | None = None,
    hydrate_integrations: bool = True,
    persistent_tasks: bool = True,
) -> ReplSession:
    """Return a session with the same defaults used by REPL boot."""
    validated_theme_name = _validate_active_theme_name(active_theme_name)
    prepared = ReplSessionBootstrapSpec(
        session=session or ReplSession(),
        hydrate_integrations=hydrate_integrations,
        persistent_tasks=persistent_tasks,
    ).session
    prepared.active_theme_name = validated_theme_name or _current_theme_name()
    _bind_shell_grounding(prepared)
    if pt_session is not None:
        prepared.prompt_history_backend = pt_session.history
    return prepared


def create_repl_runtime_context(
    session: ReplSession | None = None,
    *,
    state: ReplState | None = None,
    spinner: SpinnerState | None = None,
    pt_session: PromptSession[str] | None = None,
    inbox: _alert_inbox.AlertInbox | None = None,
    active_theme_name: str | None = None,
    hydrate_integrations: bool = True,
    persistent_tasks: bool = True,
) -> ReplRuntimeContext:
    """Create the canonical validated context for a REPL controller."""
    prepared_session = prepare_repl_session(
        session,
        pt_session=pt_session,
        active_theme_name=active_theme_name,
        hydrate_integrations=hydrate_integrations,
        persistent_tasks=persistent_tasks,
    )
    mutable_state = create_repl_mutable_state(state=state, spinner=spinner)
    return ReplRuntimeContext(
        session=prepared_session,
        state=mutable_state.state,
        spinner=mutable_state.spinner,
        pt_session=pt_session,
        inbox=inbox,
    )


__all__ = [
    "ReplRuntimeContext",
    "create_repl_runtime_context",
    "prepare_repl_session",
]
