"""Linear issue creation tool for investigation workflows."""

from __future__ import annotations

from typing import Any

from app.integrations.linear import build_linear_config, linear_graphql_request
from app.tools.base import BaseTool


class LinearCreateIssueTool(BaseTool):
    """Create a Linear issue to track an incident discovered during investigation."""

    name = "linear_create_issue"
    source = "linear"
    description = (
        "Create a new Linear issue to file an incident ticket with investigation findings, "
        "including title, description, priority, and labels."
    )
    use_cases = [
        "Filing a new incident ticket after root cause analysis",
        "Creating a bug report from investigation findings",
        "Tracking a production issue discovered during alert investigation",
        "Documenting a new issue with evidence from the investigation",
    ]
    requires = ["api_key", "title", "description"]
    input_schema = {
        "type": "object",
        "properties": {
            "api_key": {
                "type": "string",
                "description": "Linear API key for authentication",
            },
            "team_id": {
                "type": "string",
                "default": "",
                "description": "Linear team ID (e.g. ENG). Uses configured default if empty.",
            },
            "title": {"type": "string", "description": "Issue title"},
            "description": {
                "type": "string",
                "description": "Issue description with investigation findings",
            },
            "priority": {
                "type": "integer",
                "default": 2,
                "description": "Issue priority (0=No priority, 1=Urgent, 2=High, 3=Medium, 4=Low)",
            },
            "labels": {
                "type": "array",
                "items": {"type": "string"},
                "default": [],
                "description": "Labels to attach to the issue",
            },
        },
        "required": ["api_key", "title", "description"],
    }
    outputs = {
        "issue_id": "The ID of the created issue",
        "url": "Direct URL to the created issue",
        "issue_identifier": "Human-readable identifier (e.g. ENG-123)",
    }

    def is_available(self, sources: dict) -> bool:
        return bool(sources.get("linear", {}).get("api_key"))

    def extract_params(self, sources: dict) -> dict[str, Any]:
        linear = sources["linear"]
        return {
            "api_key": linear.get("api_key", ""),
            "team_id": linear.get("default_team_id", ""),
            "title": "",
            "description": "",
            "priority": 2,
            "labels": [],
        }

    def run(
        self,
        api_key: str,
        title: str,
        description: str,
        team_id: str = "",
        priority: int = 2,
        labels: list[str] | None = None,
        **_kwargs: Any,
    ) -> dict[str, Any]:
        config = build_linear_config({"api_key": api_key, "default_team_id": team_id})

        if not config.api_key:
            return {
                "source": "linear",
                "available": False,
                "error": "Linear API key is not configured.",
                "issue_id": "",
                "url": "",
                "issue_identifier": "",
            }

        if not team_id:
            return {
                "source": "linear",
                "available": False,
                "error": "Linear team_id is required.",
                "issue_id": "",
                "url": "",
                "issue_identifier": "",
            }

        if not title.strip():
            return {
                "source": "linear",
                "available": False,
                "error": "Issue title is required.",
                "issue_id": "",
                "url": "",
                "issue_identifier": "",
            }

        mutation = """
        mutation IssueCreate($input: IssueCreateInput!) {
          issueCreate(input: $input) {
            success
            issue {
              id
              identifier
              url
            }
          }
        }
        """
        variables = {
            "input": {
                "teamId": team_id,
                "title": title,
                "description": description,
                "priority": priority,
            }
        }

        if labels:
            variables["input"]["labelIds"] = labels

        try:
            data = linear_graphql_request(config, mutation, variables)
        except Exception as err:
            return {
                "source": "linear",
                "available": False,
                "error": f"Linear API request failed: {err}",
                "issue_id": "",
                "url": "",
                "issue_identifier": "",
            }

        issue_create = data.get("issueCreate", {})
        if not issue_create.get("success"):
            return {
                "source": "linear",
                "available": False,
                "error": "Linear issue creation failed.",
                "issue_id": "",
                "url": "",
                "issue_identifier": "",
            }

        issue = issue_create.get("issue", {})
        return {
            "source": "linear",
            "available": True,
            "issue_id": issue.get("id", ""),
            "issue_identifier": issue.get("identifier", ""),
            "url": issue.get("url", ""),
        }


linear_create_issue = LinearCreateIssueTool()
