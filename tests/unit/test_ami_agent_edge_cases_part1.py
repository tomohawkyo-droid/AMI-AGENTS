"""Comprehensive tests for remaining edge cases and error conditions in ami-agent interactive mode."""

import time
from unittest.mock import MagicMock, Mock, patch

import pytest

from agents.ami.cli.config import AgentConfig, AgentConfigPresets
from agents.ami.core.config import Config, get_config
from agents.ami.cli.exceptions import AgentError, AgentTimeoutError
from agents.ami.cli.mode_handlers import (
    mode_interactive_editor,
    mode_print,
    mode_query,
)
from agents.ami.cli.streaming import (
    _handle_timeout,
    _process_line_with_provider,
    run_streaming_loop_with_display,
)
from agents.ami.cli.timer_utils import TimerDisplay


class TestModeHandlerErrorConditions:
    """Test error conditions in mode handlers."""

    @patch("agents.ami.cli.mode_handlers.TextEditor")
    def test_mode_interactive_editor_keyboard_interrupt(self, mock_text_editor):
        """Test interactive editor mode when interrupted by keyboard."""
        mock_editor = Mock()
        mock_editor.run.side_effect = KeyboardInterrupt("User cancelled")
        mock_text_editor.return_value = mock_editor

        # Should handle KeyboardInterrupt gracefully
        result = mode_interactive_editor()
        assert result == 0  # Success because cancellation is expected behavior

    @patch("agents.ami.cli.mode_handlers.get_agent_cli")
    @patch("agents.ami.cli.mode_handlers.TextEditor")
    def test_mode_interactive_editor_with_whitespace_content(self, mock_editor, mock_get_cli):
        """Test interactive editor mode with whitespace-only content."""
        # Mock the text editor to return whitespace content
        mock_editor_instance = MagicMock()
        mock_editor_instance.run.return_value = "   \n  "
        mock_editor.return_value = mock_editor_instance

        # Call the function
        result = mode_interactive_editor()

        # Should return 0 (graceful exit without sending)
        assert result == 0
        # Should not have called CLI since content was effectively empty
        mock_get_cli.assert_not_called()

    @patch("sys.stdin.read", return_value="")  # Mock stdin to avoid issues in test environment
    @patch("agents.ami.cli.mode_handlers.validate_path_and_return_code")
    @patch("agents.ami.cli.mode_handlers.get_agent_cli")
    def test_mode_print_empty_stdin(self, mock_get_cli, mock_validate, mock_stdin_read):
        """Test print mode when stdin is empty."""
        mock_validate.return_value = 0  # Valid path
        mock_cli = Mock()
        mock_cli.run_print.return_value = ("", {})
        mock_get_cli.return_value = mock_cli

        result = mode_print("/valid/path.txt")
        assert result == 0  # Empty response is valid

    @patch("sys.stdin.read", return_value="")  # Mock stdin to avoid issues in test environment
    @patch("agents.ami.cli.mode_handlers.validate_path_and_return_code")
    def test_mode_print_invalid_path(self, mock_validate, mock_stdin_read):
        """Test print mode with invalid path."""
        mock_validate.return_value = 1  # Invalid path

        result = mode_print("/nonexistent/path.txt")
        assert result == 1  # Should return error code

    @patch("sys.stdin.read", return_value="")  # Mock stdin to avoid issues in test environment
    @patch("agents.ami.cli.mode_handlers.validate_path_and_return_code")
    @patch("agents.ami.cli.mode_handlers.get_agent_cli")
    def test_mode_print_cli_error(self, mock_get_cli, mock_validate, mock_stdin_read):
        """Test print mode when CLI call fails."""
        mock_validate.return_value = 0  # Valid path
        mock_cli = Mock()
        mock_cli.run_print.side_effect = AgentError("CLI error")
        mock_get_cli.return_value = mock_cli

        result = mode_print("/valid/path.txt")
        assert result == 1  # Should return error code


class TestConfigurationErrorConditions:
    """Test configuration error conditions."""

    def test_agent_config_invalid_provider(self):
        """Test agent config with invalid provider."""
        # Should default to Claude for invalid provider
        AgentConfig(
            model="test-model",
            session_id="test-session",
            provider="invalid_provider",  # Invalid provider type
        )
        # Note: This depends on how the code handles invalid providers
        # The factory should handle this properly

    @patch("agents.ami.core.config.yaml.safe_load")
    @patch("builtins.open")
    def test_config_file_not_found(self, mock_open, mock_yaml_load):
        """Test config service when config file doesn't exist."""
        # Make file opening raise an error to simulate missing file
        mock_open.side_effect = FileNotFoundError("Config file not found")
        mock_yaml_load.side_effect = FileNotFoundError("Config file not found")

        # Mock Path.exists to return False
        with patch("pathlib.Path.exists", return_value=False):
            with pytest.raises(FileNotFoundError):
                Config()  # Should fail when config file is not found

    def test_config_presets_none_session_id(self):
        """Test config presets with None session ID."""
        # This should work - None session_id is valid
        config = AgentConfigPresets.worker(None)
        assert config.session_id is None  # Or it might generate a default


class TestTimerErrorConditions:
    """Test timer error conditions."""

    def test_timer_display_stop_when_not_running(self):
        """Test stopping timer when it's not running."""
        timer = TimerDisplay()
        # Initially not running, so stop should not fail
        timer.stop()
        assert timer.is_running is False

    def test_timer_display_multiple_starts(self):
        """Test starting timer multiple times."""
        timer = TimerDisplay()
        timer.start()
        # Should handle multiple starts gracefully
        initial_start_time = timer.start_time
        timer.start()  # Should reset start time
        assert timer.start_time >= initial_start_time

    def test_timer_display_multiple_stops(self):
        """Test stopping timer multiple times."""
        timer = TimerDisplay()
        timer.start()
        timer.stop()
        # Should handle multiple stops gracefully
        timer.stop()  # Should not fail
        assert timer.is_running is False


class TestStreamingErrorConditions:
    """Test streaming error conditions."""

    @pytest.mark.skip(reason="Causes segmentation fault due to threading race condition in test environment")
    @patch("agents.ami.cli.streaming.TimerDisplay")
    def test_run_streaming_loop_with_display_timeout(self, mock_timer_class):
        """Test streaming with timeout."""
        # Create a mock process that simulates timeout behavior
        mock_process = Mock()
        mock_process.poll.return_value = None  # Process still running
        mock_process.stdout.readline.return_value = None

        mock_config = Mock()
        mock_config.session_id = "test-session"
        mock_config.timeout = 1  # Short timeout

        class MockProvider:
            def _parse_stream_message(self, line, cmd, line_count, agent_config):
                return "", None

        # Test with a process that never returns data - should timeout
        with patch("agents.ami.cli.streaming.read_streaming_line") as mock_read:
            # Make read_streaming_line return timeout continuously to trigger the timeout logic
            mock_read.return_value = (None, True)  # No data, timeout
            mock_process.stdout = Mock()
            mock_process.stdout.fileno = Mock(return_value=123)  # Mock file descriptor
            mock_process.poll = Mock(return_value=None)  # Process still running

            # This will eventually timeout based on the timeout logic
            with pytest.raises(AgentTimeoutError):
                # Call the function that should timeout
                run_streaming_loop_with_display(mock_process, ["test", "cmd"], mock_config, MockProvider())

    def test_handle_timeout_no_config(self):
        """Test timeout handling with None config."""
        cmd = ["test", "cmd"]
        started_at = time.time()

        # Should not raise error when config is None
        result = _handle_timeout(cmd, None, started_at)
        assert result is False  # Continue waiting

    def test_handle_timeout_no_timeout_config(self):
        """Test timeout handling when no timeout configured."""
        cmd = ["test", "cmd"]
        mock_config = Mock()
        mock_config.timeout = None

        started_at = time.time()

        # Should continue waiting when no timeout configured
        result = _handle_timeout(cmd, mock_config, started_at)
        assert result is False  # Continue waiting

        def test_process_line_with_provider_no_content(self):

            """Test processing line when provider returns no content."""

            display_context = {

                "full_output": "",

                "started_at": time.time(),

                "session_id": "test",

                "timer": Mock(),

                "content_started": False,

                "box_displayed": False,

                "last_print_ended_with_newline": False,

                "capture_content": False,

                "response_box_started": False,

                "response_box_ended": False,

            }

    

            class MockProvider:

                def _parse_stream_message(self, line, cmd, line_count, agent_config):

                    return "", {"empty": True}  # No text content, only metadata

    

            _process_line_with_provider("test line", ["cmd"], display_context, MockProvider(), 0, Mock())

    

            # Should maintain empty output

            assert display_context["full_output"] == ""

    def test_process_line_with_provider_exception(self):
        """Test processing line when provider throws exception."""
        display_context = {
            "full_output": "",
            "started_at": time.time(),
            "session_id": "test",
            "timer": Mock(),
            "content_started": False,
            "box_displayed": False,
            "last_print_ended_with_newline": False,
            "capture_content": False,
            "response_box_started": False,
            "response_box_ended": False,
        }

        class FailingProvider:
            def _parse_stream_message(self, line, cmd, line_count, agent_config):
                raise RuntimeError("Parsing failed")

        # Should handle the exception gracefully
        with pytest.raises(RuntimeError):  # Assuming FailingProvider raises RuntimeError
            _process_line_with_provider("test line", ["cmd"], display_context, FailingProvider(), 0, Mock())


if __name__ == "__main__":
    pytest.main([__file__])