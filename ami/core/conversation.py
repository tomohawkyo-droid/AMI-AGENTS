"""Conversation transcript system.

Provides typed conversation entries with role differentiation, metadata
preservation, and a unified service that handles both in-memory state
and persistent JSONL storage.
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from enum import Enum
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from ami.utils.uuid_utils import uuid7

if TYPE_CHECKING:
    from ami.cli.transcript_store import TranscriptStore


def _now_iso() -> str:
    """Return current UTC time as ISO string."""
    return datetime.now(tz=UTC).isoformat()


class EntryRole(str, Enum):
    """Role of a conversation entry."""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    ERROR = "error"
    INTERNAL = "internal"


class EntryOrigin(str, Enum):
    """Origin of the content in a conversation entry."""

    HUMAN = "human"
    AGENT = "agent"
    SYSTEM = "system"
    TOOL = "tool"


class EntryMetadata(BaseModel):
    """Full metadata for a conversation entry."""

    model: str | None = None
    provider: str | None = None
    tokens: int | None = None
    duration: float | None = None
    exit_code: int | None = None
    cost_usd: float | None = None
    tool_calls: int | None = None
    thinking_tokens: int | None = None
    cache_hits: int | None = None


class ConversationEntry(BaseModel):
    """A single entry in the conversation transcript."""

    entry_id: str = Field(default_factory=uuid7)
    role: EntryRole
    origin: EntryOrigin
    content: str
    timestamp: str = Field(default_factory=_now_iso)
    turn: int = 0
    parent_id: str | None = None
    metadata: EntryMetadata = Field(default_factory=EntryMetadata)


# --- Prompt label mapping ---


def _role_label(role: EntryRole) -> str | None:
    """Get prompt label for a role, or None if excluded."""
    if role == EntryRole.ASSISTANT:
        return "Agent"
    if role == EntryRole.TOOL_RESULT:
        return "Tool"
    if role == EntryRole.INTERNAL:
        return "System"
    if role == EntryRole.ERROR:
        return "Error"
    return None


class ConversationTranscript:
    """Single source of truth for conversation state.

    Manages both in-memory entries and persistent JSONL storage.
    Replaces the old conversation: list[str] + TranscriptLogger split.
    """

    def __init__(self, store: TranscriptStore, session_id: str) -> None:
        self._store = store
        self._session_id = session_id
        self._entries: list[ConversationEntry] = []
        self._turn = 0
        self._history_count = 0

    # --- Writing ---

    def add_system(self, content: str) -> ConversationEntry:
        """Add a system prompt entry (banner, template, tools)."""
        return self._record(
            ConversationEntry(
                role=EntryRole.SYSTEM,
                origin=EntryOrigin.SYSTEM,
                content=content,
                turn=0,
            )
        )

    def add_user(self, content: str) -> ConversationEntry:
        """Add a raw user input entry."""
        self._turn += 1
        return self._record(
            ConversationEntry(
                role=EntryRole.USER,
                origin=EntryOrigin.HUMAN,
                content=content,
                turn=self._turn,
            )
        )

    def add_assistant(
        self, content: str, metadata: EntryMetadata | None = None
    ) -> ConversationEntry:
        """Add an agent response entry."""
        return self._record(
            ConversationEntry(
                role=EntryRole.ASSISTANT,
                origin=EntryOrigin.AGENT,
                content=content,
                turn=self._turn,
                metadata=metadata or EntryMetadata(),
            )
        )

    def add_tool_call(self, command: str, parent_id: str) -> ConversationEntry:
        """Add a shell command extracted from agent response."""
        return self._record(
            ConversationEntry(
                role=EntryRole.TOOL_CALL,
                origin=EntryOrigin.AGENT,
                content=command,
                turn=self._turn,
                parent_id=parent_id,
            )
        )

    def add_tool_result(
        self, output: str, parent_id: str, exit_code: int = 0
    ) -> ConversationEntry:
        """Add shell execution output."""
        return self._record(
            ConversationEntry(
                role=EntryRole.TOOL_RESULT,
                origin=EntryOrigin.TOOL,
                content=output,
                turn=self._turn,
                parent_id=parent_id,
                metadata=EntryMetadata(exit_code=exit_code),
            )
        )

    def add_error(self, error: str) -> ConversationEntry:
        """Add an execution error entry."""
        return self._record(
            ConversationEntry(
                role=EntryRole.ERROR,
                origin=EntryOrigin.SYSTEM,
                content=error,
                turn=self._turn,
            )
        )

    def add_internal(self, content: str) -> ConversationEntry:
        """Add a loop control entry (e.g. 'Continue.')."""
        return self._record(
            ConversationEntry(
                role=EntryRole.INTERNAL,
                origin=EntryOrigin.SYSTEM,
                content=content,
                turn=self._turn,
            )
        )

    # --- Reading ---

    @property
    def entries(self) -> list[ConversationEntry]:
        """All entries in chronological order."""
        return list(self._entries)

    def has_history(self) -> bool:
        """True if entries were loaded from a previous session turn."""
        return self._history_count > 0

    @property
    def last_entry_id(self) -> str:
        """Entry ID of the most recent entry, or empty string if none."""
        return self._entries[-1].entry_id if self._entries else ""

    # --- Prompt Building ---

    def build_prompt(self) -> str:
        """Build the full prompt for the next LLM call.

        Maps entries to labeled text blocks matching the bootloader format:
        [Instruction], [Agent], [Tool], [System], [Error].
        SYSTEM entries are included once at the top.
        TOOL_CALL entries are folded into the preceding Agent block.
        """
        parts: list[str] = []

        for entry in self._entries:
            if entry.role == EntryRole.SYSTEM:
                if not parts:
                    parts.append(entry.content)
                continue

            if entry.role == EntryRole.TOOL_CALL:
                continue

            label = _role_label(entry.role)
            if label is None:
                continue

            if entry.role == EntryRole.TOOL_RESULT:
                parts.append(f"[{label}]\nTool Output:\n{entry.content}")
            else:
                parts.append(f"[{label}]\n{entry.content}")

        return "\n\n".join(parts)

    def build_context_summary(self) -> str:
        """Build clean USER + ASSISTANT context for session resume.

        Only includes entries from previous turns (loaded from store).
        Full content, no truncation.
        """
        lines: list[str] = ["## Previous Conversation"]

        for entry in self._entries[: self._history_count]:
            if entry.role == EntryRole.USER:
                lines.append(f"\n[User]: {entry.content}")
            elif entry.role == EntryRole.ASSISTANT:
                lines.append(f"[Assistant]: {entry.content}")

        if len(lines) <= 1:
            return ""

        return "\n".join(lines)

    # --- Persistence ---

    def load_from_store(self) -> None:
        """Hydrate entries from persistent storage (for session resume)."""
        loaded = self._store.read_entries(self._session_id)
        self._entries = loaded
        self._history_count = len(loaded)

        if loaded:
            max_turn = max(e.turn for e in loaded)
            self._turn = max_turn

    def _record(self, entry: ConversationEntry) -> ConversationEntry:
        """Store entry in-memory and persist to JSONL."""
        self._entries.append(entry)
        self._persist(entry)
        return entry

    def _persist(self, entry: ConversationEntry) -> None:
        """Write entry to the JSONL transcript store."""
        try:
            self._store.add_entry(self._session_id, entry)
        except Exception as e:
            sys.stderr.write(f"FAILED TO WRITE TRANSCRIPT ENTRY: {e}\n")
