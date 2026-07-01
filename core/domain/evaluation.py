"""Evaluation provider registry.

Decouples ``tools/investigation/reporting/evaluation.py`` from direct imports
of vendor LLM judge modules.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

EvaluationProviderFunc = Callable[..., dict[str, Any]]


class EvaluationRegistry:
    """Thread-safe registry for LLM evaluation providers."""

    def __init__(self) -> None:
        self._providers: dict[str, EvaluationProviderFunc] = {}

    def register(self, name: str, provider: EvaluationProviderFunc) -> None:
        self._providers[name] = provider

    def get(self, name: str) -> EvaluationProviderFunc | None:
        return self._providers.get(name)

    def all(self) -> dict[str, EvaluationProviderFunc]:
        return dict(self._providers)


_REGISTRY: EvaluationRegistry | None = None


def get_evaluation_registry() -> EvaluationRegistry:
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = EvaluationRegistry()
    return _REGISTRY


def reset_evaluation_registry() -> None:
    global _REGISTRY
    _REGISTRY = None
