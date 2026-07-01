from __future__ import annotations

from typing import Any

from core.domain.types.upstream import (
    UpstreamEvidenceProvider,
)
from core.domain.upstream import get_upstream_provider_registry


def target_resource_from_state(state: dict[str, Any]) -> str:
    """Pull the correlation target resource (e.g. RDS DB identifier) from a raw alert.

    Vendor-neutral: any correlation source that needs an alert target
    reads from the same keys. Defaults to ``"unknown-rds"`` when no
    relevant field is present.
    """
    raw_alert = state.get("raw_alert") or {}
    if not isinstance(raw_alert, dict):
        return "unknown-rds"
    return str(
        raw_alert.get("resource")
        or raw_alert.get("resource_name")
        or raw_alert.get("db_instance")
        or raw_alert.get("db_instance_identifier")
        or "unknown-rds"
    )


def candidate_services_from_state(state: dict[str, Any]) -> tuple[str, ...]:
    """Pull upstream-service candidate names from a raw alert.

    Accepts a comma-separated string or a list/tuple under one of
    ``upstream_services`` / ``candidate_services`` / ``related_services``.
    Empty tuple when nothing relevant is present. Vendor-neutral.
    """
    raw_alert = state.get("raw_alert") or {}
    if not isinstance(raw_alert, dict):
        return ()

    raw_candidates = (
        raw_alert.get("upstream_services")
        or raw_alert.get("candidate_services")
        or raw_alert.get("related_services")
    )
    if isinstance(raw_candidates, str):
        return tuple(item.strip() for item in raw_candidates.split(",") if item.strip())
    if isinstance(raw_candidates, list | tuple):
        return tuple(str(item).strip() for item in raw_candidates if str(item).strip())
    return ()


def build_upstream_evidence_provider(state: dict[str, Any]) -> UpstreamEvidenceProvider | None:
    """Vendor-agnostic factory: pick a correlation provider for ``state``."""
    resolved = state.get("resolved_integrations") or {}
    if not isinstance(resolved, dict):
        return None
    target_resource = target_resource_from_state(state)
    candidate_services = candidate_services_from_state(state)

    registry = get_upstream_provider_registry()
    for vendor in registry.all_vendors():
        factory = registry.get(vendor)
        if factory is None:
            continue
        vendor_config = resolved.get(vendor)
        if vendor == "datadog":
            provider: UpstreamEvidenceProvider | None = factory(
                datadog_config=vendor_config if isinstance(vendor_config, dict) else None,
                target_resource=target_resource,
                candidate_services=candidate_services,
            )
            if provider is not None:
                return provider

    return None
