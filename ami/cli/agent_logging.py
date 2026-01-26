"""Unified agent interaction logging.

Ensures all agent interactions (Claude, Qwen, Gemini) are logged to a standardized
transcript format compatible with existing analysis tools.
"""

import sys
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from ami.core.config import get_config

if TYPE_CHECKING:
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

    type: str
    timestamp: str
    message: MessageContent | None = None
    error: str | None = None
    metadata: dict[str, str | int | float | bool | None] = Field(default_factory=dict)


class TranscriptLogger:
    """Logs agent interactions to JSONL transcripts."""

    def __init__(self, session_id: str) -> None:
        self.session_id = session_id
        self.config = get_config()
        self.log_dir = self._get_log_dir()
        self.log_file = self.log_dir / f"{session_id}.jsonl"

    def _get_log_dir(self) -> Path:
        """Get or create the transcript directory for today."""
        base_dir = self.config.root / "logs" / "transcripts"
        date_str = datetime.now().strftime("%Y-%m-%d")
        log_dir = base_dir / date_str
        log_dir.mkdir(parents=True, exist_ok=True)
        return log_dir

    def log_user_message(self, content: str) -> None:
        """Log a user message (instruction)."""
        entry = TranscriptEntry(
            type="user",
            message=MessageContent(content=content),
            timestamp=datetime.now().isoformat(),
        )
        self._append_entry(entry)

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
            type="assistant",
            message=MessageContent(content=msg_content),
            timestamp=datetime.now().isoformat(),
            metadata=meta_dict,
        )
        self._append_entry(entry)

    def log_error(self, error: str) -> None:
        """Log an execution error."""
        entry = TranscriptEntry(
            type="error",
            error=error,
            timestamp=datetime.now().isoformat(),
        )
        self._append_entry(entry)

    def _append_entry(self, entry: TranscriptEntry) -> None:
        """Append a JSON entry to the log file."""
        try:
            with self.log_file.open("a", encoding="utf-8") as f:
                f.write(entry.model_dump_json() + "\n")
        except Exception as e:
            print(f"FAILED TO WRITE TRANSCRIPT LOG: {e}", file=sys.stderr)
