"""Top-level planner orchestration for LLM-driven action plans."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from app.cli.interactive_shell.routing.handle_message_with_agent.errors import PlannerLLMError
from app.cli.interactive_shell.routing.handle_message_with_agent.orchestration.interaction_models import (
    PlannedAction,
)

from .llm_client import _call_llm
from .parsing import _parse_tool_plan
from .postprocessing import (
    _fail_closed_vague_local_model,
    finalize_planner_result_with_trace,
)
from .prompting import _sanitise_text


@dataclass(frozen=True)
class LlmActionPlanResult:
    """Structured result for one LLM planning pass with postprocess trace."""

    actions: tuple[PlannedAction, ...]
    has_unhandled_clause: bool
    policy_trace: tuple[str, ...]


_INFORMATIONAL_QUESTION_RE = re.compile(
    r"\s*(?:how|what|why|which|when|where|who|can|could|should|do|does|is|are)\b",
    re.IGNORECASE,
)
_PROMPT_TOO_LONG_RE = re.compile(
    r"context.?length|context.?window|max.?token|token.?limit|"
    r"too.?long|input.*exceed|prompt.*too.?large|reduce.*context|"
    r"string too long",
    re.IGNORECASE,
)


def _is_informational_question(message: str) -> bool:
    if "?" in message:
        return True
    return _INFORMATIONAL_QUESTION_RE.match(message) is not None


def _is_prompt_too_long_error(exc: PlannerLLMError) -> bool:
    return _PROMPT_TOO_LONG_RE.search(str(exc)) is not None


def _fallback_handoff(sanitised: str) -> list[PlannedAction]:
    return [
        PlannedAction(
            kind="assistant_handoff",
            content=sanitised,
            position=0,
            source="llm",
        )
    ]


def plan_actions_with_llm_result(
    message: str,
    *,
    session: Any | None = None,
) -> LlmActionPlanResult | None:
    """Plan actions and return typed policy trace metadata."""
    sanitised = _sanitise_text(message.strip())
    early = _fail_closed_vague_local_model(sanitised)
    if early is not None:
        actions, has_unhandled = early
        return LlmActionPlanResult(
            actions=tuple(actions),
            has_unhandled_clause=has_unhandled,
            policy_trace=("fail_closed_vague_local_model",),
        )

    try:
        raw = _call_llm(sanitised, session)
    except PlannerLLMError as exc:
        if not _is_prompt_too_long_error(exc):
            raise
        from app.cli.interactive_shell.routing.handle_message_with_agent.orchestration.slash_commands.deterministic_action_mapper import (
            map_actions_result,
        )

        fallback = map_actions_result(sanitised)
        fallback_actions = list(fallback.actions)
        if not fallback_actions and (
            _is_informational_question(sanitised) or fallback.has_unhandled_clause
        ):
            fallback_actions = _fallback_handoff(sanitised)
            fallback_has_unhandled = False
        else:
            fallback_has_unhandled = fallback.has_unhandled_clause
        finalized = finalize_planner_result_with_trace(
            sanitised,
            fallback_actions,
            fallback_has_unhandled,
            session=session,
        )
        return LlmActionPlanResult(
            actions=tuple(finalized.actions),
            has_unhandled_clause=finalized.has_unhandled,
            policy_trace=("fallback_prompt_too_long",)
            + tuple(tag.value for tag in finalized.applied_policies),
        )
    if raw is None:
        return None

    parsed = _parse_tool_plan(raw, session=session)
    if parsed is None:
        return None
    actions, has_unhandled = parsed
    finalized = finalize_planner_result_with_trace(
        sanitised,
        actions,
        has_unhandled,
        session=session,
    )
    return LlmActionPlanResult(
        actions=tuple(finalized.actions),
        has_unhandled_clause=finalized.has_unhandled,
        policy_trace=tuple(tag.value for tag in finalized.applied_policies),
    )


def plan_actions_with_llm(
    message: str,
    *,
    session: Any | None = None,
) -> tuple[list[PlannedAction], bool] | None:
    """Plan actions from *message* using native tool-calling."""
    planned = plan_actions_with_llm_result(message, session=session)
    if planned is None:
        return None
    return list(planned.actions), planned.has_unhandled_clause
