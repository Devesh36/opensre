"""GitLab provider registry.

Decouples ``tools/investigation/reporting/gitlab_writeback.py`` from direct
imports of ``integrations.gitlab``.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

GitLabWritebackFunc = Callable[..., None]


class GitLabProviderRegistry:
    """Registry for GitLab writeback functions."""

    def __init__(self) -> None:
        self._writeback: GitLabWritebackFunc | None = None

    def register_writeback(self, func: GitLabWritebackFunc) -> None:
        self._writeback = func

    def post_writeback(self, state: dict[str, Any], message: str) -> None:
        if self._writeback is not None:
            self._writeback(state, message)


_REGISTRY: GitLabProviderRegistry | None = None


def get_gitlab_provider_registry() -> GitLabProviderRegistry:
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = GitLabProviderRegistry()
    return _REGISTRY


def reset_gitlab_provider_registry() -> None:
    global _REGISTRY
    _REGISTRY = None
