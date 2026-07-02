"""Tests for surface-agnostic session bootstrap."""

from __future__ import annotations

import pytest

from core.agent_harness.session import ReplSession
from core.agent_harness.session.bootstrap import (
    ReplSessionBootstrapSpec,
    bootstrap_repl_session,
)
from core.agent_harness.session.tasks import TaskRegistry


def test_bootstrap_spec_hydrates_integrations_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    hydrate_calls: list[str] = []

    def _hydrate(self: ReplSession) -> None:
        hydrate_calls.append(self.session_id)
        self.configured_integrations = ("github",)
        self.configured_integrations_known = True

    monkeypatch.setattr(ReplSession, "hydrate_configured_integrations", _hydrate)

    session = ReplSession()
    prepared = ReplSessionBootstrapSpec(session=session).session

    assert prepared is session
    assert hydrate_calls == [session.session_id]
    assert session.configured_integrations == ("github",)
    assert session.configured_integrations_known is True


def test_bootstrap_spec_can_skip_hydration(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        ReplSession,
        "hydrate_configured_integrations",
        lambda _self: (_ for _ in ()).throw(AssertionError("hydrated")),
    )

    session = ReplSessionBootstrapSpec(
        session=ReplSession(),
        hydrate_integrations=False,
    ).session

    assert isinstance(session, ReplSession)


def test_bootstrap_spec_uses_persistent_tasks_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry = TaskRegistry()
    monkeypatch.setattr(TaskRegistry, "persistent", staticmethod(lambda: registry))

    session = ReplSessionBootstrapSpec(session=ReplSession()).session

    assert session.task_registry is registry


def test_bootstrap_spec_can_skip_persistent_tasks(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        TaskRegistry,
        "persistent",
        staticmethod(lambda: (_ for _ in ()).throw(AssertionError("persistent"))),
    )

    session = ReplSessionBootstrapSpec(
        session=ReplSession(),
        persistent_tasks=False,
    ).session

    assert isinstance(session, ReplSession)


def test_bootstrap_repl_session_returns_prepared_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry = TaskRegistry()
    monkeypatch.setattr(TaskRegistry, "persistent", staticmethod(lambda: registry))
    monkeypatch.setattr(ReplSession, "hydrate_configured_integrations", lambda _self: None)

    session = bootstrap_repl_session(ReplSession())

    assert session.task_registry is registry
