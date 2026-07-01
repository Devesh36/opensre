"""Tests for the GitLab MR write-back helper."""

import os
from unittest.mock import MagicMock, patch

import pytest

from tools.investigation.reporting.gitlab_writeback import (
    _build_mr_note,
    post_gitlab_mr_writeback,
)


@pytest.fixture()
def state_with_gitlab():
    return {
        "available_sources": {
            "gitlab": {
                "merge_request_iid": "42",
                "project_id": "99",
                "gitlab_url": "https://gitlab.example.com",
                "gitlab_token": "glpat-test",
            }
        }
    }


def test_build_mr_note_short_message():
    note = _build_mr_note("Hello world")
    assert "Hello world" in note
    assert "<details>" in note


def test_build_mr_note_truncates_long_message():
    long_msg = "x" * 5000
    note = _build_mr_note(long_msg)
    assert "x" * 3997 + "..." in note
    assert "x" * 3998 not in note


def test_build_mr_note_body_capped_at_4000_chars():
    long_msg = "x" * 5000
    note = _build_mr_note(long_msg)
    body = note.split("<summary>Investigation summary</summary>\n\n")[1].split("\n\n</details>")[0]
    assert len(body) == 4000
    assert body.endswith("...")


def test_no_op_when_env_flag_off(state_with_gitlab):
    mock_registry = MagicMock()
    with (
        patch.dict(os.environ, {"GITLAB_MR_WRITEBACK": "false"}),
        patch(
            "tools.investigation.reporting.gitlab_writeback.get_gitlab_provider_registry",
            return_value=mock_registry,
        ),
    ):
        post_gitlab_mr_writeback(state_with_gitlab, "report")
        mock_registry.post_writeback.assert_not_called()


def test_no_op_when_mr_iid_missing():
    state = {"available_sources": {"gitlab": {"project_id": "99"}}}
    mock_registry = MagicMock()
    with (
        patch.dict(os.environ, {"GITLAB_MR_WRITEBACK": "true"}),
        patch(
            "tools.investigation.reporting.gitlab_writeback.get_gitlab_provider_registry",
            return_value=mock_registry,
        ),
    ):
        post_gitlab_mr_writeback(state, "report")
        mock_registry.post_writeback.assert_not_called()


def test_no_op_when_project_id_missing():
    state = {"available_sources": {"gitlab": {"merge_request_iid": "42"}}}
    mock_registry = MagicMock()
    with (
        patch.dict(os.environ, {"GITLAB_MR_WRITEBACK": "true"}),
        patch(
            "tools.investigation.reporting.gitlab_writeback.get_gitlab_provider_registry",
            return_value=mock_registry,
        ),
    ):
        post_gitlab_mr_writeback(state, "report")
        mock_registry.post_writeback.assert_not_called()


def test_failure_does_not_propagate(state_with_gitlab):
    mock_registry = MagicMock()
    mock_registry.post_writeback.side_effect = RuntimeError("network error")
    with (
        patch.dict(os.environ, {"GITLAB_MR_WRITEBACK": "true"}),
        patch(
            "tools.investigation.reporting.gitlab_writeback.get_gitlab_provider_registry",
            return_value=mock_registry,
        ),
        patch("tools.investigation.reporting.gitlab_writeback.logger") as mock_logger,
    ):
        post_gitlab_mr_writeback(state_with_gitlab, "report")
        mock_logger.warning.assert_called_once()


def test_no_op_when_writeback_provider_missing(state_with_gitlab):
    mock_registry = MagicMock()
    mock_registry.get_writeback.return_value = None
    with (
        patch.dict(os.environ, {"GITLAB_MR_WRITEBACK": "true"}),
        patch(
            "tools.investigation.reporting.gitlab_writeback.get_gitlab_provider_registry",
            return_value=mock_registry,
        ),
        patch("tools.investigation.reporting.gitlab_writeback.logger") as mock_logger,
    ):
        post_gitlab_mr_writeback(state_with_gitlab, "report")
        mock_registry.post_writeback.assert_not_called()
        mock_logger.warning.assert_called_once()


def test_happy_path_calls_post_writeback(state_with_gitlab):
    mock_registry = MagicMock()
    mock_registry.get_writeback.return_value = lambda *_args, **_kwargs: None
    with (
        patch.dict(os.environ, {"GITLAB_MR_WRITEBACK": "true"}),
        patch(
            "tools.investigation.reporting.gitlab_writeback.get_gitlab_provider_registry",
            return_value=mock_registry,
        ),
    ):
        post_gitlab_mr_writeback(state_with_gitlab, "the report")
        mock_registry.post_writeback.assert_called_once()
        args, _ = mock_registry.post_writeback.call_args
        assert "the report" in str(args)
