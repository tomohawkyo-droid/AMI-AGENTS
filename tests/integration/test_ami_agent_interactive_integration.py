"""Integration tests for ami-agent interactive mode functionality."""

from unittest.mock import Mock, patch

from ami.cli.claude_cli import ClaudeAgentCLI
from ami.cli.config import AgentConfigPresets
from ami.cli.factory import get_agent_cli
from ami.cli.main import main as cli_main
from ami.cli.mode_handlers import mode_interactive_editor, mode_query
from ami.cli.timer_utils import TimerDisplay, wrap_text_in_box
from ami.cli_components.text_editor import TextEditor
from ami.core.bootloader_agent import AgentRunResult


class TestMainIntegration:
    """Integration tests for main entry point."""

    @patch("ami.cli.main.mode_interactive_editor", return_value=0)
    def test_main_with_interactive_editor_arg(self, mock_mode_handler):
        """Test main function with --interactive-editor argument."""
        with patch("sys.argv", ["ami-agent", "--interactive-editor"]):
            result = cli_main()

            assert result == 0
            mock_mode_handler.assert_called_once()

    @patch("ami.cli.main.mode_query", return_value=0)
    def test_main_with_query_arg(self, mock_mode_handler):
        """Test main function with --query argument."""
        with patch("sys.argv", ["ami-agent", "--query", "test query"]):
            result = cli_main()

            assert result == 0
            mock_mode_handler.assert_called_once()


class TestModeHandlersIntegration:
    """Integration tests for mode handlers."""

    @patch("ami.cli.mode_handlers.confirm", return_value=False)
    @patch("ami.cli.mode_handlers.TranscriptStore")
    @patch("ami.cli.mode_handlers.TextEditor")
    @patch("ami.cli.mode_handlers.AgentFactory.create_bootloader")
    def test_mode_interactive_editor_end_to_end(
        self, mock_create_bootloader, mock_text_editor, mock_store_cls, mock_confirm
    ):
        """End-to-end test of interactive editor mode."""
        # Mock the text editor to return content then None to exit loop
        mock_editor = Mock()
        mock_editor.run.side_effect = ["Hello!", None]
        mock_text_editor.return_value = mock_editor

        # Mock the transcript store
        mock_store = mock_store_cls.return_value
        mock_store.get_resumable_session.return_value = None
        mock_store.create_session.return_value = "test-transcript-id"

        # Mock the BootloaderAgent returned by factory
        mock_agent = Mock()
        mock_agent.run.return_value = AgentRunResult("Response", "session-id")
        mock_create_bootloader.return_value = mock_agent

        # Call the mode handler
        result = mode_interactive_editor()

        # Verify success
        assert result == 0
        assert mock_agent.run.called

    @patch("ami.cli.mode_handlers.AgentFactory.create_bootloader")
    @patch("ami.cli.mode_handlers.TranscriptStore")
    def test_mode_query_end_to_end(self, mock_store_cls, mock_create_bootloader):
        """End-to-end test of query mode."""
        mock_store = mock_store_cls.return_value
        mock_store.create_session.return_value = "test-transcript-id"

        mock_agent = Mock()
        mock_agent.run.return_value = AgentRunResult("Response", None)
        mock_create_bootloader.return_value = mock_agent

        result = mode_query("Test query")

        assert result == 0
        assert mock_agent.run.called


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
        mock_get_config.return_value.get_value.return_value = "claude"
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
