"""Contract tests for scrubbing tool ``error`` values before LLM/evidence.

Desired contract:
- Planted secrets under tool ``error`` must not appear in LLM tool-result
  messages or in ``provider_content()``.
- ``merge_tool_evidence`` must not retain the secret in stored evidence.

``xfail`` marks document gaps in the current ``redact_sensitive``-only approach:
helper scrubbing of dict key ``error`` works for a few token patterns, but the
LLM tool-result path and several secret shapes still leak. Remove each
``xfail`` when that gap is closed.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from core.execution import ToolExecutionResult, execute_tool_calls, execute_tools
from core.llm.shared.openai_chat_completions import build_tool_result_messages
from core.llm.transports.sdk.agent_clients import AnthropicAgentClient
from core.llm.types import ToolCall
from core.types import AgentTool
from platform.observability.trace.redaction import redact_sensitive
from tools.investigation.stages.gather_evidence.tools import merge_tool_evidence

# Well-formed JWT (all three segments long enough for the scrubber regex).
_PLANTED_JWT = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
    "eyJzdWIiOiIxMjM0NTY3ODkwIn0."
    "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"
)
_BEARER_LEAK = f"HTTP 403: Invalid bearer {_PLANTED_JWT}"
_OPENAI_KEY_LEAK = "HTTP 401: Invalid API key sk-proj-abcdefghijklmnopqrstuvwxyz0123456789ABCD"
_PASSWORD_LEAK = "connection failed password=SuperSecretPassw0rd host=db.internal"

_XFAIL_REGEX_GAPS = pytest.mark.xfail(
    strict=True,
    reason="error-value scrubber regex allowlist is incomplete",
)
_XFAIL_LLM_PATH = pytest.mark.xfail(
    strict=True,
    reason="execute_tools / provider_content still send raw error strings to the LLM",
)
_XFAIL_EVIDENCE_RAW = pytest.mark.xfail(
    strict=True,
    reason="merge_tool_evidence keeps raw output under evidence[tool_name]",
)


def _echo_tool(payload: dict[str, Any]) -> AgentTool:
    return AgentTool(
        name="leaky_integration",
        description="returns a fixed failure envelope",
        input_schema={
            "type": "object",
            "properties": {"value": {"type": "string"}},
            "required": ["value"],
            "additionalProperties": False,
        },
        execute=lambda _args, _ctx: payload,
        source="test",
    )


def _call() -> ToolCall:
    return ToolCall(id="c1", name="leaky_integration", input={"value": "x"})


def test_redact_sensitive_scrubs_jwt_under_error_key() -> None:
    redacted = redact_sensitive({"success": False, "error": _BEARER_LEAK})
    assert _PLANTED_JWT not in redacted["error"]
    assert "[redacted]" in redacted["error"]


@_XFAIL_REGEX_GAPS
def test_redact_sensitive_scrubs_openai_sk_proj_keys() -> None:
    redacted = redact_sensitive({"error": _OPENAI_KEY_LEAK})
    assert "sk-proj-" not in redacted["error"]


@_XFAIL_REGEX_GAPS
def test_redact_sensitive_scrubs_password_assignments() -> None:
    redacted = redact_sensitive({"error": _PASSWORD_LEAK})
    assert "SuperSecretPassw0rd" not in redacted["error"]


@_XFAIL_REGEX_GAPS
def test_redact_sensitive_scrubs_error_message_key() -> None:
    redacted = redact_sensitive({"error_message": _BEARER_LEAK})
    assert _PLANTED_JWT not in redacted["error_message"]


@_XFAIL_REGEX_GAPS
def test_redact_sensitive_sanitizes_bare_error_strings() -> None:
    assert _PLANTED_JWT not in str(redact_sensitive(_BEARER_LEAK))


@_XFAIL_LLM_PATH
def test_execute_tools_payload_must_not_carry_planted_jwt() -> None:
    payloads = execute_tools(
        [_call()],
        [_echo_tool({"success": False, "error": _BEARER_LEAK})],
        {},
    )
    assert _PLANTED_JWT not in json.dumps(payloads)


@_XFAIL_LLM_PATH
def test_openai_tool_result_messages_must_not_include_planted_jwt() -> None:
    results = execute_tools(
        [_call()],
        [_echo_tool({"success": False, "error": _BEARER_LEAK})],
        {},
    )
    messages = build_tool_result_messages([_call()], results)
    assert _PLANTED_JWT not in json.dumps(messages)


@_XFAIL_LLM_PATH
def test_anthropic_tool_result_message_must_not_include_planted_jwt() -> None:
    results = execute_tools(
        [_call()],
        [_echo_tool({"success": False, "error": _BEARER_LEAK})],
        {},
    )
    message = AnthropicAgentClient.build_tool_result_message([_call()], results)
    assert _PLANTED_JWT not in json.dumps(message)


@_XFAIL_LLM_PATH
def test_provider_content_must_not_be_raw_error_with_secret() -> None:
    result = execute_tool_calls(
        [_call()],
        [_echo_tool({"success": False, "error": _BEARER_LEAK})],
        {},
    )[0]
    assert isinstance(result, ToolExecutionResult)
    assert result.is_error is True
    assert _PLANTED_JWT not in str(result.provider_content())
    assert _PLANTED_JWT not in str(result.content)


def test_merge_tool_evidence_tool_outputs_entry_is_scrubbed() -> None:
    evidence: dict[str, Any] = {}
    output = {"success": False, "error": _BEARER_LEAK}

    merge_tool_evidence(evidence, "leaky_integration", output, {"value": "x"})

    tool_outputs = evidence["tool_outputs"]
    assert isinstance(tool_outputs, list)
    assert _PLANTED_JWT not in tool_outputs[0]["data"]["error"]
    assert "[redacted]" in tool_outputs[0]["data"]["error"]


@_XFAIL_EVIDENCE_RAW
def test_merge_tool_evidence_by_tool_name_must_not_keep_raw_secret() -> None:
    evidence: dict[str, Any] = {}
    output = {"success": False, "error": _BEARER_LEAK}

    merge_tool_evidence(evidence, "leaky_integration", output, {"value": "x"})

    assert _PLANTED_JWT not in json.dumps(evidence["leaky_integration"])


@pytest.mark.parametrize(
    "secret_fragment",
    [_PLANTED_JWT, "sk-proj-", "SuperSecretPassw0rd"],
)
def test_planted_secret_fragments_are_recognisable(secret_fragment: str) -> None:
    blob = " ".join([_BEARER_LEAK, _OPENAI_KEY_LEAK, _PASSWORD_LEAK])
    assert secret_fragment in blob
