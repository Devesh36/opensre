from __future__ import annotations

from integrations.github.client import GitHubApiError, GitHubRestClient, resolve_github_token

__all__ = ["GitHubApiError", "GitHubRestClient", "resolve_github_token"]


def _register_with_core() -> None:
    from core.domain.github_provider import get_github_registry
    from core.domain.registry_utils import register_best_effort
    from integrations.github.adapter import GitHubProviderAdapter

    register_best_effort(
        "github",
        lambda: get_github_registry().register(GitHubProviderAdapter()),
    )


_register_with_core()
