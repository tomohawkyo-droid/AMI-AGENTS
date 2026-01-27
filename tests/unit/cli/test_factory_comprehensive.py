"""Comprehensive unit tests for ami/cli/factory.py."""

from unittest.mock import MagicMock, patch

from ami.cli.claude_cli import ClaudeAgentCLI
from ami.cli.factory import get_agent_cli
from ami.cli.gemini_cli import GeminiAgentCLI
from ami.cli.interface import AgentCLI
from ami.cli.provider_type import ProviderType
from ami.cli.qwen_cli import QwenAgentCLI
from ami.types.config import AgentConfig


class TestGetAgentCLI:
    """Tests for get_agent_cli factory function."""

    def test_claude_provider(self):
        """Test returns ClaudeAgentCLI for Claude provider."""
        config = AgentConfig(
            model="claude-sonnet",
            provider=ProviderType.CLAUDE,
        )

        result = get_agent_cli(config)

        assert isinstance(result, ClaudeAgentCLI)

    def test_qwen_provider(self):
        """Test returns QwenAgentCLI for Qwen provider."""
        config = AgentConfig(
            model="qwen-coder",
            provider=ProviderType.QWEN,
        )

        result = get_agent_cli(config)

        assert isinstance(result, QwenAgentCLI)

    def test_gemini_provider(self):
        """Test returns GeminiAgentCLI for Gemini provider."""
        config = AgentConfig(
            model="gemini-pro",
            provider=ProviderType.GEMINI,
        )

        result = get_agent_cli(config)

        assert isinstance(result, GeminiAgentCLI)

    @patch("ami.cli.factory.get_config")
    def test_no_config_uses_global_default(self, mock_get_config):
        """Test uses global default when no config provided."""
        mock_config = MagicMock()
        mock_config.get_value.return_value = "claude"
        mock_get_config.return_value = mock_config

        result = get_agent_cli(None)

        assert isinstance(result, ClaudeAgentCLI)
        mock_config.get_value.assert_called_with("agent.provider", "claude")

    @patch("ami.cli.factory.get_config")
    def test_config_without_provider_uses_global(self, mock_get_config):
        """Test uses global default when config has no provider."""
        mock_config = MagicMock()
        mock_config.get_value.return_value = "qwen"
        mock_get_config.return_value = mock_config

        config = AgentConfig(model="some-model", provider=None)

        result = get_agent_cli(config)

        assert isinstance(result, QwenAgentCLI)

    @patch("ami.cli.factory.get_config")
    def test_invalid_global_provider_defaults_to_claude(self, mock_get_config):
        """Test invalid global provider defaults to Claude."""
        mock_config = MagicMock()
        mock_config.get_value.return_value = "invalid-provider"
        mock_get_config.return_value = mock_config

        result = get_agent_cli(None)

        assert isinstance(result, ClaudeAgentCLI)

    @patch("ami.cli.factory.get_config")
    def test_global_gemini_provider(self, mock_get_config):
        """Test global config with Gemini provider."""
        mock_config = MagicMock()
        mock_config.get_value.return_value = "gemini"
        mock_get_config.return_value = mock_config

        result = get_agent_cli(None)

        assert isinstance(result, GeminiAgentCLI)

    def test_unknown_provider_defaults_to_claude(self):
        """Test unknown provider type defaults to Claude."""
        # Create a mock config with an unknown provider
        # This tests the final fallback in the function
        config = MagicMock(spec=AgentConfig)
        config.provider = MagicMock()  # Unknown provider type

        result = get_agent_cli(config)

        assert isinstance(result, ClaudeAgentCLI)

    def test_returns_agent_cli_interface(self):
        """Test returns object implementing AgentCLI interface."""
        config = AgentConfig(
            model="claude-sonnet",
            provider=ProviderType.CLAUDE,
        )

        result = get_agent_cli(config)

        assert isinstance(result, AgentCLI)
