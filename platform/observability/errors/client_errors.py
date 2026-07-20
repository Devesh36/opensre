"""Safe error envelopes for integration service clients.

Investigation tool payloads and LLM context consume client ``error`` strings.
Those surfaces must not receive ``str(exc)``, response bodies, or other
exception detail (CWE-209). Full detail is logged server-side via
``capture_service_error``.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from platform.observability.errors.service import capture_service_error


def safe_integration_error_message(exc: BaseException) -> str:
    """Return a safe, investigation-facing error string."""
    if isinstance(exc, httpx.HTTPStatusError):
        return f"HTTP {exc.response.status_code}"
    return type(exc).__name__


def integration_client_error_result(
    exc: BaseException,
    *,
    integration: str,
    method: str,
    logger: logging.Logger,
    extras: dict[str, Any] | None = None,
    **fields: Any,
) -> dict[str, Any]:
    """Log the failure and return a sanitized ``success: False`` envelope."""
    capture_service_error(
        exc,
        logger=logger,
        integration=integration,
        method=method,
        extras=extras,
    )
    # Unpack fields first so a caller-supplied error= cannot replace the
    # sanitized message (CWE-209).
    return {"success": False, **fields, "error": safe_integration_error_message(exc)}


__all__ = [
    "integration_client_error_result",
    "safe_integration_error_message",
]
