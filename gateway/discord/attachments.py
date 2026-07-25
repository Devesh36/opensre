"""Download and inline Discord attachments for gateway turns."""

from __future__ import annotations

import logging

import httpx

from core.llm.image_description import describe_image_via_provider, is_supported_image
from gateway.attachments.inline import (
    _MAX_FILE_CHARS,
    _MAX_TOTAL_CHARS,
    budgeted_section,
    is_text_mimetype,
    join_attachment_sections,
    truncate_attachment_text,
)
from gateway.discord.events import DiscordInboundAttachment

logger = logging.getLogger(__name__)

_MAX_BYTES = 256 * 1024


def _download(url: str, bot_token: str) -> bytes | None:
    try:
        with httpx.stream(
            "GET",
            url,
            headers={"Authorization": f"Bot {bot_token}"},
            follow_redirects=True,
            timeout=10.0,
        ) as response:
            if response.status_code != httpx.codes.OK:
                return None
            chunks: list[bytes] = []
            total = 0
            for chunk in response.iter_bytes():
                total += len(chunk)
                if total > _MAX_BYTES:
                    return None
                chunks.append(chunk)
            return b"".join(chunks)
    except httpx.HTTPError:
        return None


def build_discord_attachments_context(
    attachments: tuple[DiscordInboundAttachment, ...],
    *,
    bot_token: str,
) -> str:
    if not attachments:
        return ""
    sections: list[str] = []
    remaining = _MAX_TOTAL_CHARS
    for item in attachments:
        label = item.filename or "attachment"
        if remaining <= 0:
            sections.append(f"- {label} — omitted (attachment budget reached)")
            continue
        if is_supported_image(item.content_type):
            data = _download(item.url, bot_token)
            if data is None:
                sections.append(f"- {label} — could not be downloaded")
                continue
            description = describe_image_via_provider(data, item.content_type)
            if not description:
                sections.append(f"- {label} — image could not be described")
                continue
            header = f"--- image: {label} (vision description) ---"
            section, consumed = budgeted_section(header, description, remaining)
            remaining -= consumed
            sections.append(section)
            continue
        if is_text_mimetype(item.content_type):
            data = _download(item.url, bot_token)
            if data is None:
                sections.append(f"- {label} — could not be downloaded")
                continue
            try:
                text = data.decode("utf-8")
            except UnicodeDecodeError:
                text = data.decode("latin-1", errors="replace")
            text = truncate_attachment_text(text, max_chars=_MAX_FILE_CHARS)
            header = f"--- attached file: {label} ---"
            section, consumed = budgeted_section(header, text, remaining)
            remaining -= consumed
            sections.append(section)
            continue
        sections.append(f"- {label} ({item.content_type}) — not readable")
    return join_attachment_sections(sections)
