"""When Hermes tools may run: catalog connection, fixture backend, or local log."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from config.constants.hermes import HERMES_LOG_PATH_ENV

_DEFAULT_LOG_RELATIVE: tuple[str, ...] = (".hermes", "logs", "errors.log")


def hermes_available_or_backend(sources: dict[str, dict]) -> bool:
    """Available when Hermes integration is connected or a fixture backend is injected."""
    hermes = sources.get("hermes", {})
    return bool(hermes.get("connection_verified") or hermes.get("_backend"))


def default_hermes_log_path() -> Path:
    """Resolve ``$HERMES_LOG_PATH`` or ``~/.hermes/logs/errors.log``."""
    override = os.environ.get(HERMES_LOG_PATH_ENV, "").strip()
    if override:
        return Path(override).expanduser()
    return Path.home().joinpath(*_DEFAULT_LOG_RELATIVE)


def attach_hermes_log_source(
    resolved: dict[str, Any],
    *,
    alert_source: str,
) -> dict[str, Any]:
    """Add Hermes when this is a Hermes alert with a configured local log.

    Leaves an existing ``hermes`` entry unchanged. Does not attach on other
    alert sources even if the default log file exists.
    """
    attached = dict(resolved)
    if "hermes" in attached or alert_source.strip().lower() != "hermes":
        return attached
    override = os.environ.get(HERMES_LOG_PATH_ENV, "").strip()
    path = default_hermes_log_path()
    if not override and not path.is_file():
        return attached
    attached["hermes"] = {"log_path": str(path), "connection_verified": True}
    return attached
