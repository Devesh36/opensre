from __future__ import annotations

import pytest


@pytest.fixture(autouse=True, scope="session")
def _ensure_cli_providers_registered() -> None:
    """Import the LLM CLI integration module so its providers register with
    the core ports registry before any tests that need CLI-backed providers run.

    Once the CLI entrypoint triggers these registrations at startup this fixture
    can be removed — but until then tests that exercise CLI provider routing
    need the side effects of importing the integration package.
    """
    import integrations.llm_cli  # noqa: F401
    import integrations.llm_cli.registry  # noqa: F401
