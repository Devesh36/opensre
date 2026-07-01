"""Config-local CLI provider probe — decouples ``config/`` from ``integrations/``.

The ``integrations.llm_cli.registry`` package registers its probe function here
at import time so ``config.llm_auth.credentials`` can check whether a CLI
adapter is available without a direct import of the integrations package.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

CLIProbeFunc = Callable[[str], Any | None]


class CLIProbeRegistry:
    """Registry for CLI provider probe functions."""

    def __init__(self) -> None:
        self._probes: dict[str, CLIProbeFunc] = {}

    def register(self, provider: str, probe: CLIProbeFunc) -> None:
        self._probes[provider] = probe

    def get(self, provider: str) -> CLIProbeFunc | None:
        return self._probes.get(provider)


_REGISTRY: CLIProbeRegistry | None = None


def get_cli_probe_registry() -> CLIProbeRegistry:
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = CLIProbeRegistry()
    return _REGISTRY


def reset_cli_probe_registry() -> None:
    global _REGISTRY
    _REGISTRY = None
