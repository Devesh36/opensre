"""REPL inline-spinner phase labels (decoupled from UI imports)."""

from __future__ import annotations

SPINNER_PHASE_PLANNING = "planning"
SPINNER_PHASE_STREAMING_ANSWER = "streaming answer"
SPINNER_PHASE_RUNNING_INVESTIGATION = "running investigation"

_STATIC_RUNNING_PHASES: dict[str, str] = {
    "shell": "running shell command",
    "investigation": SPINNER_PHASE_RUNNING_INVESTIGATION,
    "synthetic_test": "running synthetic test",
    "sample_alert": "running sample alert",
    "implementation": "running implementation task",
    "task_cancel": "running /cancel",
}


def running_phase(target: str, *, fallback: str = "action") -> str:
    """Format a ``running …`` spinner label for a command or target name."""
    label = target.strip()
    return f"running {label}" if label else f"running {fallback}"


def slash_command_phase(content: str, *, fallback: str = "/command") -> str:
    """Format ``running /command`` for a slash-command action payload."""
    command = content.split(maxsplit=1)[0] if content else fallback
    if not command.startswith("/"):
        command = f"/{command}"
    return running_phase(command)


def spinner_phase_for_action(*, kind: str, content: str) -> str:
    """Map a planned action to a concrete REPL spinner phase label."""
    stripped = content.strip()
    match kind:
        case "slash":
            return slash_command_phase(stripped)
        case "cli_command":
            head = stripped.split(maxsplit=1)[0] if stripped else ""
            return running_phase(head, fallback="cli command")
        case "llm_provider":
            if stripped.startswith("/"):
                return running_phase(stripped.split(maxsplit=1)[0])
            token = stripped.split(maxsplit=1)
            return running_phase(f"/model {token[0]}") if token else running_phase("/model")
        case static if static in _STATIC_RUNNING_PHASES:
            return _STATIC_RUNNING_PHASES[static]
        case _:
            return running_phase("", fallback="action")


def set_spinner_phase(console: object, phase: str) -> None:
    """Update the REPL inline spinner label when the console exposes the hook."""
    label = phase.strip()
    if not label:
        return
    hook = getattr(console, "set_spinner_phase", None)
    if callable(hook):
        hook(label)


__all__ = [
    "SPINNER_PHASE_PLANNING",
    "SPINNER_PHASE_RUNNING_INVESTIGATION",
    "SPINNER_PHASE_STREAMING_ANSWER",
    "running_phase",
    "set_spinner_phase",
    "slash_command_phase",
    "spinner_phase_for_action",
]
