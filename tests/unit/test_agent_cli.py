"""Unit tests for automation.agent_cli module."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ami.cli.claude_cli import ClaudeAgentCLI
from ami.cli.config import AgentConfig, AgentConfigPresets
from ami.cli.factory import get_agent_cli
from ami.cli.provider_type import ProviderType
from ami.cli.streaming_utils import load_instruction_with_replacements

# Test constants
DEFAULT_TIMEOUT = 180
AUDIT_DIFF_TIMEOUT = 60
CONSOLIDATE_TIMEOUT = 300
ALL_TOOLS_COUNT = 15
TOOLS_WITHOUT_WEB_COUNT = 13


class TestAgentConfig:
    """Unit tests for AgentConfig dataclass."""

    def test_create_basic_config(self):
        """AgentConfig creates with required fields."""
        config = AgentConfig(
            model="claude-sonnet-4-5",
            session_id="test-session",
            provider=ProviderType.CLAUDE,
        )

        assert config.model == "claude-sonnet-4-5"
        assert config.session_id == "test-session"
        assert config.provider == ProviderType.CLAUDE
        assert config.allowed_tools is None
        assert config.enable_hooks is True
        assert config.timeout == DEFAULT_TIMEOUT

    def test_default_allowed_tools(self):
        """AgentConfig defaults allowed_tools to None."""
        config = AgentConfig(
            model="test-model", session_id="test-session", provider=ProviderType.CLAUDE
        )

        assert config.allowed_tools is None  # All tools allowed

    def test_default_enable_hooks(self):
        """AgentConfig defaults enable_hooks to True."""
        config = AgentConfig(
            model="test-model", session_id="test-session", provider=ProviderType.CLAUDE
        )

        assert config.enable_hooks is True

    def test_default_timeout(self):
        """AgentConfig defaults timeout to 180."""
        config = AgentConfig(
            model="test-model", session_id="test-session", provider=ProviderType.CLAUDE
        )

        assert config.timeout == DEFAULT_TIMEOUT


class TestAgentConfigPresets:
    """Unit tests for AgentConfigPresets."""

    @pytest.fixture(autouse=True)
    def mock_config(self):
        """Mock configuration for all tests in this class."""
        with patch("ami.cli.config.get_config") as mock_get_config:
            mock_config_instance = MagicMock()
            mock_get_config.return_value = mock_config_instance

            # Setup default return values - use get_value which is what the code uses
            def get_value_side_effect(key, default=None):
                values = {
                    "agent.provider": "claude",
                    "agent.worker.provider": "claude",
                    "agent.worker.model": "claude-sonnet-4-5",
                    "agent.moderator.provider": "claude",
                    "agent.moderator.model": "claude-sonnet-4-5",
                }
                return values.get(key, default)

            mock_config_instance.get_value.side_effect = get_value_side_effect
            mock_config_instance.get.side_effect = (
                get_value_side_effect  # Also mock get for older interface support
            )
            mock_config_instance.get_provider_audit_model.return_value = (
                "claude-sonnet-4-5"
            )
            mock_config_instance.get_provider_default_model.return_value = (
                "claude-sonnet-4-5"
            )
            mock_config_instance.root = Path("/mock/root")

            yield mock_config_instance

    def test_worker_preset(self, mock_config):
        """worker() preset has correct config."""
        config = AgentConfigPresets.worker(session_id="test-session")
        assert config.session_id == "test-session"
        assert config.provider == ProviderType.CLAUDE
        assert config.allowed_tools is None  # All tools allowed
        assert config.enable_hooks is True

    def test_interactive_preset(self, mock_config):
        """interactive() preset has correct config."""
        # Mock specific paths for interactive preset
        mock_config.root = Path("/mock/root")

        config = AgentConfigPresets.interactive(session_id="test-session")

        assert config.model == "claude-sonnet-4-5"
        assert config.allowed_tools is None  # All tools allowed
        assert config.enable_hooks is True
        assert config.timeout is None  # No timeout


class TestClaudeAgentCLI:
    """Unit tests for ClaudeAgentCLI."""

    def test_all_tools_list_complete(self):
        """ALL_TOOLS contains all Claude Code tools."""
        # Should have 15 tools
        assert len(ClaudeAgentCLI.ALL_TOOLS) == ALL_TOOLS_COUNT
        assert "Bash" in ClaudeAgentCLI.ALL_TOOLS
        assert "Read" in ClaudeAgentCLI.ALL_TOOLS
        assert "Write" in ClaudeAgentCLI.ALL_TOOLS
        assert "WebSearch" in ClaudeAgentCLI.ALL_TOOLS

    def test_load_instruction_from_file(self):
        """load_instruction_with_replacements() reads file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("Test instruction")
            temp_path = Path(f.name)

        try:
            result = load_instruction_with_replacements(temp_path)

            assert "Test instruction" in result
        finally:
            if temp_path.exists():
                temp_path.unlink()

    def test_load_instruction_template_substitution(self):
        """load_instruction_with_replacements() substitutes {date}."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("Date: {date}")
            temp_path = Path(f.name)

        try:
            result = load_instruction_with_replacements(temp_path)

            # {date} should be replaced
            assert "{date}" not in result
            # Should contain actual date
            assert "Date:" in result
        finally:
            if temp_path.exists():
                temp_path.unlink()

    @patch("ami.cli.factory.get_config")
    def test_get_agent_cli_returns_claude(self, mock_get_config):
        """get_agent_cli() returns ClaudeAgentCLI."""
        mock_config = MagicMock()
        mock_config.get.return_value = "claude"
        mock_get_config.return_value = mock_config

        cli = get_agent_cli()

        assert isinstance(cli, ClaudeAgentCLI)
