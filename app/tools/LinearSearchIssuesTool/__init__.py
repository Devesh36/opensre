"""Linear issue search tool for investigation workflows."""

from __future__ import annotations

from typing import Any

from app.integrations.linear import build_linear_config, linear_graphql_request
from app.tools.base import BaseTool


class LinearSearchIssuesTool(BaseTool):
    """Search Linear issues during investigation."""

    name = "linear_search_issues"
    source = "linear"
    description = (
        "Search for Linear issues matching a query string to find existing incident tickets, "
        "bug reports, or task items related to the current investigation."
    )
    use_cases = [
        "Finding existing incident tickets related to an alert",
        "Checking if a bug report already exists for a known issue",
        "Looking up prior investigation context from closed Linear issues",
        "Searching for known deployment or release tracking issues",
    ]
    requires = ["api_key", "query"]
    input_schema = {
        "type": "object",
        "properties": {
            "api_key": {
                "type": "string",
                "description": "Linear API key for authentication",
            },
            "query": {
                "type": "string",
                "description": "Search query to find issues by title, description, or identifier",
            },
            "first": {
                "type": "integer",
                "default": 10,
                "description": "Maximum number of results to return",
            },
        },
        "required": ["api_key", "query"],
    }
    outputs = {
        "issues": "List of matching issues with id, identifier, title, url, and state",
        "total_count": "Total number of matching results",
    }

    def is_available(self, sources: dict) -> bool:
        return bool(sources.get("linear", {}).get("api_key"))

    def extract_params(self, sources: dict) -> dict[str, Any]:
        linear = sources["linear"]
        return {
            "api_key": linear.get("api_key", ""),
            "query": "",
            "first": 10,
        }

    def run(
        self,
        api_key: str,
        query: str,
        first: int = 10,
        **_kwargs: Any,
    ) -> dict[str, Any]:
        config = build_linear_config({"api_key": api_key})

        if not config.api_key:
            return {
                "source": "linear",
                "available": False,
                "error": "Linear API key is not configured.",
                "issues": [],
                "total_count": 0,
            }

        if not query.strip():
            return {
                "source": "linear",
                "available": False,
                "error": "Search query is required.",
                "issues": [],
                "total_count": 0,
            }

        gql_query = """
        query SearchIssues($term: String!, $first: Int) {
          searchIssues(term: $term, first: $first) {
            nodes {
              id
              identifier
              title
              url
              description
              priority
              state {
                name
                type
              }
              createdAt
              updatedAt
            }
          }
        }
        """
        variables = {
            "term": query,
            "first": max(1, min(first, 50)),
        }

        try:
            data = linear_graphql_request(config, gql_query, variables)
        except Exception as err:
            return {
                "source": "linear",
                "available": False,
                "error": f"Linear API request failed: {err}",
                "issues": [],
                "total_count": 0,
            }

        issues_data = data.get("searchIssues", {})
        nodes = issues_data.get("nodes", [])

        issues = []
        for node in nodes:
            state = node.get("state") or {}
            issues.append(
                {
                    "id": node.get("id", ""),
                    "identifier": node.get("identifier", ""),
                    "title": node.get("title", ""),
                    "url": node.get("url", ""),
                    "description": node.get("description", ""),
                    "priority": node.get("priority", 0),
                    "state": state.get("name", "Unknown"),
                    "state_type": state.get("type", ""),
                    "created_at": node.get("createdAt", ""),
                    "updated_at": node.get("updatedAt", ""),
                }
            )

        return {
            "source": "linear",
            "available": True,
            "issues": issues,
            "total_count": len(issues),
        }


linear_search_issues = LinearSearchIssuesTool()
