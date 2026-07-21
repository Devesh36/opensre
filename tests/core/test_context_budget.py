from __future__ import annotations

import json
from unittest.mock import patch

from core.context_budget import (
    context_budget_ceiling_for_model,
    enforce_context_budget,
    estimate_message_tokens,
    strip_internal_message_markers,
)


class TestGpt56ContextWindow:
    """GPT-5.6 ships a 1M-token window, unlike the 128k-pinned gpt-5 family (#3931)."""

    def test_sol_reclaims_the_million_token_window(self) -> None:
        # 1_000_000 window - 16_000 response headroom.
        assert context_budget_ceiling_for_model("gpt-5.6-sol") == 984_000

    def test_all_tiers_share_the_family_window(self) -> None:
        sol = context_budget_ceiling_for_model("gpt-5.6-sol")
        assert context_budget_ceiling_for_model("gpt-5.6-terra") == sol
        assert context_budget_ceiling_for_model("gpt-5.6-luna") == sol
        assert context_budget_ceiling_for_model("gpt-5.6") == sol

    def test_gpt56_is_not_shadowed_by_the_gpt5_catch_all(self) -> None:
        # ``_MODEL_CONTEXT_WINDOWS`` is matched by substring in insertion
        # order with a break, so moving the ``gpt-5.6`` key below ``gpt-5``
        # would silently pin 5.6 back to 128k. Nothing else would fail.
        assert context_budget_ceiling_for_model("gpt-5.6-sol") > context_budget_ceiling_for_model(
            "gpt-5.5"
        )

    def test_older_gpt5_models_keep_their_conservative_pin(self) -> None:
        # 128_000 window - 16_000 response headroom.
        assert context_budget_ceiling_for_model("gpt-5.5") == 112_000
        assert context_budget_ceiling_for_model("gpt-5") == 112_000


def test_strip_internal_message_markers_removes_opensre_keys() -> None:
    messages = [
        {"role": "user", "content": "alert"},
        {
            "role": "assistant",
            "content": [{"type": "tool_use", "id": "seed", "name": "n", "input": {}}],
            "_opensre_seed": True,
        },
        {
            "role": "user",
            "content": [{"type": "tool_result", "tool_use_id": "seed", "content": "ok"}],
            "_opensre_seed": True,
            "_opensre_duplicate_result": True,
        },
    ]

    cleaned = strip_internal_message_markers(messages)

    assert cleaned[0] == messages[0]
    assert cleaned[1] == {
        "role": "assistant",
        "content": [{"type": "tool_use", "id": "seed", "name": "n", "input": {}}],
    }
    assert cleaned[2] == {
        "role": "user",
        "content": [{"type": "tool_result", "tool_use_id": "seed", "content": "ok"}],
    }
    assert messages[1]["_opensre_seed"] is True
    assert messages[2]["_opensre_duplicate_result"] is True


def test_strip_internal_message_markers_preserves_other_underscore_keys() -> None:
    messages = [{"role": "user", "content": "hi", "_custom": "keep"}]

    cleaned = strip_internal_message_markers(messages)

    assert cleaned == [{"role": "user", "content": "hi", "_custom": "keep"}]


def test_estimate_message_tokens_includes_system_and_tools_overhead() -> None:
    messages = [{"role": "user", "content": "abcd"}]
    system = "sys"
    tools = [
        {"type": "function", "name": "alpha", "parameters": {"type": "object"}},
        {
            "type": "function",
            "name": "beta",
            "parameters": {"type": "object", "properties": {"q": {"type": "string"}}},
        },
    ]

    message_tokens = int(len("abcd") * 0.50)
    system_tokens = int(len(system) * 0.50)
    tool_tokens = sum(int(len(json.dumps(schema, default=str)) * 0.50) for schema in tools)
    expected = message_tokens + system_tokens + tool_tokens

    assert estimate_message_tokens(messages, system=system, tools=tools) == expected


def test_estimate_message_tokens_distinguishes_distinct_tool_lists() -> None:
    messages: list[dict[str, str]] = []
    system = "system prompt"
    tools_a = [{"type": "function", "name": "alpha"}]
    tools_b = [{"type": "function", "name": "beta", "parameters": {"type": "object"}}]

    assert estimate_message_tokens(
        messages, system=system, tools=tools_a
    ) != estimate_message_tokens(messages, system=system, tools=tools_b)
    assert estimate_message_tokens(messages, system=system, tools=[]) == int(len(system) * 0.50)


def test_estimate_message_tokens_reuses_precomputed_overhead() -> None:
    tools = [
        {
            "type": "function",
            "name": f"tool_{index}",
            "parameters": {"type": "object", "x": "y" * 40},
        }
        for index in range(20)
    ]
    messages = [{"role": "user", "content": "hi"}]
    system = "system prompt"

    schema_dump_calls = 0
    original_dumps = json.dumps

    def counting_dumps(value: object, *args: object, **kwargs: object) -> str:
        nonlocal schema_dump_calls
        if isinstance(value, dict) and value.get("type") == "function":
            schema_dump_calls += 1
        return original_dumps(value, *args, **kwargs)

    overhead = sum(int(len(json.dumps(schema, default=str)) * 0.50) for schema in tools) + int(
        len(system) * 0.50
    )

    with patch("core.context_budget.json.dumps", side_effect=counting_dumps):
        estimate_message_tokens(
            messages,
            tools=tools,
            system=system,
            system_tools_overhead_tokens=overhead,
        )

    assert schema_dump_calls == 0


def test_enforce_context_budget_serializes_tool_schemas_once_per_invocation() -> None:
    tools = [
        {"type": "function", "name": f"tool_{index}", "parameters": {"type": "object"}}
        for index in range(12)
    ]
    messages = [
        {"role": "user", "content": "alert"},
        {
            "role": "assistant",
            "content": [{"type": "tool_use", "id": "t1", "name": "noop", "input": {}}],
        },
        {
            "role": "user",
            "content": [{"type": "tool_result", "tool_use_id": "t1", "content": "x" * 4000}],
        },
        {
            "role": "assistant",
            "content": [{"type": "tool_use", "id": "t2", "name": "noop", "input": {}}],
        },
        {
            "role": "user",
            "content": [{"type": "tool_result", "tool_use_id": "t2", "content": "y" * 4000}],
        },
    ]
    ceiling = 500
    schema_dump_calls = 0
    original_dumps = json.dumps

    def counting_dumps(value: object, *args: object, **kwargs: object) -> str:
        nonlocal schema_dump_calls
        if isinstance(value, dict) and value.get("type") == "function":
            schema_dump_calls += 1
        return original_dumps(value, *args, **kwargs)

    with patch("core.context_budget.json.dumps", side_effect=counting_dumps):
        enforce_context_budget(messages, tools=tools, ceiling=ceiling)

    assert schema_dump_calls == len(tools)


def test_enforce_context_budget_still_trims_when_over_ceiling_with_tools() -> None:
    tools = [{"type": "function", "name": "noop", "parameters": {"type": "object"}}]
    messages = [
        {"role": "user", "content": "alert"},
        {
            "role": "assistant",
            "content": [{"type": "tool_use", "id": "t1", "name": "noop", "input": {}}],
        },
        {
            "role": "user",
            "content": [{"type": "tool_result", "tool_use_id": "t1", "content": "x" * 4000}],
        },
        {
            "role": "assistant",
            "content": [{"type": "tool_use", "id": "t2", "name": "noop", "input": {}}],
        },
        {
            "role": "user",
            "content": [{"type": "tool_result", "tool_use_id": "t2", "content": "y" * 4000}],
        },
    ]
    ceiling = 500

    enforce_context_budget(messages, tools=tools, ceiling=ceiling)

    assert estimate_message_tokens(messages, tools=tools) <= ceiling
    assert len(messages) < 5
