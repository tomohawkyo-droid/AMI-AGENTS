"""Unified agent interaction logging.

Ensures all agent interactions (Claude, Qwen, Gemini) are logged to a standardized
transcript format via TranscriptStore (file-per-entry, session-aware).
"""

import sys
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from ami.types.common import TranscriptMetadata
from ami.utils.uuid_utils import uuid7


def _empty_transcript_metadata() -> TranscriptMetadata:
    """Factory for empty TranscriptMetadata."""
    return TranscriptMetadata()


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
    metadata: TranscriptMetadata = Field(default_factory=_empty_transcript_metadata)


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

        meta_dict: TranscriptMetadata = {}
        if metadata:
            meta_dict = TranscriptMetadata(
                session_id=metadata.session_id or "",
                duration=metadata.duration or 0.0,
                exit_code=metadata.exit_code or 0,
                model=metadata.model or "",
                tokens=metadata.tokens or 0,
            )

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
