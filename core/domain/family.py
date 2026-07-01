"""Family-key resolution for integration service families.

Decouples ``tools/`` from ``integrations/registry.py`` by routing
``family_key()`` through a simple callable registry.
"""

from __future__ import annotations

from collections.abc import Callable

FamilyKeyFunc = Callable[[str], str]

_registry: dict[str, FamilyKeyFunc] = {}


def register_family_key(provider: FamilyKeyFunc) -> None:
    _registry["default"] = provider


def family_key(service_key: str) -> str:
    provider = _registry.get("default")
    if provider is None:
        return service_key
    return provider(service_key)
