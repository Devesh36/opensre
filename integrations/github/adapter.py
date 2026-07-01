from __future__ import annotations

from typing import Any

from core.domain.github_provider import GitHubProvider
from integrations.github.client import GitHubApiError, GitHubRestClient, resolve_github_token
from integrations.github.helpers import (
    github_creds,
    github_source_available,
    normalize_github_tool_result,
    resolve_github_mcp_config,
)
from integrations.github.tools.work_status import (
    list_github_work_items,
    summarize_github_pr_status,
)
from integrations.github.tools.workflow.report import build_work_status_report
from integrations.github_mcp import GitHubMCPConfig, call_github_mcp_tool


class GitHubProviderAdapter(GitHubProvider):
    def resolve_token(self, github_token: str | None = None) -> str:
        return resolve_github_token(github_token)

    def extract_creds(self, gh_source: dict[str, Any]) -> dict[str, Any]:
        return github_creds(gh_source)

    def is_source_available(self, sources: dict[str, dict]) -> bool:
        return github_source_available(sources)

    def normalize_tool_result(self, result: dict[str, Any]) -> dict[str, Any]:
        return normalize_github_tool_result(result)

    def resolve_mcp_config(
        self,
        github_url: str | None = None,
        github_mode: str | None = None,
        github_token: str | None = None,
        github_command: str | None = None,
        github_args: list[str] | None = None,
    ) -> GitHubMCPConfig | None:
        return resolve_github_mcp_config(
            github_url, github_mode, github_token, github_command, github_args
        )

    def call_mcp_tool(
        self, config: GitHubMCPConfig, tool_name: str, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        return call_github_mcp_tool(config, tool_name, arguments)

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
        return list_github_work_items(
            owner=owner,
            repo=repo,
            state=state,
            labels=labels,
            include_prs=include_prs,
            per_page=per_page,
            github_token=github_token,
            **kwargs,
        )

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
        return summarize_github_pr_status(
            owner=owner,
            repo=repo,
            state=state,
            per_page=per_page,
            include_checks=include_checks,
            github_token=github_token,
            **kwargs,
        )

    def build_work_status_report(
        self,
        *,
        work_items: Any,
        pull_requests: Any,
        context: str = "today",
        errors: list[str] | None = None,
    ) -> Any:
        return build_work_status_report(
            work_items=work_items,
            pull_requests=pull_requests,
            context=context,
            errors=errors,
        )

    def create_rest_client(self, token: str | None = None) -> GitHubRestClient:
        return GitHubRestClient(token)

    @property
    def api_error_type(self) -> type[Exception]:
        return GitHubApiError


__all__ = ["GitHubProviderAdapter"]
