from __future__ import annotations

from core.domain.pi_coding import PiCodingProvider, PiCodingResult
from integrations.pi.client import run_pi_coding_task
from integrations.pi.verifier import verify_pi_coding


class _PiCodingAdapter(PiCodingProvider):
    def is_enabled(self) -> bool:
        # Defer import to avoid circular import (adapter is imported by __init__.py).
        from integrations.pi import is_pi_coding_enabled  # noqa: PLC0415

        return is_pi_coding_enabled()

    def verify(self) -> tuple[bool, str]:
        return verify_pi_coding()

    def run_task(
        self,
        task: str,
        *,
        workspace: str,
        model: str | None,
        timeout_sec: float,
    ) -> PiCodingResult:
        return run_pi_coding_task(task, workspace=workspace, model=model, timeout_sec=timeout_sec)
