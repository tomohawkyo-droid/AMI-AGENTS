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
        # The exact command depends on the config,
        # but it should have model and instruction
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

    def test_build_command_with_session_id(self):
        """_build_command() includes --resume flag with valid UUID session_id."""
        cli = QwenAgentCLI()
        valid_uuid = "019c0334-c453-7790-b794-15f3b446a10a"
        config = AgentConfig(
            model="qwen-coder",
            session_id=valid_uuid,
            provider=ProviderType.QWEN,
        )

        cmd = cli._build_command("test", None, config)

        assert "--resume" in cmd
        assert valid_uuid in cmd

    def test_build_command_with_invalid_session_id(self):
        """_build_command() skips --resume for invalid UUID session_id."""
        cli = QwenAgentCLI()
        config = AgentConfig(
            model="qwen-coder",
            session_id="not-a-uuid",
            provider=ProviderType.QWEN,
        )

        cmd = cli._build_command("test", None, config)

        assert "--resume" not in cmd

    def test_build_command_without_session_id(self):
        """_build_command() does not include --resume without session_id."""
        cli = QwenAgentCLI()
        config = AgentConfig(
            model="qwen-coder",
            session_id=None,
            provider=ProviderType.QWEN,
        )

        cmd = cli._build_command("test", None, config)

        assert "--resume" not in cmd

    def test_build_command_with_allowed_tools(self):
        """_build_command() includes --allowed-tools."""
        cli = QwenAgentCLI()
        config = AgentConfig(
            model="qwen-coder",
            allowed_tools=["read_file", "write_file"],
            provider=ProviderType.QWEN,
        )

        cmd = cli._build_command("test", None, config)

        assert "--allowed-tools" in cmd
        assert "read_file" in cmd
        assert "write_file" in cmd

    def test_build_command_with_streaming(self):
        """_build_command() includes streaming flags."""
        cli = QwenAgentCLI()
        config = AgentConfig(
            model="qwen-coder",
            enable_streaming=True,
            provider=ProviderType.QWEN,
        )

        cmd = cli._build_command("test", None, config)

        assert "--output-format" in cmd
        assert "stream-json" in cmd
        assert "--include-partial-messages" in cmd

    def test_build_command_includes_yolo(self):
        """_build_command() always includes --yolo flag."""
        cli = QwenAgentCLI()
        config = AgentConfig(
            model="qwen-coder",
            provider=ProviderType.QWEN,
        )

        cmd = cli._build_command("test", None, config)

        assert "--yolo" in cmd


class TestQwenStreamParsing:
    """Tests for Qwen stream message parsing."""

    def test_parse_stream_message_empty_line(self):
        """Test parsing empty line returns empty."""
        cli = QwenAgentCLI()

        output, metadata = cli._parse_stream_message("", [], 0, None)

        assert output == ""
        assert metadata is None

    def test_parse_stream_message_whitespace_line(self):
        """Test parsing whitespace line returns empty."""
        cli = QwenAgentCLI()

        output, metadata = cli._parse_stream_message("   ", [], 0, None)

        assert output == ""
        assert metadata is None

    def test_parse_stream_message_invalid_json(self):
        """Test parsing invalid JSON returns line as-is."""
        cli = QwenAgentCLI()

        output, metadata = cli._parse_stream_message("not json", [], 0, None)

        assert output == "not json"
        assert metadata is None

    def test_parse_stream_message_stream_event(self):
        """Test parsing stream_event message."""
        cli = QwenAgentCLI()
        line = (
            '{"type": "stream_event", "event":'
            ' {"type": "content_block_delta",'
            ' "delta": {"text": "hello"}}}'
        )

        output, _metadata = cli._parse_stream_message(line, [], 0, None)

        assert output == "hello"

    def test_parse_stream_message_system_init(self):
        """Test parsing system init message."""
        cli = QwenAgentCLI()
        line = '{"type": "system", "subtype": "init", "session_id": "sess-123"}'

        output, metadata = cli._parse_stream_message(line, [], 0, None)

        assert output == ""
        assert metadata is not None
        assert metadata.session_id == "sess-123"

    def test_parse_stream_message_result(self):
        """Test parsing result message."""
        cli = QwenAgentCLI()
        line = '{"type": "result", "session_id": "sess-456"}'

        output, metadata = cli._parse_stream_message(line, [], 0, None)

        assert output == ""
        assert metadata is not None
        assert metadata.session_id == "sess-456"

    def test_parse_stream_message_content_block_delta(self):
        """Test parsing content_block_delta message."""
        cli = QwenAgentCLI()
        line = '{"type": "content_block_delta", "delta": {"text": "world"}}'

        output, metadata = cli._parse_stream_message(line, [], 0, None)

        assert output == "world"
        assert metadata is None

    def test_handle_stream_event_message_start(self):
        """Test handling message_start event."""
        cli = QwenAgentCLI()
        data = {
            "type": "stream_event",
            "session_id": "sess-789",
            "event": {"type": "message_start"},
        }

        output, metadata = cli._handle_stream_event(data)

        assert output == ""
        assert metadata is not None
        assert metadata.session_id == "sess-789"

    def test_handle_stream_event_with_session_id(self):
        """Test handling event with session_id at top level."""
        cli = QwenAgentCLI()
        data = {
            "type": "stream_event",
            "session_id": "sess-abc",
            "event": {"type": "other"},
        }

        _output, metadata = cli._handle_stream_event(data)

        assert metadata is not None
        assert metadata.session_id == "sess-abc"

    def test_handle_system_init(self):
        """Test handling system init."""
        cli = QwenAgentCLI()
        data = {"session_id": "sess-init"}

        output, metadata = cli._handle_system_init(data)

        assert output == ""
        assert metadata is not None
        assert metadata.session_id == "sess-init"

    def test_parse_json_message_unknown_type(self):
        """Test parsing unknown message type."""
        cli = QwenAgentCLI()
        data = {"type": "unknown_type", "foo": "bar"}

        output, metadata = cli._parse_json_message(data)

        assert output == ""
        assert metadata is None
