"""Credential/environment resolution for the Python execution tool."""

from __future__ import annotations

from typing import Any

GITHUB_TOKEN_ENV = "GITHUB_TOKEN"


def github_extract_params(sources: dict[str, dict]) -> dict[str, Any]:
    """Extract GitHub credentials from resolved integration sources."""
    from core.domain.github_provider import get_github_provider

    provider = get_github_provider()
    gh = sources.get("github", {})
    token = provider.extract_creds(gh).get("github_token") if gh and provider else None
    return {"github_token": token} if token else {}


def execution_env(*, github_token: str | None = None) -> tuple[dict[str, str], list[str]]:
    """Return approved env vars for generated Python code plus credential labels."""
    from core.domain.github_provider import get_github_provider

    env: dict[str, str] = {}
    available: list[str] = []

    provider = get_github_provider()
    token = provider.resolve_token(github_token) if provider else github_token
    if token:
        env[GITHUB_TOKEN_ENV] = token
        available.append("github")

    return env, available


__all__ = ["GITHUB_TOKEN_ENV", "execution_env", "github_extract_params"]
