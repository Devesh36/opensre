"""Reconcile checklist progress when the user edits an attached goal."""

from __future__ import annotations

from collections import deque
from dataclasses import replace
from typing import Any

from core.agent_harness.session_goal.goal import (
    MAX_GOAL_CONDITION_CHARS,
    SessionGoal,
    attach_session_goal,
    derive_session_goal_checklist,
    refresh_session_goal_reason,
    strip_shell_prompt_chrome,
)
from core.agent_harness.task_plan.discard import discard_task_plan
from infrastructure.evidence.evidence_compaction import truncate_message


def edit_session_goal(session: Any, goal: SessionGoal, condition: str) -> SessionGoal:
    """Replace the condition, preserving progress only for unchanged checklist items."""
    condition = truncate_message(strip_shell_prompt_chrome(condition), MAX_GOAL_CONDITION_CHARS)
    checklist = derive_session_goal_checklist(condition)
    if not checklist and goal.checklist != derive_session_goal_checklist(goal.condition):
        # Separately supplied items remain required unless the edit supplies new steps.
        checklist = goal.checklist
    if (
        condition == goal.condition
        and checklist == goal.checklist
        and goal.step_count == (len(checklist) or None)
    ):
        return goal

    prior_indices: dict[str, deque[int]] = {}
    for index, item in enumerate(goal.checklist):
        prior_indices.setdefault(item, deque()).append(index)

    completed: set[int] = set()
    new_ticks: set[int] = set()
    for index, item in enumerate(checklist):
        matches = prior_indices.get(item)
        if not matches:
            continue
        # Match duplicate items one-to-one so one tick cannot finish several steps.
        prior_index = matches.popleft()
        if prior_index in goal.completed:
            completed.add(index)
            if prior_index in goal.new_ticks:
                new_ticks.add(index)

    edited = replace(
        goal,
        condition=condition,
        checklist=checklist,
        step_count=len(checklist) or None,
        completed=frozenset(completed),
        new_ticks=frozenset(new_ticks),
        findings=(),
        last_answer="",
        last_verdict="",
        verdict_repeated=False,
        last_progress_turns_used=goal.turns_used,
    )
    # A prior plan may contain removed work or credit a changed step by fuzzy match.
    plan_only = getattr(session, "plan_only_until_authorized", False)
    discard_task_plan(session)
    edited = attach_session_goal(session, refresh_session_goal_reason(edited))
    if plan_only:
        session.plan_only_until_authorized = True
    return edited


__all__ = ["edit_session_goal"]
