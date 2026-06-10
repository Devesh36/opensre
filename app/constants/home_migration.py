"""One-time migration from accidental ~/.config/opensre default (#1348)."""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

from app.constants import OPENSRE_HOME_DIR

logger = logging.getLogger(__name__)

# Introduced in fix(analytics): persist unique CLI install IDs (#1348), reverted in #2504.
CONFIG_OPENSRE_HOME_DIR: Path = Path.home() / ".config" / "opensre"

# Top-level files written under OPENSRE_HOME_DIR during the #1348 window.
_TOP_LEVEL_DATA_FILES: tuple[str, ...] = (
    "integrations.json",
    "opensre.json",
    "config.yml",
    "guardrails.yml",
    "guardrail_audit.jsonl",
    "scheduler.db",
    "anonymous_id",
    "installed",
    "prompt_log.jsonl",
    "agents.jsonl",
    "branch_claims.jsonl",
)


def _should_take_legacy_file(home_file: Path, legacy_file: Path) -> bool:
    if not legacy_file.is_file():
        return False
    if not home_file.exists():
        return True
    try:
        return legacy_file.stat().st_mtime > home_file.stat().st_mtime
    except OSError:
        return False


def migrate_opensre_home_from_config() -> None:
    """Restore user data left in ~/.config/opensre after #2504 reverted the home path.

    When ~/.opensre does not exist, the entire legacy directory is moved.
    When both exist, known data files are copied only if missing or older in ~/.opensre.
    """
    legacy = CONFIG_OPENSRE_HOME_DIR
    home = OPENSRE_HOME_DIR
    if not legacy.is_dir():
        return

    if not home.exists():
        try:
            legacy.rename(home)
            logger.info("Migrated OpenSRE home from %s to %s", legacy, home)
        except OSError:
            try:
                shutil.copytree(legacy, home, dirs_exist_ok=False)
                shutil.rmtree(legacy)
                logger.info("Copied OpenSRE home from %s to %s", legacy, home)
            except OSError:
                logger.warning(
                    "Failed to migrate OpenSRE home from %s to %s",
                    legacy,
                    home,
                    exc_info=True,
                )
        return

    for name in _TOP_LEVEL_DATA_FILES:
        legacy_file = legacy / name
        home_file = home / name
        if not _should_take_legacy_file(home_file, legacy_file):
            continue
        try:
            shutil.copy2(legacy_file, home_file)
            logger.info("Migrated %s from %s into %s", name, legacy, home)
        except OSError:
            logger.warning(
                "Failed to migrate %s from %s to %s",
                name,
                legacy,
                home,
                exc_info=True,
            )

    legacy_agents = legacy / "agents"
    home_agents = home / "agents"
    if legacy_agents.is_dir() and not home_agents.exists():
        try:
            shutil.copytree(legacy_agents, home_agents)
            logger.info("Migrated agents/ from %s into %s", legacy, home)
        except OSError:
            logger.warning(
                "Failed to migrate agents/ from %s to %s",
                legacy,
                home,
                exc_info=True,
            )


__all__ = ["CONFIG_OPENSRE_HOME_DIR", "migrate_opensre_home_from_config"]
