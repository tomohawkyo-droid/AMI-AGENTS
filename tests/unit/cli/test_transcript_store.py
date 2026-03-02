"""Unit tests for TranscriptStore."""

from pathlib import Path

from ami.cli.transcript_store import SessionMetadata, TranscriptStore
from ami.core.conversation import (
    ConversationEntry,
    EntryMetadata,
    EntryOrigin,
    EntryRole,
)

# Test constants
EXPECTED_ROUNDTRIP_ENTRY_COUNT = 5
EXPECTED_SESSION_COUNT = 2
EXPECTED_ENTRY_PAIR = 2
EXPECTED_RECENT_COUNT = 2


def _make_entry(
    role: EntryRole = EntryRole.USER,
    text: str = "hello",
    tokens: int | None = None,
) -> ConversationEntry:
    return ConversationEntry(
        role=role,
        origin=EntryOrigin.HUMAN if role == EntryRole.USER else EntryOrigin.AGENT,
        content=text,
        metadata=EntryMetadata(tokens=tokens),
    )


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
        assert meta.turn_count == 0
        assert meta.total_tokens == 0
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

    def test_delete_session(self, tmp_path: Path):
        store = TranscriptStore(root=tmp_path)
        sid = store.create_session(provider="test", model="m")
        assert (tmp_path / sid).is_dir()
        assert store.delete_session(sid) is True
        assert not (tmp_path / sid).exists()
        assert store.get_session(sid) is None

    def test_delete_session_nonexistent(self, tmp_path: Path):
        store = TranscriptStore(root=tmp_path)
        assert store.delete_session("nonexistent") is False

    def test_create_session_with_cwd(self, tmp_path: Path):
        store = TranscriptStore(root=tmp_path)
        sid = store.create_session(provider="a", model="m", cwd="/tmp/test/project")
        meta = store.get_session(sid)
        assert meta is not None
        assert meta.cwd == "/tmp/test/project"

    def test_create_session_cwd_defaults_empty(self, tmp_path: Path):
        store = TranscriptStore(root=tmp_path)
        sid = store.create_session(provider="a", model="m")
        meta = store.get_session(sid)
        assert meta is not None
        assert meta.cwd == ""

    def test_list_sessions_filtered_by_cwd(self, tmp_path: Path):
        store = TranscriptStore(root=tmp_path)
        store.create_session(provider="a", model="m", cwd="/project/frontend")
        store.create_session(provider="b", model="m", cwd="/project/backend")
        store.create_session(provider="c", model="m", cwd="/project/frontend")

        frontend = store.list_sessions(cwd="/project/frontend")
        expected_frontend = 2
        assert len(frontend) == expected_frontend
        backend = store.list_sessions(cwd="/project/backend")
        expected_backend = 1
        assert len(backend) == expected_backend

    def test_list_sessions_cwd_none_returns_all(self, tmp_path: Path):
        store = TranscriptStore(root=tmp_path)
        store.create_session(provider="a", model="m", cwd="/project/frontend")
        store.create_session(provider="b", model="m", cwd="/project/backend")
        all_sessions = store.list_sessions(cwd=None)
        expected_count = 2
        assert len(all_sessions) == expected_count

    def test_get_resumable_session_filtered_by_cwd(self, tmp_path: Path):
        store = TranscriptStore(root=tmp_path)
        sid_fe = store.create_session(provider="a", model="m", cwd="/project/frontend")
        sid_be = store.create_session(provider="b", model="m", cwd="/project/backend")
        store.update_session(sid_fe, status="paused")
        store.update_session(sid_be, status="paused")

        resumable = store.get_resumable_session(cwd="/project/frontend")
        assert resumable is not None
        assert resumable.session_id == sid_fe

    def test_get_resumable_session_cwd_no_match(self, tmp_path: Path):
        store = TranscriptStore(root=tmp_path)
        sid = store.create_session(provider="a", model="m", cwd="/project/backend")
        store.update_session(sid, status="paused")
        assert store.get_resumable_session(cwd="/project/frontend") is None

    def test_delete_session_removes_from_listing(self, tmp_path: Path):
        store = TranscriptStore(root=tmp_path)
        sid = store.create_session(provider="test", model="m")
        store.delete_session(sid)
        assert all(s.session_id != sid for s in store.list_sessions())


class TestPruneSessions:
    """Tests for prune_sessions method."""

    def test_prunes_old_sessions(self, tmp_path: Path):
        store = TranscriptStore(root=tmp_path)
        sid = store.create_session(provider="a", model="m")
        store.update_session(sid, last_active="2020-01-01T00:00:00+00:00")
        deleted = store.prune_sessions(retention_days=90)
        assert deleted == 1
        assert store.get_session(sid) is None

    def test_keeps_recent_sessions(self, tmp_path: Path):
        store = TranscriptStore(root=tmp_path)
        sid = store.create_session(provider="a", model="m")
        deleted = store.prune_sessions(retention_days=90)
        assert deleted == 0
        assert store.get_session(sid) is not None

    def test_returns_zero_on_empty_store(self, tmp_path: Path):
        store = TranscriptStore(root=tmp_path)
        assert store.prune_sessions(retention_days=90) == 0

    def test_prunes_selectively(self, tmp_path: Path):
        store = TranscriptStore(root=tmp_path)
        old_sid = store.create_session(provider="a", model="m")
        new_sid = store.create_session(provider="b", model="m")
        store.update_session(old_sid, last_active="2020-01-01T00:00:00+00:00")
        deleted = store.prune_sessions(retention_days=90)
        assert deleted == 1
        assert store.get_session(old_sid) is None
        assert store.get_session(new_sid) is not None


class TestTranscriptStoreEntries:
    """Tests for JSONL entry CRUD operations."""

    def test_add_and_read_entry(self, tmp_path: Path):
        store = TranscriptStore(root=tmp_path)
        sid = store.create_session(provider="test", model="m")
        entry = _make_entry()
        entry_id = store.add_entry(sid, entry)
        assert len(entry_id) > 0
        assert (tmp_path / sid / "transcript.jsonl").exists()

    def test_read_entries(self, tmp_path: Path):
        store = TranscriptStore(root=tmp_path)
        sid = store.create_session(provider="test", model="m")
        store.add_entry(sid, _make_entry(text="first"))
        store.add_entry(sid, _make_entry(role=EntryRole.ASSISTANT, text="second"))
        entries = store.read_entries(sid)
        assert len(entries) == EXPECTED_ENTRY_PAIR

    def test_read_entries_nonexistent_session(self, tmp_path: Path):
        store = TranscriptStore(root=tmp_path)
        assert store.read_entries("nonexistent") == []

    def test_read_entries_preserves_content(self, tmp_path: Path):
        store = TranscriptStore(root=tmp_path)
        sid = store.create_session(provider="test", model="m")
        store.add_entry(sid, _make_entry(text="hello world"))
        entries = store.read_entries(sid)
        assert len(entries) == 1
        assert entries[0].content == "hello world"
        assert entries[0].role == EntryRole.USER

    def test_read_entries_skips_corrupt_lines(self, tmp_path: Path):
        store = TranscriptStore(root=tmp_path)
        sid = store.create_session(provider="test", model="m")
        store.add_entry(sid, _make_entry())
        # Append a corrupt line to the JSONL
        jsonl = tmp_path / sid / "transcript.jsonl"
        with open(jsonl, "a", encoding="utf-8") as f:
            f.write("bad json line\n")
        entries = store.read_entries(sid)
        assert len(entries) == 1

    def test_read_recent(self, tmp_path: Path):
        store = TranscriptStore(root=tmp_path)
        sid = store.create_session(provider="test", model="m")
        for i in range(5):
            store.add_entry(sid, _make_entry(text=f"msg-{i}"))
        recent = store.read_recent(sid, n=EXPECTED_RECENT_COUNT)
        assert len(recent) == EXPECTED_RECENT_COUNT

    def test_read_recent_fewer_than_n(self, tmp_path: Path):
        store = TranscriptStore(root=tmp_path)
        sid = store.create_session(provider="test", model="m")
        store.add_entry(sid, _make_entry())
        recent = store.read_recent(sid, n=10)
        assert len(recent) == 1

    def test_add_entry_updates_metadata(self, tmp_path: Path):
        store = TranscriptStore(root=tmp_path)
        sid = store.create_session(provider="test", model="m")
        store.add_entry(sid, _make_entry(text="first message"))
        meta = store.get_session(sid)
        assert meta is not None
        assert meta.entry_count == 1
        assert meta.summary == "first message"
        assert meta.turn_count == 1

    def test_add_entry_does_not_overwrite_summary(self, tmp_path: Path):
        store = TranscriptStore(root=tmp_path)
        sid = store.create_session(provider="test", model="m")
        store.add_entry(sid, _make_entry(text="first"))
        store.add_entry(sid, _make_entry(text="second"))
        meta = store.get_session(sid)
        assert meta is not None
        assert meta.summary == "first"
        assert meta.entry_count == EXPECTED_ENTRY_PAIR

    def test_add_error_entry_no_summary(self, tmp_path: Path):
        store = TranscriptStore(root=tmp_path)
        sid = store.create_session(provider="test", model="m")
        store.add_entry(
            sid,
            ConversationEntry(
                role=EntryRole.ERROR,
                origin=EntryOrigin.SYSTEM,
                content="boom",
            ),
        )
        meta = store.get_session(sid)
        assert meta is not None
        assert meta.summary == ""
        assert meta.entry_count == 1

    def test_add_entry_accumulates_tokens(self, tmp_path: Path):
        store = TranscriptStore(root=tmp_path)
        sid = store.create_session(provider="test", model="m")
        expected_tokens = 150
        store.add_entry(sid, _make_entry(text="q1", tokens=100))
        store.add_entry(
            sid,
            _make_entry(role=EntryRole.ASSISTANT, text="a1", tokens=50),
        )
        meta = store.get_session(sid)
        assert meta is not None
        assert meta.total_tokens == expected_tokens

    def test_add_entry_write_failure(self, tmp_path: Path, capsys):
        store = TranscriptStore(root=tmp_path)
        sid = store.create_session(provider="test", model="m")
        session_dir = tmp_path / sid
        session_dir.chmod(0o444)
        try:
            entry = _make_entry()
            entry_id = store.add_entry(sid, entry)
            assert len(entry_id) > 0
        finally:
            session_dir.chmod(0o755)
