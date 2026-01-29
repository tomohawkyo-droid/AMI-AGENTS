"""File-per-entry transcript storage grouped by session.

Replaces the flat JSONL transcript format with individual JSON files
per entry, grouped under UUIDv7-named session directories. Lexicographic
sort of UUIDv7 filenames == chronological sort.

Storage layout:
    logs/transcripts/{session_uuid7}/
        session.json          # SessionMetadata
        {entry_uuid7}.json    # TranscriptEntry per turn
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from ami.cli.agent_logging import TranscriptEntry
from ami.core.config import get_config
from ami.utils.uuid_utils import uuid7


class SessionMetadata(BaseModel):
    """Metadata for a transcript session."""

    session_id: str
    status: Literal["active", "paused", "completed"] = "active"
    created: str
    last_active: str
    provider: str
    model: str
    entry_count: int = 0
    summary: str = ""


class TranscriptStore:
    """File-per-entry transcript storage grouped by session."""

    def __init__(self, root: Path | None = None) -> None:
        if root is None:
            root = get_config().root / "logs" / "transcripts"
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    # --- Session lifecycle ---

    def create_session(
        self, provider: str, model: str, session_id: str | None = None
    ) -> str:
        """Create new session dir + session.json. Returns session_id."""
        session_id = session_id or uuid7()
        session_dir = self.root / session_id
        session_dir.mkdir(parents=True, exist_ok=True)

        now = datetime.now(tz=UTC).isoformat()
        meta = SessionMetadata(
            session_id=session_id,
            status="active",
            created=now,
            last_active=now,
            provider=provider,
            model=model,
        )
        self._write_session_meta(session_id, meta)
        return session_id

    def get_session(self, session_id: str) -> SessionMetadata | None:
        """Read session.json for a session."""
        path = self.root / session_id / "session.json"
        if not path.exists():
            return None
        try:
            return SessionMetadata.model_validate_json(path.read_text("utf-8"))
        except Exception:
            return None

    def update_session(self, session_id: str, **fields: object) -> None:
        """Update session.json fields (status, last_active, entry_count, etc)."""
        meta = self.get_session(session_id)
        if meta is None:
            return
        valid_fields = SessionMetadata.model_fields
        for key, value in fields.items():
            if key in valid_fields:
                object.__setattr__(meta, key, value)
        self._write_session_meta(session_id, meta)

    def list_sessions(self, status: str | None = None) -> list[SessionMetadata]:
        """List all sessions, optionally filtered by status. Newest first."""
        sessions: list[SessionMetadata] = []
        if not self.root.exists():
            return sessions
        for child in sorted(self.root.iterdir(), reverse=True):
            if not child.is_dir():
                continue
            meta = self.get_session(child.name)
            if meta is None:
                continue
            if status and meta.status != status:
                continue
            sessions.append(meta)
        return sessions

    def get_resumable_session(self) -> SessionMetadata | None:
        """Get most recent 'paused' session, if any."""
        paused = self.list_sessions(status="paused")
        return paused[0] if paused else None

    # --- Entry CRUD ---

    def add_entry(self, session_id: str, entry: TranscriptEntry) -> str:
        """Write entry to {session_id}/{entry_id}.json. Returns entry_id."""
        entry_id = entry.entry_id

        session_dir = self.root / session_id
        session_dir.mkdir(parents=True, exist_ok=True)

        entry_path = session_dir / f"{entry_id}.json"
        try:
            entry_path.write_text(entry.model_dump_json(indent=2), encoding="utf-8")
        except Exception as e:
            sys.stderr.write(f"FAILED TO WRITE TRANSCRIPT ENTRY: {e}\n")
            return entry_id

        # Update session metadata
        now = datetime.now(tz=UTC).isoformat()
        meta = self.get_session(session_id)
        if meta:
            # Build updates dict (no explicit type annotation needed)
            updates = {
                "last_active": now,
                "entry_count": meta.entry_count + 1,
            }
            if not meta.summary and entry.type == "user" and entry.message:
                content = entry.message.content
                text = (
                    content
                    if isinstance(content, str)
                    else " ".join(b.text for b in content)
                )
                updates["summary"] = text[:120]
            self.update_session(session_id, **updates)

        return entry_id

    def read_entries(self, session_id: str) -> list[TranscriptEntry]:
        """Read all entries for a session, sorted chronologically by timestamp."""
        session_dir = self.root / session_id
        if not session_dir.exists():
            return []

        entries: list[TranscriptEntry] = []
        for path in session_dir.glob("*.json"):
            if path.name == "session.json":
                continue
            try:
                entries.append(
                    TranscriptEntry.model_validate_json(path.read_text("utf-8"))
                )
            except Exception:
                continue
        entries.sort(key=lambda e: e.timestamp)
        return entries

    def read_recent(self, session_id: str, n: int = 10) -> list[TranscriptEntry]:
        """Read last N entries (for rolling window)."""
        all_entries = self.read_entries(session_id)
        return all_entries[-n:] if len(all_entries) > n else all_entries

    # --- Internal ---

    def _write_session_meta(self, session_id: str, meta: SessionMetadata) -> None:
        """Write session.json atomically."""
        session_dir = self.root / session_id
        session_dir.mkdir(parents=True, exist_ok=True)
        path = session_dir / "session.json"
        try:
            path.write_text(meta.model_dump_json(indent=2), encoding="utf-8")
        except Exception as e:
            sys.stderr.write(f"FAILED TO WRITE SESSION METADATA: {e}\n")
