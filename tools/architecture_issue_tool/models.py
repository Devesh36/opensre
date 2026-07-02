"""Typed models for architecture violation scan results."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

ViolationType = Literal[
    "dependency_direction",
    "oversized_file",
    "compatibility_shim",
    "misplaced_module",
]

RefactorPriority = Literal["high", "medium", "low"]


@dataclass(frozen=True)
class ArchitectureViolation:
    type: ViolationType
    file_path: str
    description: str
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RefactorTask:
    title: str
    description: str
    target_file: str
    violation_type: ViolationType
    priority: RefactorPriority
    suggested_labels: tuple[str, ...] = ("refactor", "maintainability")

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["suggested_labels"] = list(self.suggested_labels)
        return payload
