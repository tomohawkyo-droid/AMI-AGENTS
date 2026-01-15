"""Unified agent interaction logging.

Ensures all agent interactions (Claude, Qwen, Gemini) are logged to a standardized
transcript format compatible with existing analysis tools.
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from agents.ami.core.config import get_config


class TranscriptLogger:
    """Logs agent interactions to JSONL transcripts."""

    def __init__(self, session_id: str):
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
        entry = {
            "type": "user",
            "message": {
                "content": content,
            },
            "timestamp": datetime.now().isoformat()
        }
        self._append_entry(entry)

    def log_assistant_message(self, content: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        """Log an assistant message (response)."""
        # Format content as list of text blocks to match Claude format
        msg_content = [{"type": "text", "text": content}]
        
        entry = {
            "type": "assistant",
            "message": {
                "content": msg_content,
            },
            "timestamp": datetime.now().isoformat(),
            "metadata": metadata or {}
        }
        self._append_entry(entry)

    def log_error(self, error: str) -> None:
        """Log an execution error."""
        entry = {
            "type": "error",
            "error": error,
            "timestamp": datetime.now().isoformat()
        }
        self._append_entry(entry)

    def _append_entry(self, entry: Dict[str, Any]) -> None:
        """Append a JSON entry to the log file."""
        try:
            with self.log_file.open("a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception as e:
            # Fallback to stderr if logging fails
            print(f"FAILED TO WRITE TRANSCRIPT LOG: {e}", file=sys.stderr)
