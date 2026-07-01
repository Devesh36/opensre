"""Scoring points provider registry.

Decouples ``tools/investigation/state_factory.py`` from direct imports of
``integrations.opensre.hf_remote``.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

ScoringPointsExtractor = Callable[[dict[str, Any]], list[dict[str, Any]]]
ScoringPointsStripper = Callable[[dict[str, Any]], dict[str, Any]]


class ScoringPointsRegistry:
    """Registry for scoring points extraction helpers."""

    def __init__(self) -> None:
        self._extractor: ScoringPointsExtractor | None = None
        self._stripper: ScoringPointsStripper | None = None

    def register_extractor(self, func: ScoringPointsExtractor) -> None:
        self._extractor = func

    def register_stripper(self, func: ScoringPointsStripper) -> None:
        self._stripper = func

    def extract(self, raw_alert: dict[str, Any]) -> list[dict[str, Any]]:
        if self._extractor is not None:
            return self._extractor(raw_alert)
        return []

    def strip(self, raw_alert: dict[str, Any]) -> dict[str, Any]:
        if self._stripper is not None:
            return self._stripper(raw_alert)
        return raw_alert


_REGISTRY: ScoringPointsRegistry | None = None


def get_scoring_points_registry() -> ScoringPointsRegistry:
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = ScoringPointsRegistry()
    return _REGISTRY


def reset_scoring_points_registry() -> None:
    global _REGISTRY
    _REGISTRY = None
