from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class OpenSreScoringProvider(Protocol):
    def extract_scoring_points(self, alert_payload: dict[str, Any]) -> str: ...

    def strip_scoring_points_from_alert(self, alert_payload: dict[str, Any]) -> dict[str, Any]: ...


class OpenSreScoringRegistry:
    def __init__(self) -> None:
        self._provider: OpenSreScoringProvider | None = None

    def register(self, provider: OpenSreScoringProvider) -> None:
        self._provider = provider

    def get(self) -> OpenSreScoringProvider | None:
        return self._provider


_REGISTRY: OpenSreScoringRegistry | None = None


def get_opensre_scoring_registry() -> OpenSreScoringRegistry:
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = OpenSreScoringRegistry()
    return _REGISTRY


def reset_opensre_scoring_registry() -> None:
    global _REGISTRY
    _REGISTRY = None
