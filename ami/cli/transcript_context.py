"""Builds conversation context from transcript entries.

Used to inject a rolling window of recent conversation history
into the prompt on turn 2+, enabling multi-turn without relying
on provider-native session resume.
"""

from __future__ import annotations

from ami.cli.agent_logging import TranscriptEntry
from ami.cli.transcript_store import TranscriptStore

_MAX_MESSAGE_LEN = 2000


def _extract_text(entry: TranscriptEntry) -> str:
    """Pull plain text out of an entry's message."""
    if entry.message is None:
        return ""
    content = entry.message.content
    if isinstance(content, str):
        return content
    return " ".join(block.text for block in content)


def _truncate(text: str, limit: int = _MAX_MESSAGE_LEN) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + "..."


def _format_entry(entry: TranscriptEntry, truncate: bool = True) -> str:
    """Format a single entry as a labeled line."""
    if entry.type == "error":
        return f"[Error]: {entry.error or '(unknown)'}"

    text = _extract_text(entry)
    if truncate:
        text = _truncate(text)

    label = entry.type.capitalize()
    return f"[{label}]: {text}"


class TranscriptContextBuilder:
    """Builds conversation context from transcript entries."""

    def __init__(self, store: TranscriptStore, window_size: int = 10) -> None:
        self.store = store
        self.window_size = window_size

    def build_context(self, session_id: str) -> str:
        """Build context string from last N entries for prompt injection.

        Returns empty string if no entries exist.
        """
        entries = self.store.read_recent(session_id, n=self.window_size)
        if not entries:
            return ""

        lines = ["## Previous Conversation"]
        lines.extend(_format_entry(entry, truncate=True) for entry in entries)
        return "\n".join(lines)

    def build_replay(self, session_id: str) -> str:
        """Build full session replay (all entries, no truncation)."""
        entries = self.store.read_entries(session_id)
        if not entries:
            return ""

        lines = ["## Full Session Replay"]
        lines.extend(_format_entry(entry, truncate=False) for entry in entries)
        return "\n".join(lines)
