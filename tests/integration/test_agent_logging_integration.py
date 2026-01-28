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
from ami.core.config import Config, _ConfigSingleton
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
    """Test TranscriptLogger creates directories and writes entries."""

    def test_creates_log_directory(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """Logger should create date-based log directory."""
        monkeypatch.setenv("AMI_TEST_MODE", "1")
        _ConfigSingleton.instance = None
        config = Config()
        # Override root to use tmp_path for log isolation
        original_root = config.root
        config.root = tmp_path
        _ConfigSingleton.instance = config
        try:
            logger = TranscriptLogger(session_id="test-session")
            assert logger.log_dir.exists()
            assert "transcripts" in str(logger.log_dir)
        finally:
            config.root = original_root
            _ConfigSingleton.instance = None

    def test_log_user_message(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("AMI_TEST_MODE", "1")
        _ConfigSingleton.instance = None
        config = Config()
        original_root = config.root
        config.root = tmp_path
        _ConfigSingleton.instance = config
        try:
            logger = TranscriptLogger(session_id="user-test")
            logger.log_user_message("Hello agent")
            assert logger.log_file.exists()
            entries = logger.log_file.read_text().strip().split("\n")
            assert len(entries) == 1
            data = json.loads(entries[0])
            assert data["type"] == "user"
            assert data["message"]["content"] == "Hello agent"
        finally:
            config.root = original_root
            _ConfigSingleton.instance = None

    def test_log_assistant_message(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setenv("AMI_TEST_MODE", "1")
        _ConfigSingleton.instance = None
        config = Config()
        original_root = config.root
        config.root = tmp_path
        _ConfigSingleton.instance = config
        try:
            meta = ProviderMetadata(session_id="s1", duration=2.0, exit_code=0)
            logger = TranscriptLogger(session_id="assist-test")
            logger.log_assistant_message("Response text", metadata=meta)
            entries = logger.log_file.read_text().strip().split("\n")
            data = json.loads(entries[0])
            assert data["type"] == "assistant"
            assert data["metadata"]["session_id"] == "s1"
            assert data["metadata"]["duration"] == EXPECTED_DURATION
        finally:
            config.root = original_root
            _ConfigSingleton.instance = None

    def test_log_error(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("AMI_TEST_MODE", "1")
        _ConfigSingleton.instance = None
        config = Config()
        original_root = config.root
        config.root = tmp_path
        _ConfigSingleton.instance = config
        try:
            logger = TranscriptLogger(session_id="error-test")
            logger.log_error("Something went wrong")
            entries = logger.log_file.read_text().strip().split("\n")
            data = json.loads(entries[0])
            assert data["type"] == "error"
            assert data["error"] == "Something went wrong"
        finally:
            config.root = original_root
            _ConfigSingleton.instance = None

    def test_multiple_entries(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("AMI_TEST_MODE", "1")
        _ConfigSingleton.instance = None
        config = Config()
        original_root = config.root
        config.root = tmp_path
        _ConfigSingleton.instance = config
        try:
            logger = TranscriptLogger(session_id="multi-test")
            logger.log_user_message("First")
            logger.log_assistant_message("Second")
            logger.log_error("Third")
            entries = logger.log_file.read_text().strip().split("\n")
            assert len(entries) == EXPECTED_ENTRY_COUNT
        finally:
            config.root = original_root
            _ConfigSingleton.instance = None


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
