"""Terminal CPR (cursor position report) helpers for the interactive REPL."""

from __future__ import annotations

import os
import re
import select
import sys

_CPR_SEQUENCE_RE = re.compile(
    r"(?:\x1b\[|\x9b)\d{1,4};\d{1,4}R"  # ESC [ row ; col R
    r"|\[\d{1,4};\d{1,4}R"  # [row;colR without ESC (leaked into input)
    r"|\d{1,4};\d{1,4}R"  # row;colR without ESC or [
    r"|\d{1,4}R(?=[\[\d])"  # trailing rowR before another CPR fragment
)
_CPR_ESCAPED_SEQUENCE_RE = re.compile(r"(?:\x1b\[|\x9b)\d{1,4};\d{1,4}R")


def drain_stale_cpr_bytes() -> None:
    """Discard CPR escape-sequence bytes left in stdin after a prompt_async teardown.

    When prompt_async returns, prompt_toolkit tears down its input-reader thread.
    CPR responses (ESC[row;colR) that arrive just after the reader stops sit in
    the OS stdin buffer and appear as literal keystrokes in the next prompt.
    """
    if os.name == "nt" or not sys.stdin.isatty():
        return
    try:
        fd = sys.stdin.fileno()
        while select.select([fd], [], [], 0)[0]:
            chunk = os.read(fd, 256)
            if not chunk:
                break
    except OSError:
        # Draining stdin is best-effort; ignore when the fd is not readable.
        pass


def strip_cpr_sequences(text: str | None) -> str:
    """Remove terminal cursor-position replies that leaked into submitted text."""
    if not text:
        return ""
    return _CPR_SEQUENCE_RE.sub("", text)


def strip_cpr_escape_sequences(text: str | None) -> str:
    """Remove only canonical escaped CPR sequences from text."""
    if not text:
        return ""
    return _CPR_ESCAPED_SEQUENCE_RE.sub("", text)


def contains_cpr_sequence(text: str | None) -> bool:
    return bool(text and _CPR_SEQUENCE_RE.search(text))


__all__ = [
    "contains_cpr_sequence",
    "drain_stale_cpr_bytes",
    "strip_cpr_escape_sequences",
    "strip_cpr_sequences",
]
