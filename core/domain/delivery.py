"""Report delivery provider protocol and registry.

Decouples ``tools/investigation/reporting/delivery/`` from direct imports of
``integrations/<vendor>/delivery.py`` modules.  Vendor packages register their
delivery and reaction providers with the global ``DeliveryRegistry``, and the
dispatch module looks them up by channel name at runtime.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class ReportDeliveryProvider(Protocol):
    """Deliver a formatted report to one specific channel type (Slack, Discord, …).

    Any callable with signature ``(message: str, credentials: dict) -> tuple[bool, str]``
    satisfies this protocol structurally.
    """

    def __call__(
        self,
        message: str,
        credentials: dict[str, Any],
    ) -> tuple[bool, str]:
        """Deliver ``message`` to the channel using ``credentials``.

        Returns ``(success, error_detail)``.  ``error_detail`` is empty on success.
        """


@runtime_checkable
class ReactionProvider(Protocol):
    """Add / swap emoji reactions on a Slack (or compatible) message."""

    def add_reaction(
        self,
        emoji: str,
        channel: str,
        timestamp: str,
        token: str,
    ) -> None:
        """Add ``emoji`` to the message identified by ``channel`` + ``timestamp``."""

    def swap_reaction(
        self,
        remove_emoji: str,
        add_emoji: str,
        channel: str,
        timestamp: str,
        token: str,
    ) -> None:
        """Replace ``remove_emoji`` with ``add_emoji`` on the target message."""


class DeliveryRegistry:
    """Thread-safe registry of delivery and reaction providers, keyed by channel name.

    Vendor packages register themselves at import time so the dispatch module
    does not need to import vendor packages directly.
    """

    def __init__(self) -> None:
        self._delivery_providers: dict[str, ReportDeliveryProvider] = {}
        self._reaction_providers: dict[str, ReactionProvider] = {}

    def register_delivery(self, channel: str, provider: ReportDeliveryProvider) -> None:
        self._delivery_providers[channel] = provider

    def register_reaction(self, channel: str, provider: ReactionProvider) -> None:
        self._reaction_providers[channel] = provider

    def get_delivery(self, channel: str) -> ReportDeliveryProvider | None:
        return self._delivery_providers.get(channel)

    def get_all_delivery(self) -> dict[str, ReportDeliveryProvider]:
        return dict(self._delivery_providers)

    def get_reaction(self, channel: str) -> ReactionProvider | None:
        return self._reaction_providers.get(channel)


_REGISTRY: DeliveryRegistry | None = None


def get_delivery_registry() -> DeliveryRegistry:
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = DeliveryRegistry()
    return _REGISTRY


def reset_delivery_registry() -> None:
    global _REGISTRY
    _REGISTRY = None
