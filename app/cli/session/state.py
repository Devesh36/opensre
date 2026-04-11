"""Session state for persistent interactive CLI mode."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.config import LLMSettings


@dataclass
class SessionState:
    """In-memory state that survives across REPL commands."""

    trust_mode: bool = False
    active_run: bool = False
    interruption_requested: bool = False
    last_alert: dict[str, Any] | None = None
    last_result: dict[str, Any] | None = None
    conversation: list[str] = field(default_factory=list)
    last_duration_s: float | None = None

    def append_turn(self, text: str) -> None:
        if text.strip():
            self.conversation.append(text.strip())

    @property
    def model_label(self) -> str:
        try:
            settings = LLMSettings.from_env()
        except Exception:
            return "unknown"
        provider = settings.provider
        if provider == "anthropic":
            return settings.anthropic_reasoning_model
        if provider == "openai":
            return settings.openai_reasoning_model
        if provider == "openrouter":
            return settings.openrouter_reasoning_model
        if provider == "gemini":
            return settings.gemini_reasoning_model
        if provider == "nvidia":
            return settings.nvidia_reasoning_model
        if provider == "bedrock":
            return settings.bedrock_reasoning_model
        if provider == "ollama":
            return settings.ollama_model
        return "unknown"
