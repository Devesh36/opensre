from __future__ import annotations

import pytest


@pytest.fixture(autouse=True, scope="session")
def _ensure_cli_providers_registered() -> None:
    """Import integrations.llm_cli so provider registration runs before LLM tests."""
    import integrations.llm_cli  # noqa: F401
