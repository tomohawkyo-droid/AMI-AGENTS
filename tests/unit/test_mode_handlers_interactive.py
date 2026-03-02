"""Unit tests for interactive mode handlers."""

import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ami.cli.mode_handlers import (
    get_latest_session_id,
    get_user_confirmation,
    mode_interactive_editor,
    mode_print,
    mode_query,
)
from ami.core.bootloader_agent import AgentRunResult

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
    @patch("ami.cli.mode_handlers.confirm", return_value=False)
    @patch("ami.cli.mode_handlers.TranscriptStore")
    @patch("ami.cli.mode_handlers.TextEditor")
    @patch("ami.cli.mode_handlers.AgentFactory.create_bootloader")
    def test_interactive_editor_success(self, *mocks):
        """Test successful execution flow."""
        MockCreateBootloader, MockTextEditor, MockTranscriptStore = mocks[:3]

        # Setup mocks
        mock_editor = MockTextEditor.return_value
        # First call returns instruction, second call returns None to break the loop
        mock_editor.run.side_effect = ["Do something", None]
        mock_editor.lines = ["Do something"]

        mock_store = MockTranscriptStore.return_value
        mock_store.get_resumable_session.return_value = None
        mock_store.create_session.return_value = "test-transcript-id"

        mock_agent = MockCreateBootloader.return_value
        mock_agent.run.return_value = AgentRunResult("Output", "sess-id")

        # Execute
        exit_code = mode_interactive_editor()

        # Verify
        assert exit_code == 0
        assert mock_editor.run.call_count == EXPECTED_EDITOR_RUN_CALLS
        mock_agent.run.assert_called_once()
        call_ctx = mock_agent.run.call_args[0][0]  # First positional arg is RunContext
        assert call_ctx.instruction == "Do something"
        assert call_ctx.transcript_id == "test-transcript-id"
        assert call_ctx.input_func == get_user_confirmation

    @patch("ami.cli.timer_utils.TimerDisplay")
    @patch("sys.stdin.isatty", return_value=False)
    @patch("ami.cli.mode_handlers.confirm", return_value=False)
    @patch("ami.cli.mode_handlers.TranscriptStore")
    @patch("ami.cli.mode_handlers.TextEditor")
    @patch("ami.cli.mode_handlers.AgentFactory.create_bootloader")
    def test_interactive_editor_cancel(
        self,
        MockCreateBootloader,
        MockTextEditor,
        *mocks,
    ):
        """Test user cancellation in editor."""
        mock_editor = MockTextEditor.return_value
        mock_editor.run.return_value = None  # None means cancelled

        exit_code = mode_interactive_editor()

        assert exit_code == 0
        # create_bootloader is called once during mode_interactive_editor init
        MockCreateBootloader.assert_called_once()

    @patch("ami.cli.timer_utils.TimerDisplay")
    @patch("sys.stdin.isatty", return_value=False)
    @patch("ami.cli.mode_handlers.confirm", return_value=False)
    @patch("ami.cli.mode_handlers.TranscriptStore")
    @patch("ami.cli.mode_handlers.TextEditor")
    @patch("ami.cli.mode_handlers.AgentFactory.create_bootloader")
    def test_interactive_editor_empty(
        self,
        MockCreateBootloader,
        MockTextEditor,
        *mocks,
    ):
        """Test empty input."""
        mock_editor = MockTextEditor.return_value
        mock_editor.run.return_value = "   "  # Empty/whitespace

        exit_code = mode_interactive_editor()

        assert exit_code == 0
        # create_bootloader is called once during mode_interactive_editor init
        MockCreateBootloader.assert_called_once()

    @patch("ami.cli.timer_utils.TimerDisplay")
    @patch("sys.stdin.isatty", return_value=False)
    @patch("ami.cli.mode_handlers.confirm", return_value=False)
    @patch("ami.cli.mode_handlers.TranscriptStore")
    @patch("ami.cli.mode_handlers.TextEditor")
    @patch("ami.cli.mode_handlers.AgentFactory.create_bootloader")
    def test_interactive_editor_agent_error(self, *mocks):
        """Test exception during agent execution."""
        MockCreateBootloader, MockTextEditor, MockTranscriptStore = mocks[:3]

        mock_editor = MockTextEditor.return_value
        mock_editor.run.side_effect = ["Do task", None]

        mock_store = MockTranscriptStore.return_value
        mock_store.get_resumable_session.return_value = None
        mock_store.create_session.return_value = "test-transcript-id"

        mock_agent = MockCreateBootloader.return_value
        mock_agent.run.side_effect = Exception("Agent crashed")

        with patch.object(sys.stderr, "write") as mock_stderr:
            exit_code = mode_interactive_editor()

            assert exit_code == 1
            mock_stderr.assert_any_call("\nError: Agent crashed\n")


class TestGetLatestSessionId:
    """Tests for get_latest_session_id function."""

    @patch("ami.cli.mode_handlers.TranscriptStore")
    def test_returns_none_when_no_sessions(self, MockStore):
        """Test returns None when no sessions exist."""
        mock_store = MockStore.return_value
        mock_store.list_sessions.return_value = []

        result = get_latest_session_id()

        assert result is None

    @patch("ami.cli.mode_handlers.TranscriptStore")
    def test_returns_newest_session_id(self, MockStore):
        """Test returns session_id of the newest session."""
        mock_session = MagicMock()
        mock_session.session_id = "newest-session-id"
        mock_store = MockStore.return_value
        mock_store.list_sessions.return_value = [mock_session]

        result = get_latest_session_id()

        assert result == "newest-session-id"

    @patch("ami.cli.mode_handlers.TranscriptStore")
    def test_returns_none_on_exception(self, MockStore):
        """Test returns None when exception occurs."""
        MockStore.side_effect = Exception("Store error")

        result = get_latest_session_id()

        assert result is None


class TestModeQuery:
    """Tests for mode_query function."""

    @patch("ami.cli.mode_handlers.AgentFactory.create_bootloader")
    @patch("ami.cli.mode_handlers.TranscriptStore")
    @patch("ami.cli.mode_handlers.wrap_text_in_box")
    @patch.object(sys.stdout, "write")
    @patch.object(sys.stdout, "flush")
    def test_mode_query_creates_fresh_session(
        self, mock_flush, mock_write, mock_wrap, MockStore, MockAgent
    ):
        """Test query always creates a fresh session (never reuses paused)."""
        mock_wrap.return_value = "boxed text"
        mock_store = MockStore.return_value
        mock_store.create_session.return_value = "fresh-session-id"
        mock_agent = MockAgent.return_value
        mock_agent.run.return_value = AgentRunResult("output", "sess-id")

        result = mode_query("What is Python?")

        assert result == 0
        mock_store.create_session.assert_called_once()
        # Must NOT call get_resumable_session
        mock_store.get_resumable_session.assert_not_called()
        mock_agent.run.assert_called_once()

    @patch("ami.cli.mode_handlers.AgentFactory.create_bootloader")
    @patch("ami.cli.mode_handlers.TranscriptStore")
    @patch("ami.cli.mode_handlers.wrap_text_in_box")
    @patch.object(sys.stdout, "write")
    @patch.object(sys.stdout, "flush")
    def test_mode_query_marks_completed(
        self, mock_flush, mock_write, mock_wrap, MockStore, MockAgent
    ):
        """Test query session is marked completed after successful execution."""
        mock_wrap.return_value = "boxed text"
        mock_store = MockStore.return_value
        mock_store.create_session.return_value = "query-session-id"
        mock_agent = MockAgent.return_value
        mock_agent.run.return_value = AgentRunResult("output", "sess-id")

        result = mode_query("What is Python?")

        assert result == 0
        mock_store.update_session.assert_called_with(
            "query-session-id", status="completed"
        )

    @patch("ami.cli.mode_handlers.AgentFactory.create_bootloader")
    @patch("ami.cli.mode_handlers.TranscriptStore")
    @patch("ami.cli.mode_handlers.wrap_text_in_box")
    @patch.object(sys.stdout, "write")
    @patch.object(sys.stdout, "flush")
    def test_mode_query_keyboard_interrupt(
        self, mock_flush, mock_write, mock_wrap, MockStore, MockAgent
    ):
        """Test query cancellation with Ctrl+C."""
        mock_wrap.return_value = "boxed text"
        mock_store = MockStore.return_value
        mock_store.create_session.return_value = "query-session-id"
        mock_agent = MockAgent.return_value
        mock_agent.run.side_effect = KeyboardInterrupt()

        result = mode_query("What is Python?")

        assert result == 0

    @patch("ami.cli.mode_handlers.AgentFactory.create_bootloader")
    @patch("ami.cli.mode_handlers.TranscriptStore")
    @patch("ami.cli.mode_handlers.wrap_text_in_box")
    @patch.object(sys.stdout, "write")
    @patch.object(sys.stdout, "flush")
    def test_mode_query_exception_marks_paused(
        self, mock_flush, mock_write, mock_wrap, MockStore, MockAgent
    ):
        """Test query exception marks session as paused."""
        mock_wrap.return_value = "boxed text"
        mock_store = MockStore.return_value
        mock_store.create_session.return_value = "query-session-id"
        mock_agent = MockAgent.return_value
        mock_agent.run.side_effect = Exception("Query failed")

        result = mode_query("What is Python?")

        assert result == 1
        mock_store.update_session.assert_called_with(
            "query-session-id", status="paused"
        )


class TestModePrint:
    """Tests for mode_print function."""

    def test_mode_print_invalid_path(self):
        """Test mode_print with non-existent path."""
        result = mode_print("/nonexistent/path.txt")

        assert result == 1

    @patch("ami.cli.mode_handlers.AgentFactory.create_bootloader")
    @patch("ami.cli.mode_handlers.TranscriptStore")
    @patch.object(sys.stdin, "read")
    def test_mode_print_success(self, mock_stdin_read, MockStore, MockAgent):
        """Test successful print execution."""
        mock_stdin_read.return_value = ""
        mock_store = MockStore.return_value
        mock_store.create_session.return_value = "test-session-id"
        mock_agent = MockAgent.return_value
        mock_agent.run.return_value = AgentRunResult("output", "sess-id")

        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("Test instruction")
            temp_path = f.name

        try:
            result = mode_print(temp_path)

            assert result == 0
            mock_agent.run.assert_called_once()
        finally:
            Path(temp_path).unlink()
