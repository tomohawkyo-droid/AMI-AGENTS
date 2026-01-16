"""Unit tests for interactive mode handlers."""

import sys
from unittest.mock import MagicMock, patch

import pytest

from ami.cli.mode_handlers import get_user_confirmation, mode_interactive_editor


class TestInteractiveHelpers:
    """Tests for interactive helper functions."""

    @patch("ami.cli.mode_handlers.getchar")
    def test_get_user_confirmation_yes(self, mock_getchar):
        """Test confirmation with 'y'."""
        mock_getchar.return_value = 'y'
        with patch.object(sys.stdout, 'write') as mock_write:
            assert get_user_confirmation() is True
            mock_write.assert_called_with("y\n")

    @patch("ami.cli.mode_handlers.getchar")
    def test_get_user_confirmation_no(self, mock_getchar):
        """Test confirmation with 'n'."""
        mock_getchar.return_value = 'n'
        with patch.object(sys.stdout, 'write') as mock_write:
            assert get_user_confirmation() is False
            mock_write.assert_called_with("n\n")

    @patch("ami.cli.mode_handlers.getchar")
    def test_get_user_confirmation_cancel(self, mock_getchar):
        """Test confirmation with Ctrl+C."""
        mock_getchar.return_value = '\x03'
        with pytest.raises(KeyboardInterrupt):
            get_user_confirmation()

    @patch("ami.cli.mode_handlers.getchar")
    def test_get_user_confirmation_loop(self, mock_getchar):
        """Test confirmation ignores invalid keys."""
        # 'a' (invalid), 'b' (invalid), 'y' (valid)
        mock_getchar.side_effect = ['a', 'b', 'y']
        with patch.object(sys.stdout, 'write') as mock_write:
            assert get_user_confirmation() is True
            assert mock_getchar.call_count == 3


class TestModeInteractiveEditor:
    """Tests for mode_interactive_editor."""

    @patch("ami.cli.streaming.TimerDisplay")
    @patch("sys.stdin.isatty", return_value=False)
    @patch("ami.cli.mode_handlers.TextEditor")
    @patch("ami.cli.mode_handlers.BootloaderAgent")
    @patch("ami.cli.mode_handlers.display_final_output")
    def test_interactive_editor_success(self, mock_display, MockBootloaderAgent, MockTextEditor, mock_isatty, MockTimerDisplay):
        """Test successful execution flow."""
        # Setup mocks
        mock_editor = MockTextEditor.return_value
        # First call returns instruction, second call returns None to break the loop
        mock_editor.run.side_effect = ["Do something", None]
        mock_editor.lines = ["Do something"]
        
        mock_agent = MockBootloaderAgent.return_value
        mock_agent.run.return_value = ("Output", "sess-id")

        # Execute
        exit_code = mode_interactive_editor()

        # Verify
        assert exit_code == 0
        assert mock_editor.run.call_count == 2
        mock_display.assert_called_with(["Do something"], "✅ Sent to agent")
        mock_agent.run.assert_called_once()
        args, kwargs = mock_agent.run.call_args
        assert kwargs["instruction"] == "Do something"
        assert kwargs["input_func"] == get_user_confirmation

    @patch("ami.cli.streaming.TimerDisplay")
    @patch("sys.stdin.isatty", return_value=False)
    @patch("ami.cli.mode_handlers.TextEditor")
    @patch("ami.cli.mode_handlers.BootloaderAgent")
    def test_interactive_editor_cancel(self, MockBootloaderAgent, MockTextEditor, mock_isatty, MockTimerDisplay):
        """Test user cancellation in editor."""
        mock_editor = MockTextEditor.return_value
        mock_editor.run.return_value = None # None means cancelled

        exit_code = mode_interactive_editor()

        assert exit_code == 0
        MockBootloaderAgent.assert_not_called()

    @patch("ami.cli.streaming.TimerDisplay")
    @patch("sys.stdin.isatty", return_value=False)
    @patch("ami.cli.mode_handlers.TextEditor")
    @patch("ami.cli.mode_handlers.BootloaderAgent")
    def test_interactive_editor_empty(self, MockBootloaderAgent, MockTextEditor, mock_isatty, MockTimerDisplay):
        """Test empty input."""
        mock_editor = MockTextEditor.return_value
        mock_editor.run.return_value = "   " # Empty/whitespace

        exit_code = mode_interactive_editor()

        assert exit_code == 0
        MockBootloaderAgent.assert_not_called()

    @patch("ami.cli.streaming.TimerDisplay")
    @patch("sys.stdin.isatty", return_value=False)
    @patch("ami.cli.mode_handlers.TextEditor")
    @patch("ami.cli.mode_handlers.BootloaderAgent")
    def test_interactive_editor_agent_error(self, MockBootloaderAgent, MockTextEditor, mock_isatty, MockTimerDisplay):
        """Test exception during agent execution."""
        mock_editor = MockTextEditor.return_value
        mock_editor.run.side_effect = ["Do task", None]
        
        mock_agent = MockBootloaderAgent.return_value
        mock_agent.run.side_effect = Exception("Agent crashed")

        with patch.object(sys.stderr, 'write') as mock_stderr:
            exit_code = mode_interactive_editor()
            
            assert exit_code == 1
            mock_stderr.assert_any_call("Error calling agent: Agent crashed\n")
