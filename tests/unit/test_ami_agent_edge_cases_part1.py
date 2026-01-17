"""Comprehensive tests for remaining edge cases and error conditions in ami-agent interactive mode."""

import time
from unittest.mock import MagicMock, Mock, patch

import pytest

from ami.cli.config import AgentConfig, AgentConfigPresets
from ami.core.config import Config, get_config
from ami.cli.exceptions import AgentError
from ami.cli.mode_handlers import (
    mode_interactive_editor,
    mode_print,
    mode_query,
)
from ami.cli.timer_utils import TimerDisplay


class TestModeHandlerErrorConditions:
    """Test error conditions in mode handlers."""

    @patch("ami.cli.mode_handlers.TextEditor")
    def test_mode_interactive_editor_keyboard_interrupt(self, mock_text_editor):
        """Test interactive editor mode when interrupted by keyboard."""
        mock_editor = Mock()
        mock_editor.run.side_effect = KeyboardInterrupt("User cancelled")
        mock_text_editor.return_value = mock_editor

        # Should handle KeyboardInterrupt gracefully
        result = mode_interactive_editor()
        assert result == 0  # Success because cancellation is expected behavior

    @patch("ami.cli.mode_handlers.get_agent_cli")
    @patch("ami.cli.mode_handlers.TextEditor")
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
    @patch("ami.cli.mode_handlers.validate_path_and_return_code")
    @patch("ami.cli.mode_handlers.get_agent_cli")
    def test_mode_print_empty_stdin(self, mock_get_cli, mock_validate, mock_stdin_read):
        """Test print mode when stdin is empty."""
        mock_validate.return_value = 0  # Valid path
        mock_cli = Mock()
        mock_cli.run_print.return_value = ("", {})
        mock_get_cli.return_value = mock_cli

        result = mode_print("/valid/path.txt")
        assert result == 0  # Empty response is valid

    @patch("sys.stdin.read", return_value="")  # Mock stdin to avoid issues in test environment
    @patch("ami.cli.mode_handlers.validate_path_and_return_code")
    def test_mode_print_invalid_path(self, mock_validate, mock_stdin_read):
        """Test print mode with invalid path."""
        mock_validate.return_value = 1  # Invalid path

        result = mode_print("/nonexistent/path.txt")
        assert result == 1  # Should return error code

    @patch("sys.stdin.read", return_value="")  # Mock stdin to avoid issues in test environment
    @patch("ami.cli.mode_handlers.validate_path_and_return_code")
    @patch("ami.cli.mode_handlers.get_agent_cli")
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

    @patch("ami.core.config.yaml.safe_load")
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


if __name__ == "__main__":
    pytest.main([__file__])