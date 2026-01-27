"""Unit tests for ami/cli/process_utils.py."""

import subprocess
import time
from unittest.mock import MagicMock, patch

import pytest

from ami.cli.exceptions import (
    AgentCommandNotFoundError,
    AgentExecutionError,
    AgentTimeoutError,
)
from ami.cli.process_utils import (
    ESC_KEY_CODE,
    handle_first_output_logging,
    handle_first_output_timeout,
    handle_process_completion,
    handle_process_exit,
    read_streaming_line,
    start_streaming_process,
)

EXPECTED_ESC_KEY_CODE = 27


class TestStartStreamingProcess:
    """Tests for start_streaming_process function."""

    @patch("ami.cli.process_utils.subprocess.Popen")
    @patch("ami.cli.process_utils.get_unprivileged_env")
    @patch("ami.cli.process_utils.get_config")
    def test_starts_process_successfully(
        self, mock_get_config, mock_get_env, mock_popen
    ):
        """Test successful process start."""
        mock_get_config.return_value = MagicMock()
        mock_get_env.return_value = {"HOME": "/tmp/test"}
        mock_process = MagicMock()
        mock_popen.return_value = mock_process

        result = start_streaming_process(["echo", "test"], None, None)

        assert result == mock_process
        mock_popen.assert_called_once()

    @patch("ami.cli.process_utils.subprocess.Popen", side_effect=FileNotFoundError)
    @patch("ami.cli.process_utils.get_unprivileged_env")
    @patch("ami.cli.process_utils.get_config")
    def test_raises_command_not_found(self, mock_get_config, mock_get_env, mock_popen):
        """Test raises AgentCommandNotFoundError when command not found."""
        mock_get_config.return_value = MagicMock()
        mock_get_env.return_value = None

        with pytest.raises(AgentCommandNotFoundError):
            start_streaming_process(["nonexistent"], None, None)

    @patch("ami.cli.process_utils.get_unprivileged_env")
    @patch("ami.cli.process_utils.get_config")
    def test_raises_for_invalid_command_format(self, mock_get_config, mock_get_env):
        """Test raises ValueError for invalid command format."""
        mock_get_config.return_value = MagicMock()
        mock_get_env.return_value = None

        with pytest.raises(ValueError, match="invalid command format"):
            start_streaming_process("not a list", None, None)

    @patch("ami.cli.process_utils.get_unprivileged_env")
    @patch("ami.cli.process_utils.get_config")
    def test_raises_for_unsafe_path(self, mock_get_config, mock_get_env):
        """Test raises ValueError for unsafe command path."""
        mock_get_config.return_value = MagicMock()
        mock_get_env.return_value = None

        with pytest.raises(ValueError, match="unsafe command path"):
            start_streaming_process(["../unsafe/cmd"], None, None)

    @patch("ami.cli.process_utils.subprocess.Popen")
    @patch("ami.cli.process_utils.get_unprivileged_env")
    @patch("ami.cli.process_utils.get_config")
    def test_passes_stdin_data(self, mock_get_config, mock_get_env, mock_popen):
        """Test stdin_data is passed to process."""
        mock_get_config.return_value = MagicMock()
        mock_get_env.return_value = None

        start_streaming_process(["cat"], "input data", None)

        call_kwargs = mock_popen.call_args.kwargs
        assert call_kwargs["stdin"] == subprocess.PIPE


class TestReadStreamingLine:
    """Tests for read_streaming_line function."""

    @patch("ami.cli.process_utils.select.select")
    def test_reads_line_successfully(self, mock_select):
        """Test successful line read."""
        mock_process = MagicMock()
        mock_process.stdout.readline.return_value = "test line\n"
        mock_select.return_value = ([mock_process.stdout], [], [])

        line, timed_out = read_streaming_line(mock_process, 5.0, ["cmd"])

        assert line == "test line"
        assert timed_out is False

    @patch("ami.cli.process_utils.select.select")
    def test_returns_timeout(self, mock_select):
        """Test returns timeout flag when select times out."""
        mock_process = MagicMock()
        mock_select.return_value = ([], [], [])

        line, timed_out = read_streaming_line(mock_process, 1.0, ["cmd"])

        assert line is None
        assert timed_out is True

    @patch("ami.cli.process_utils.select.select")
    def test_returns_none_on_empty_line(self, mock_select):
        """Test returns None when readline returns empty."""
        mock_process = MagicMock()
        mock_process.stdout.readline.return_value = ""
        mock_select.return_value = ([mock_process.stdout], [], [])

        line, timed_out = read_streaming_line(mock_process, 5.0, ["cmd"])

        assert line is None
        assert timed_out is False


class TestHandleFirstOutputTimeout:
    """Tests for handle_first_output_timeout function."""

    def test_raises_timeout_when_exceeded(self):
        """Test raises AgentTimeoutError when timeout exceeded."""
        started_at = time.time() - 100  # 100 seconds ago

        with pytest.raises(AgentTimeoutError):
            handle_first_output_timeout(started_at, ["cmd"], timeout=10)

    def test_no_raise_when_within_timeout(self):
        """Test doesn't raise when within timeout."""
        started_at = time.time()

        # Should not raise
        handle_first_output_timeout(started_at, ["cmd"], timeout=60)

    def test_no_raise_when_timeout_none(self):
        """Test doesn't raise when timeout is None."""
        started_at = time.time() - 1000

        # Should not raise
        handle_first_output_timeout(started_at, ["cmd"], timeout=None)


class TestHandleProcessExit:
    """Tests for handle_process_exit function."""

    def test_returns_stdout_on_success(self):
        """Test returns stdout when process succeeds."""
        mock_process = MagicMock()
        mock_process.communicate.return_value = ("output", "")
        mock_process.returncode = 0

        result = handle_process_exit(mock_process)

        assert result == "output"

    def test_raises_on_non_zero_exit(self):
        """Test raises AgentExecutionError on non-zero exit."""
        mock_process = MagicMock()
        mock_process.communicate.return_value = ("out", "err")
        mock_process.returncode = 1

        with pytest.raises(AgentExecutionError):
            handle_process_exit(mock_process)


class TestHandleFirstOutputLogging:
    """Tests for handle_first_output_logging function."""

    @patch("ami.cli.process_utils.logger")
    def test_logs_with_config(self, mock_logger):
        """Test logs when config provided."""
        mock_config = MagicMock()
        mock_config.session_id = "test-session"
        mock_config.timeout = 60

        handle_first_output_logging(mock_config)

        mock_logger.info.assert_called_once()

    @patch("ami.cli.process_utils.logger")
    def test_no_log_without_config(self, mock_logger):
        """Test doesn't log when config is None."""
        handle_first_output_logging(None)

        mock_logger.info.assert_not_called()

    @patch("ami.cli.process_utils.logger")
    def test_uses_unknown_session_id(self, mock_logger):
        """Test uses 'unknown' when session_id is None."""
        mock_config = MagicMock()
        mock_config.session_id = None
        mock_config.timeout = 60

        handle_first_output_logging(mock_config)

        mock_logger.info.assert_called_once()


class TestHandleProcessCompletion:
    """Tests for handle_process_completion function."""

    @patch("ami.cli.process_utils.logger")
    def test_returns_output_and_metadata_on_success(self, mock_logger):
        """Test returns output and metadata when process succeeds."""
        mock_process = MagicMock()
        mock_process.poll.return_value = 0
        mock_process.communicate.return_value = ("output", "")
        mock_process.returncode = 0

        started_at = time.time() - 5
        output, metadata = handle_process_completion(
            mock_process, ["cmd"], started_at, "test-session"
        )

        assert output == "output"
        assert metadata is not None
        assert metadata.session_id == "test-session"
        assert metadata.exit_code == 0

    @patch("ami.cli.process_utils.logger")
    def test_raises_on_non_zero_exit(self, mock_logger):
        """Test raises AgentExecutionError on non-zero exit."""
        mock_process = MagicMock()
        mock_process.poll.return_value = 1
        mock_process.communicate.return_value = ("out", "err")
        mock_process.returncode = 1

        with pytest.raises(AgentExecutionError):
            handle_process_completion(mock_process, ["cmd"], time.time(), "session")

    @patch("ami.cli.process_utils.logger")
    def test_calls_communicate_when_process_running(self, mock_logger):
        """Test calls communicate when process is still running."""
        mock_process = MagicMock()
        mock_process.poll.return_value = None  # Still running
        mock_process.communicate.return_value = ("output", "")
        mock_process.returncode = 0

        output, _metadata = handle_process_completion(
            mock_process, ["cmd"], time.time(), "session"
        )

        mock_process.communicate.assert_called()
        assert output == "output"


class TestConstants:
    """Tests for module constants."""

    def test_esc_key_code_value(self):
        """Test ESC_KEY_CODE has correct value."""
        assert ESC_KEY_CODE == EXPECTED_ESC_KEY_CODE
