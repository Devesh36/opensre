"""Unit tests for LinearCreateIssueTool."""

from __future__ import annotations

from unittest.mock import patch

from app.tools.LinearCreateIssueTool import LinearCreateIssueTool


def _tool() -> LinearCreateIssueTool:
    return LinearCreateIssueTool()


def test_is_available_with_api_key() -> None:
    assert _tool().is_available({"linear": {"api_key": "key-123"}}) is True


def test_is_available_false_without_api_key() -> None:
    assert _tool().is_available({"linear": {}}) is False
    assert _tool().is_available({}) is False


@patch("app.tools.LinearCreateIssueTool.linear_graphql_request")
def test_run_creates_issue(mock_gql) -> None:
    mock_gql.return_value = {
        "issueCreate": {
            "success": True,
            "issue": {
                "id": "issue-1",
                "identifier": "ENG-123",
                "url": "https://linear.app/team/issue/ENG-123",
            },
        }
    }

    result = _tool().run(
        api_key="lin-key",
        team_id="team-1",
        title="Incident: API down",
        description="Root cause: DB connection pool exhausted.",
        priority=2,
        labels=["incident", "rca"],
    )
    assert result["available"] is True
    assert result["issue_id"] == "issue-1"
    assert result["issue_identifier"] == "ENG-123"
    assert "linear.app" in result["url"]


@patch("app.tools.LinearCreateIssueTool.linear_graphql_request")
def test_run_returns_error_on_api_failure(mock_gql) -> None:
    mock_gql.return_value = {"issueCreate": {"success": False, "issue": None}}

    result = _tool().run(
        api_key="lin-key",
        team_id="team-1",
        title="Incident: API down",
        description="Root cause: DB connection pool exhausted.",
    )
    assert result["available"] is False
    assert "creation failed" in result["error"]


@patch("app.tools.LinearCreateIssueTool.linear_graphql_request")
def test_run_returns_error_on_exception(mock_gql) -> None:
    mock_gql.side_effect = RuntimeError("Network error")

    result = _tool().run(
        api_key="lin-key",
        team_id="team-1",
        title="Incident: API down",
        description="Root cause: DB connection pool exhausted.",
    )
    assert result["available"] is False
    assert "Network error" in result["error"]


def test_run_returns_unavailable_without_api_key() -> None:
    result = _tool().run(api_key="", team_id="team-1", title="test", description="test")
    assert result["available"] is False
    assert "API key" in result["error"]


def test_run_returns_error_without_team_id() -> None:
    result = _tool().run(api_key="key", team_id="", title="test", description="test")
    assert result["available"] is False
    assert "team_id" in result["error"]


def test_metadata_is_valid() -> None:
    t = _tool()
    assert t.name == "linear_create_issue"
    assert t.source == "linear"
    assert t.description
