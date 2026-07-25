from __future__ import annotations

from gateway.discord.events import DiscordInboundMessage


def test_conversation_key_includes_guild_channel_thread() -> None:
    inbound = DiscordInboundMessage(
        guild_id="G1",
        user_id="U1",
        channel_id="C1",
        message_id="M1",
        thread_id="T1",
        text="hello",
    )
    assert inbound.conversation_key == "G1:C1:T1"
