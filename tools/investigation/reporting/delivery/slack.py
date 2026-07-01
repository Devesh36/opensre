"""Slack delivery policy for publish findings."""

from __future__ import annotations

import logging
from typing import Any

from core.context.state import InvestigationState

logger = logging.getLogger(__name__)


def build_action_blocks(
    investigation_url: str, investigation_id: str | None = None
) -> list[dict[str, Any]]:
    """Build Slack Block Kit action blocks with interactive buttons."""
    feedback_options = [
        {
            "text": {"type": "plain_text", "text": "\U0001f44d Accurate"},
            "value": f"accurate|{investigation_id or ''}",
        },
        {
            "text": {"type": "plain_text", "text": "\U0001f914 Partially accurate"},
            "value": f"partial|{investigation_id or ''}",
        },
        {
            "text": {"type": "plain_text", "text": "\U0001f44e Inaccurate"},
            "value": f"inaccurate|{investigation_id or ''}",
        },
    ]
    elements: list[dict[str, Any]] = [
        {
            "type": "button",
            "text": {"type": "plain_text", "text": "View Details in Tracer"},
            "url": investigation_url,
            "style": "primary",
            "action_id": "view_investigation",
        },
        {
            "type": "static_select",
            "placeholder": {"type": "plain_text", "text": "\U0001f4dd Give Feedback"},
            "action_id": "give_feedback",
            "options": feedback_options,
        },
    ]
    return [{"type": "actions", "elements": elements}]


def _slack_delivery_registry() -> tuple[Any, Any] | None:
    """Look up the Slack delivery and reaction providers from the registry."""
    from core.domain.delivery import get_delivery_registry

    registry = get_delivery_registry()
    delivery = registry.get_delivery("slack")
    reaction = registry.get_reaction("slack")
    if delivery is None:
        return None
    return delivery, reaction


def deliver_slack_report(
    state: InvestigationState,
    message: str,
    blocks: list[dict],
) -> None:
    """Deliver a Slack report and preserve the threaded fail-closed behavior."""
    slack_ctx = state.get("slack_context", {}) or {}
    thread_ts = slack_ctx.get("thread_ts") or slack_ctx.get("ts")
    channel = slack_ctx.get("channel_id")
    token = slack_ctx.get("access_token")
    alert_ts = slack_ctx.get("ts") or slack_ctx.get("thread_ts")

    providers = _slack_delivery_registry()
    if providers is None:
        logger.warning("[publish] Slack delivery: no provider registered")
        return
    delivery, reaction = providers

    logger.debug("[publish] slack_ctx=%s", slack_ctx)
    creds: dict[str, Any] = {
        "channel_id": channel or "",
        "thread_ts": thread_ts or "",
        "access_token": token or "",
        "_blocks": blocks,
    }
    report_posted, delivery_error = delivery(message, creds)

    logger.debug(
        "[publish] slack delivery: posted=%s channel=%s thread_ts=%s error=%s",
        report_posted,
        channel,
        thread_ts,
        delivery_error,
    )
    if report_posted and token and channel and alert_ts:
        if reaction is not None:
            reaction.swap_reaction("eyes", "clipboard", channel, alert_ts, token)
    elif thread_ts and not report_posted:
        raise RuntimeError(
            f"[publish] Slack delivery failed: channel={channel}, "
            f"thread_ts={thread_ts}, reason={delivery_error}"
        )
