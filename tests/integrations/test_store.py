"""Tests for the integrations credential store."""

from __future__ import annotations

import json
import os
import stat
from collections.abc import Iterator
from pathlib import Path
from unittest.mock import patch

import pytest

from integrations import store
from integrations.store import (
    _save,
    clear_integrations_cache,
    load_integrations,
    upsert_integration,
)


@pytest.fixture(autouse=True)
def _clear_store_cache() -> Iterator[None]:
    clear_integrations_cache()
    yield
    clear_integrations_cache()


def _assert_private_permissions(store_file: Path) -> None:
    mode = stat.S_IMODE(store_file.stat().st_mode)
    if os.name == "nt":
        # Windows file access is governed by ACLs; chmod-style mode bits are not portable here.
        assert mode & stat.S_IWRITE
        return
    assert mode == 0o600, f"Expected 0o600, got 0o{mode:o}"


class TestSavePermissions:
    def test_saved_file_has_0o600_permissions(self, tmp_path: Path) -> None:
        store_file = tmp_path / "integrations.json"
        data = {"mariadb": {"host": "db.example.com", "database": "prod"}}

        with patch("integrations.store.STORE_PATH", store_file):
            _save(data)

        _assert_private_permissions(store_file)

    def test_saved_file_content_is_valid_json(self, tmp_path: Path) -> None:
        store_file = tmp_path / "integrations.json"
        data = {"mariadb": {"host": "db.example.com"}}

        with patch("integrations.store.STORE_PATH", store_file):
            _save(data)

        content = json.loads(store_file.read_text())
        assert content == data

    def test_save_creates_parent_directories(self, tmp_path: Path) -> None:
        nested = tmp_path / "a" / "b" / "integrations.json"

        with patch("integrations.store.STORE_PATH", nested):
            _save({"key": "value"})

        assert nested.exists()

    def test_save_overwrites_existing_file_with_correct_permissions(self, tmp_path: Path) -> None:
        store_file = tmp_path / "integrations.json"
        store_file.write_text("{}")
        store_file.chmod(0o644)

        with patch("integrations.store.STORE_PATH", store_file):
            _save({"updated": True})

        _assert_private_permissions(store_file)
        assert json.loads(store_file.read_text())["updated"] is True


class TestLoadIntegrationsCache:
    def test_repeated_loads_hit_disk_once(self, tmp_path: Path) -> None:
        store_file = tmp_path / "integrations.json"
        payload = {
            "version": 2,
            "integrations": [
                {"id": "gh-1", "service": "github", "status": "active", "instances": []}
            ],
        }
        store_file.write_text(json.dumps(payload))

        with (
            patch("integrations.store.STORE_PATH", store_file),
            patch(
                "integrations.store._read_raw_unlocked",
                wraps=store._read_raw_unlocked,
            ) as read_raw,
        ):
            for _ in range(10):
                records = load_integrations()
            assert len(records) == 1
            assert records[0]["service"] == "github"
            assert read_raw.call_count == 1

    def test_save_refreshes_cache(self, tmp_path: Path) -> None:
        store_file = tmp_path / "integrations.json"
        store_file.write_text(json.dumps({"version": 2, "integrations": []}))

        with (
            patch("integrations.store.STORE_PATH", store_file),
            patch(
                "integrations.store._read_raw_unlocked",
                wraps=store._read_raw_unlocked,
            ) as read_raw,
        ):
            load_integrations()
            upsert_integration("gitlab", {"credentials": {"token": "glpat-test"}})
            records = load_integrations()
            assert any(record.get("service") == "gitlab" for record in records)
            assert read_raw.call_count == 2

    def test_cache_records_are_isolated_from_caller_mutation(self, tmp_path: Path) -> None:
        """Top-level record mutation by one caller must not leak into later loads."""
        store_file = tmp_path / "integrations.json"
        payload = {
            "version": 2,
            "integrations": [
                {"id": "gh-1", "service": "github", "status": "active", "instances": []}
            ],
        }
        store_file.write_text(json.dumps(payload))

        with patch("integrations.store.STORE_PATH", store_file):
            first = load_integrations()
            first[0]["status"] = "mutated"
            second = load_integrations()
            assert second[0]["status"] == "active"

    def test_stale_data_not_cached_when_file_changes_mid_read(self, tmp_path: Path) -> None:
        """A concurrent overwrite during the disk read must not poison the cache.

        The cache key is the mtime snapshotted *before* the read, so data read
        alongside a mid-read overwrite is stored under the old key and the next
        load re-reads fresh state instead of serving the stale snapshot.
        """
        store_file = tmp_path / "integrations.json"
        old_payload = {
            "version": 2,
            "integrations": [
                {"id": "old-1", "service": "old", "status": "active", "instances": []}
            ],
        }
        new_payload = {
            "version": 2,
            "integrations": [
                {"id": "new-1", "service": "new", "status": "active", "instances": []}
            ],
        }
        store_file.write_text(json.dumps(old_payload))

        original_read = store._read_raw_unlocked
        overwritten = False

        def read_then_overwrite() -> tuple[dict[str, object], bool]:
            nonlocal overwritten
            data = original_read()
            if not overwritten:
                overwritten = True
                store_file.write_text(json.dumps(new_payload))
                # Force a different mtime even on coarse-timestamp filesystems.
                stat_result = store_file.stat()
                os.utime(store_file, ns=(stat_result.st_atime_ns, stat_result.st_mtime_ns + 1))
            return data

        with (
            patch("integrations.store.STORE_PATH", store_file),
            patch("integrations.store._read_raw_unlocked", side_effect=read_then_overwrite),
        ):
            first = load_integrations()
            assert first[0]["service"] == "old"
            # The overwrite advanced the mtime past the cached snapshot, so
            # this load must miss the cache and see the new content.
            second = load_integrations()
            assert second[0]["service"] == "new"
