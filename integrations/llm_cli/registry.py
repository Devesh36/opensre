"""Registration table for CLI-backed LLM providers (``LLM_PROVIDER`` subprocess path)."""

from __future__ import annotations

from collections.abc import Callable

from config.llm_auth.provider_catalog import require_provider_spec
from core.llm.ports import CLIProviderRegistration, get_cli_provider_registry
from integrations.llm_cli.base import LLMCLIAdapter


def _codex_factory() -> LLMCLIAdapter:
    from integrations.llm_cli.codex import CodexAdapter

    return CodexAdapter()


def _cursor_factory() -> LLMCLIAdapter:
    from integrations.llm_cli.cursor import CursorAdapter

    return CursorAdapter()


def _claude_code_factory() -> LLMCLIAdapter:
    from integrations.llm_cli.claude_code import ClaudeCodeAdapter

    return ClaudeCodeAdapter()


def _gemini_cli_factory() -> LLMCLIAdapter:
    from integrations.llm_cli.gemini_cli import GeminiCLIAdapter

    return GeminiCLIAdapter()


def _antigravity_cli_factory() -> LLMCLIAdapter:
    from integrations.llm_cli.antigravity_cli import AntigravityCLIAdapter

    return AntigravityCLIAdapter()


def _opencode_factory() -> LLMCLIAdapter:
    from integrations.llm_cli.opencode import OpenCodeAdapter

    return OpenCodeAdapter()


def _kimi_factory() -> LLMCLIAdapter:
    from integrations.llm_cli.kimi import KimiAdapter

    return KimiAdapter()


def _copilot_factory() -> LLMCLIAdapter:
    from integrations.llm_cli.copilot import CopilotAdapter

    return CopilotAdapter()


def _grok_cli_factory() -> LLMCLIAdapter:
    from integrations.llm_cli.grok_cli import GrokCLIAdapter

    return GrokCLIAdapter()


def _pi_factory() -> LLMCLIAdapter:
    from integrations.llm_cli.pi_cli import PiAdapter

    return PiAdapter()


def _build_registration(
    name: str, adapter_factory: Callable[[], LLMCLIAdapter], model_env_key: str
) -> CLIProviderRegistration:
    return CLIProviderRegistration(
        name=name,
        adapter_factory=adapter_factory,
        model_env_key=model_env_key,
    )


_CLI_PROVIDER_REGISTRY: dict[str, CLIProviderRegistration] = {
    "codex": _build_registration(
        "codex",
        _codex_factory,
        require_provider_spec("codex").cli_model_env or "CODEX_MODEL",
    ),
    "cursor": _build_registration(
        "cursor",
        _cursor_factory,
        require_provider_spec("cursor").cli_model_env or "CURSOR_MODEL",
    ),
    "claude-code": _build_registration(
        "claude-code",
        _claude_code_factory,
        require_provider_spec("claude-code").cli_model_env or "CLAUDE_CODE_MODEL",
    ),
    "gemini-cli": _build_registration(
        "gemini-cli",
        _gemini_cli_factory,
        require_provider_spec("gemini-cli").cli_model_env or "GEMINI_CLI_MODEL",
    ),
    "antigravity-cli": _build_registration(
        "antigravity-cli",
        _antigravity_cli_factory,
        require_provider_spec("antigravity-cli").cli_model_env or "ANTIGRAVITY_CLI_MODEL",
    ),
    "opencode": _build_registration(
        "opencode",
        _opencode_factory,
        require_provider_spec("opencode").cli_model_env or "OPENCODE_MODEL",
    ),
    "kimi": _build_registration(
        "kimi",
        _kimi_factory,
        require_provider_spec("kimi").cli_model_env or "KIMI_MODEL",
    ),
    "copilot": _build_registration(
        "copilot",
        _copilot_factory,
        require_provider_spec("copilot").cli_model_env or "COPILOT_MODEL",
    ),
    "grok-cli": _build_registration(
        "grok-cli",
        _grok_cli_factory,
        require_provider_spec("grok-cli").cli_model_env or "GROK_CLI_MODEL",
    ),
    "pi": _build_registration(
        "pi",
        _pi_factory,
        require_provider_spec("pi").cli_model_env or "PI_MODEL",
    ),
}


def get_cli_provider_registration(provider: str) -> CLIProviderRegistration | None:
    """Return registration for *provider* if it is a registered CLI-backed LLM."""
    return _CLI_PROVIDER_REGISTRY.get(provider)


def _register_with_core() -> None:
    """Register all CLI providers with the core ports registry."""
    registry = get_cli_provider_registry()
    for name, reg in _CLI_PROVIDER_REGISTRY.items():
        registry.register_provider(name, reg)


_register_with_core()


def _register_cli_probe() -> None:
    try:
        from config.llm_auth._cli_probe import get_cli_probe_registry

        probe_registry = get_cli_probe_registry()
        probe_registry.register("llm_cli", get_cli_provider_registration)
    except Exception:
        # Registration is best-effort; caller handles missing providers.
        pass


_register_cli_probe()
