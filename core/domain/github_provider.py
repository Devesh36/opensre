from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class GitHubProvider(Protocol):
    def resolve_token(self, github_token: str | None = None) -> str:
        pass

    def extract_creds(self, gh_source: dict[str, Any]) -> dict[str, Any]:
        pass

    def is_source_available(self, sources: dict[str, dict]) -> bool:
        pass

    def normalize_tool_result(self, result: dict[str, Any]) -> dict[str, Any]:
        pass

    def resolve_mcp_config(
        self,
        github_url: str | None = None,
        github_mode: str | None = None,
        github_token: str | None = None,
        github_command: str | None = None,
        github_args: list[str] | None = None,
    ) -> Any | None:
        pass

    def call_mcp_tool(
        self, config: Any, tool_name: str, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        pass

    def create_rest_client(self, token: str | None = None) -> Any:
        pass

    def list_work_items(
        self,
        owner: str,
        repo: str,
        state: str = "open",
        labels: str = "",
        include_prs: bool = False,
        per_page: int = 50,
        github_token: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        pass

    def summarize_pr_status(
        self,
        owner: str,
        repo: str,
        state: str = "open",
        per_page: int = 30,
        include_checks: bool = True,
        github_token: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        pass

    def build_work_status_report(
        self,
        *,
        work_items: Any,
        pull_requests: Any,
        context: str = "today",
        errors: list[str] | None = None,
    ) -> Any:
        pass

    @property
    def api_error_type(self) -> type[Exception]:
        pass


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


def get_github_provider() -> GitHubProvider | None:
    """Return the registered GitHub provider, if any."""
    return get_github_registry().get()


def github_repo_available(sources: dict[str, dict]) -> bool:
    """Whether GitHub repo context is present and the provider can run."""
    provider = get_github_provider()
    if not provider:
        return False
    gh = sources.get("github", {})
    return bool(
        (provider.is_source_available(sources) or provider.resolve_token(None))
        and gh.get("owner")
        and gh.get("repo")
    )


def github_repo_extract_params(sources: dict[str, dict]) -> dict[str, Any]:
    """Extract owner/repo and GitHub creds from investigation sources."""
    provider = get_github_provider()
    gh = sources.get("github", {})
    if not gh or not provider:
        return {}
    return {"owner": gh.get("owner"), "repo": gh.get("repo"), **provider.extract_creds(gh)}
