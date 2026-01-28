"""Integration tests for agent logging, env utils, and process utils.

Exercises: cli/agent_logging.py, cli/env_utils.py, cli/process_utils.py
"""

import json
import subprocess
import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from ami.cli.agent_logging import (
    MessageContent,
    TextBlock,
    TranscriptEntry,
    TranscriptLogger,
)
from ami.cli.env_utils import get_unprivileged_env
from ami.cli.exceptions import (
    AgentCommandNotFoundError,
    AgentExecutionError,
    AgentTimeoutError,
)
from ami.cli.process_utils import (
    handle_first_output_timeout,
    handle_process_completion,
    handle_process_exit,
    start_streaming_process,
)
from ami.cli.transcript_store import TranscriptStore
from ami.core.config import _ConfigSingleton
from ami.types.api import ProviderMetadata

# ---------------------------------------------------------------------------
# Named constants for magic values used in assertions
# ---------------------------------------------------------------------------
EXPECTED_BLOCK_COUNT = 2
EXPECTED_DURATION = 2.0
EXPECTED_ENTRY_COUNT = 3


@pytest.fixture(autouse=True)
def _ensure_config(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("AMI_TEST_MODE", "1")
    _ConfigSingleton.instance = None
    yield
    _ConfigSingleton.instance = None


# ---------------------------------------------------------------------------
# Transcript data models
# ---------------------------------------------------------------------------


class TestTranscriptModels:
    """Test Pydantic models for transcript logging."""

    def test_text_block(self):
        block = TextBlock(text="hello")
        assert block.type == "text"
        assert block.text == "hello"

    def test_message_content_string(self):
        msg = MessageContent(content="simple string")
        assert msg.content == "simple string"

    def test_message_content_blocks(self):
        blocks = [TextBlock(text="part1"), TextBlock(text="part2")]
        msg = MessageContent(content=blocks)
        assert len(msg.content) == EXPECTED_BLOCK_COUNT

    def test_transcript_entry_user(self):
        entry = TranscriptEntry(
            type="user",
            timestamp="2025-01-01T00:00:00",
            message=MessageContent(content="hello"),
        )
        assert entry.type == "user"
        assert entry.error is None
        assert entry.metadata == {}

    def test_transcript_entry_error(self):
        entry = TranscriptEntry(
            type="error",
            timestamp="2025-01-01T00:00:00",
            error="something broke",
        )
        assert entry.error == "something broke"
        assert entry.message is None

    def test_transcript_entry_with_metadata(self):
        entry = TranscriptEntry(
            type="assistant",
            timestamp="2025-01-01T00:00:00",
            metadata={"session_id": "s1", "duration": 1.5},
        )
        assert entry.metadata["session_id"] == "s1"

    def test_entry_to_json(self):
        entry = TranscriptEntry(
            type="user",
            timestamp="2025-01-01T00:00:00",
            message=MessageContent(content="test"),
        )
        json_str = entry.model_dump_json()
        parsed = json.loads(json_str)
        assert parsed["type"] == "user"


# ---------------------------------------------------------------------------
# TranscriptLogger with real filesystem
# ---------------------------------------------------------------------------


class TestTranscriptLogger:
    """Test TranscriptLogger writes entries via TranscriptStore."""

    def _make_logger(self, tmp_path: Path):
        """Create a logger backed by a real store in tmp_path."""
        store = TranscriptStore(root=tmp_path / "transcripts")
        transcript_id = store.create_session(provider="test", model="test-model")
        logger = TranscriptLogger(store=store, transcript_id=transcript_id)
        return logger, store, transcript_id

    def test_creates_session_directory(self, tmp_path: Path):
        """Logger should create session directory via store."""
        _logger, store, transcript_id = self._make_logger(tmp_path)
        session_dir = store.root / transcript_id
        assert session_dir.exists()
        assert (session_dir / "session.json").exists()

    def test_log_user_message(self, tmp_path: Path):
        logger, store, transcript_id = self._make_logger(tmp_path)
        logger.log_user_message("Hello agent")

        entries = store.read_entries(transcript_id)
        assert len(entries) == 1
        assert entries[0].type == "user"
        assert entries[0].message is not None
        assert entries[0].message.content == "Hello agent"

    def test_log_assistant_message(self, tmp_path: Path):
        meta = ProviderMetadata(session_id="s1", duration=2.0, exit_code=0)
        logger, store, transcript_id = self._make_logger(tmp_path)
        logger.log_assistant_message("Response text", metadata=meta)

        entries = store.read_entries(transcript_id)
        assert len(entries) == 1
        assert entries[0].type == "assistant"
        assert entries[0].metadata["session_id"] == "s1"
        assert entries[0].metadata["duration"] == EXPECTED_DURATION

    def test_log_error(self, tmp_path: Path):
        logger, store, transcript_id = self._make_logger(tmp_path)
        logger.log_error("Something went wrong")

        entries = store.read_entries(transcript_id)
        assert len(entries) == 1
        assert entries[0].type == "error"
        assert entries[0].error == "Something went wrong"

    def test_multiple_entries(self, tmp_path: Path):
        logger, store, transcript_id = self._make_logger(tmp_path)
        logger.log_user_message("First")
        logger.log_assistant_message("Second")
        logger.log_error("Third")

        entries = store.read_entries(transcript_id)
        assert len(entries) == EXPECTED_ENTRY_COUNT


# ---------------------------------------------------------------------------
# env_utils
# ---------------------------------------------------------------------------


class TestEnvUtils:
    """Test get_unprivileged_env with various configurations."""

    def test_no_unprivileged_user_returns_none(self):
        mock_config = MagicMock()
        mock_config.get_value.return_value = None
        result = get_unprivileged_env(mock_config)
        assert result is None

    def test_empty_unprivileged_user_returns_none(self):
        mock_config = MagicMock()
        mock_config.get_value.return_value = ""
        result = get_unprivileged_env(mock_config)
        assert result is None

    def test_nonexistent_user_returns_env(self):
        """When user doesn't exist, falls back to current env."""
        mock_config = MagicMock()
        mock_config.get_value.return_value = "nonexistent_user_xyz_12345"
        result = get_unprivileged_env(mock_config)
        # Should return some env (fallback behavior)
        assert result is not None
        assert "PYTHONUNBUFFERED" in result


# ---------------------------------------------------------------------------
# process_utils
# ---------------------------------------------------------------------------


class TestProcessUtils:
    """Test process utility functions."""

    def test_start_streaming_process_real_command(self):
        proc = start_streaming_process(
            cmd=["echo", "hello"],
            stdin_data=None,
            cwd=None,
        )
        try:
            stdout, _stderr = proc.communicate(timeout=5)
            assert proc.returncode == 0
            assert "hello" in stdout
        finally:
            if proc.poll() is None:
                proc.kill()

    def test_start_streaming_process_nonexistent_binary(self):
        with pytest.raises(AgentCommandNotFoundError):
            start_streaming_process(
                cmd=["nonexistent_binary_xyz_12345"],
                stdin_data=None,
                cwd=None,
            )

    def test_handle_first_output_timeout_within_limit(self):
        started = time.time()
        # Should not raise (just started, well within timeout)
        handle_first_output_timeout(started, ["cmd"], 60)

    def test_handle_first_output_timeout_expired(self):
        started = time.time() - 100  # Started 100 seconds ago
        with pytest.raises(AgentTimeoutError):
            handle_first_output_timeout(started, ["cmd"], 10)

    def test_handle_first_output_timeout_none(self):
        # Should not raise when timeout is None
        handle_first_output_timeout(time.time() - 1000, ["cmd"], None)

    def test_handle_process_exit_success(self):
        proc = subprocess.Popen(
            ["echo", "done"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        proc.wait()
        result = handle_process_exit(proc)
        assert "done" in result

    def test_handle_process_exit_failure(self):
        proc = subprocess.Popen(
            ["false"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        proc.wait()
        with pytest.raises(AgentExecutionError):
            handle_process_exit(proc)

    def test_handle_process_completion(self):
        proc = subprocess.Popen(
            ["echo", "output"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        proc.wait()
        started = time.time() - 1.0
        result, meta = handle_process_completion(proc, ["echo"], started, "sess-1")
        assert "output" in result
        assert meta is not None
        assert meta.session_id == "sess-1"
        assert meta.duration >= 0
