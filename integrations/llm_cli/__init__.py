"""Subprocess-backed LLM providers (Codex CLI, future Gemini/Claude CLIs)."""

from __future__ import annotations

from integrations.llm_cli.base import CLIInvocation, CLIProbe, LLMCLIAdapter
from integrations.llm_cli.errors import CLIAuthenticationRequired
from integrations.llm_cli.runner import CLIBackedLLMClient

__all__ = ["CLIAuthenticationRequired", "CLIInvocation", "CLIProbe", "CLIBackedLLMClient"]


def _register_with_core() -> None:
    from core.llm.ports import get_cli_provider_registry

    registry = get_cli_provider_registry()

    def _client_factory(
        adapter: LLMCLIAdapter,
        *,
        model: str | None = None,
        max_tokens: int = 1024,
        model_type: str = "reasoning",
    ) -> CLIBackedLLMClient:
        return CLIBackedLLMClient(
            adapter, model=model, max_tokens=max_tokens, model_type=model_type
        )

    registry.register_client_factory("CLIBackedLLMClient", _client_factory)

    def _flattener(messages: list[dict]) -> str:
        from integrations.llm_cli.text import flatten_messages_to_prompt

        return flatten_messages_to_prompt(messages)

    registry.register_prompt_flattener(_flattener)

    from integrations.llm_cli.claude_code import ClaudeCodeAdapter as _ClaudeCodeAdapter
    from integrations.llm_cli.subprocess_env import build_cli_subprocess_env as _build_env

    registry.register_adapter_factory("claude_code", _ClaudeCodeAdapter)
    registry.register_env_builder("claude_code", _build_env)


_register_with_core()
