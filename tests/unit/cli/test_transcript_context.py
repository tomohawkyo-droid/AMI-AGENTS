"""Unit tests for TranscriptContextBuilder."""

from pathlib import Path

from ami.cli.agent_logging import MessageContent, TextBlock, TranscriptEntry
from ami.cli.transcript_context import (
    TranscriptContextBuilder,
    _extract_text,
    _format_entry,
    _truncate,
)
from ami.cli.transcript_store import TranscriptStore

# Test constants
EXPECTED_TRUNCATED_LEN = 2003  # 2000 chars + "..."
EXPECTED_HEADER_PLUS_5 = 6  # 1 header line + 5 entry lines


class TestHelpers:
    """Tests for module-level helper functions."""

    def test_extract_text_string(self):
        entry = TranscriptEntry(
            type="user",
            timestamp="2025-01-01T00:00:00",
            message=MessageContent(content="hello"),
        )
        assert _extract_text(entry) == "hello"

    def test_extract_text_blocks(self):
        entry = TranscriptEntry(
            type="user",
            timestamp="2025-01-01T00:00:00",
            message=MessageContent(content=[TextBlock(text="a"), TextBlock(text="b")]),
        )
        assert _extract_text(entry) == "a b"

    def test_extract_text_no_message(self):
        entry = TranscriptEntry(
            type="error",
            timestamp="2025-01-01T00:00:00",
            error="broke",
        )
        assert _extract_text(entry) == ""

    def test_truncate_short(self):
        assert _truncate("short", 100) == "short"

    def test_truncate_long(self):
        text = "a" * 3000
        result = _truncate(text, 2000)
        assert len(result) == EXPECTED_TRUNCATED_LEN
        assert result.endswith("...")

    def test_truncate_exact_limit(self):
        text = "a" * 2000
        assert _truncate(text, 2000) == text

    def test_format_entry_user(self):
        entry = TranscriptEntry(
            type="user",
            timestamp="2025-01-01T00:00:00",
            message=MessageContent(content="hello"),
        )
        result = _format_entry(entry)
        assert result == "[User]: hello"

    def test_format_entry_assistant(self):
        entry = TranscriptEntry(
            type="assistant",
            timestamp="2025-01-01T00:00:00",
            message=MessageContent(content="response"),
        )
        result = _format_entry(entry)
        assert result == "[Assistant]: response"

    def test_format_entry_error(self):
        entry = TranscriptEntry(
            type="error",
            timestamp="2025-01-01T00:00:00",
            error="crashed",
        )
        result = _format_entry(entry)
        assert result == "[Error]: crashed"

    def test_format_entry_error_none(self):
        entry = TranscriptEntry(
            type="error",
            timestamp="2025-01-01T00:00:00",
        )
        result = _format_entry(entry)
        assert result == "[Error]: (unknown)"

    def test_format_entry_no_truncate(self):
        long_text = "x" * 3000
        entry = TranscriptEntry(
            type="user",
            timestamp="2025-01-01T00:00:00",
            message=MessageContent(content=long_text),
        )
        result = _format_entry(entry, truncate=False)
        assert long_text in result

    def test_format_entry_truncate(self):
        long_text = "x" * 3000
        entry = TranscriptEntry(
            type="user",
            timestamp="2025-01-01T00:00:00",
            message=MessageContent(content=long_text),
        )
        result = _format_entry(entry, truncate=True)
        assert "..." in result


class TestTranscriptContextBuilder:
    """Tests for TranscriptContextBuilder."""

    def _make_store_with_entries(
        self, tmp_path: Path, count: int = 3
    ) -> tuple[TranscriptStore, str]:
        store = TranscriptStore(root=tmp_path)
        sid = store.create_session(provider="test", model="m")
        for i in range(count):
            entry_type = "user" if i % 2 == 0 else "assistant"
            store.add_entry(
                sid,
                TranscriptEntry(
                    type=entry_type,
                    timestamp=f"2025-01-01T00:00:{i:02d}",
                    message=MessageContent(content=f"message {i}"),
                ),
            )
        return store, sid

    def test_build_context_empty(self, tmp_path: Path):
        store = TranscriptStore(root=tmp_path)
        sid = store.create_session(provider="test", model="m")
        builder = TranscriptContextBuilder(store)
        assert builder.build_context(sid) == ""

    def test_build_context_with_entries(self, tmp_path: Path):
        store, sid = self._make_store_with_entries(tmp_path, count=3)
        builder = TranscriptContextBuilder(store)
        context = builder.build_context(sid)
        assert "## Previous Conversation" in context
        assert "[User]:" in context
        assert "[Assistant]:" in context

    def test_build_context_respects_window_size(self, tmp_path: Path):
        store, sid = self._make_store_with_entries(tmp_path, count=20)
        builder = TranscriptContextBuilder(store, window_size=5)
        context = builder.build_context(sid)
        lines = context.split("\n")
        assert len(lines) == EXPECTED_HEADER_PLUS_5

    def test_build_replay_empty(self, tmp_path: Path):
        store = TranscriptStore(root=tmp_path)
        sid = store.create_session(provider="test", model="m")
        builder = TranscriptContextBuilder(store)
        assert builder.build_replay(sid) == ""

    def test_build_replay_all_entries(self, tmp_path: Path):
        store, sid = self._make_store_with_entries(tmp_path, count=5)
        builder = TranscriptContextBuilder(store)
        replay = builder.build_replay(sid)
        assert "## Full Session Replay" in replay
        lines = replay.split("\n")
        assert len(lines) == EXPECTED_HEADER_PLUS_5

    def test_build_replay_no_truncation(self, tmp_path: Path):
        store = TranscriptStore(root=tmp_path)
        sid = store.create_session(provider="test", model="m")
        long_text = "x" * 3000
        store.add_entry(
            sid,
            TranscriptEntry(
                type="user",
                timestamp="2025-01-01T00:00:00",
                message=MessageContent(content=long_text),
            ),
        )
        builder = TranscriptContextBuilder(store)
        replay = builder.build_replay(sid)
        assert long_text in replay
