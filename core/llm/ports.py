"""LLM provider ports — decouple ``core/llm/`` from ``integrations/llm_cli/``.

Vendor CLI packages register their factories and helpers with the global
``CLIProviderRegistry`` so ``core/llm/`` modules can look them up by name
without direct imports of ``integrations.llm_cli``.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol, runtime_checkable


class CLIAdapter(Protocol):
    """Adapter around a vendor CLI (Anthropic Codex, etc.)."""

    def detect(self) -> Any:
        """Probe whether the adapter's CLI is installed and logged in.

        Returns an object with ``installed``, ``logged_in``, and ``detail`` attributes.
        """


class CLIProviderRegistration:
    """Registration payload for one CLI-based LLM provider."""

    def __init__(
        self, name: str, adapter_factory: Callable[[], Any], model_env_key: str = ""
    ) -> None:
        self.name = name
        self.adapter_factory = adapter_factory
        self.model_env_key = model_env_key


class CLIProviderRegistry:
    """Thread-safe registry for CLI-based LLM provider helpers."""

    def __init__(self) -> None:
        self._registrations: dict[str, CLIProviderRegistration] = {}
        self._client_factories: dict[str, Callable[..., Any]] = {}
        self._prompt_flatteners: list[Callable[..., str]] = []
        self._error_classifiers: dict[str, type[Exception]] = {}
        self._env_builders: dict[str, Callable[..., dict[str, str]]] = {}

    def register_provider(self, name: str, registration: CLIProviderRegistration) -> None:
        self._registrations[name] = registration

    def get_provider(self, name: str) -> CLIProviderRegistration | None:
        return self._registrations.get(name)

    def register_client_factory(self, name: str, factory: Callable[..., Any]) -> None:
        self._client_factories[name] = factory

    def get_client_factory(self, name: str) -> Callable[..., Any] | None:
        return self._client_factories.get(name)

    def register_prompt_flattener(self, flattener: Callable[..., str]) -> None:
        self._prompt_flatteners.append(flattener)

    def flatten_messages(self, messages: list[dict[str, Any]]) -> str:
        for flattener in self._prompt_flatteners:
            return flattener(messages)
        return ""

    def register_error_type(self, name: str, exc_type: type[Exception]) -> None:
        self._error_classifiers[name] = exc_type

    def get_error_type(self, name: str) -> type[Exception] | None:
        return self._error_classifiers.get(name)

    def register_adapter_factory(self, name: str, factory: Callable[[], Any]) -> None:
        self._registrations[name] = CLIProviderRegistration(name, factory)

    def register_env_builder(self, name: str, builder: Callable[..., dict[str, str]]) -> None:
        self._env_builders[name] = builder

    def get_env_builder(self, name: str) -> Callable[..., dict[str, str]] | None:
        return self._env_builders.get(name)


_REGISTRY: CLIProviderRegistry | None = None


def get_cli_provider_registry() -> CLIProviderRegistry:
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = CLIProviderRegistry()
    return _REGISTRY


def reset_cli_provider_registry() -> None:
    global _REGISTRY
    _REGISTRY = None
