"""Pi coding tool configuration defaults.

Extracted from ``integrations.pi`` so the tool package does not import
integration internals for simple config lookups.
"""

from __future__ import annotations

import os


def pi_coding_model() -> str | None:
    return os.environ.get("PI_CODING_MODEL", "").strip() or None


def pi_coding_timeout_seconds() -> int:
    return int(os.getenv("PI_CODING_TIMEOUT_SECONDS", "180"))


def pi_coding_workspace() -> str:
    return os.getenv("PI_CODING_WORKSPACE", "") or os.getcwd()


_TRUTHY = {"1", "true", "yes", "on"}


def is_pi_coding_enabled() -> bool:
    """Whether the Pi coding tool is opted in via ``PI_CODING_ENABLED``."""
    return os.environ.get("PI_CODING_ENABLED", "").strip().lower() in _TRUTHY
