"""Local telemetry from the tracer-cloud/opensre Hugging Face dataset."""

from __future__ import annotations

from integrations.opensre.constants import OPENSRE_HF_DATASET_ID
from integrations.opensre.csv_grafana_backend import OpenSRECsvGrafanaBackend
from integrations.opensre.hf_remote import (
    extract_scoring_points,
    infer_opensre_telemetry_relative,
    materialize_opensre_telemetry_from_hub,
    stream_opensre_query_alerts,
    strip_scoring_points_from_alert,
)
from integrations.opensre.inject import (
    inject_opensre_into_resolved_integrations,
    resolve_opensre_telemetry_dir,
)
from integrations.opensre.seed_evidence import merge_opensre_seed_into_state

__all__ = (
    "OPENSRE_HF_DATASET_ID",
    "OpenSRECsvGrafanaBackend",
    "extract_scoring_points",
    "infer_opensre_telemetry_relative",
    "inject_opensre_into_resolved_integrations",
    "merge_opensre_seed_into_state",
    "materialize_opensre_telemetry_from_hub",
    "resolve_opensre_telemetry_dir",
    "stream_opensre_query_alerts",
    "strip_scoring_points_from_alert",
)


def _register_with_core() -> None:
    from core.domain.opensre_scoring import get_opensre_scoring_registry

    from integrations.opensre.hf_remote import (
        extract_scoring_points as _extract,
        strip_scoring_points_from_alert as _strip,
    )

    class _Provider:
        def extract_scoring_points(self, alert_payload: dict) -> str:
            return _extract(alert_payload)

        def strip_scoring_points_from_alert(self, alert_payload: dict) -> dict:
            return _strip(alert_payload)

    get_opensre_scoring_registry().register(_Provider())


_register_with_core()
