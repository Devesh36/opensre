"""Surface-agnostic session bootstrap for agent surfaces."""

from __future__ import annotations

from typing import Self

from pydantic import BaseModel, ConfigDict, Field, InstanceOf, model_validator

from core.agent_harness.session.state import ReplSession
from core.agent_harness.session.tasks import TaskRegistry


class ReplSessionBootstrapSpec(BaseModel):
    """Pydantic-enforced inputs for preparing a reusable agent session."""

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="forbid")

    session: InstanceOf[ReplSession] = Field(default_factory=ReplSession)
    hydrate_integrations: bool = True
    persistent_tasks: bool = True

    @model_validator(mode="after")
    def apply_to_session(self) -> Self:
        """Apply the canonical startup mutations to the validated session."""
        if self.hydrate_integrations:
            self.session.hydrate_configured_integrations()
        if self.persistent_tasks:
            self.session.task_registry = TaskRegistry.persistent()
        return self


def bootstrap_repl_session(
    session: ReplSession | None = None,
    *,
    hydrate_integrations: bool = True,
    persistent_tasks: bool = True,
) -> ReplSession:
    """Return a session with the shared surface-agnostic bootstrap defaults."""
    spec = ReplSessionBootstrapSpec(
        session=session or ReplSession(),
        hydrate_integrations=hydrate_integrations,
        persistent_tasks=persistent_tasks,
    )
    return spec.session


__all__ = [
    "ReplSessionBootstrapSpec",
    "bootstrap_repl_session",
]
