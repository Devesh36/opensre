"""Tests for ~/.config/opensre → ~/.opensre home migration (#2504 regression)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from app.constants.home_migration import migrate_opensre_home_from_config


def _write_integrations(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"version": 2, "integrations": [{"id": "g1", "service": "grafana"}]}) + "\n",
        encoding="utf-8",
    )


def test_migrates_entire_config_home_when_opensre_home_missing(tmp_path: Path) -> None:
    legacy = tmp_path / ".config" / "opensre"
    home = tmp_path / ".opensre"
    _write_integrations(legacy / "integrations.json")

    with (
        patch("app.constants.home_migration.CONFIG_OPENSRE_HOME_DIR", legacy),
        patch("app.constants.home_migration.OPENSRE_HOME_DIR", home),
    ):
        migrate_opensre_home_from_config()

    assert home.is_dir()
    assert (home / "integrations.json").exists()
    assert not legacy.exists()


def test_migrates_newer_integrations_when_both_homes_exist(tmp_path: Path) -> None:
    legacy = tmp_path / ".config" / "opensre"
    home = tmp_path / ".opensre"
    home.mkdir(parents=True)
    _write_integrations(home / "integrations.json")
    legacy_integrations = legacy / "integrations.json"
    _write_integrations(legacy_integrations)
    # Ensure legacy file is strictly newer than the home copy.
    legacy_integrations.touch()

    with (
        patch("app.constants.home_migration.CONFIG_OPENSRE_HOME_DIR", legacy),
        patch("app.constants.home_migration.OPENSRE_HOME_DIR", home),
    ):
        migrate_opensre_home_from_config()

    data = json.loads((home / "integrations.json").read_text(encoding="utf-8"))
    assert data["integrations"][0]["id"] == "g1"


def test_skips_migration_when_legacy_config_home_absent(tmp_path: Path) -> None:
    legacy = tmp_path / ".config" / "opensre"
    home = tmp_path / ".opensre"
    home.mkdir()

    with (
        patch("app.constants.home_migration.CONFIG_OPENSRE_HOME_DIR", legacy),
        patch("app.constants.home_migration.OPENSRE_HOME_DIR", home),
    ):
        migrate_opensre_home_from_config()

    assert home.is_dir()
    assert not legacy.exists()
