"""Unified agent interaction logging.

Ensures all agent interactions (Claude, Qwen, Gemini) are logged to a standardized
transcript format via TranscriptStore (file-per-entry, session-aware).
"""

import sys
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from ami.utils.uuid_utils import uuid7

if TYPE_CHECKING:
    from ami.cli.transcript_store import TranscriptStore
    from ami.types.api import ProviderMetadata


class TextBlock(BaseModel):
    """Content block in transcript."""

    type: str = "text"
    text: str


class MessageContent(BaseModel):
    """Message content wrapper."""

    content: str | list[TextBlock]


class TranscriptEntry(BaseModel):
    """A single entry in the transcript log."""

    entry_id: str = Field(default_factory=uuid7)
    type: str
    timestamp: str
    message: MessageContent | None = None
    error: str | None = None
    metadata: dict[str, str | int | float | bool | None] = Field(default_factory=dict)


class TranscriptLogger:
    """Logs agent interactions via TranscriptStore."""

    def __init__(self, store: "TranscriptStore", transcript_id: str) -> None:
        self.transcript_id = transcript_id
        self._store = store

    def log_user_message(self, content: str) -> None:
        """Log a user message (instruction)."""
        entry = TranscriptEntry(
            entry_id=uuid7(),
            type="user",
            message=MessageContent(content=content),
            timestamp=datetime.now(tz=UTC).isoformat(),
        )
        self._write(entry)

    def log_assistant_message(
        self, content: str, metadata: "ProviderMetadata | None" = None
    ) -> None:
        """Log an assistant message (response)."""
        msg_content = [TextBlock(type="text", text=content)]

        meta_dict: dict[str, str | int | float | bool | None] = {}
        if metadata:
            meta_dict = {
                "session_id": metadata.session_id,
                "duration": metadata.duration,
                "exit_code": metadata.exit_code,
                "model": metadata.model,
                "tokens": metadata.tokens,
            }

        entry = TranscriptEntry(
            entry_id=uuid7(),
            type="assistant",
            message=MessageContent(content=msg_content),
            timestamp=datetime.now(tz=UTC).isoformat(),
            metadata=meta_dict,
        )
        self._write(entry)

    def log_error(self, error: str) -> None:
        """Log an execution error."""
        entry = TranscriptEntry(
            entry_id=uuid7(),
            type="error",
            error=error,
            timestamp=datetime.now(tz=UTC).isoformat(),
        )
        self._write(entry)

    def _write(self, entry: TranscriptEntry) -> None:
        """Write entry to the store."""
        try:
            self._store.add_entry(self.transcript_id, entry)
        except Exception as e:
            sys.stderr.write(f"FAILED TO WRITE TRANSCRIPT ENTRY: {e}\n")
