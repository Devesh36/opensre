"""Discord button approval gate for write tools."""

from __future__ import annotations

import json
import logging
from collections.abc import Mapping
from typing import Any

import discord

from core.execution import BeforeToolCallResult, ToolExecutionHooks, ToolExecutionRequest
from gateway.discord.client import edit_message, send_message_with_components
from gateway.slack.approvals import APPROVE_ACTION_ID, DENY_ACTION_ID, ApprovalBroker

logger = logging.getLogger("gateway")

_MAX_APPROVAL_WAIT_SECONDS = 180.0
_ARGS_PREVIEW_LIMIT = 400


class DiscordApprovalPrompter:
    """Posts Approve/Deny buttons in-channel and waits for an authorized click."""

    def __init__(
        self,
        *,
        broker: ApprovalBroker,
        bot_token: str,
        channel_id: str,
        allowed_user_ids: list[str],
        allow_open_guild: bool,
    ) -> None:
        self._broker = broker
        self._bot_token = bot_token
        self._channel_id = channel_id
        self._allowed_user_ids = allowed_user_ids
        self._allow_open_guild = allow_open_guild

    def request(
        self,
        *,
        tool_name: str,
        reason: str,
        arguments: Mapping[str, Any],
        expiry_seconds: float,
    ) -> tuple[bool, str]:
        approval_id = self._broker.create()
        preview = _arguments_preview(arguments)
        body = f"**Approval needed — `{tool_name}`**"
        if reason.strip():
            body += f"\n{reason.strip()}"
        if preview:
            body += f"\n```\n{preview}\n```"
        components = _approval_components(approval_id)
        message_id = send_message_with_components(
            channel_id=self._channel_id,
            content=body[:2000],
            components=components,
            bot_token=self._bot_token,
        )
        if message_id is None:
            logger.warning(
                "[discord-gateway] approval prompt post failed tool=%s channel=%s",
                tool_name,
                self._channel_id,
            )
            return (False, "")
        timeout = min(float(expiry_seconds), _MAX_APPROVAL_WAIT_SECONDS)
        approved, decided_by = self._broker.wait(approval_id, timeout=timeout)
        outcome = _outcome_text(tool_name, approved=approved, decided_by=decided_by)
        edit_message(
            channel_id=self._channel_id,
            message_id=message_id,
            content=outcome,
            bot_token=self._bot_token,
        )
        return (approved, decided_by)


def approval_tool_hooks(prompter: DiscordApprovalPrompter) -> ToolExecutionHooks:
    def before_tool_call(request: ToolExecutionRequest) -> BeforeToolCallResult | None:
        tool = request.tool
        if not bool(getattr(tool, "requires_approval", False)):
            return None
        approved, decided_by = prompter.request(
            tool_name=request.tool_call.name,
            reason=str(getattr(tool, "approval_reason", "") or ""),
            arguments=request.arguments,
            expiry_seconds=float(getattr(tool, "approval_expiry_seconds", 300)),
        )
        if approved:
            return BeforeToolCallResult(approved=True)
        who = f"<@{decided_by}>" if decided_by else "nobody (request expired)"
        return BeforeToolCallResult(
            blocked=True,
            reason=(
                f"The user denied approval for {request.tool_call.name} "
                f"(decision by {who}). Do not retry; tell the user what you "
                "wanted to do and why."
            ),
        )

    return ToolExecutionHooks(before_tool_call=before_tool_call)


def handle_component_interaction(
    interaction: discord.Interaction,
    *,
    broker: ApprovalBroker,
    allowed_user_ids: list[str],
    allow_open_guild: bool,
) -> bool:
    data = interaction.data
    if not isinstance(data, dict):
        return False
    custom_id = str(data.get("custom_id") or "")
    if custom_id.startswith(f"{APPROVE_ACTION_ID}:"):
        approval_id = custom_id[len(APPROVE_ACTION_ID) + 1 :]
        approved = True
    elif custom_id.startswith(f"{DENY_ACTION_ID}:"):
        approval_id = custom_id[len(DENY_ACTION_ID) + 1 :]
        approved = False
    else:
        return False
    user_id = str(interaction.user.id)
    if allowed_user_ids and user_id not in allowed_user_ids:
        logger.info("[discord-gateway] approval click from unauthorized user=%s ignored", user_id)
        return False
    if not allowed_user_ids and not allow_open_guild:
        return False
    return broker.resolve(approval_id, approved=approved, decided_by=user_id)


def _approval_components(approval_id: str) -> list[dict[str, Any]]:
    return [
        {
            "type": 1,
            "components": [
                {
                    "type": 2,
                    "style": 3,
                    "label": "Approve",
                    "custom_id": f"{APPROVE_ACTION_ID}:{approval_id}",
                },
                {
                    "type": 2,
                    "style": 4,
                    "label": "Deny",
                    "custom_id": f"{DENY_ACTION_ID}:{approval_id}",
                },
            ],
        }
    ]


def _arguments_preview(arguments: Mapping[str, Any]) -> str:
    if not arguments:
        return ""
    try:
        preview = json.dumps(dict(arguments), ensure_ascii=False, default=str)
    except Exception:
        preview = str(dict(arguments))
    if len(preview) > _ARGS_PREVIEW_LIMIT:
        preview = preview[: _ARGS_PREVIEW_LIMIT - 1] + "…"
    return preview


def _outcome_text(tool_name: str, *, approved: bool, decided_by: str) -> str:
    if approved:
        return f"✅ `{tool_name}` approved by <@{decided_by}>"
    if decided_by:
        return f"🚫 `{tool_name}` denied by <@{decided_by}>"
    return f"⏱ Approval request for `{tool_name}` expired — action skipped."


__all__ = [
    "DiscordApprovalPrompter",
    "approval_tool_hooks",
    "handle_component_interaction",
]
