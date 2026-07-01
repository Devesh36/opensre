"""GitHub integration package."""

from __future__ import annotations

from typing import Any

from integrations.github.client import GitHubApiError, GitHubRestClient, resolve_github_token

__all__ = ["GitHubApiError", "GitHubRestClient", "resolve_github_token"]


def _register_with_core() -> None:
    from core.domain.github_provider import get_github_registry
    from integrations.github.client import GitHubApiError as _GitHubApiError
    from integrations.github.client import GitHubRestClient as _GitHubRestClient
    from integrations.github.client import resolve_github_token as _resolve_github_token
    from integrations.github.helpers import github_creds as _github_creds
    from integrations.github.helpers import github_source_available as _github_source_available
    from integrations.github.helpers import (
        normalize_github_tool_result as _normalize_github_tool_result,
    )
    from integrations.github.helpers import resolve_github_mcp_config as _resolve_github_mcp_config
    from integrations.github.tools.work_status import (
        list_github_work_items as _list_github_work_items,
    )
    from integrations.github.tools.work_status import (
        summarize_github_pr_status as _summarize_github_pr_status,
    )
    from integrations.github.tools.workflow.report import (
        build_work_status_report as _build_work_status_report,
    )
    from integrations.github_mcp import call_github_mcp_tool as _call_github_mcp_tool

    class _GitHubProvider:
        def resolve_token(self, github_token: str | None = None) -> str:
            return _resolve_github_token(github_token)

        def extract_creds(self, gh_source: dict) -> dict:
            return _github_creds(gh_source)

        def is_source_available(self, sources: dict) -> bool:
            return _github_source_available(sources)

        def normalize_tool_result(self, result: dict) -> dict:
            return _normalize_github_tool_result(result)

        def resolve_mcp_config(
            self,
            github_url: str | None = None,
            github_mode: str | None = None,
            github_token: str | None = None,
            github_command: str | None = None,
            github_args: list[str] | None = None,
        ) -> object | None:
            return _resolve_github_mcp_config(
                github_url, github_mode, github_token, github_command, github_args
            )

        def call_mcp_tool(self, config: object, tool_name: str, arguments: dict) -> dict:
            return _call_github_mcp_tool(config, tool_name, arguments)

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
            return _list_github_work_items(
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
            return _summarize_github_pr_status(
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
            return _build_work_status_report(
                work_items=work_items,
                pull_requests=pull_requests,
                context=context,
                errors=errors,
            )

        def create_rest_client(self, token: str | None = None) -> object:
            return _GitHubRestClient(token)

        @property
        def api_error_type(self) -> type[Exception]:
            return _GitHubApiError

    get_github_registry().register(_GitHubProvider())


_register_with_core()
