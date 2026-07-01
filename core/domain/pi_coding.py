from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class PiCodingResult:
    success: bool
    summary: str
    changed_files: list[str] = field(default_factory=list)
    diff: str = ""
    returncode: int = 0
    timed_out: bool = False
    error: str | None = None
    diff_truncated: bool = False


@runtime_checkable
class PiCodingProvider(Protocol):
    def is_enabled(self) -> bool: ...

    def verify(self) -> tuple[bool, str]: ...

    def run_task(
        self,
        task: str,
        *,
        workspace: str,
        model: str | None,
        timeout_sec: float,
    ) -> PiCodingResult: ...


class PiCodingRegistry:
    def __init__(self) -> None:
        self._provider: PiCodingProvider | None = None

    def register(self, provider: PiCodingProvider) -> None:
        self._provider = provider

    def get(self) -> PiCodingProvider | None:
        return self._provider


_REGISTRY: PiCodingRegistry | None = None


def get_pi_coding_registry() -> PiCodingRegistry:
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = PiCodingRegistry()
    return _REGISTRY


def reset_pi_coding_registry() -> None:
    global _REGISTRY
    _REGISTRY = None
