import os
from dataclasses import dataclass
from typing import Any

import httpx
from pydantic import BaseModel, Field


class LinearConfig(BaseModel):
    """Normalized Linear connection settings."""

    api_key: str = ""
    default_team_id: str = ""
    timeout_seconds: float = Field(default=15.0, gt=0)


@dataclass(frozen=True)
class LinearValidationResult:
    """Result of validating a Linear integration."""

    ok: bool
    detail: str


def build_linear_config(raw: dict[str, Any] | None) -> LinearConfig:
    """Build a normalized Linear config object from env/store data."""
    return LinearConfig.model_validate(raw or {})


def linear_config_from_env() -> LinearConfig | None:
    """Load a Linear config from env vars."""
    api_key = os.getenv("LINEAR_API_KEY", "").strip()
    if not api_key:
        return None

    return build_linear_config(
        {
            "api_key": api_key,
            "default_team_id": os.getenv("LINEAR_DEFAULT_TEAM_ID", "").strip(),
        }
    )


def linear_graphql_request(
    config: LinearConfig,
    query: str,
    variables: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Make a GraphQL request to the Linear API."""
    url = "https://api.linear.app/graphql"
    headers = {
        "Authorization": config.api_key,
        "Content-Type": "application/json",
    }
    payload: dict[str, Any] = {"query": query}
    if variables:
        payload["variables"] = variables

    response = httpx.post(
        url,
        headers=headers,
        json=payload,
        timeout=config.timeout_seconds,
    )
    response.raise_for_status()
    result: Any = response.json()

    if "errors" in result:
        raise ValueError(f"Linear API error: {result['errors']}")

    data: dict[str, Any] = result.get("data", {})
    return data


def validate_linear_connection(
    *,
    config: LinearConfig,
) -> dict[str, Any]:
    """Validate Linear connection with a lightweight viewer query."""
    query = """
    query {
      viewer {
        id
        name
        email
      }
    }
    """
    return linear_graphql_request(config, query)


def validate_linear_config(config: LinearConfig) -> LinearValidationResult:
    """Validate Linear connectivity."""
    if not config.api_key:
        return LinearValidationResult(ok=False, detail="Linear API key is required.")

    try:
        data = validate_linear_connection(config=config)
        viewer = data.get("viewer", {})
        name = viewer.get("name", "unknown")
        return LinearValidationResult(
            ok=True,
            detail=f"Linear connectivity successful. Authenticated as {name}",
        )
    except httpx.HTTPStatusError as err:
        detail = err.response.text.strip() or str(err)
        return LinearValidationResult(ok=False, detail=f"Linear validation failed: {detail}")
    except Exception as err:
        return LinearValidationResult(ok=False, detail=f"Linear validation failed: {err}")
