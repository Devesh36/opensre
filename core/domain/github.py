"""GitHub credential and helper provider registry.

Decouples tools that need GitHub credentials / helpers from direct imports of
``integrations.github.*`` modules.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

GitHubCredsResolver = Callable[[dict[str, Any]], dict[str, str]]
GitHubTokenResolver = Callable[[], str]
GitHubAvailabilityCheck = Callable[[dict[str, Any]], bool]


class GitHubProviderRegistry:
    """Registry for GitHub credential and helper providers."""

    def __init__(self) -> None:
        self._creds_resolver: GitHubCredsResolver | None = None
        self._token_resolver: GitHubTokenResolver | None = None
        self._availability_check: GitHubAvailabilityCheck | None = None

    def register_creds_resolver(self, resolver: GitHubCredsResolver) -> None:
        self._creds_resolver = resolver

    def register_token_resolver(self, resolver: GitHubTokenResolver) -> None:
        self._token_resolver = resolver

    def register_availability_check(self, check: GitHubAvailabilityCheck) -> None:
        self._availability_check = check

    def resolve_creds(self, sources: dict[str, Any]) -> dict[str, str]:
        if self._creds_resolver is not None:
            return self._creds_resolver(sources)
        return {}

    def resolve_token(self) -> str:
        if self._token_resolver is not None:
            return self._token_resolver()
        return ""

    def is_available(self, sources: dict[str, Any]) -> bool:
        if self._availability_check is not None:
            return self._availability_check(sources)
        return False


_REGISTRY: GitHubProviderRegistry | None = None


def get_github_provider_registry() -> GitHubProviderRegistry:
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = GitHubProviderRegistry()
    return _REGISTRY


def reset_github_provider_registry() -> None:
    global _REGISTRY
    _REGISTRY = None
