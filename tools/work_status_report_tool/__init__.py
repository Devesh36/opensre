"""Slack-ready engineering work status report tool."""

from __future__ import annotations

from typing import Any

from core.tool_framework.tool_decorator import tool


def _report_available(sources: dict[str, dict]) -> bool:
    from core.domain.github_provider import get_github_registry

    provider = get_github_registry().get()
    if not provider:
        return False
    gh = sources.get("github", {})
    return bool(
        (provider.is_source_available(sources) or provider.resolve_token(None))
        and gh.get("owner")
        and gh.get("repo")
    )


def _report_extract_params(sources: dict[str, dict]) -> dict[str, Any]:
    from core.domain.github_provider import get_github_registry

    provider = get_github_registry().get()
    gh = sources.get("github", {})
    if not gh or not provider:
        return {}
    return {"owner": gh.get("owner"), "repo": gh.get("repo"), **provider.extract_creds(gh)}


@tool(
    name="generate_work_status_report",
    source="github",
    description="Generate a Slack-ready engineering status report from GitHub work items and PR status without mutating state.",
    use_cases=[
        "Answering what is left to do today",
        "Drafting morning check-ins with open work, owners, blockers, and next actions",
        "Summarizing GitHub work status for Slack without changing GitHub",
    ],
    anti_examples=["Creating or updating tasks", "Posting to Slack directly"],
    surfaces=("investigation", "chat"),
    side_effect_level="read_only",
    input_schema={
        "type": "object",
        "properties": {
            "owner": {"type": "string"},
            "repo": {"type": "string"},
            "context": {"type": "string"},
            "work_items": {"type": "array"},
            "pull_requests": {"type": "array"},
            "github_token": {"type": "string"},
        },
        "required": [],
    },
    is_available=_report_available,
    extract_params=_report_extract_params,
)
def generate_work_status_report(
    owner: str = "",
    repo: str = "",
    context: str = "today",
    work_items: list[dict[str, Any]] | None = None,
    pull_requests: list[dict[str, Any]] | None = None,
    github_token: str | None = None,
    **_kwargs: Any,
) -> dict[str, Any]:
    from core.domain.github_provider import get_github_registry

    from integrations.github.tools.work_status import (
        list_github_work_items,
        summarize_github_pr_status,
    )
    from integrations.github.tools.workflow import build_work_status_report

    provider = get_github_registry().get()
    token = provider.resolve_token(github_token) if provider else github_token

    errors: list[str] = []
    if work_items is None and owner and repo:
        work_result = list_github_work_items(owner=owner, repo=repo, github_token=token)
        if not work_result.get("available", False):
            errors.append(f"work_items: {work_result.get('error', 'unavailable')}")
        work_items = list(work_result.get("items", []))
    if pull_requests is None and owner and repo:
        pr_result = summarize_github_pr_status(owner=owner, repo=repo, github_token=token)
        if not pr_result.get("available", False):
            errors.append(f"pull_requests: {pr_result.get('error', 'unavailable')}")
        pull_requests = list(pr_result.get("pull_requests", []))
    report = build_work_status_report(
        work_items=work_items or [],
        pull_requests=pull_requests or [],
        context=context,
        errors=errors,
    )
    return {"source": "github", **report.to_dict()}
