"""Unit tests for TranscriptSearcher."""

from pathlib import Path

from ami.cli.agent_logging import MessageContent, TextBlock, TranscriptEntry
from ami.cli.transcript_search import (
    SearchHit,
    SessionSearchResult,
    TranscriptSearcher,
    _build_automaton,
    _extract_text,
    _snippet,
)
from ami.cli.transcript_store import TranscriptStore


class TestSearchModels:
    """Tests for search data models."""

    def test_search_hit(self):
        hit = SearchHit(
            session_id="s1",
            entry_id="e1",
            keyword="error",
            line="an error occurred",
            context_snippet="...an error occurred...",
        )
        assert hit.keyword == "error"

    def test_session_search_result_defaults(self):
        result = SessionSearchResult(session_id="s1", summary="test")
        assert result.hits == []


class TestHelpers:
    """Tests for module-level helper functions."""

    def test_extract_text_string_content(self):
        entry = TranscriptEntry(
            type="user",
            timestamp="2025-01-01T00:00:00",
            message=MessageContent(content="hello world"),
        )
        assert _extract_text(entry) == "hello world"

    def test_extract_text_block_content(self):
        entry = TranscriptEntry(
            type="user",
            timestamp="2025-01-01T00:00:00",
            message=MessageContent(
                content=[TextBlock(text="part1"), TextBlock(text="part2")]
            ),
        )
        assert _extract_text(entry) == "part1\npart2"

    def test_extract_text_error_entry(self):
        entry = TranscriptEntry(
            type="error",
            timestamp="2025-01-01T00:00:00",
            error="something broke",
        )
        assert _extract_text(entry) == "something broke"

    def test_extract_text_no_message(self):
        entry = TranscriptEntry(
            type="assistant",
            timestamp="2025-01-01T00:00:00",
        )
        assert _extract_text(entry) == ""

    def test_build_automaton(self):
        aut = _build_automaton(["hello", "world"])
        text = "hello there world"
        matches = [kw for _, kw in aut.iter(text.lower())]
        assert "hello" in matches
        assert "world" in matches

    def test_build_automaton_case_insensitive(self):
        aut = _build_automaton(["Error"])
        matches = [kw for _, kw in aut.iter("an error occurred")]
        assert "Error" in matches

    def test_snippet_short_text(self):
        text = "short"
        result = _snippet(text, 2, radius=60)
        assert result == "short"

    def test_snippet_with_ellipsis(self):
        text = "a" * 200
        result = _snippet(text, 100, radius=10)
        assert result.startswith("...")
        assert result.endswith("...")

    def test_snippet_at_start(self):
        text = "a" * 200
        result = _snippet(text, 5, radius=10)
        assert not result.startswith("...")
        assert result.endswith("...")

    def test_snippet_at_end(self):
        text = "a" * 200
        result = _snippet(text, 195, radius=10)
        assert result.startswith("...")
        assert not result.endswith("...")

    def test_snippet_replaces_newlines(self):
        text = "line1\nline2\nline3"
        result = _snippet(text, 5, radius=60)
        assert "\n" not in result


class TestTranscriptSearcher:
    """Tests for TranscriptSearcher.search and search_sessions."""

    def _populate_store(self, tmp_path: Path) -> tuple[TranscriptStore, str]:
        """Create a store with a session containing searchable entries."""
        store = TranscriptStore(root=tmp_path)
        sid = store.create_session(provider="test", model="m")
        store.add_entry(
            sid,
            TranscriptEntry(
                type="user",
                timestamp="2025-01-01T00:00:00",
                message=MessageContent(content="deploy the application"),
            ),
        )
        store.add_entry(
            sid,
            TranscriptEntry(
                type="assistant",
                timestamp="2025-01-01T00:00:01",
                message=MessageContent(content="application deployed successfully"),
            ),
        )
        store.add_entry(
            sid,
            TranscriptEntry(
                type="error",
                timestamp="2025-01-01T00:00:02",
                error="connection timeout error",
            ),
        )
        return store, sid

    def test_search_empty_keywords(self, tmp_path: Path):
        store, _ = self._populate_store(tmp_path)
        searcher = TranscriptSearcher(store)
        assert searcher.search([]) == []

    def test_search_single_keyword(self, tmp_path: Path):
        store, sid = self._populate_store(tmp_path)
        searcher = TranscriptSearcher(store)
        hits = searcher.search(["deploy"], session_id=sid)
        assert len(hits) >= 1
        assert all(h.keyword == "deploy" for h in hits)

    def test_search_multiple_keywords(self, tmp_path: Path):
        store, sid = self._populate_store(tmp_path)
        searcher = TranscriptSearcher(store)
        hits = searcher.search(["deploy", "error"], session_id=sid)
        keywords_found = {h.keyword for h in hits}
        assert "deploy" in keywords_found
        assert "error" in keywords_found

    def test_search_case_insensitive(self, tmp_path: Path):
        store, sid = self._populate_store(tmp_path)
        searcher = TranscriptSearcher(store)
        hits = searcher.search(["DEPLOY"], session_id=sid)
        assert len(hits) >= 1

    def test_search_no_matches(self, tmp_path: Path):
        store, sid = self._populate_store(tmp_path)
        searcher = TranscriptSearcher(store)
        hits = searcher.search(["nonexistent_xyz"], session_id=sid)
        assert hits == []

    def test_search_all_sessions(self, tmp_path: Path):
        store, _ = self._populate_store(tmp_path)
        searcher = TranscriptSearcher(store)
        hits = searcher.search(["deploy"])
        assert len(hits) >= 1

    def test_search_sessions_grouped(self, tmp_path: Path):
        store, sid = self._populate_store(tmp_path)
        searcher = TranscriptSearcher(store)
        results = searcher.search_sessions(["deploy"])
        assert len(results) >= 1
        assert results[0].session_id == sid
        assert len(results[0].hits) >= 1

    def test_search_sessions_empty(self, tmp_path: Path):
        store = TranscriptStore(root=tmp_path)
        searcher = TranscriptSearcher(store)
        results = searcher.search_sessions(["anything"])
        assert results == []

    def test_search_sessions_summary(self, tmp_path: Path):
        store, sid = self._populate_store(tmp_path)
        searcher = TranscriptSearcher(store)
        results = searcher.search_sessions(["deploy"])
        assert results[0].summary != ""

    def test_search_in_error_entries(self, tmp_path: Path):
        store, sid = self._populate_store(tmp_path)
        searcher = TranscriptSearcher(store)
        hits = searcher.search(["timeout"], session_id=sid)
        assert len(hits) >= 1

    def test_search_skips_empty_entries(self, tmp_path: Path):
        store = TranscriptStore(root=tmp_path)
        sid = store.create_session(provider="test", model="m")
        store.add_entry(
            sid,
            TranscriptEntry(
                type="assistant",
                timestamp="2025-01-01T00:00:00",
            ),
        )
        searcher = TranscriptSearcher(store)
        hits = searcher.search(["anything"], session_id=sid)
        assert hits == []
