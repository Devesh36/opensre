"""Community and contributor follow-up summary tool."""

from __future__ import annotations

from typing import Any

from core.domain.github_provider import (
    get_github_provider,
    github_repo_available,
    github_repo_extract_params,
)
from core.tool_framework.tool_decorator import tool


@tool(
    name="summarize_community_followups",
    source="github",
    description="Summarize unanswered community questions, meeting agenda items, and suggested replies from GitHub issue comments.",
    use_cases=[
        "Finding unanswered contributor questions in GitHub issue comments",
        "Preparing community meeting agenda follow-ups",
        "Drafting suggested replies without mutating GitHub or messaging platforms",
    ],
    anti_examples=["Posting replies", "Changing GitHub labels or assignees"],
    surfaces=("investigation", "chat"),
    side_effect_level="read_only",
    input_schema={
        "type": "object",
        "properties": {
            "owner": {"type": "string"},
            "repo": {"type": "string"},
            "comments": {"type": "array"},
            "maintainer_logins": {"type": "array", "items": {"type": "string"}},
            "per_page": {"type": "integer"},
            "github_token": {"type": "string"},
        },
        "required": [],
    },
    is_available=github_repo_available,
    extract_params=github_repo_extract_params,
)
def summarize_community_followups(
    owner: str = "",
    repo: str = "",
    comments: list[dict[str, Any]] | None = None,
    maintainer_logins: list[str] | None = None,
    per_page: int = 100,
    github_token: str | None = None,
    **_kwargs: Any,
) -> dict[str, Any]:
    from integrations.github.tools.workflow import summarize_community_followups_from_comments

    provider = get_github_provider()
    if not provider:
        return {
            "source": "github",
            "available": False,
            "error": "GitHub provider is not configured.",
            "unanswered_questions": [],
            "agenda_items": [],
            "suggested_replies": [],
            "side_effects": [],
        }

    try:
        rest_client = provider.create_rest_client(github_token)
        normalized_comments = (
            comments
            if comments is not None
            else rest_client.paginate(
                f"/repos/{owner}/{repo}/issues/comments",
                params={"per_page": max(1, min(per_page, 100))},
            )
        )
    except provider.api_error_type as exc:
        return {
            "source": "github",
            "available": False,
            "error": str(exc),
            "unanswered_questions": [],
            "agenda_items": [],
            "suggested_replies": [],
            "side_effects": [],
        }

    summary = summarize_community_followups_from_comments(
        comments=normalized_comments,
        maintainer_logins=maintainer_logins,
    )
    return {"source": "github", "available": True, **summary}
