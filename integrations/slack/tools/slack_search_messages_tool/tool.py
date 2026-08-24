"""Agent-callable Slack workspace message search."""

from __future__ import annotations

from typing import Any

from core.domain.types.tools import ToolSurface
from core.tool import BaseTool, SideEffectLevel
from core.tool_framework import SUMMARIZE_OBSERVATION_TAG, tool
from core.tool_framework.utils import tool_unavailable
from integrations.slack.tools.slack_read_messages_tool.constants import SOURCE
from integrations.slack.web_client import resolve_bot_token, search_messages


class SlackSearchMessagesTool(BaseTool):
    """Search Slack messages across the workspace."""

    name = "slack_search_messages"
    source = SOURCE
    description = (
        "Search Slack *messages* workspace-wide (search.messages). Slack only allows "
        "this method with a user token (xoxp-…); it rejects bot tokens (xoxb-…) "
        "outright with not_allowed_token_type, regardless of scopes granted. This "
        "integration configures a bot token only, so this tool cannot currently "
        "return results — use slack_read_messages for one known channel/thread or "
        "slack_list_team_members for the workspace roster instead."
    )
    use_cases = [
        "Finding prior discussion of an incident keyword",
        "Locating where a bug was reported in Slack",
    ]
    anti_examples = [
        'Answering "who is on the team?" (use slack_list_team_members)',
        "Reading one known channel's recent history (use slack_read_messages)",
        "Searching without a concrete query",
    ]
    tags = (SUMMARIZE_OBSERVATION_TAG,)
    requires = ["slack"]
    side_effect_level = SideEffectLevel.READ_ONLY
    requires_approval = False
    input_schema = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Slack search query string.",
            },
            "count": {
                "type": "integer",
                "description": "Max matches to return (1-100, default 20).",
            },
        },
        "required": ["query"],
        "additionalProperties": False,
    }
    outputs = {
        "status": "'read' on success, 'failed' otherwise",
        "matches": "list of {channel_id, user, ts, text, permalink}",
        "match_count": "number of matches returned",
        "error": "error detail when status is 'failed'",
        "error_type": "validation_error, configuration_error, or api_error",
    }

    def is_available(self, _sources: dict[str, Any]) -> bool:
        """Always unavailable: search.messages needs a user token this integration never has.

        No bot scope makes ``search.messages`` work — Slack rejects bot tokens for
        this method with ``not_allowed_token_type`` regardless of scopes, and
        ``integrations/slack/setup.py`` only collects a bot token. Advertising this
        as available would offer a capability that fails on every call.
        """
        return False

    def run(self, query: str, count: int = 20, **_kwargs: Any) -> dict[str, Any]:
        target, resolution_error = resolve_bot_token()
        if target is None:
            return tool_unavailable(
                SOURCE,
                resolution_error,
                status="failed",
                error_type="configuration_error",
                matches=[],
                match_count=0,
            )

        matches, error = search_messages(target, query=query, count=count)
        if matches is None:
            return {
                "source": SOURCE,
                "available": True,
                "status": "failed",
                "error": error,
                "error_type": ("validation_error" if "empty" in error else "api_error"),
                "matches": [],
                "match_count": 0,
            }
        return {
            "source": SOURCE,
            "available": True,
            "status": "read",
            "matches": matches,
            "match_count": len(matches),
        }


slack_search_messages = tool(
    SlackSearchMessagesTool(),
    surfaces=(ToolSurface.INVESTIGATION, ToolSurface.CHAT, ToolSurface.ACTION),
)
