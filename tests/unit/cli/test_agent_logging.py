"""Unit tests for ami/cli/agent_logging.py."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from ami.cli.agent_logging import (
    MessageContent,
    TextBlock,
    TranscriptEntry,
    TranscriptLogger,
)

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

    @patch("ami.cli.agent_logging.get_config")
    def test_init(self, mock_get_config, tmp_path):
        """Test TranscriptLogger initialization."""
        mock_config = MagicMock()
        mock_config.root = tmp_path
        mock_get_config.return_value = mock_config

        logger = TranscriptLogger("test-session-123")

        assert logger.session_id == "test-session-123"
        assert logger.log_dir.exists()
        assert logger.log_file.name == "test-session-123.jsonl"

    @patch("ami.cli.agent_logging.get_config")
    def test_get_log_dir_creates_directory(self, mock_get_config, tmp_path):
        """Test _get_log_dir creates directory structure."""
        mock_config = MagicMock()
        mock_config.root = tmp_path
        mock_get_config.return_value = mock_config

        logger = TranscriptLogger("test-session")
        log_dir = logger._get_log_dir()

        assert log_dir.exists()
        # Should be under logs/transcripts/YYYY-MM-DD/
        assert "transcripts" in str(log_dir)

    @patch("ami.cli.agent_logging.get_config")
    def test_log_user_message(self, mock_get_config, tmp_path):
        """Test logging a user message."""
        mock_config = MagicMock()
        mock_config.root = tmp_path
        mock_get_config.return_value = mock_config

        logger = TranscriptLogger("test-session")
        logger.log_user_message("Hello, agent!")

        assert logger.log_file.exists()
        content = logger.log_file.read_text()
        data = json.loads(content.strip())
        assert data["type"] == "user"
        assert data["message"]["content"] == "Hello, agent!"
        assert "timestamp" in data

    @patch("ami.cli.agent_logging.get_config")
    def test_log_assistant_message_without_metadata(self, mock_get_config, tmp_path):
        """Test logging assistant message without metadata."""
        mock_config = MagicMock()
        mock_config.root = tmp_path
        mock_get_config.return_value = mock_config

        logger = TranscriptLogger("test-session")
        logger.log_assistant_message("Here is my response")

        content = logger.log_file.read_text()
        data = json.loads(content.strip())
        assert data["type"] == "assistant"
        assert data["message"]["content"][0]["text"] == "Here is my response"
        assert data["metadata"] == {}

    @patch("ami.cli.agent_logging.get_config")
    def test_log_assistant_message_with_metadata(self, mock_get_config, tmp_path):
        """Test logging assistant message with metadata."""
        mock_config = MagicMock()
        mock_config.root = tmp_path
        mock_get_config.return_value = mock_config

        # Create mock metadata
        mock_metadata = MagicMock()
        mock_metadata.session_id = "sess-123"
        mock_metadata.duration = 1.5
        mock_metadata.exit_code = 0
        mock_metadata.model = "claude"
        mock_metadata.tokens = 150

        logger = TranscriptLogger("test-session")
        logger.log_assistant_message("Response with metadata", metadata=mock_metadata)

        content = logger.log_file.read_text()
        data = json.loads(content.strip())
        assert data["metadata"]["session_id"] == "sess-123"
        assert data["metadata"]["duration"] == EXPECTED_DURATION
        assert data["metadata"]["exit_code"] == 0
        assert data["metadata"]["model"] == "claude"
        assert data["metadata"]["tokens"] == EXPECTED_LOGGED_TOKEN_COUNT

    @patch("ami.cli.agent_logging.get_config")
    def test_log_error(self, mock_get_config, tmp_path):
        """Test logging an error."""
        mock_config = MagicMock()
        mock_config.root = tmp_path
        mock_get_config.return_value = mock_config

        logger = TranscriptLogger("test-session")
        logger.log_error("Connection timeout occurred")

        content = logger.log_file.read_text()
        data = json.loads(content.strip())
        assert data["type"] == "error"
        assert data["error"] == "Connection timeout occurred"

    @patch("ami.cli.agent_logging.get_config")
    def test_multiple_entries(self, mock_get_config, tmp_path):
        """Test logging multiple entries to same file."""
        mock_config = MagicMock()
        mock_config.root = tmp_path
        mock_get_config.return_value = mock_config

        logger = TranscriptLogger("test-session")
        logger.log_user_message("First message")
        logger.log_assistant_message("First response")
        logger.log_user_message("Second message")
        logger.log_assistant_message("Second response")

        content = logger.log_file.read_text()
        lines = [line for line in content.strip().split("\n") if line]
        assert len(lines) == EXPECTED_LOG_ENTRY_COUNT

        # Verify order
        assert json.loads(lines[0])["type"] == "user"
        assert json.loads(lines[1])["type"] == "assistant"
        assert json.loads(lines[2])["type"] == "user"
        assert json.loads(lines[3])["type"] == "assistant"

    @patch("ami.cli.agent_logging.get_config")
    @patch("builtins.open", side_effect=PermissionError("Access denied"))
    @patch("sys.stderr")
    def test_append_entry_handles_write_error(
        self, mock_stderr, mock_open, mock_get_config, tmp_path
    ):
        """Test _append_entry handles write errors gracefully."""
        mock_config = MagicMock()
        mock_config.root = tmp_path
        mock_get_config.return_value = mock_config

        logger = TranscriptLogger("test-session")

        # Manually set log_file to a mock path that will fail
        logger.log_file = Path("/nonexistent/path/log.jsonl")

        # Should not raise, but print error
        logger.log_user_message("Test message")

        # Error should be printed to stderr
        mock_stderr.write.assert_called()
