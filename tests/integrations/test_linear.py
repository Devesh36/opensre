"""Unit tests for the Linear integration module."""

from unittest.mock import patch

import httpx

from app.integrations.linear import (
    LinearConfig,
    LinearValidationResult,
    build_linear_config,
    linear_config_from_env,
    linear_graphql_request,
    validate_linear_config,
)


class TestLinearConfig:
    """Tests for LinearConfig model."""

    def test_defaults(self) -> None:
        config = LinearConfig(api_key="lin-api-key")
        assert config.api_key == "lin-api-key"
        assert config.default_team_id == ""
        assert config.timeout_seconds == 15.0

    def test_with_team_id(self) -> None:
        config = LinearConfig(api_key="key", default_team_id="team-1")
        assert config.default_team_id == "team-1"

    def test_empty_api_key(self) -> None:
        config = LinearConfig()
        assert config.api_key == ""


class TestBuildLinearConfig:
    """Tests for build_linear_config helper."""

    def test_from_dict(self) -> None:
        config = build_linear_config({"api_key": "lin-key", "default_team_id": "team-abc"})
        assert config.api_key == "lin-key"
        assert config.default_team_id == "team-abc"

    def test_from_none(self) -> None:
        config = build_linear_config(None)
        assert config.api_key == ""
        assert config.default_team_id == ""


class TestLinearConfigFromEnv:
    """Tests for linear_config_from_env helper."""

    def test_returns_none_without_api_key(self) -> None:
        import os

        old = os.environ.get("LINEAR_API_KEY")
        os.environ.pop("LINEAR_API_KEY", None)
        try:
            result = linear_config_from_env()
            assert result is None
        finally:
            if old is not None:
                os.environ["LINEAR_API_KEY"] = old

    def test_returns_config_with_api_key(self) -> None:
        import os

        os.environ["LINEAR_API_KEY"] = "lin-api-key-123"
        os.environ["LINEAR_DEFAULT_TEAM_ID"] = "team-xyz"
        try:
            config = linear_config_from_env()
            assert config is not None
            assert config.api_key == "lin-api-key-123"
            assert config.default_team_id == "team-xyz"
        finally:
            for key in ["LINEAR_API_KEY", "LINEAR_DEFAULT_TEAM_ID"]:
                os.environ.pop(key, None)


class TestLinearValidationResult:
    """Tests for LinearValidationResult dataclass."""

    def test_ok_result(self) -> None:
        result = LinearValidationResult(ok=True, detail="Connected.")
        assert result.ok is True

    def test_error_result(self) -> None:
        result = LinearValidationResult(ok=False, detail="Auth failed.")
        assert result.ok is False


class TestValidateLinearConfig:
    """Tests for validate_linear_config."""

    def test_fails_without_api_key(self) -> None:
        config = LinearConfig()
        result = validate_linear_config(config)
        assert result.ok is False
        assert "API key" in result.detail

    @patch("app.integrations.linear.linear_graphql_request")
    def test_passes_with_valid_key(self, mock_request) -> None:
        mock_request.return_value = {
            "viewer": {"id": "user-1", "name": "Test User", "email": "t@t.com"}
        }
        config = LinearConfig(api_key="valid-key")
        result = validate_linear_config(config)
        assert result.ok is True
        assert "Test User" in result.detail

    @patch("app.integrations.linear.linear_graphql_request")
    def test_fails_on_http_error(self, mock_request) -> None:
        mock_request.side_effect = httpx.HTTPStatusError(
            "401 Unauthorized",
            request=httpx.Request("POST", "https://api.linear.app/graphql"),
            response=httpx.Response(401),
        )
        config = LinearConfig(api_key="bad-key")
        result = validate_linear_config(config)
        assert result.ok is False
        assert "validation failed" in result.detail.lower()

    @patch("app.integrations.linear.linear_graphql_request")
    def test_fails_on_generic_error(self, mock_request) -> None:
        mock_request.side_effect = RuntimeError("Connection refused")
        config = LinearConfig(api_key="bad-key")
        result = validate_linear_config(config)
        assert result.ok is False


class TestLinearGraphQLRequest:
    """Tests for linear_graphql_request."""

    @patch("app.integrations.linear.httpx.post")
    def test_successful_request(self, mock_post) -> None:
        mock_response = mock_post.return_value
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {"data": {"viewer": {"id": "u1"}}}

        config = LinearConfig(api_key="key")
        result = linear_graphql_request(config, "query { viewer { id } }")

        assert result == {"viewer": {"id": "u1"}}
        mock_post.assert_called_once()

    @patch("app.integrations.linear.httpx.post")
    def test_handles_graphql_errors(self, mock_post) -> None:
        mock_response = mock_post.return_value
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {"errors": [{"message": "Invalid API key"}]}

        import pytest

        config = LinearConfig(api_key="bad-key")
        with pytest.raises(ValueError, match="Linear API error"):
            linear_graphql_request(config, "query { viewer { id } }")
