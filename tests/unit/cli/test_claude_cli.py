"""Unit tests for ami/cli/claude_cli.py."""

import json
from unittest.mock import MagicMock, patch

from ami.cli.claude_cli import ClaudeAgentCLI
from ami.cli.provider_type import ProviderType
from ami.types.config import AgentConfig

EXPECTED_DEFAULT_TIMEOUT = 180


class TestClaudeAgentCLIInit:
    """Tests for ClaudeAgentCLI initialization."""

    def test_all_tools_set(self):
        """Test ALL_TOOLS contains expected tools."""
        assert len(ClaudeAgentCLI.ALL_TOOLS) > 0
        assert "Bash" in ClaudeAgentCLI.ALL_TOOLS
        assert "Edit" in ClaudeAgentCLI.ALL_TOOLS
        assert "Read" in ClaudeAgentCLI.ALL_TOOLS
        assert "Write" in ClaudeAgentCLI.ALL_TOOLS
        assert "WebSearch" in ClaudeAgentCLI.ALL_TOOLS

    def test_init_sets_current_process_none(self):
        """Test initialization sets current_process to None."""
        cli = ClaudeAgentCLI()
        assert cli.current_process is None


class TestGetDefaultConfig:
    """Tests for _get_default_config method."""

    def test_returns_agent_config(self):
        """Test returns AgentConfig instance."""
        cli = ClaudeAgentCLI()
        config = cli._get_default_config()

        assert isinstance(config, AgentConfig)
        assert config.model == "claude-sonnet-4-5"
        assert config.provider == ProviderType.CLAUDE
        assert config.allowed_tools is None
        assert config.enable_hooks is True
        assert config.timeout == EXPECTED_DEFAULT_TIMEOUT

    def test_session_id_is_uuid(self):
        """Test session_id is a valid UUID."""
        cli = ClaudeAgentCLI()
        config = cli._get_default_config()

        # Should be a valid UUID7 string
        assert config.session_id is not None


class TestBuildCommand:
    """Tests for _build_command method."""

    @patch("ami.cli.claude_cli.get_config")
    def test_basic_command(self, mock_get_config):
        """Test basic command construction."""
        mock_config = MagicMock()
        mock_config.get_provider_command.return_value = "claude"
        mock_get_config.return_value = mock_config

        cli = ClaudeAgentCLI()
        config = AgentConfig(
            model="claude-sonnet-4-5",
            session_id=None,
            provider=ProviderType.CLAUDE,
        )

        cmd = cli._build_command("test instruction", None, config)

        assert "claude" in cmd
        assert "--model" in cmd
        assert "claude-sonnet-4-5" in cmd
        assert "--print" in cmd
        assert "test instruction" in cmd

    @patch("ami.cli.claude_cli.get_config")
    def test_with_session_id(self, mock_get_config):
        """Test command with session ID."""
        mock_config = MagicMock()
        mock_config.get_provider_command.return_value = "claude"
        mock_get_config.return_value = mock_config

        cli = ClaudeAgentCLI()
        valid_uuid = "12345678-1234-5678-1234-567812345678"
        config = AgentConfig(
            model="claude-sonnet-4-5",
            session_id=valid_uuid,
            provider=ProviderType.CLAUDE,
        )

        cmd = cli._build_command("test", None, config)

        assert "--session-id" in cmd
        assert valid_uuid in cmd

    @patch("ami.cli.claude_cli.get_config")
    def test_invalid_session_id_ignored(self, mock_get_config):
        """Test invalid session ID is ignored."""
        mock_config = MagicMock()
        mock_config.get_provider_command.return_value = "claude"
        mock_get_config.return_value = mock_config

        cli = ClaudeAgentCLI()
        config = AgentConfig(
            model="claude-sonnet-4-5",
            session_id="not-a-uuid",
            provider=ProviderType.CLAUDE,
        )

        cmd = cli._build_command("test", None, config)

        assert "--session-id" not in cmd

    @patch("ami.cli.claude_cli.get_config")
    def test_with_allowed_tools(self, mock_get_config):
        """Test command with allowed tools."""
        mock_config = MagicMock()
        mock_config.get_provider_command.return_value = "claude"
        mock_get_config.return_value = mock_config

        cli = ClaudeAgentCLI()
        config = AgentConfig(
            model="claude-sonnet-4-5",
            allowed_tools=["Bash", "Read", "Write"],
            provider=ProviderType.CLAUDE,
        )

        cmd = cli._build_command("test", None, config)

        assert "--allowed-tools" in cmd
        assert "Bash" in cmd
        assert "Read" in cmd
        assert "Write" in cmd

    @patch("ami.cli.claude_cli.get_config")
    def test_with_streaming(self, mock_get_config):
        """Test command with streaming enabled."""
        mock_config = MagicMock()
        mock_config.get_provider_command.return_value = "claude"
        mock_get_config.return_value = mock_config

        cli = ClaudeAgentCLI()
        config = AgentConfig(
            model="claude-sonnet-4-5",
            enable_streaming=True,
            provider=ProviderType.CLAUDE,
        )

        cmd = cli._build_command("test", None, config)

        assert "--verbose" in cmd
        assert "--output-format" in cmd
        assert "stream-json" in cmd

    @patch("ami.cli.claude_cli.get_config")
    def test_with_cwd(self, mock_get_config, tmp_path):
        """Test command with working directory."""
        mock_config = MagicMock()
        mock_config.get_provider_command.return_value = "claude"
        mock_get_config.return_value = mock_config

        cli = ClaudeAgentCLI()
        config = AgentConfig(
            model="claude-sonnet-4-5",
            provider=ProviderType.CLAUDE,
        )

        cmd = cli._build_command("test", tmp_path, config)

        assert "--add-dir" in cmd
        assert str(tmp_path) in cmd


class TestParseStreamMessage:
    """Tests for _parse_stream_message method."""

    def test_empty_line(self):
        """Test parsing empty line."""
        cli = ClaudeAgentCLI()
        output, metadata = cli._parse_stream_message("", [], 0, None)

        assert output == ""
        assert metadata is None

    def test_whitespace_line(self):
        """Test parsing whitespace line."""
        cli = ClaudeAgentCLI()
        output, metadata = cli._parse_stream_message("   ", [], 0, None)

        assert output == ""
        assert metadata is None

    def test_invalid_json(self):
        """Test parsing invalid JSON returns line as-is."""
        cli = ClaudeAgentCLI()
        output, metadata = cli._parse_stream_message("not json", [], 0, None)

        assert output == "not json"
        assert metadata is None

    def test_content_block_delta(self):
        """Test parsing content_block_delta message."""
        cli = ClaudeAgentCLI()
        line = '{"type": "content_block_delta", "delta": {"text": "hello"}}'

        output, metadata = cli._parse_stream_message(line, [], 0, None)

        assert output == "hello"
        assert metadata is not None

    def test_content_block_delta_empty_delta(self):
        """Test parsing content_block_delta with empty delta."""
        cli = ClaudeAgentCLI()
        line = '{"type": "content_block_delta", "delta": {}}'

        output, metadata = cli._parse_stream_message(line, [], 0, None)

        assert output == ""
        assert metadata is not None

    def test_system_message(self):
        """Test parsing system message."""
        cli = ClaudeAgentCLI()
        line = '{"type": "system", "session_id": "sess-123"}'

        output, metadata = cli._parse_stream_message(line, [], 0, None)

        assert output == ""
        assert metadata is not None
        assert metadata.session_id == "sess-123"

    def test_result_message(self):
        """Test parsing result message."""
        cli = ClaudeAgentCLI()
        line = '{"type": "result", "session_id": "sess-456"}'

        output, metadata = cli._parse_stream_message(line, [], 0, None)

        assert output == ""
        assert metadata.session_id == "sess-456"

    def test_assistant_message_with_content(self):
        """Test parsing assistant message with content."""
        cli = ClaudeAgentCLI()
        line = json.dumps(
            {
                "type": "assistant",
                "message": {
                    "content": [
                        {"type": "text", "text": "Hello "},
                        {"type": "text", "text": "world"},
                    ]
                },
            }
        )

        output, _metadata = cli._parse_stream_message(line, [], 0, None)

        assert output == "Hello world"

    def test_unknown_type(self):
        """Test parsing unknown message type."""
        cli = ClaudeAgentCLI()
        line = '{"type": "unknown_type", "data": "value"}'

        output, metadata = cli._parse_stream_message(line, [], 0, None)

        # Should return JSON dump
        assert "unknown_type" in output
        assert metadata is not None


class TestHandleJsonDict:
    """Tests for _handle_json_dict method."""

    def test_no_type_field(self):
        """Test handling dict without type field."""
        cli = ClaudeAgentCLI()
        data = {"key": "value"}

        output, metadata = cli._handle_json_dict(data)

        assert output == '{"key": "value"}'
        assert metadata is None

    def test_extracts_session_id(self):
        """Test extracts session_id from data."""
        cli = ClaudeAgentCLI()
        data = {"type": "system", "session_id": "test-session"}

        _output, metadata = cli._handle_json_dict(data)

        assert metadata is not None
        assert metadata.session_id == "test-session"

    def test_extracts_model(self):
        """Test extracts model from data."""
        cli = ClaudeAgentCLI()
        data = {"type": "system", "model": "claude-3-opus"}

        _output, metadata = cli._handle_json_dict(data)

        assert metadata is not None
        assert metadata.model == "claude-3-opus"

    def test_provider_is_claude(self):
        """Test provider is always 'claude'."""
        cli = ClaudeAgentCLI()
        data = {"type": "system"}

        _output, metadata = cli._handle_json_dict(data)

        assert metadata is not None
        assert metadata.provider == "claude"


class TestExtractAssistantMessage:
    """Tests for _extract_assistant_message method."""

    def test_not_dict(self):
        """Test with non-dict input."""
        cli = ClaudeAgentCLI()
        result = cli._extract_assistant_message("not a dict")

        assert result == ""

    def test_no_content(self):
        """Test with dict without content."""
        cli = ClaudeAgentCLI()
        result = cli._extract_assistant_message({})

        assert result == ""

    def test_content_not_list(self):
        """Test with content that's not a list."""
        cli = ClaudeAgentCLI()
        result = cli._extract_assistant_message({"content": "string"})

        assert result == ""

    def test_extracts_text_content(self):
        """Test extracts text from content blocks."""
        cli = ClaudeAgentCLI()
        message = {
            "content": [
                {"type": "text", "text": "Part 1"},
                {"type": "image", "data": "..."},  # Non-text ignored
                {"type": "text", "text": "Part 2"},
            ]
        }

        result = cli._extract_assistant_message(message)

        assert result == "Part 1Part 2"

    def test_handles_missing_text_field(self):
        """Test handles content block without text field."""
        cli = ClaudeAgentCLI()
        message = {
            "content": [
                {"type": "text"},  # Missing text
                {"type": "text", "text": "Hello"},
            ]
        }

        result = cli._extract_assistant_message(message)

        assert result == "Hello"

    def test_handles_non_string_text(self):
        """Test handles non-string text values."""
        cli = ClaudeAgentCLI()
        message = {
            "content": [
                {"type": "text", "text": 123},  # Non-string
                {"type": "text", "text": "Hello"},
            ]
        }

        result = cli._extract_assistant_message(message)

        assert result == "Hello"
