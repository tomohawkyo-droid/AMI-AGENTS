"""Integration tests for ami-agent interactive mode functionality."""

import importlib.util
from pathlib import Path
import sys
from unittest.mock import MagicMock, Mock, patch

import pytest

from ami.cli.claude_cli import ClaudeAgentCLI
from ami.cli.config import AgentConfigPresets
from ami.cli.factory import get_agent_cli
from ami.cli.mode_handlers import mode_interactive_editor, mode_query
from ami.cli.provider_type import ProviderType
from ami.cli.qwen_cli import QwenAgentCLI
from ami.cli.timer_utils import TimerDisplay, wrap_text_in_box
from ami.cli_components.text_editor import TextEditor


class TestMainIntegration:
    """Integration tests for main entry point."""

    @patch("sys.argv", ["ami-agent", "--interactive-editor"])
    @patch("sys.exit")
    @patch("ami.cli.mode_handlers.mode_interactive_editor", return_value=0)
    def test_main_with_interactive_editor_arg(self, mock_mode_handler, mock_exit):
        """Test main function with --interactive-editor argument."""
        # Setup paths
        agents_root = Path(__file__).resolve().parent.parent.parent
        main_py_path = agents_root / "ami" / "cli" / "main.py"
        
        # Mock sys.argv
        with patch("sys.argv", ["ami-agent", "--interactive-editor"]):
            spec = importlib.util.spec_from_file_location("__main__", str(main_py_path.resolve()))
            main_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(main_module)
            
            mock_exit.assert_called_once()
            mock_mode_handler.assert_called_once()

    @patch("sys.argv", ["ami-agent", "--query", "test query"])
    @patch("sys.exit")
    @patch("ami.cli.mode_handlers.mode_query", return_value=0)
    def test_main_with_query_arg(self, mock_mode_handler, mock_exit):
        """Test main function with --query argument."""
        agents_root = Path(__file__).resolve().parent.parent.parent
        main_py_path = agents_root / "ami" / "cli" / "main.py"

        with patch("sys.argv", ["ami-agent", "--query", "test query"]):
            spec = importlib.util.spec_from_file_location("__main__", str(main_py_path.resolve()))
            main_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(main_module)

            mock_exit.assert_called_once()
            mock_mode_handler.assert_called_once()


class TestModeHandlersIntegration:
    """Integration tests for mode handlers."""

    @patch("ami.cli.mode_handlers.TextEditor")
    @patch("ami.cli.mode_handlers.AgentFactory.create_bootloader")
    def test_mode_interactive_editor_end_to_end(self, mock_create_bootloader, mock_text_editor):
        """End-to-end test of interactive editor mode."""
        # Mock the text editor to return content then None to exit loop
        mock_editor = Mock()
        mock_editor.run.side_effect = ["Hello!", None]
        mock_text_editor.return_value = mock_editor

        # Mock the BootloaderAgent returned by factory
        mock_agent = Mock()
        mock_agent.run.return_value = ("Response", "session-id")
        mock_create_bootloader.return_value = mock_agent

        # Call the mode handler
        result = mode_interactive_editor()

        # Verify success
        assert result == 0
        assert mock_agent.run.called

    @patch("ami.cli.mode_handlers.get_agent_cli")
    def test_mode_query_end_to_end(self, mock_get_cli):
        """End-to-end test of query mode."""
        mock_cli = Mock()
        mock_cli.run_print.return_value = ("Response", {})
        mock_get_cli.return_value = mock_cli

        result = mode_query("Test query")

        assert result == 0
        assert mock_cli.run_print.called


class TestConfigurationIntegration:
    """Integration tests for configuration system."""

    def test_config_presets_worker(self):
        """Test that worker preset works."""
        session_id = "test-session-123"
        config = AgentConfigPresets.worker(session_id)
        assert config.session_id == session_id
        assert config.enable_hooks is True


class TestCLIIntegration:
    """Integration tests for CLI factory."""

    @patch("ami.cli.factory.get_config")
    def test_cli_factory_default(self, mock_get_config):
        """Test CLI factory returns Claude when configured."""
        mock_get_config.return_value.get.return_value = "claude"
        cli = get_agent_cli()
        assert isinstance(cli, ClaudeAgentCLI)


class TestTimerUtilsIntegration:
    """Integration tests for timer and text utilities."""

    def test_timer_display(self):
        """Test timer display lifecycle."""
        timer = TimerDisplay()
        assert timer.is_running is False
        timer.start()
        assert timer.is_running is True
        timer.stop()
        assert timer.is_running is False

    def test_wrap_text_in_box(self):
        """Test text wrapping."""
        result = wrap_text_in_box("Hello")
        assert "Hello" in result
        assert result.startswith("┌")


class TestTextEditorIntegration:
    """Integration tests for text editor components."""

    def test_text_editor_initialization(self):
        """Test text editor initialization."""
        editor = TextEditor("Test content")
        assert "Test content" in editor.lines
        assert editor.cursor_manager is not None