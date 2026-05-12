"""Unit tests for LinearSearchIssuesTool."""

from __future__ import annotations

from unittest.mock import patch

from app.tools.LinearSearchIssuesTool import LinearSearchIssuesTool


def _tool() -> LinearSearchIssuesTool:
    return LinearSearchIssuesTool()


def test_is_available_with_api_key() -> None:
    assert _tool().is_available({"linear": {"api_key": "key-123"}}) is True


def test_is_available_false_without_api_key() -> None:
    assert _tool().is_available({"linear": {}}) is False
    assert _tool().is_available({}) is False


@patch("app.tools.LinearSearchIssuesTool.linear_graphql_request")
def test_run_returns_issues(mock_gql) -> None:
    mock_gql.return_value = {
        "searchIssues": {
            "nodes": [
                {
                    "id": "issue-1",
                    "identifier": "ENG-123",
                    "title": "API latency spike",
                    "url": "https://linear.app/team/issue/ENG-123",
                    "description": "API latency spike investigation",
                    "priority": 2,
                    "state": {"name": "In Progress", "type": "started"},
                    "createdAt": "2026-01-15T10:00:00Z",
                    "updatedAt": "2026-01-15T12:00:00Z",
                },
                {
                    "id": "issue-2",
                    "identifier": "ENG-456",
                    "title": "DB connection pool issue",
                    "url": "https://linear.app/team/issue/ENG-456",
                    "description": "DB connection pool investigation",
                    "priority": 1,
                    "state": {"name": "Todo", "type": "unstarted"},
                    "createdAt": "2026-01-14T08:00:00Z",
                    "updatedAt": "2026-01-14T09:00:00Z",
                },
            ]
        }
    }

    result = _tool().run(api_key="lin-key", query="API latency")
    assert result["available"] is True
    assert result["total_count"] == 2
    assert len(result["issues"]) == 2
    assert result["issues"][0]["identifier"] == "ENG-123"
    assert result["issues"][0]["state"] == "In Progress"
    assert result["issues"][1]["state_type"] == "unstarted"


@patch("app.tools.LinearSearchIssuesTool.linear_graphql_request")
def test_run_handles_empty_results(mock_gql) -> None:
    mock_gql.return_value = {"searchIssues": {"nodes": []}}

    result = _tool().run(api_key="lin-key", query="nonexistent")
    assert result["available"] is True
    assert result["total_count"] == 0
    assert result["issues"] == []


@patch("app.tools.LinearSearchIssuesTool.linear_graphql_request")
def test_run_handles_api_error(mock_gql) -> None:
    mock_gql.side_effect = RuntimeError("API error")

    result = _tool().run(api_key="lin-key", query="test")
    assert result["available"] is False
    assert "API error" in result["error"]


def test_run_returns_unavailable_without_api_key() -> None:
    result = _tool().run(api_key="", query="test")
    assert result["available"] is False
    assert "API key" in result["error"]


def test_run_returns_error_without_query() -> None:
    result = _tool().run(api_key="key", query="")
    assert result["available"] is False
    assert "query" in result["error"]


def test_metadata_is_valid() -> None:
    t = _tool()
    assert t.name == "linear_search_issues"
    assert t.source == "linear"
    assert t.description
