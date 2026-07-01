"""Upstream evidence provider factory registry.

Decouples ``tools/investigation/reporting/upstream_correlation/registry.py``
from direct imports of vendor correlation modules.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol, runtime_checkable

if True:
    UpstreamProviderFactory = Callable[..., Any]


class UpstreamProviderRegistry:
    """Thread-safe registry for upstream evidence provider factories."""

    def __init__(self) -> None:
        self._factories: dict[str, UpstreamProviderFactory] = {}

    def register(self, vendor: str, factory: UpstreamProviderFactory) -> None:
        self._factories[vendor] = factory

    def get(self, vendor: str) -> UpstreamProviderFactory | None:
        return self._factories.get(vendor)

    def all_vendors(self) -> tuple[str, ...]:
        return tuple(self._factories.keys())


_REGISTRY: UpstreamProviderRegistry | None = None


def get_upstream_provider_registry() -> UpstreamProviderRegistry:
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = UpstreamProviderRegistry()
    return _REGISTRY


def reset_upstream_provider_registry() -> None:
    global _REGISTRY
    _REGISTRY = None
