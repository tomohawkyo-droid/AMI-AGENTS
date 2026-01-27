"""Unit tests for ami/cli/gemini_cli.py."""

from ami.cli.gemini_cli import GeminiAgentCLI
from ami.cli.provider_type import ProviderType
from ami.types.config import AgentConfig

EXPECTED_DEFAULT_TIMEOUT = 180


class TestGeminiAgentCLI:
    """Tests for GeminiAgentCLI class."""

    def test_all_tools_set(self):
        """Test ALL_TOOLS contains expected tools."""
        assert len(GeminiAgentCLI.ALL_TOOLS) > 0
        assert "read_file" in GeminiAgentCLI.ALL_TOOLS
        assert "write_file" in GeminiAgentCLI.ALL_TOOLS
        assert "edit" in GeminiAgentCLI.ALL_TOOLS
        assert "run_shell_command" in GeminiAgentCLI.ALL_TOOLS
        assert "google_web_search" in GeminiAgentCLI.ALL_TOOLS

    def test_get_default_config(self):
        """Test _get_default_config returns correct defaults."""
        cli = GeminiAgentCLI()
        config = cli._get_default_config()

        assert config.model == "gemini-3-pro"
        assert config.provider == ProviderType.GEMINI
        assert config.allowed_tools is None
        assert config.enable_hooks is True
        assert config.timeout == EXPECTED_DEFAULT_TIMEOUT
        assert config.session_id is not None  # Should have UUID7

    def test_build_command_basic(self):
        """Test _build_command creates correct command."""
        cli = GeminiAgentCLI()
        config = AgentConfig(
            model="gemini-3-pro",
            session_id=None,
            provider=ProviderType.GEMINI,
        )

        cmd = cli._build_command("test instruction", None, config)

        assert "--prompt" in cmd
        assert "test instruction" in cmd
        assert "--model" in cmd
        assert "gemini-3-pro" in cmd
        assert "--output-format" in cmd
        assert "json" in cmd
        assert "--yolo" in cmd

    def test_build_command_with_session_id(self):
        """Test _build_command includes --resume with session_id."""
        cli = GeminiAgentCLI()
        config = AgentConfig(
            model="gemini-3-pro",
            session_id="session-123",
            provider=ProviderType.GEMINI,
        )

        cmd = cli._build_command("test", None, config)

        assert "--resume" in cmd
        assert "session-123" in cmd

    def test_build_command_without_session_id(self):
        """Test _build_command excludes --resume without session_id."""
        cli = GeminiAgentCLI()
        config = AgentConfig(
            model="gemini-3-pro",
            session_id=None,
            provider=ProviderType.GEMINI,
        )

        cmd = cli._build_command("test", None, config)

        assert "--resume" not in cmd

    def test_parse_stream_message_returns_line(self):
        """Test _parse_stream_message returns line as-is."""
        cli = GeminiAgentCLI()

        output, metadata = cli._parse_stream_message("test line", [], 0, None)

        assert output == "test line"
        assert metadata is None

    def test_parse_stream_message_empty_line(self):
        """Test _parse_stream_message with empty line."""
        cli = GeminiAgentCLI()

        output, metadata = cli._parse_stream_message("", [], 0, None)

        assert output == ""
        assert metadata is None
