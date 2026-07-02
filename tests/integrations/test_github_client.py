"""Tests for the GitHub REST integration client."""

from __future__ import annotations

import json
from email.message import Message
from typing import Any
from urllib import error, request

import pytest

from integrations.github.client import (
    GitHubApiError,
    GitHubRestClient,
    resolve_github_token,
    resolve_github_token_from_integration_store,
)


class _Response:
    def __init__(
        self, payload: Any, *, status: int = 200, headers: dict[str, str] | None = None
    ) -> None:
        self._payload = payload
        self.status = status
        self.headers = headers or {}

    def __enter__(self) -> _Response:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")


class _RawResponse(_Response):
    def __init__(self, payload: str, *, headers: dict[str, str] | None = None) -> None:
        super().__init__({}, headers=headers)
        self._raw_payload = payload

    def read(self) -> bytes:
        return self._raw_payload.encode("utf-8")


def test_resolve_github_token_prefers_explicit_then_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "env-token")
    monkeypatch.setattr(
        "integrations.github.client.resolve_github_token_from_integration_store",
        lambda: "store-token",
    )
    assert resolve_github_token("explicit") == "explicit"
    assert resolve_github_token(None) == "env-token"


def test_resolve_github_token_falls_back_to_integration_store(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GH_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_MCP_AUTH_TOKEN", raising=False)
    monkeypatch.setattr(
        "integrations.github.client.resolve_github_token_from_integration_store",
        lambda: "store-token",
    )
    assert resolve_github_token(None) == "store-token"


def test_resolve_github_token_from_integration_store_reads_saved_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from integrations import github_mcp as github_mcp_module

    monkeypatch.setattr(
        "integrations.store.get_integration",
        lambda service: (
            {
                "credentials": {
                    "mode": "streamable-http",
                    "url": github_mcp_module.DEFAULT_GITHUB_MCP_URL,
                    "auth_token": "gho_saved",
                }
            }
            if service == "github"
            else None
        ),
    )
    monkeypatch.setattr(github_mcp_module, "github_mcp_config_from_env", lambda: None)

    assert resolve_github_token_from_integration_store() == "gho_saved"


def test_resolve_github_token_from_integration_store_ignores_invalid_store(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "integrations.store.get_integration",
        lambda service: (
            {
                "credentials": {
                    "mode": "streamable-http",
                    "url": "https://example.com",
                    "auth_token": "x",
                }
            }
            if service == "github"
            else None
        ),
    )

    def _raise(_credentials: dict[str, object]) -> None:
        raise ValueError("invalid credentials")

    monkeypatch.setattr("integrations.github_mcp.build_github_mcp_config", _raise)
    monkeypatch.setattr("integrations.github_mcp.github_mcp_config_from_env", lambda: None)

    assert resolve_github_token_from_integration_store() == ""


def test_missing_token_raises_typed_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GH_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_MCP_AUTH_TOKEN", raising=False)
    monkeypatch.setattr(
        "integrations.github.client.resolve_github_token_from_integration_store",
        lambda: "",
    )
    client = GitHubRestClient(github_token=None)

    with pytest.raises(GitHubApiError) as exc:
        client.request("GET", "/repos/o/r/issues")

    assert exc.value.status_code is None
    assert "GitHub token is required" in str(exc.value)


def test_paginate_follows_link_header(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    def fake_urlopen(req: request.Request, timeout: int = 0) -> _Response:  # noqa: ARG001
        url = req.full_url
        calls.append(url)
        if "page=2" in url:
            return _Response([{"number": 2}], headers={})
        return _Response(
            [{"number": 1}],
            headers={"Link": '<https://api.github.com/repos/o/r/issues?page=2>; rel="next"'},
        )

    monkeypatch.setattr("integrations.github.client.request.urlopen", fake_urlopen)
    client = GitHubRestClient(github_token="tok")

    assert client.paginate("/repos/o/r/issues") == [{"number": 1}, {"number": 2}]
    assert len(calls) == 2


def test_http_error_preserves_status_and_rate_limit_headers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_urlopen(_req: request.Request, timeout: int = 0) -> _Response:  # noqa: ARG001
        headers = Message()
        headers["X-RateLimit-Remaining"] = "0"
        headers["X-RateLimit-Reset"] = "123"
        raise error.HTTPError(
            url="https://api.github.com/repos/o/r/issues",
            code=403,
            msg="rate limited",
            hdrs=headers,
            fp=None,
        )

    monkeypatch.setattr("integrations.github.client.request.urlopen", fake_urlopen)
    client = GitHubRestClient(github_token="tok")

    with pytest.raises(GitHubApiError) as exc:
        client.request("GET", "/repos/o/r/issues")

    assert exc.value.status_code == 403
    assert exc.value.rate_limit_remaining == "0"
    assert exc.value.rate_limit_reset == "123"


def test_invalid_json_raises_typed_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_urlopen(_req: request.Request, timeout: int = 0) -> _RawResponse:  # noqa: ARG001
        return _RawResponse("not-json")

    monkeypatch.setattr("integrations.github.client.request.urlopen", fake_urlopen)
    client = GitHubRestClient(github_token="tok")

    with pytest.raises(GitHubApiError) as exc:
        client.request("GET", "/repos/o/r/issues")

    assert "invalid JSON" in str(exc.value)
