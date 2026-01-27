"""Unit tests for interactive mode handlers."""

import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ami.cli.exceptions import AgentError, AgentExecutionError
from ami.cli.mode_handlers import (
    get_latest_session_id,
    get_user_confirmation,
    mode_interactive_editor,
    mode_print,
    mode_query,
)

# Test constants
EXPECTED_EDITOR_RUN_CALLS = 2
EXPECTED_AGENT_EXEC_ERROR_EXIT_CODE = 2


class TestInteractiveHelpers:
    """Tests for interactive helper functions."""

    @patch("ami.cli.mode_handlers.confirm")
    def test_get_user_confirmation_yes(self, mock_confirm):
        """Test confirmation with 'y' (True)."""
        mock_confirm.return_value = True
        assert get_user_confirmation("test command") is True
        mock_confirm.assert_called_once()
        args, kwargs = mock_confirm.call_args
        assert args[0] == "test command"
        assert kwargs["title"] == "Execute Command?"

    @patch("ami.cli.mode_handlers.confirm")
    def test_get_user_confirmation_no(self, mock_confirm):
        """Test confirmation with 'n' (False)."""
        mock_confirm.return_value = False
        assert get_user_confirmation("test command") is False
        mock_confirm.assert_called_once()

    @patch("ami.cli.mode_handlers.confirm")
    def test_get_user_confirmation_cancel(self, mock_confirm):
        """Test confirmation cancellation (exception propagation)."""
        mock_confirm.side_effect = KeyboardInterrupt()
        with pytest.raises(KeyboardInterrupt):
            get_user_confirmation("test command")


class TestModeInteractiveEditor:
    """Tests for mode_interactive_editor."""

    @patch("ami.cli.timer_utils.TimerDisplay")
    @patch("sys.stdin.isatty", return_value=False)
    @patch("ami.cli.mode_handlers.TextEditor")
    @patch("ami.cli.mode_handlers.AgentFactory.create_bootloader")
    @patch("ami.cli.mode_handlers.display_final_output")
    def test_interactive_editor_success(
        self,
        mock_display,
        MockCreateBootloader,
        MockTextEditor,
        mock_isatty,
        MockTimerDisplay,
    ):
        """Test successful execution flow."""
        # Setup mocks
        mock_editor = MockTextEditor.return_value
        # First call returns instruction, second call returns None to break the loop
        mock_editor.run.side_effect = ["Do something", None]
        mock_editor.lines = ["Do something"]

        mock_agent = MockCreateBootloader.return_value
        mock_agent.run.return_value = ("Output", "sess-id")

        # Execute
        exit_code = mode_interactive_editor()

        # Verify
        assert exit_code == 0
        assert mock_editor.run.call_count == EXPECTED_EDITOR_RUN_CALLS
        mock_display.assert_called_with(["Do something"], "✅ Sent to agent")
        mock_agent.run.assert_called_once()
        call_ctx = mock_agent.run.call_args[0][0]  # First positional arg is RunContext
        assert call_ctx.instruction == "Do something"
        assert call_ctx.input_func == get_user_confirmation

    @patch("ami.cli.timer_utils.TimerDisplay")
    @patch("sys.stdin.isatty", return_value=False)
    @patch("ami.cli.mode_handlers.TextEditor")
    @patch("ami.cli.mode_handlers.AgentFactory.create_bootloader")
    def test_interactive_editor_cancel(
        self, MockCreateBootloader, MockTextEditor, mock_isatty, MockTimerDisplay
    ):
        """Test user cancellation in editor."""
        mock_editor = MockTextEditor.return_value
        mock_editor.run.return_value = None  # None means cancelled

        exit_code = mode_interactive_editor()

        assert exit_code == 0
        MockCreateBootloader.assert_not_called()

    @patch("ami.cli.timer_utils.TimerDisplay")
    @patch("sys.stdin.isatty", return_value=False)
    @patch("ami.cli.mode_handlers.TextEditor")
    @patch("ami.cli.mode_handlers.AgentFactory.create_bootloader")
    def test_interactive_editor_empty(
        self, MockCreateBootloader, MockTextEditor, mock_isatty, MockTimerDisplay
    ):
        """Test empty input."""
        mock_editor = MockTextEditor.return_value
        mock_editor.run.return_value = "   "  # Empty/whitespace

        exit_code = mode_interactive_editor()

        assert exit_code == 0
        MockCreateBootloader.assert_not_called()

    @patch("ami.cli.timer_utils.TimerDisplay")
    @patch("sys.stdin.isatty", return_value=False)
    @patch("ami.cli.mode_handlers.TextEditor")
    @patch("ami.cli.mode_handlers.AgentFactory.create_bootloader")
    def test_interactive_editor_agent_error(
        self, MockCreateBootloader, MockTextEditor, mock_isatty, MockTimerDisplay
    ):
        """Test exception during agent execution."""
        mock_editor = MockTextEditor.return_value
        mock_editor.run.side_effect = ["Do task", None]

        mock_agent = MockCreateBootloader.return_value
        mock_agent.run.side_effect = Exception("Agent crashed")

        with patch.object(sys.stderr, "write") as mock_stderr:
            exit_code = mode_interactive_editor()

            assert exit_code == 1
            mock_stderr.assert_any_call("Error calling agent: Agent crashed\n")


class TestGetLatestSessionId:
    """Tests for get_latest_session_id function."""

    @patch("ami.cli.mode_handlers.get_config")
    def test_returns_none_when_transcripts_dir_not_exists(self, mock_get_config):
        """Test returns None when transcripts directory doesn't exist."""
        mock_config = MagicMock()
        mock_config.root = Path("/nonexistent")
        mock_get_config.return_value = mock_config

        result = get_latest_session_id()

        assert result is None

    @patch("ami.cli.mode_handlers.get_config")
    def test_returns_none_when_no_jsonl_files(self, mock_get_config):
        """Test returns None when no .jsonl files exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_config = MagicMock()
            mock_config.root = Path(tmpdir)
            mock_get_config.return_value = mock_config

            # Create transcripts dir but no files
            transcripts_dir = Path(tmpdir) / "logs" / "transcripts"
            transcripts_dir.mkdir(parents=True)

            result = get_latest_session_id()

            assert result is None

    @patch("ami.cli.mode_handlers.get_config")
    def test_returns_newest_session_id(self, mock_get_config):
        """Test returns stem of the newest .jsonl file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_config = MagicMock()
            mock_config.root = Path(tmpdir)
            mock_get_config.return_value = mock_config

            transcripts_dir = Path(tmpdir) / "logs" / "transcripts"
            transcripts_dir.mkdir(parents=True)

            # Create two files with different timestamps
            old_file = transcripts_dir / "old-session.jsonl"
            old_file.write_text("{}")
            time.sleep(0.1)  # Ensure different mtime

            new_file = transcripts_dir / "new-session.jsonl"
            new_file.write_text("{}")

            result = get_latest_session_id()

            assert result == "new-session"

    @patch("ami.cli.mode_handlers.get_config")
    def test_returns_none_on_exception(self, mock_get_config):
        """Test returns None when exception occurs."""
        mock_get_config.side_effect = Exception("Config error")

        result = get_latest_session_id()

        assert result is None


class TestModeQuery:
    """Tests for mode_query function."""

    @patch("ami.cli.mode_handlers.get_agent_cli")
    @patch("ami.cli.mode_handlers.wrap_text_in_box")
    @patch.object(sys.stdout, "write")
    @patch.object(sys.stdout, "flush")
    def test_mode_query_success(self, mock_flush, mock_write, mock_wrap, mock_get_cli):
        """Test successful query execution."""
        mock_wrap.return_value = "boxed text"
        mock_cli = MagicMock()
        mock_cli.run_print.return_value = ("output", MagicMock())
        mock_get_cli.return_value = mock_cli

        result = mode_query("What is Python?")

        assert result == 0
        mock_cli.run_print.assert_called_once()

    @patch("ami.cli.mode_handlers.get_agent_cli")
    @patch("ami.cli.mode_handlers.wrap_text_in_box")
    @patch.object(sys.stdout, "write")
    @patch.object(sys.stdout, "flush")
    def test_mode_query_keyboard_interrupt(
        self, mock_flush, mock_write, mock_wrap, mock_get_cli
    ):
        """Test query cancellation with Ctrl+C."""
        mock_wrap.return_value = "boxed text"
        mock_cli = MagicMock()
        mock_cli.run_print.side_effect = KeyboardInterrupt()
        mock_get_cli.return_value = mock_cli

        result = mode_query("What is Python?")

        assert result == 0

    @patch("ami.cli.mode_handlers.get_agent_cli")
    @patch("ami.cli.mode_handlers.wrap_text_in_box")
    @patch.object(sys.stdout, "write")
    @patch.object(sys.stdout, "flush")
    def test_mode_query_exception(
        self, mock_flush, mock_write, mock_wrap, mock_get_cli
    ):
        """Test query execution with exception."""
        mock_wrap.return_value = "boxed text"
        mock_cli = MagicMock()
        mock_cli.run_print.side_effect = Exception("Query failed")
        mock_get_cli.return_value = mock_cli

        result = mode_query("What is Python?")

        assert result == 1


class TestModePrint:
    """Tests for mode_print function."""

    def test_mode_print_invalid_path(self):
        """Test mode_print with non-existent path."""
        result = mode_print("/nonexistent/path.txt")

        assert result == 1

    @patch("ami.cli.mode_handlers.get_agent_cli")
    @patch.object(sys.stdin, "read")
    def test_mode_print_success(self, mock_stdin_read, mock_get_cli):
        """Test successful print execution."""
        mock_stdin_read.return_value = ""
        mock_cli = MagicMock()
        mock_cli.run_print.return_value = ("output", MagicMock())
        mock_get_cli.return_value = mock_cli

        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("Test instruction")
            temp_path = f.name

        try:
            result = mode_print(temp_path)

            assert result == 0
            mock_cli.run_print.assert_called_once()
        finally:
            Path(temp_path).unlink()

    @patch("ami.cli.mode_handlers.get_agent_cli")
    @patch.object(sys.stdin, "read")
    @patch.object(sys.stderr, "write")
    def test_mode_print_agent_execution_error(
        self, mock_stderr, mock_stdin_read, mock_get_cli
    ):
        """Test mode_print with AgentExecutionError."""
        mock_stdin_read.return_value = ""
        mock_cli = MagicMock()
        # AgentExecutionError takes (exit_code, stdout, stderr, cmd)
        mock_cli.run_print.side_effect = AgentExecutionError(
            exit_code=2, stdout="", stderr="Exec failed", cmd=["test"]
        )
        mock_get_cli.return_value = mock_cli

        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("Test instruction")
            temp_path = f.name

        try:
            result = mode_print(temp_path)

            assert result == EXPECTED_AGENT_EXEC_ERROR_EXIT_CODE
        finally:
            Path(temp_path).unlink()

    @patch("ami.cli.mode_handlers.get_agent_cli")
    @patch.object(sys.stdin, "read")
    @patch.object(sys.stderr, "write")
    def test_mode_print_agent_error(self, mock_stderr, mock_stdin_read, mock_get_cli):
        """Test mode_print with AgentError."""
        mock_stdin_read.return_value = ""
        mock_cli = MagicMock()
        mock_cli.run_print.side_effect = AgentError("Agent error")
        mock_get_cli.return_value = mock_cli

        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("Test instruction")
            temp_path = f.name

        try:
            result = mode_print(temp_path)

            assert result == 1
        finally:
            Path(temp_path).unlink()

    @patch("ami.cli.mode_handlers.get_agent_cli")
    @patch.object(sys.stdin, "read")
    @patch.object(sys.stderr, "write")
    def test_mode_print_unexpected_error(
        self, mock_stderr, mock_stdin_read, mock_get_cli
    ):
        """Test mode_print with unexpected exception."""
        mock_stdin_read.return_value = ""
        mock_cli = MagicMock()
        mock_cli.run_print.side_effect = Exception("Unexpected error")
        mock_get_cli.return_value = mock_cli

        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("Test instruction")
            temp_path = f.name

        try:
            result = mode_print(temp_path)

            assert result == 1
        finally:
            Path(temp_path).unlink()
