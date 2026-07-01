from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class GitHubProvider(Protocol):
    def resolve_token(self, github_token: str | None = None) -> str: ...

    def extract_creds(self, gh_source: dict[str, Any]) -> dict[str, Any]: ...

    def is_source_available(self, sources: dict[str, dict]) -> bool: ...

    def normalize_tool_result(self, result: dict[str, Any]) -> dict[str, Any]: ...

    def resolve_mcp_config(
        self,
        github_url: str | None = None,
        github_mode: str | None = None,
        github_token: str | None = None,
        github_command: str | None = None,
        github_args: list[str] | None = None,
    ) -> Any | None: ...

    def call_mcp_tool(
        self, config: Any, tool_name: str, arguments: dict[str, Any]
    ) -> dict[str, Any]: ...

    def create_rest_client(self, token: str | None = None) -> Any: ...

    @property
    def api_error_type(self) -> type[Exception]: ...


class GitHubRegistry:
    def __init__(self) -> None:
        self._provider: GitHubProvider | None = None

    def register(self, provider: GitHubProvider) -> None:
        self._provider = provider

    def get(self) -> GitHubProvider | None:
        return self._provider


_REGISTRY: GitHubRegistry | None = None


def get_github_registry() -> GitHubRegistry:
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = GitHubRegistry()
    return _REGISTRY


def reset_github_registry() -> None:
    global _REGISTRY
    _REGISTRY = None
