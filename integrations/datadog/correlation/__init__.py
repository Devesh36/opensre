from __future__ import annotations

from integrations.datadog.correlation.adapter import DatadogCorrelationAdapter
from integrations.datadog.correlation.factory import (
    build_datadog_provider,
    datadog_avg_query,
)
from integrations.datadog.correlation.provider import (
    DatadogCorrelationQueries,
    DatadogUpstreamEvidenceProvider,
)

__all__ = [
    "DatadogCorrelationAdapter",
    "DatadogCorrelationQueries",
    "DatadogUpstreamEvidenceProvider",
    "build_datadog_provider",
    "datadog_avg_query",
]


def _register_upstream_provider() -> None:
    from core.domain.registry_utils import register_best_effort
    from core.domain.upstream import get_upstream_provider_registry

    register_best_effort(
        "upstream.datadog",
        lambda: get_upstream_provider_registry().register("datadog", build_datadog_provider),
    )


_register_upstream_provider()
