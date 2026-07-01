"""Tests for the Pi coding tool: metadata, gating, validators, lifecycle, error_kind."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from core.domain.pi_coding import PiCodingResult, get_pi_coding_registry, reset_pi_coding_registry
from tools.pi_coding_tool import PiCodingTool, pi_coding_task
from tools.pi_coding_tool.errors import PiCodingError
from tools.pi_coding_tool.validation import validate_model, validate_task, validate_workspace


@pytest.fixture(autouse=True)
def _clean_registry() -> None:
    reset_pi_coding_registry()


def _mock_provider() -> MagicMock:
    provider = MagicMock()
    get_pi_coding_registry().register(provider)
    return provider


# --------------------------------------------------------------------------- #
# metadata + availability
# --------------------------------------------------------------------------- #
def test_metadata_is_mutating_on_investigation_surface() -> None:
    t = pi_coding_task
    assert t.name == "pi_coding_task"
    assert t.source == "knowledge"
    assert t.side_effect_level == "mutating"
    assert t.requires_approval is False
    assert t.surfaces == ("investigation",)
    assert t.input_schema["required"] == ["task"]
    assert "error_kind" in t.outputs
    assert t.metadata().name == "pi_coding_task"


def test_is_available_off_by_default_then_opt_in() -> None:
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("PI_CODING_ENABLED", None)
        assert pi_coding_task.is_available({}) is False
    with patch.dict(os.environ, {"PI_CODING_ENABLED": "1"}, clear=False):
        assert pi_coding_task.is_available({}) is True


# --------------------------------------------------------------------------- #
# validators
# --------------------------------------------------------------------------- #
def test_validate_task() -> None:
    assert validate_task("  do it  ") == "do it"
    with pytest.raises(PiCodingError) as empty:
        validate_task("   ")
    assert empty.value.kind == "invalid_input"
    with pytest.raises(PiCodingError) as too_long:
        validate_task("x" * 5000)
    assert too_long.value.kind == "invalid_input"


def test_validate_workspace(tmp_path: Path) -> None:
    assert validate_workspace(str(tmp_path)) == str(tmp_path)
    with pytest.raises(PiCodingError) as missing:
        validate_workspace("/no/such/path/xyz123")
    assert missing.value.kind == "invalid_input"


def test_validate_model() -> None:
    assert validate_model("anthropic/claude-haiku-4-5") == "anthropic/claude-haiku-4-5"
    with pytest.raises(PiCodingError) as bad:
        validate_model("bad model")
    assert bad.value.kind == "invalid_input"
    with patch.dict(os.environ, {"PI_CODING_MODEL": ""}, clear=False):
        assert validate_model("") is None


# --------------------------------------------------------------------------- #
# run() lifecycle + error_kind
# --------------------------------------------------------------------------- #
def test_run_disabled() -> None:
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("PI_CODING_ENABLED", None)
        out = pi_coding_task.run(task="do something")
    assert out["success"] is False
    assert out["error_kind"] == "disabled"


def test_run_invalid_task() -> None:
    with patch.dict(os.environ, {"PI_CODING_ENABLED": "1"}, clear=False):
        out = pi_coding_task.run(task="   ")
    assert out["success"] is False
    assert out["error_kind"] == "invalid_input"


def test_run_cli_unavailable(tmp_path: Path) -> None:
    provider = _mock_provider()
    provider.verify.return_value = (False, "pi not installed")
    with patch.dict(os.environ, {"PI_CODING_ENABLED": "1"}, clear=False):
        out = pi_coding_task.run(task="fix it", workspace=str(tmp_path))
    assert out["success"] is False
    assert out["error_kind"] == "cli_unavailable"


def test_run_success(tmp_path: Path) -> None:
    provider = _mock_provider()
    provider.verify.return_value = (True, "ok")
    provider.run_task.return_value = PiCodingResult(
        success=True,
        summary="edited foo.py",
        changed_files=["foo.py"],
        diff="diff --git a/foo.py b/foo.py\n",
        returncode=0,
    )
    with patch.dict(os.environ, {"PI_CODING_ENABLED": "1"}, clear=False):
        out = pi_coding_task.run(
            task="fix it", workspace=str(tmp_path), model="groq/llama-3.1-8b-instant"
        )
    assert out["success"] is True
    assert out["error_kind"] is None
    assert out["changed_files"] == ["foo.py"]
    assert "diff --git" in out["diff"]
    kwargs = provider.run_task.call_args.kwargs
    assert kwargs["workspace"] == str(tmp_path)
    assert kwargs["model"] == "groq/llama-3.1-8b-instant"


def test_run_error_kinds(tmp_path: Path) -> None:
    provider = _mock_provider()
    provider.verify.return_value = (True, "ok")

    provider.run_task.return_value = PiCodingResult(
        success=False, summary="", error="pi timed out", timed_out=True
    )
    with patch.dict(os.environ, {"PI_CODING_ENABLED": "1"}, clear=False):
        out = pi_coding_task.run(task="fix it", workspace=str(tmp_path))
    assert out["error_kind"] == "timeout"

    provider.run_task.return_value = PiCodingResult(
        success=False, summary="", error="model not found"
    )
    with patch.dict(os.environ, {"PI_CODING_ENABLED": "1"}, clear=False):
        out = pi_coding_task.run(task="fix it", workspace=str(tmp_path))
    assert out["error_kind"] == "execution_error"


def test_run_unexpected_exception_returns_error_dict(tmp_path: Path) -> None:
    provider = _mock_provider()
    provider.verify.side_effect = RuntimeError("boom")
    with patch.dict(os.environ, {"PI_CODING_ENABLED": "1"}, clear=False):
        out = pi_coding_task(task="fix it", workspace=str(tmp_path))
    assert "error" in out


# --------------------------------------------------------------------------- #
# registry discovery
# --------------------------------------------------------------------------- #
def test_registry_discovers_pi_coding_on_investigation_surface() -> None:
    from tools.registry import get_registered_tool_map

    investigation = get_registered_tool_map("investigation")
    chat = get_registered_tool_map("chat")
    assert "pi_coding_task" in investigation
    assert "pi_coding_task" not in chat
    rt = investigation["pi_coding_task"]
    assert rt.requires_approval is False
    assert rt.side_effect_level == "mutating"


def test_tool_subclass_constructs() -> None:
    assert isinstance(pi_coding_task, PiCodingTool)
