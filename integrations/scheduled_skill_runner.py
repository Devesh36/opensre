"""Headless scheduled runner for pinned recurring action skills."""

from __future__ import annotations

import logging
from typing import Any

from core.agent_harness import AgentSession
from core.agent_harness.harness import SCHEDULED_RUN_CONFIG
from core.agent_harness.ports import ConfirmFn, ToolEventObserver, ToolProvider
from core.agent_harness.prompts.skills.schedule import resolve_scheduled_skill
from core.agent_harness.turns.headless_adapters import BufferOutputSink
from core.agent_harness.turns.headless_build import DefaultHeadlessBuild
from infrastructure.scheduling.scheduler.agent_runner import AgentPayload

logger = logging.getLogger(__name__)

_BLOCKED_TOOL_NAMES = frozenset(
    {
        "slack_send_message",
        "telegram_send_message",
        "rocketchat_send_message",
        "buzz_send_message",
        "propose_scheduled_delivery",
    }
)

_SCHEDULED_SKILL_INSTRUCTIONS = """Scheduled recurring skill run.

Follow the skill recipe below exactly for this unattended tick.
Produce only the final report body text the scheduler should deliver.
Do not send, post, notify, or message any channel from inside this turn; the
scheduler will deliver the final report body to the configured channels after
this runner returns.
Do not call propose_scheduled_delivery or offer to schedule again.
Use read-only tools when data is required.
"""


class _DeliveryStrippedToolProvider:
    """Wrap a tool provider and remove delivery / reschedule tools."""

    def __init__(self, inner: ToolProvider) -> None:
        self._inner = inner

    def action_tools(
        self,
        *,
        confirm_fn: ConfirmFn | None,
        is_tty: bool | None,
        resolved_integrations: dict[str, Any] | None = None,
    ) -> list[Any]:
        return [
            tool
            for tool in self._inner.action_tools(
                confirm_fn=confirm_fn,
                is_tty=is_tty,
                resolved_integrations=resolved_integrations,
            )
            if getattr(tool, "name", None) not in _BLOCKED_TOOL_NAMES
        ]

    def tool_resources(self) -> dict[str, Any]:
        return self._inner.tool_resources()

    def observer(self, *, message: str) -> ToolEventObserver:
        return self._inner.observer(message=message)


def run_scheduled_recurring_skill(payload: AgentPayload) -> str:
    """Run one headless turn for a pinned recurring skill and return report text."""
    resolved = resolve_scheduled_skill(
        str(payload.get("skill_name") or ""),
        str(payload.get("skill_revision") or ""),
    )
    inputs = payload.get("skill_inputs") or {}
    input_block = ""
    if isinstance(inputs, dict) and inputs:
        rendered = "\n".join(f"- {key}: {value}" for key, value in sorted(inputs.items()))
        input_block = f"\nValidated inputs:\n{rendered}\n"
    message = (
        f"{_SCHEDULED_SKILL_INSTRUCTIONS}\n"
        f"Skill: {resolved.name}\n"
        f"{input_block}\n"
        f"Skill recipe:\n{resolved.body}"
    )

    agent_session = AgentSession.start(
        config=SCHEDULED_RUN_CONFIG, logger=logger, is_tty=False
    )
    session = agent_session.bound_session
    if session is None:
        raise RuntimeError("Scheduled skill runner failed to bind a session.")
    build = DefaultHeadlessBuild(session=session, output=BufferOutputSink(), logger=logger)
    agent_session.attach_agent(build.agent(tools=_DeliveryStrippedToolProvider(build.tools())))
    result = agent_session.chat(message)
    report = result.primary_response_text
    if not result.answered or not report:
        raise RuntimeError(
            f"Scheduled skill {resolved.name!r} failed: "
            "the reasoning client did not produce a report."
        )
    return report


__all__ = ["_BLOCKED_TOOL_NAMES", "run_scheduled_recurring_skill"]
