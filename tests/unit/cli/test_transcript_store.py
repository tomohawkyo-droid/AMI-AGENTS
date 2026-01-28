"""Unit tests for TranscriptStore."""

from pathlib import Path

from ami.cli.agent_logging import MessageContent, TranscriptEntry
from ami.cli.transcript_store import SessionMetadata, TranscriptStore

# Test constants
EXPECTED_ROUNDTRIP_ENTRY_COUNT = 5
EXPECTED_SESSION_COUNT = 2
EXPECTED_ENTRY_PAIR = 2
EXPECTED_RECENT_COUNT = 2


class TestSessionMetadata:
    """Tests for SessionMetadata model."""

    def test_defaults(self):
        meta = SessionMetadata(
            session_id="s1",
            created="2025-01-01T00:00:00",
            last_active="2025-01-01T00:00:00",
            provider="test",
            model="test-model",
        )
        assert meta.status == "active"
        assert meta.entry_count == 0
        assert meta.summary == ""

    def test_roundtrip_json(self):
        meta = SessionMetadata(
            session_id="s1",
            created="2025-01-01T00:00:00",
            last_active="2025-01-01T00:00:00",
            provider="claude",
            model="opus",
            status="paused",
            entry_count=5,
            summary="hello world",
        )
        restored = SessionMetadata.model_validate_json(meta.model_dump_json())
        assert restored.session_id == "s1"
        assert restored.status == "paused"
        assert restored.entry_count == EXPECTED_ROUNDTRIP_ENTRY_COUNT


class TestTranscriptStoreLifecycle:
    """Tests for session creation, reading, updating, and listing."""

    def test_create_session(self, tmp_path: Path):
        store = TranscriptStore(root=tmp_path)
        sid = store.create_session(provider="claude", model="opus")
        assert (tmp_path / sid / "session.json").exists()

    def test_create_session_custom_id(self, tmp_path: Path):
        store = TranscriptStore(root=tmp_path)
        sid = store.create_session(
            provider="claude", model="opus", session_id="custom-id"
        )
        assert sid == "custom-id"
        assert (tmp_path / "custom-id" / "session.json").exists()

    def test_get_session(self, tmp_path: Path):
        store = TranscriptStore(root=tmp_path)
        sid = store.create_session(provider="qwen", model="coder")
        meta = store.get_session(sid)
        assert meta is not None
        assert meta.provider == "qwen"
        assert meta.model == "coder"
        assert meta.status == "active"

    def test_get_session_not_found(self, tmp_path: Path):
        store = TranscriptStore(root=tmp_path)
        assert store.get_session("nonexistent") is None

    def test_get_session_corrupt_json(self, tmp_path: Path):
        store = TranscriptStore(root=tmp_path)
        sid = "corrupt"
        session_dir = tmp_path / sid
        session_dir.mkdir()
        (session_dir / "session.json").write_text("not valid json", encoding="utf-8")
        assert store.get_session(sid) is None

    def test_update_session(self, tmp_path: Path):
        store = TranscriptStore(root=tmp_path)
        sid = store.create_session(provider="test", model="m")
        store.update_session(sid, status="paused", summary="updated")
        meta = store.get_session(sid)
        assert meta is not None
        assert meta.status == "paused"
        assert meta.summary == "updated"

    def test_update_session_ignores_invalid_fields(self, tmp_path: Path):
        store = TranscriptStore(root=tmp_path)
        sid = store.create_session(provider="test", model="m")
        store.update_session(sid, bogus_field="ignored")
        meta = store.get_session(sid)
        assert meta is not None
        assert not hasattr(meta, "bogus_field")

    def test_update_nonexistent_session(self, tmp_path: Path):
        store = TranscriptStore(root=tmp_path)
        # Should not raise
        store.update_session("nonexistent", status="paused")

    def test_list_sessions_empty(self, tmp_path: Path):
        store = TranscriptStore(root=tmp_path)
        assert store.list_sessions() == []

    def test_list_sessions(self, tmp_path: Path):
        store = TranscriptStore(root=tmp_path)
        store.create_session(provider="a", model="m", session_id="aaa")
        store.create_session(provider="b", model="m", session_id="bbb")
        sessions = store.list_sessions()
        assert len(sessions) == EXPECTED_SESSION_COUNT

    def test_list_sessions_filtered_by_status(self, tmp_path: Path):
        store = TranscriptStore(root=tmp_path)
        sid1 = store.create_session(provider="a", model="m")
        store.create_session(provider="b", model="m")
        store.update_session(sid1, status="paused")
        paused = store.list_sessions(status="paused")
        assert len(paused) == 1
        assert paused[0].session_id == sid1

    def test_list_sessions_skips_non_dirs(self, tmp_path: Path):
        store = TranscriptStore(root=tmp_path)
        store.create_session(provider="a", model="m")
        # Create a stray file in root
        (tmp_path / "stray.txt").write_text("ignore me", encoding="utf-8")
        sessions = store.list_sessions()
        assert len(sessions) == 1

    def test_list_sessions_skips_dirs_without_session_json(self, tmp_path: Path):
        store = TranscriptStore(root=tmp_path)
        (tmp_path / "empty-dir").mkdir()
        sessions = store.list_sessions()
        assert len(sessions) == 0

    def test_get_resumable_session(self, tmp_path: Path):
        store = TranscriptStore(root=tmp_path)
        sid = store.create_session(provider="a", model="m")
        store.update_session(sid, status="paused")
        resumable = store.get_resumable_session()
        assert resumable is not None
        assert resumable.session_id == sid

    def test_get_resumable_session_none(self, tmp_path: Path):
        store = TranscriptStore(root=tmp_path)
        store.create_session(provider="a", model="m")
        assert store.get_resumable_session() is None


class TestTranscriptStoreEntries:
    """Tests for entry CRUD operations."""

    def _make_entry(self, entry_type: str = "user", text: str = "hello"):
        return TranscriptEntry(
            type=entry_type,
            timestamp="2025-01-01T00:00:00",
            message=MessageContent(content=text),
        )

    def _make_error_entry(self, error: str = "boom"):
        return TranscriptEntry(
            type="error",
            timestamp="2025-01-01T00:00:01",
            error=error,
        )

    def test_add_and_read_entry(self, tmp_path: Path):
        store = TranscriptStore(root=tmp_path)
        sid = store.create_session(provider="test", model="m")
        entry = self._make_entry()
        entry_id = store.add_entry(sid, entry)
        assert len(entry_id) > 0
        assert (tmp_path / sid / f"{entry_id}.json").exists()

    def test_read_entries(self, tmp_path: Path):
        store = TranscriptStore(root=tmp_path)
        sid = store.create_session(provider="test", model="m")
        store.add_entry(sid, self._make_entry(text="first"))
        store.add_entry(sid, self._make_entry(entry_type="assistant", text="second"))
        entries = store.read_entries(sid)
        assert len(entries) == EXPECTED_ENTRY_PAIR

    def test_read_entries_nonexistent_session(self, tmp_path: Path):
        store = TranscriptStore(root=tmp_path)
        assert store.read_entries("nonexistent") == []

    def test_read_entries_skips_session_json(self, tmp_path: Path):
        store = TranscriptStore(root=tmp_path)
        sid = store.create_session(provider="test", model="m")
        store.add_entry(sid, self._make_entry())
        entries = store.read_entries(sid)
        # Should not include session.json
        assert all(e.type in ("user", "assistant", "error") for e in entries)

    def test_read_entries_skips_corrupt_entry(self, tmp_path: Path):
        store = TranscriptStore(root=tmp_path)
        sid = store.create_session(provider="test", model="m")
        store.add_entry(sid, self._make_entry())
        # Write a corrupt entry file
        (tmp_path / sid / "corrupt.json").write_text("bad json", encoding="utf-8")
        entries = store.read_entries(sid)
        assert len(entries) == 1

    def test_read_recent(self, tmp_path: Path):
        store = TranscriptStore(root=tmp_path)
        sid = store.create_session(provider="test", model="m")
        for i in range(5):
            entry = TranscriptEntry(
                type="user",
                timestamp=f"2025-01-01T00:00:{i:02d}",
                message=MessageContent(content=f"msg-{i}"),
            )
            store.add_entry(sid, entry)
        recent = store.read_recent(sid, n=EXPECTED_RECENT_COUNT)
        assert len(recent) == EXPECTED_RECENT_COUNT

    def test_read_recent_fewer_than_n(self, tmp_path: Path):
        store = TranscriptStore(root=tmp_path)
        sid = store.create_session(provider="test", model="m")
        store.add_entry(sid, self._make_entry())
        recent = store.read_recent(sid, n=10)
        assert len(recent) == 1

    def test_add_entry_updates_metadata(self, tmp_path: Path):
        store = TranscriptStore(root=tmp_path)
        sid = store.create_session(provider="test", model="m")
        store.add_entry(sid, self._make_entry(text="first message"))
        meta = store.get_session(sid)
        assert meta is not None
        assert meta.entry_count == 1
        assert meta.summary == "first message"

    def test_add_entry_does_not_overwrite_summary(self, tmp_path: Path):
        store = TranscriptStore(root=tmp_path)
        sid = store.create_session(provider="test", model="m")
        store.add_entry(sid, self._make_entry(text="first"))
        store.add_entry(sid, self._make_entry(text="second"))
        meta = store.get_session(sid)
        assert meta is not None
        assert meta.summary == "first"
        assert meta.entry_count == EXPECTED_ENTRY_PAIR

    def test_add_error_entry_no_summary(self, tmp_path: Path):
        store = TranscriptStore(root=tmp_path)
        sid = store.create_session(provider="test", model="m")
        store.add_entry(sid, self._make_error_entry())
        meta = store.get_session(sid)
        assert meta is not None
        assert meta.summary == ""
        assert meta.entry_count == 1

    def test_add_entry_write_failure(self, tmp_path: Path, capsys):
        store = TranscriptStore(root=tmp_path)
        sid = store.create_session(provider="test", model="m")
        # Make session dir read-only to trigger write failure
        session_dir = tmp_path / sid
        session_dir.chmod(0o444)
        try:
            entry = self._make_entry()
            entry_id = store.add_entry(sid, entry)
            # Should return entry_id even on failure
            assert len(entry_id) > 0
        finally:
            session_dir.chmod(0o755)
