"""Unit tests for ami/cli/main.py."""

from unittest.mock import MagicMock, patch

from ami.cli.main import main


class TestMain:
    """Tests for main function."""

    @patch("ami.cli.main.mode_interactive_editor")
    @patch("ami.cli.main.argparse.ArgumentParser.parse_args")
    def test_no_args_defaults_to_interactive_editor(
        self, mock_parse_args, mock_mode_editor
    ):
        """Test no arguments defaults to interactive editor mode."""
        mock_args = MagicMock()
        mock_args.print = None
        mock_args.interactive_editor = False
        mock_args.sessions = False
        mock_args.prune = False
        mock_args.query = None
        mock_args.query_args = []
        mock_parse_args.return_value = mock_args
        mock_mode_editor.return_value = 0

        result = main()

        assert result == 0
        mock_mode_editor.assert_called_once()

    @patch("ami.cli.main.mode_print")
    @patch("ami.cli.main.argparse.ArgumentParser.parse_args")
    def test_print_mode(self, mock_parse_args, mock_mode_print):
        """Test --print mode is invoked."""
        mock_args = MagicMock()
        mock_args.print = "config/prompt.txt"
        mock_args.interactive_editor = False
        mock_args.sessions = False
        mock_args.prune = False
        mock_args.query = None
        mock_args.query_args = []
        mock_parse_args.return_value = mock_args
        mock_mode_print.return_value = 0

        result = main()

        assert result == 0
        mock_mode_print.assert_called_once_with("config/prompt.txt")

    @patch("ami.cli.main.mode_query")
    @patch("ami.cli.main.argparse.ArgumentParser.parse_args")
    def test_query_mode(self, mock_parse_args, mock_mode_query):
        """Test --query mode is invoked."""
        mock_args = MagicMock()
        mock_args.print = None
        mock_args.interactive_editor = False
        mock_args.sessions = False
        mock_args.prune = False
        mock_args.query = "What is Python?"
        mock_args.query_args = []
        mock_parse_args.return_value = mock_args
        mock_mode_query.return_value = 0

        result = main()

        assert result == 0
        mock_mode_query.assert_called_once_with("What is Python?")

    @patch("ami.cli.main.mode_interactive_editor")
    @patch("ami.cli.main.argparse.ArgumentParser.parse_args")
    def test_interactive_editor_mode_flag(self, mock_parse_args, mock_mode_editor):
        """Test --interactive-editor flag is handled."""
        mock_args = MagicMock()
        mock_args.print = None
        mock_args.interactive_editor = True
        mock_args.sessions = False
        mock_args.prune = False
        mock_args.query = None
        mock_args.query_args = []
        mock_parse_args.return_value = mock_args
        mock_mode_editor.return_value = 0

        result = main()

        assert result == 0
        mock_mode_editor.assert_called_once()

    @patch("ami.cli.main.mode_print")
    @patch("ami.cli.main.argparse.ArgumentParser.parse_args")
    def test_print_mode_returns_error_code(self, mock_parse_args, mock_mode_print):
        """Test print mode error code is propagated."""
        mock_args = MagicMock()
        mock_args.print = "nonexistent.txt"
        mock_args.interactive_editor = False
        mock_args.sessions = False
        mock_args.prune = False
        mock_args.query = None
        mock_args.query_args = []
        mock_parse_args.return_value = mock_args
        mock_mode_print.return_value = 1

        result = main()

        assert result == 1

    @patch("ami.cli.main.mode_interactive_editor")
    @patch("ami.cli.main.argparse.ArgumentParser.parse_args")
    def test_interactive_editor_returns_error_code(
        self, mock_parse_args, mock_mode_editor
    ):
        """Test interactive editor error code is propagated."""
        mock_args = MagicMock()
        mock_args.print = None
        mock_args.interactive_editor = False
        mock_args.sessions = False
        mock_args.prune = False
        mock_args.query = None
        mock_args.query_args = []
        mock_parse_args.return_value = mock_args
        mock_mode_editor.return_value = 1

        result = main()

        assert result == 1

    @patch("ami.cli.main.argparse.ArgumentParser.parse_args")
    def test_prune_mode(self, mock_parse_args):
        """Test --prune flag invokes session pruning."""
        mock_args = MagicMock()
        mock_args.print = None
        mock_args.interactive_editor = False
        mock_args.sessions = False
        mock_args.prune = True
        mock_args.query = None
        mock_args.query_args = []
        mock_parse_args.return_value = mock_args

        with (
            patch("ami.cli.main.TranscriptStore") as MockStore,
            patch("ami.cli.main.get_config") as mock_config,
        ):
            mock_store = MockStore.return_value
            mock_store.prune_sessions.return_value = 3
            mock_config.return_value.get_value.return_value = 90

            result = main()

        assert result == 0
        mock_store.prune_sessions.assert_called_once_with(retention_days=90)
