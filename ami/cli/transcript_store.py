"""JSONL transcript storage grouped by session.

Storage layout:
    logs/transcripts/{session_uuid7}/
        session.json        # SessionMetadata
        transcript.jsonl    # One ConversationEntry per line, append-only
"""

from __future__ import annotations

import shutil
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from ami.core.config import get_config
from ami.core.conversation import ConversationEntry, EntryRole
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
    turn_count: int = 0
    total_tokens: int = 0
    summary: str = ""
    cwd: str = ""


class TranscriptStore:
    """JSONL transcript storage grouped by session."""

    def __init__(self, root: Path | None = None) -> None:
        if root is None:
            root = get_config().root / "logs" / "transcripts"
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    # --- Session lifecycle ---

    def create_session(
        self,
        provider: str,
        model: str,
        session_id: str | None = None,
        cwd: str = "",
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
            cwd=cwd,
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

    def list_sessions(
        self, status: str | None = None, cwd: str | None = None
    ) -> list[SessionMetadata]:
        """List all sessions, optionally filtered by status and/or cwd. Newest first."""
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
            if cwd and meta.cwd != cwd:
                continue
            sessions.append(meta)
        return sessions

    def delete_session(self, session_id: str) -> bool:
        """Delete a session directory and all its entries. Returns True if deleted."""
        session_dir = self.root / session_id
        if not session_dir.is_dir():
            return False
        shutil.rmtree(session_dir)
        return True

    def get_resumable_session(self, cwd: str | None = None) -> SessionMetadata | None:
        """Get most recent 'paused' session, optionally scoped to cwd."""
        paused = self.list_sessions(status="paused", cwd=cwd)
        return paused[0] if paused else None

    def prune_sessions(self, retention_days: int = 90) -> int:
        """Delete sessions older than retention_days. Returns count deleted."""
        cutoff = (datetime.now(tz=UTC) - timedelta(days=retention_days)).isoformat()
        deleted = 0
        if not self.root.exists():
            return deleted
        for child in list(self.root.iterdir()):
            if not child.is_dir():
                continue
            meta = self.get_session(child.name)
            if meta is None:
                continue
            if meta.last_active < cutoff:
                self.delete_session(child.name)
                deleted += 1
        return deleted

    # --- Entry CRUD (JSONL) ---

    def add_entry(self, session_id: str, entry: ConversationEntry) -> str:
        """Append entry as one JSON line to transcript.jsonl. Returns entry_id."""
        session_dir = self.root / session_id
        session_dir.mkdir(parents=True, exist_ok=True)

        jsonl_path = session_dir / "transcript.jsonl"
        try:
            with open(jsonl_path, "a", encoding="utf-8") as f:
                f.write(entry.model_dump_json() + "\n")
        except Exception as e:
            sys.stderr.write(f"FAILED TO WRITE TRANSCRIPT ENTRY: {e}\n")
            return entry.entry_id

        # Update session metadata
        now = datetime.now(tz=UTC).isoformat()
        meta = self.get_session(session_id)
        if meta:
            self._apply_entry_updates(meta, session_id, entry, now)

        return entry.entry_id

    def read_entries(self, session_id: str) -> list[ConversationEntry]:
        """Read all entries from transcript.jsonl, in order."""
        jsonl_path = self.root / session_id / "transcript.jsonl"
        if not jsonl_path.exists():
            return []

        entries: list[ConversationEntry] = []
        try:
            with open(jsonl_path, encoding="utf-8") as f:
                for raw_line in f:
                    stripped = raw_line.strip()
                    if not stripped:
                        continue
                    try:
                        entries.append(ConversationEntry.model_validate_json(stripped))
                    except Exception:
                        continue
        except Exception:
            return []
        return entries

    def read_recent(self, session_id: str, n: int = 10) -> list[ConversationEntry]:
        """Read last N entries from transcript.jsonl."""
        all_entries = self.read_entries(session_id)
        return all_entries[-n:] if len(all_entries) > n else all_entries

    # --- Internal ---

    def _apply_entry_updates(
        self,
        meta: SessionMetadata,
        session_id: str,
        entry: ConversationEntry,
        now: str,
    ) -> None:
        """Update session metadata after adding an entry."""
        self.update_session(
            session_id, last_active=now, entry_count=meta.entry_count + 1
        )

        if entry.role == EntryRole.USER:
            self.update_session(session_id, turn_count=meta.turn_count + 1)
            if not meta.summary:
                self.update_session(session_id, summary=entry.content[:120])

        if entry.metadata.tokens:
            self.update_session(
                session_id, total_tokens=meta.total_tokens + entry.metadata.tokens
            )

    def _write_session_meta(self, session_id: str, meta: SessionMetadata) -> None:
        """Write session.json."""
        session_dir = self.root / session_id
        session_dir.mkdir(parents=True, exist_ok=True)
        path = session_dir / "session.json"
        try:
            path.write_text(meta.model_dump_json(indent=2), encoding="utf-8")
        except Exception as e:
            sys.stderr.write(f"FAILED TO WRITE SESSION METADATA: {e}\n")
