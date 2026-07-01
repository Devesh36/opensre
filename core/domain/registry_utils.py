"""Shared helpers for best-effort provider registration at import time."""

from __future__ import annotations

import logging
from collections.abc import Callable

logger = logging.getLogger(__name__)


def register_best_effort(label: str, registrar: Callable[[], None]) -> None:
    """Run *registrar* once; log and continue when registration fails."""
    try:
        registrar()
    except Exception as exc:
        logger.warning("[%s] provider registration failed: %s", label, exc)


__all__ = ["register_best_effort"]
