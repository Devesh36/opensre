"""Ports for the scheduler layer — decouple ``platform/scheduler/`` from ``tools/``."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class SchedulerInvestigationRunner(Protocol):
    """Runs an investigation for scheduled task report generation."""

    def run(self, alert_payload: dict[str, Any]) -> dict[str, Any] | None:
        """Execute an investigation and return the result state.

        Args:
            alert_payload: The alert / incident payload describing what to investigate.

        Returns:
            The investigation result state (with a ``report`` key), or ``None`` if
            the investigation produced no report.
        """
