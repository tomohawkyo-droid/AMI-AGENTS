"""Unit tests for ami.cli.transcript_search."""

from __future__ import annotations

from unittest.mock import MagicMock

from ami.cli.transcript_search import (
    SearchHit,
    SessionSearchResult,
    TranscriptSearcher,
    _build_automaton,
    _extract_text,
    _snippet,
)
from ami.core.conversation import ConversationEntry


class TestExtractText:
    def test_returns_content(self) -> None:
        entry = ConversationEntry(
            entry_id="1",
            role="user",
            content="hello world",
            origin="human",
        )
        assert _extract_text(entry) == "hello world"

    def test_empty_content(self) -> None:
        entry = ConversationEntry(
            entry_id="1",
            role="user",
            content="",
            origin="human",
        )
        assert _extract_text(entry) == ""


class TestBuildAutomaton:
    def test_single_keyword(self) -> None:
        auto = _build_automaton(["hello"])
        matches = list(auto.iter("hello world"))
        assert len(matches) == 1
        assert matches[0][1] == "hello"

    def test_multiple_keywords(self) -> None:
        auto = _build_automaton(["foo", "bar"])
        text = "foo and bar"
        matches = list(auto.iter(text))
        keywords_found = {m[1] for m in matches}
        assert "foo" in keywords_found
        assert "bar" in keywords_found

    def test_case_insensitive(self) -> None:
        auto = _build_automaton(["Hello"])
        matches = list(auto.iter("hello world"))
        assert len(matches) == 1


class TestSnippet:
    def test_short_text(self) -> None:
        result = _snippet("short", pos=2)
        assert "short" in result

    def test_long_text_start_ellipsis(self) -> None:
        text = "a" * 200
        result = _snippet(text, pos=100)
        assert result.startswith("...")

    def test_long_text_end_ellipsis(self) -> None:
        text = "a" * 200
        result = _snippet(text, pos=100)
        assert result.endswith("...")

    def test_at_start(self) -> None:
        text = "a" * 200
        result = _snippet(text, pos=0)
        assert not result.startswith("...")

    def test_newlines_replaced(self) -> None:
        result = _snippet("line1\nline2", pos=3)
        assert "\n" not in result


class TestSearchHit:
    def test_fields(self) -> None:
        hit = SearchHit(
            session_id="s1",
            entry_id="e1",
            keyword="test",
            line="test line",
            context_snippet="...test...",
        )
        assert hit.session_id == "s1"
        assert hit.keyword == "test"


class TestSessionSearchResult:
    def test_empty_hits(self) -> None:
        result = SessionSearchResult(
            session_id="s1",
            summary="Test session",
        )
        assert result.hits == []
        assert result.summary == "Test session"


class TestTranscriptSearcher:
    def _make_store(self, entries_by_session=None) -> MagicMock:
        store = MagicMock()
        if entries_by_session is None:
            entries_by_session = {}
        store.list_sessions.return_value = [
            MagicMock(session_id=sid) for sid in entries_by_session
        ]
        store.read_entries.side_effect = lambda sid: entries_by_session.get(sid, [])
        store.get_session.return_value = MagicMock(summary="test summary")
        return store

    def test_empty_keywords(self) -> None:
        store = self._make_store()
        searcher = TranscriptSearcher(store)
        assert searcher.search([]) == []

    def test_finds_keyword(self) -> None:
        entry = ConversationEntry(
            entry_id="e1",
            role="user",
            content="hello world foo bar",
            origin="human",
        )
        store = self._make_store({"s1": [entry]})
        searcher = TranscriptSearcher(store)
        hits = searcher.search(["foo"])
        assert len(hits) == 1
        assert hits[0].keyword == "foo"
        assert hits[0].session_id == "s1"

    def test_specific_session(self) -> None:
        entry = ConversationEntry(
            entry_id="e1",
            role="user",
            content="match here",
            origin="human",
        )
        store = self._make_store({"s1": [entry]})
        searcher = TranscriptSearcher(store)
        hits = searcher.search(["match"], session_id="s1")
        assert len(hits) == 1

    def test_search_sessions_groups(self) -> None:
        entry = ConversationEntry(
            entry_id="e1",
            role="user",
            content="keyword found",
            origin="human",
        )
        store = self._make_store({"s1": [entry]})
        searcher = TranscriptSearcher(store)
        results = searcher.search_sessions(["keyword"])
        assert len(results) == 1
        assert results[0].session_id == "s1"
        assert len(results[0].hits) == 1
