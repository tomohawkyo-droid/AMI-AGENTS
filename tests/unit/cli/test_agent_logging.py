"""Unit tests for ami/cli/agent_logging.py."""

import json
from unittest.mock import MagicMock, patch

from ami.cli.agent_logging import (
    MessageContent,
    TextBlock,
    TranscriptEntry,
    TranscriptLogger,
)
from ami.cli.transcript_store import TranscriptStore

EXPECTED_CONTENT_BLOCK_COUNT = 2
EXPECTED_TOKEN_COUNT = 100
EXPECTED_DURATION = 1.5
EXPECTED_LOGGED_TOKEN_COUNT = 150
EXPECTED_LOG_ENTRY_COUNT = 4


class TestTextBlock:
    """Tests for TextBlock model."""

    def test_default_type(self):
        """Test TextBlock has default type 'text'."""
        block = TextBlock(text="hello")
        assert block.type == "text"
        assert block.text == "hello"

    def test_custom_type(self):
        """Test TextBlock can have custom type."""
        block = TextBlock(type="code", text="print('hi')")
        assert block.type == "code"

    def test_serialization(self):
        """Test TextBlock serializes to JSON."""
        block = TextBlock(text="hello")
        data = block.model_dump()
        assert data == {"type": "text", "text": "hello"}


class TestMessageContent:
    """Tests for MessageContent model."""

    def test_string_content(self):
        """Test MessageContent with string content."""
        msg = MessageContent(content="hello world")
        assert msg.content == "hello world"

    def test_list_content(self):
        """Test MessageContent with list of TextBlocks."""
        blocks = [TextBlock(text="part1"), TextBlock(text="part2")]
        msg = MessageContent(content=blocks)
        assert len(msg.content) == EXPECTED_CONTENT_BLOCK_COUNT
        assert msg.content[0].text == "part1"


class TestTranscriptEntry:
    """Tests for TranscriptEntry model."""

    def test_basic_entry(self):
        """Test basic TranscriptEntry."""
        entry = TranscriptEntry(
            type="user",
            timestamp="2024-01-01T00:00:00",
        )
        assert entry.type == "user"
        assert entry.timestamp == "2024-01-01T00:00:00"
        assert entry.message is None
        assert entry.error is None
        assert entry.metadata == {}

    def test_entry_with_message(self):
        """Test TranscriptEntry with message."""
        entry = TranscriptEntry(
            type="assistant",
            timestamp="2024-01-01T00:00:00",
            message=MessageContent(content="response"),
        )
        assert entry.message is not None
        assert entry.message.content == "response"

    def test_entry_with_error(self):
        """Test TranscriptEntry with error."""
        entry = TranscriptEntry(
            type="error",
            timestamp="2024-01-01T00:00:00",
            error="Something went wrong",
        )
        assert entry.error == "Something went wrong"

    def test_entry_with_metadata(self):
        """Test TranscriptEntry with metadata."""
        entry = TranscriptEntry(
            type="assistant",
            timestamp="2024-01-01T00:00:00",
            metadata={"model": "claude", "tokens": 100},
        )
        assert entry.metadata["model"] == "claude"
        assert entry.metadata["tokens"] == EXPECTED_TOKEN_COUNT

    def test_entry_with_entry_id(self):
        """Test TranscriptEntry has entry_id field."""
        entry = TranscriptEntry(
            entry_id="test-uuid",
            type="user",
            timestamp="2024-01-01T00:00:00",
        )
        assert entry.entry_id == "test-uuid"

    def test_entry_id_auto_generated(self):
        """Test TranscriptEntry entry_id auto-generates a UUID."""
        entry = TranscriptEntry(
            type="user",
            timestamp="2024-01-01T00:00:00",
        )
        assert len(entry.entry_id) > 0
        assert "-" in entry.entry_id

    def test_json_serialization(self):
        """Test TranscriptEntry JSON serialization."""
        entry = TranscriptEntry(
            type="user",
            timestamp="2024-01-01T00:00:00",
            message=MessageContent(content="test"),
        )
        json_str = entry.model_dump_json()
        data = json.loads(json_str)
        assert data["type"] == "user"


class TestTranscriptLogger:
    """Tests for TranscriptLogger class."""

    def _make_logger(self, tmp_path):
        """Create a TranscriptLogger backed by a real TranscriptStore."""
        store = TranscriptStore(root=tmp_path)
        transcript_id = store.create_session(provider="test", model="test-model")
        return (
            TranscriptLogger(store=store, transcript_id=transcript_id),
            store,
            transcript_id,
        )

    def test_init(self, tmp_path):
        """Test TranscriptLogger initialization."""
        logger, _store, transcript_id = self._make_logger(tmp_path)
        assert logger.transcript_id == transcript_id

    def test_log_user_message(self, tmp_path):
        """Test logging a user message."""
        logger, store, transcript_id = self._make_logger(tmp_path)
        logger.log_user_message("Hello, agent!")

        entries = store.read_entries(transcript_id)
        assert len(entries) == 1
        assert entries[0].type == "user"
        assert entries[0].message is not None
        assert entries[0].message.content == "Hello, agent!"
        assert entries[0].entry_id != ""

    def test_log_assistant_message_without_metadata(self, tmp_path):
        """Test logging assistant message without metadata."""
        logger, store, transcript_id = self._make_logger(tmp_path)
        logger.log_assistant_message("Here is my response")

        entries = store.read_entries(transcript_id)
        assert len(entries) == 1
        assert entries[0].type == "assistant"
        assert entries[0].message is not None
        assert entries[0].message.content[0].text == "Here is my response"
        assert entries[0].metadata == {}

    def test_log_assistant_message_with_metadata(self, tmp_path):
        """Test logging assistant message with metadata."""
        mock_metadata = MagicMock()
        mock_metadata.session_id = "sess-123"
        mock_metadata.duration = 1.5
        mock_metadata.exit_code = 0
        mock_metadata.model = "claude"
        mock_metadata.tokens = 150

        logger, store, transcript_id = self._make_logger(tmp_path)
        logger.log_assistant_message("Response with metadata", metadata=mock_metadata)

        entries = store.read_entries(transcript_id)
        assert len(entries) == 1
        assert entries[0].metadata["session_id"] == "sess-123"
        assert entries[0].metadata["duration"] == EXPECTED_DURATION
        assert entries[0].metadata["exit_code"] == 0
        assert entries[0].metadata["model"] == "claude"
        assert entries[0].metadata["tokens"] == EXPECTED_LOGGED_TOKEN_COUNT

    def test_log_error(self, tmp_path):
        """Test logging an error."""
        logger, store, transcript_id = self._make_logger(tmp_path)
        logger.log_error("Connection timeout occurred")

        entries = store.read_entries(transcript_id)
        assert len(entries) == 1
        assert entries[0].type == "error"
        assert entries[0].error == "Connection timeout occurred"

    def test_multiple_entries(self, tmp_path):
        """Test logging multiple entries to same session."""
        logger, store, transcript_id = self._make_logger(tmp_path)
        logger.log_user_message("First message")
        logger.log_assistant_message("First response")
        logger.log_user_message("Second message")
        logger.log_assistant_message("Second response")

        entries = store.read_entries(transcript_id)
        assert len(entries) == EXPECTED_LOG_ENTRY_COUNT

        # Verify order
        assert entries[0].type == "user"
        assert entries[1].type == "assistant"
        assert entries[2].type == "user"
        assert entries[3].type == "assistant"

    def test_write_handles_error_gracefully(self, tmp_path, capsys):
        """Test _write handles errors gracefully."""
        store = TranscriptStore(root=tmp_path)
        transcript_id = store.create_session(provider="test", model="test-model")
        logger = TranscriptLogger(store=store, transcript_id=transcript_id)

        # Force add_entry to raise
        with patch.object(store, "add_entry", side_effect=OSError("disk full")):
            # Should not raise
            logger.log_user_message("Test message")

        captured = capsys.readouterr()
        assert "FAILED TO WRITE TRANSCRIPT ENTRY" in captured.err
