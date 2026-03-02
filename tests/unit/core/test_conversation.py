"""Unit tests for ami/core/conversation.py."""

from pathlib import Path
from typing import NamedTuple

import pytest

from ami.cli.transcript_store import TranscriptStore
from ami.core.conversation import (
    ConversationEntry,
    ConversationTranscript,
    EntryMetadata,
    EntryOrigin,
    EntryRole,
)

# Test constants
EXPECTED_PAIR = 2
EXPECTED_THREE = 3
EXPECTED_FOUR = 4
EXPECTED_CONTEXT_LINES = 4
EXPECTED_PROMPT_SECTIONS = 3
TOKENS_100 = 100
TOKENS_50 = 50
TOKENS_42 = 42
DURATION_1_5 = 1.5
COST_0_01 = 0.01
TURN_2 = 2
TURN_3 = 3


class _Env(NamedTuple):
    """Shared test environment."""

    store: TranscriptStore
    sid: str
    transcript: ConversationTranscript


@pytest.fixture
def env(tmp_path: Path) -> _Env:
    """Create a fresh TranscriptStore + session + ConversationTranscript."""
    store = TranscriptStore(root=tmp_path)
    sid = store.create_session(provider="test", model="m")
    transcript = ConversationTranscript(store, sid)
    return _Env(store, sid, transcript)


class TestEntryRole:
    """Tests for EntryRole enum."""

    def test_values(self):
        assert EntryRole.SYSTEM.value == "system"
        assert EntryRole.USER.value == "user"
        assert EntryRole.ASSISTANT.value == "assistant"
        assert EntryRole.TOOL_CALL.value == "tool_call"
        assert EntryRole.TOOL_RESULT.value == "tool_result"
        assert EntryRole.ERROR.value == "error"
        assert EntryRole.INTERNAL.value == "internal"

    def test_string_comparison(self):
        assert EntryRole.USER == "user"
        assert EntryRole.ASSISTANT == "assistant"


class TestEntryOrigin:
    """Tests for EntryOrigin enum."""

    def test_values(self):
        assert EntryOrigin.HUMAN.value == "human"
        assert EntryOrigin.AGENT.value == "agent"
        assert EntryOrigin.SYSTEM.value == "system"
        assert EntryOrigin.TOOL.value == "tool"


class TestEntryMetadata:
    """Tests for EntryMetadata model."""

    def test_defaults_all_none(self):
        meta = EntryMetadata()
        assert meta.model is None
        assert meta.tokens is None
        assert meta.cost_usd is None
        assert meta.exit_code is None

    def test_with_values(self):
        meta = EntryMetadata(
            model="opus",
            provider="claude",
            tokens=TOKENS_100,
            duration=DURATION_1_5,
            cost_usd=COST_0_01,
        )
        assert meta.model == "opus"
        assert meta.tokens == TOKENS_100
        assert meta.duration == DURATION_1_5


class TestConversationEntry:
    """Tests for ConversationEntry model."""

    def test_defaults(self):
        entry = ConversationEntry(
            role=EntryRole.USER,
            origin=EntryOrigin.HUMAN,
            content="hello",
        )
        assert entry.role == EntryRole.USER
        assert entry.origin == EntryOrigin.HUMAN
        assert entry.content == "hello"
        assert entry.turn == 0
        assert entry.parent_id is None
        assert len(entry.entry_id) > 0
        assert len(entry.timestamp) > 0

    def test_with_metadata(self):
        meta = EntryMetadata(tokens=TOKENS_50)
        entry = ConversationEntry(
            role=EntryRole.ASSISTANT,
            origin=EntryOrigin.AGENT,
            content="response",
            metadata=meta,
        )
        assert entry.metadata.tokens == TOKENS_50

    def test_with_parent_id(self):
        entry = ConversationEntry(
            role=EntryRole.TOOL_RESULT,
            origin=EntryOrigin.TOOL,
            content="output",
            parent_id="parent-123",
        )
        assert entry.parent_id == "parent-123"

    def test_json_roundtrip(self):
        entry = ConversationEntry(
            role=EntryRole.ASSISTANT,
            origin=EntryOrigin.AGENT,
            content="hello world",
            turn=TURN_3,
            metadata=EntryMetadata(tokens=TOKENS_42),
        )
        restored = ConversationEntry.model_validate_json(entry.model_dump_json())
        assert restored.role == EntryRole.ASSISTANT
        assert restored.content == "hello world"
        assert restored.turn == TURN_3
        assert restored.metadata.tokens == TOKENS_42


class TestConversationTranscriptWriting:
    """Tests for ConversationTranscript add_* methods."""

    def test_add_system(self, env: _Env):
        entry = env.transcript.add_system("You are an agent.")
        assert entry.role == EntryRole.SYSTEM
        assert entry.origin == EntryOrigin.SYSTEM
        assert entry.content == "You are an agent."
        assert entry.turn == 0

    def test_add_user(self, env: _Env):
        entry = env.transcript.add_user("what is 2+2?")
        assert entry.role == EntryRole.USER
        assert entry.origin == EntryOrigin.HUMAN
        assert entry.turn == 1

    def test_add_user_increments_turn(self, env: _Env):
        e1 = env.transcript.add_user("first")
        e2 = env.transcript.add_user("second")
        assert e1.turn == 1
        assert e2.turn == TURN_2

    def test_add_assistant(self, env: _Env):
        env.transcript.add_user("q")
        meta = EntryMetadata(tokens=TOKENS_100, model="opus")
        entry = env.transcript.add_assistant("the answer is 4", metadata=meta)
        assert entry.role == EntryRole.ASSISTANT
        assert entry.origin == EntryOrigin.AGENT
        assert entry.metadata.tokens == TOKENS_100
        assert entry.turn == 1

    def test_add_tool_call(self, env: _Env):
        env.transcript.add_user("run ls")
        assistant = env.transcript.add_assistant("running ls")
        entry = env.transcript.add_tool_call("ls -la", parent_id=assistant.entry_id)
        assert entry.role == EntryRole.TOOL_CALL
        assert entry.origin == EntryOrigin.AGENT
        assert entry.parent_id == assistant.entry_id

    def test_add_tool_result(self, env: _Env):
        env.transcript.add_user("run ls")
        assistant = env.transcript.add_assistant("running ls")
        call = env.transcript.add_tool_call("ls", parent_id=assistant.entry_id)
        entry = env.transcript.add_tool_result(
            "file1\nfile2",
            parent_id=call.entry_id,
            exit_code=0,
        )
        assert entry.role == EntryRole.TOOL_RESULT
        assert entry.origin == EntryOrigin.TOOL
        assert entry.parent_id == call.entry_id
        assert entry.metadata.exit_code == 0

    def test_add_error(self, env: _Env):
        entry = env.transcript.add_error("timeout")
        assert entry.role == EntryRole.ERROR
        assert entry.origin == EntryOrigin.SYSTEM

    def test_add_internal(self, env: _Env):
        entry = env.transcript.add_internal("Continue.")
        assert entry.role == EntryRole.INTERNAL
        assert entry.origin == EntryOrigin.SYSTEM

    def test_entries_property(self, env: _Env):
        env.transcript.add_system("sys")
        env.transcript.add_user("q")
        env.transcript.add_assistant("a")
        assert len(env.transcript.entries) == EXPECTED_THREE

    def test_entries_returns_copy(self, env: _Env):
        env.transcript.add_user("q")
        entries = env.transcript.entries
        entries.clear()
        assert len(env.transcript.entries) == 1


class TestConversationTranscriptPrompt:
    """Tests for build_prompt method."""

    def test_system_at_top(self, env: _Env):
        env.transcript.add_system("You are an agent.")
        prompt = env.transcript.build_prompt()
        assert prompt.startswith("You are an agent.")

    def test_assistant_labeled(self, env: _Env):
        env.transcript.add_system("sys")
        env.transcript.add_user("q")
        env.transcript.add_assistant("the answer is 4")
        prompt = env.transcript.build_prompt()
        assert "[Agent]\nthe answer is 4" in prompt

    def test_tool_result_labeled(self, env: _Env):
        env.transcript.add_system("sys")
        env.transcript.add_user("q")
        assistant = env.transcript.add_assistant("running ls")
        call = env.transcript.add_tool_call("ls", parent_id=assistant.entry_id)
        env.transcript.add_tool_result("file1", parent_id=call.entry_id)
        prompt = env.transcript.build_prompt()
        assert "[Tool]\nTool Output:\nfile1" in prompt

    def test_tool_call_excluded(self, env: _Env):
        env.transcript.add_system("sys")
        env.transcript.add_user("q")
        assistant = env.transcript.add_assistant("running ls")
        env.transcript.add_tool_call("ls -la", parent_id=assistant.entry_id)
        prompt = env.transcript.build_prompt()
        assert "ls -la" not in prompt

    def test_user_excluded_from_prompt(self, env: _Env):
        env.transcript.add_system("sys")
        env.transcript.add_user("my question")
        env.transcript.add_assistant("answer")
        prompt = env.transcript.build_prompt()
        assert "[User]" not in prompt
        assert "[Instruction]" not in prompt

    def test_internal_labeled_system(self, env: _Env):
        env.transcript.add_system("sys")
        env.transcript.add_internal("Continue.")
        prompt = env.transcript.build_prompt()
        assert "[System]\nContinue." in prompt

    def test_error_labeled(self, env: _Env):
        env.transcript.add_system("sys")
        env.transcript.add_error("boom")
        prompt = env.transcript.build_prompt()
        assert "[Error]\nboom" in prompt


class TestConversationTranscriptContextSummary:
    """Tests for build_context_summary method."""

    def test_empty_when_no_history(self, env: _Env):
        env.transcript.add_user("q")
        env.transcript.add_assistant("a")
        assert env.transcript.build_context_summary() == ""

    def test_includes_user_and_assistant(self, tmp_path: Path):
        store = TranscriptStore(root=tmp_path)
        sid = store.create_session(provider="test", model="m")
        store.add_entry(
            sid,
            ConversationEntry(
                role=EntryRole.USER,
                origin=EntryOrigin.HUMAN,
                content="what is 2+2?",
                turn=1,
            ),
        )
        store.add_entry(
            sid,
            ConversationEntry(
                role=EntryRole.ASSISTANT,
                origin=EntryOrigin.AGENT,
                content="2 + 2 = 4.",
                turn=1,
            ),
        )
        transcript = ConversationTranscript(store, sid)
        transcript.load_from_store()
        assert transcript.has_history() is True
        summary = transcript.build_context_summary()
        assert "## Previous Conversation" in summary
        assert "[User]: what is 2+2?" in summary
        assert "[Assistant]: 2 + 2 = 4." in summary

    def test_excludes_system_entries(self, tmp_path: Path):
        store = TranscriptStore(root=tmp_path)
        sid = store.create_session(provider="test", model="m")
        store.add_entry(
            sid,
            ConversationEntry(
                role=EntryRole.SYSTEM,
                origin=EntryOrigin.SYSTEM,
                content="secret system prompt",
            ),
        )
        store.add_entry(
            sid,
            ConversationEntry(
                role=EntryRole.USER,
                origin=EntryOrigin.HUMAN,
                content="q",
                turn=1,
            ),
        )
        transcript = ConversationTranscript(store, sid)
        transcript.load_from_store()
        assert "secret system prompt" not in transcript.build_context_summary()

    def test_excludes_tool_entries(self, tmp_path: Path):
        store = TranscriptStore(root=tmp_path)
        sid = store.create_session(provider="test", model="m")
        store.add_entry(
            sid,
            ConversationEntry(
                role=EntryRole.TOOL_RESULT,
                origin=EntryOrigin.TOOL,
                content="file1\nfile2",
                turn=1,
            ),
        )
        transcript = ConversationTranscript(store, sid)
        transcript.load_from_store()
        assert "file1" not in transcript.build_context_summary()


class TestConversationTranscriptPersistence:
    """Tests for load_from_store and persistence."""

    def test_load_from_store(self, tmp_path: Path):
        store = TranscriptStore(root=tmp_path)
        sid = store.create_session(provider="test", model="m")
        store.add_entry(
            sid,
            ConversationEntry(
                role=EntryRole.USER,
                origin=EntryOrigin.HUMAN,
                content="q1",
                turn=1,
            ),
        )
        store.add_entry(
            sid,
            ConversationEntry(
                role=EntryRole.ASSISTANT,
                origin=EntryOrigin.AGENT,
                content="a1",
                turn=1,
            ),
        )
        transcript = ConversationTranscript(store, sid)
        transcript.load_from_store()
        assert len(transcript.entries) == EXPECTED_PAIR
        assert transcript.has_history() is True

    def test_load_restores_turn_counter(self, tmp_path: Path):
        store = TranscriptStore(root=tmp_path)
        sid = store.create_session(provider="test", model="m")
        store.add_entry(
            sid,
            ConversationEntry(
                role=EntryRole.USER,
                origin=EntryOrigin.HUMAN,
                content="q1",
                turn=1,
            ),
        )
        store.add_entry(
            sid,
            ConversationEntry(
                role=EntryRole.USER,
                origin=EntryOrigin.HUMAN,
                content="q2",
                turn=TURN_2,
            ),
        )
        transcript = ConversationTranscript(store, sid)
        transcript.load_from_store()
        entry = transcript.add_user("q3")
        assert entry.turn == TURN_3

    def test_has_history_false_when_empty(self, tmp_path: Path):
        store = TranscriptStore(root=tmp_path)
        sid = store.create_session(provider="test", model="m")
        transcript = ConversationTranscript(store, sid)
        transcript.load_from_store()
        assert transcript.has_history() is False

    def test_entries_persisted_to_store(self, env: _Env):
        env.transcript.add_user("hello")
        env.transcript.add_assistant("hi there")
        entries = env.store.read_entries(env.sid)
        assert len(entries) == EXPECTED_PAIR
        assert entries[0].content == "hello"
        assert entries[1].content == "hi there"

    def test_parent_chain_preserved(self, env: _Env):
        env.transcript.add_user("run ls")
        assistant = env.transcript.add_assistant("running ls")
        call = env.transcript.add_tool_call("ls", parent_id=assistant.entry_id)
        result = env.transcript.add_tool_result("file1", parent_id=call.entry_id)
        entries = env.store.read_entries(env.sid)
        assert len(entries) == EXPECTED_FOUR
        assert entries[EXPECTED_PAIR].parent_id == assistant.entry_id
        assert entries[EXPECTED_THREE].parent_id == call.entry_id
        assert result.parent_id == call.entry_id
