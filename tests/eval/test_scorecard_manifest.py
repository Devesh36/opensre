from __future__ import annotations

from pathlib import Path

import yaml

MANIFEST_PATH = Path(__file__).resolve().parent / "manifest.yml"
RDS_SUITE_DIR = Path(__file__).resolve().parents[1] / "synthetic" / "rds_postgres"
HERMES_SUITE_DIR = Path(__file__).resolve().parents[1] / "synthetic" / "hermes_rca"

_SUITE_DIRS = {
    "rds": RDS_SUITE_DIR,
    "hermes_rca": HERMES_SUITE_DIR,
}


def _load_manifest() -> dict[str, object]:
    raw = yaml.safe_load(MANIFEST_PATH.read_text(encoding="utf-8"))
    assert isinstance(raw, dict), "manifest.yml must be a mapping"
    return raw


def _scenario_dir(case_id: str) -> Path:
    prefix, scenario_id = case_id.split("/", 1)
    suite_dir = _SUITE_DIRS.get(prefix)
    assert suite_dir is not None, f"unknown suite prefix in {case_id!r}"
    return suite_dir / scenario_id


def test_manifest_structure() -> None:
    manifest = _load_manifest()
    assert int(manifest.get("version", 0)) >= 1
    assert str(manifest.get("owner", "")).strip()

    for tier in ("smoke_offline", "smoke_live"):
        entries = manifest.get(tier)
        assert isinstance(entries, list), f"{tier} must be a list"
        assert entries, f"{tier} must not be empty"
        for entry in entries:
            assert isinstance(entry, str) and "/" in entry, (
                f"{tier} entries must be suite/scenario ids"
            )


def test_manifest_scenarios_exist() -> None:
    manifest = _load_manifest()
    case_ids = list(manifest.get("smoke_offline") or []) + list(manifest.get("smoke_live") or [])
    for case_id in case_ids:
        scenario_dir = _scenario_dir(str(case_id))
        assert scenario_dir.is_dir(), f"missing scenario directory: {scenario_dir}"
        assert (scenario_dir / "answer.yml").is_file(), f"missing answer.yml for {case_id}"
