"""Aho-Corasick multi-pattern search across transcript entries."""

from __future__ import annotations

import ahocorasick
from pydantic import BaseModel, Field

from ami.cli.agent_logging import TranscriptEntry
from ami.cli.transcript_store import TranscriptStore


class SearchHit(BaseModel):
    """A single keyword match within an entry."""

    session_id: str
    entry_id: str
    keyword: str
    line: str
    context_snippet: str


class SessionSearchResult(BaseModel):
    """Search hits grouped by session."""

    session_id: str
    summary: str
    hits: list[SearchHit] = Field(default_factory=list)


def _extract_text(entry: TranscriptEntry) -> str:
    """Pull searchable text from an entry."""
    parts: list[str] = []
    if entry.message:
        content = entry.message.content
        if isinstance(content, str):
            parts.append(content)
        else:
            parts.extend(block.text for block in content)
    if entry.error:
        parts.append(entry.error)
    return "\n".join(parts)


def _build_automaton(keywords: list[str]) -> ahocorasick.Automaton:
    """Build an Aho-Corasick automaton from keywords."""
    automaton = ahocorasick.Automaton()
    for keyword in keywords:
        lower = keyword.lower()
        automaton.add_word(lower, keyword)
    automaton.make_automaton()
    return automaton


def _snippet(text: str, pos: int, radius: int = 60) -> str:
    """Extract a context snippet around a match position."""
    start = max(0, pos - radius)
    end = min(len(text), pos + radius)
    snippet = text[start:end].replace("\n", " ")
    if start > 0:
        snippet = "..." + snippet
    if end < len(text):
        snippet = snippet + "..."
    return snippet


class TranscriptSearcher:
    """Aho-Corasick multi-pattern search across transcripts."""

    def __init__(self, store: TranscriptStore) -> None:
        self.store = store

    def search(
        self, keywords: list[str], session_id: str | None = None
    ) -> list[SearchHit]:
        """Search for keywords across entries.

        If session_id is given, search only that session. Otherwise, search all.
        """
        if not keywords:
            return []

        automaton = _build_automaton(keywords)
        hits: list[SearchHit] = []

        if session_id:
            sessions = [session_id]
        else:
            sessions = [s.session_id for s in self.store.list_sessions()]

        for sid in sessions:
            entries = self.store.read_entries(sid)
            for entry in entries:
                text = _extract_text(entry)
                if not text:
                    continue
                lower_text = text.lower()
                for end_idx, keyword in automaton.iter(lower_text):
                    line_start = lower_text.rfind("\n", 0, end_idx) + 1
                    line_end = lower_text.find("\n", end_idx)
                    if line_end == -1:
                        line_end = len(text)
                    hits.append(
                        SearchHit(
                            session_id=sid,
                            entry_id=entry.entry_id,
                            keyword=keyword,
                            line=text[line_start:line_end].strip(),
                            context_snippet=_snippet(text, end_idx),
                        )
                    )

        return hits

    def search_sessions(self, keywords: list[str]) -> list[SessionSearchResult]:
        """Group search hits by session for summary display."""
        hits = self.search(keywords)
        by_session: dict[str, SessionSearchResult] = {}
        for hit in hits:
            if hit.session_id not in by_session:
                meta = self.store.get_session(hit.session_id)
                summary = meta.summary if meta else ""
                by_session[hit.session_id] = SessionSearchResult(
                    session_id=hit.session_id, summary=summary
                )
            by_session[hit.session_id].hits.append(hit)
        return list(by_session.values())
