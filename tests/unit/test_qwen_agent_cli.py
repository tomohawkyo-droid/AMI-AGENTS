"""Unit tests for QwenAgentCLI."""

import tempfile
from pathlib import Path

from ami.cli.config import AgentConfig
from ami.cli.provider_type import ProviderType
from ami.cli.qwen_cli import QwenAgentCLI
from ami.cli.streaming_utils import load_instruction_with_replacements

# Test constants
DEFAULT_QWEN_TIMEOUT = 180


class TestQwenAgentCLI:
    """Unit tests for QwenAgentCLI."""

    def test_all_tools_list_complete(self):
        """ALL_TOOLS contains all Qwen Code tools."""
        # Should have the main tools
        assert len(QwenAgentCLI.ALL_TOOLS) > 0
        assert "read_file" in QwenAgentCLI.ALL_TOOLS
        assert "write_file" in QwenAgentCLI.ALL_TOOLS
        assert "edit" in QwenAgentCLI.ALL_TOOLS
        assert "run_shell_command" in QwenAgentCLI.ALL_TOOLS

    def test_get_default_config(self):
        """_get_default_config() returns proper default config."""
        cli = QwenAgentCLI()
        config = cli._get_default_config()

        assert config.model == "qwen-coder"
        assert config.provider == ProviderType.QWEN
        assert config.allowed_tools is None
        assert config.enable_hooks is True
        assert config.timeout == DEFAULT_QWEN_TIMEOUT

    def test_build_command_basic(self):
        """_build_command() creates basic command correctly."""
        cli = QwenAgentCLI()
        config = AgentConfig(
            model="qwen-coder", session_id="test-session", provider=ProviderType.QWEN
        )

        cmd = cli._build_command("test instruction", None, config)

        # Should start with qwen command
        assert len(cmd) > 0
        # The exact command depends on the config, but it should have model and instruction
        assert "--model" in cmd
        assert "qwen-coder" in cmd

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
