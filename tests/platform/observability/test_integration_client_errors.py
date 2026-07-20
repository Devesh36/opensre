from __future__ import annotations

import logging
from unittest.mock import patch

import httpx
import pytest

from platform.observability.errors.client_errors import (
    integration_client_error_result,
    safe_integration_error_message,
)


def test_http_status_error_returns_status_only() -> None:
    request = httpx.Request("GET", "https://api.example.com/logs")
    response = httpx.Response(
        403,
        request=request,
        text="Invalid key dd_api_key=LEAKED_SECRET",
    )
    exc = httpx.HTTPStatusError("forbidden", request=request, response=response)

    message = safe_integration_error_message(exc)

    assert message == "HTTP 403"
    assert "LEAKED_SECRET" not in message
    assert "Invalid key" not in message


def test_generic_exception_returns_type_name_only() -> None:
    message = safe_integration_error_message(RuntimeError("db-host:5432 connection refused"))

    assert message == "RuntimeError"
    assert "5432" not in message


def test_integration_client_error_result_logs_and_returns_safe_envelope() -> None:
    logger = logging.getLogger("test.integration_client_errors")
    exc = RuntimeError("sensitive detail")

    with patch("platform.observability.errors.client_errors.capture_service_error") as mock_capture:
        result = integration_client_error_result(
            exc,
            integration="datadog",
            method="search_logs",
            logger=logger,
            extras={"query": "status:error"},
            duration_ms=123,
        )

    mock_capture.assert_called_once_with(
        exc,
        logger=logger,
        integration="datadog",
        method="search_logs",
        extras={"query": "status:error"},
    )
    assert result == {
        "success": False,
        "error": "RuntimeError",
        "duration_ms": 123,
    }


def test_integration_client_error_result_ignores_caller_error_override() -> None:
    logger = logging.getLogger("test.integration_client_errors")
    exc = RuntimeError("sensitive detail")

    with patch("platform.observability.errors.client_errors.capture_service_error"):
        result = integration_client_error_result(
            exc,
            integration="datadog",
            method="search_logs",
            logger=logger,
            error="HTTP 500: secret=LEAKED",
        )

    assert result["error"] == "RuntimeError"
    assert "LEAKED" not in result["error"]


@pytest.mark.parametrize(
    ("exc", "expected"),
    [
        (httpx.ConnectError("connection refused"), "ConnectError"),
        (httpx.TimeoutException("timed out"), "TimeoutException"),
        (ValueError("bad query"), "ValueError"),
    ],
)
def test_safe_message_for_common_exception_types(
    exc: BaseException,
    expected: str,
) -> None:
    assert safe_integration_error_message(exc) == expected
