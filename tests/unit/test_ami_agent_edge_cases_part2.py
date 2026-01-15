"""Additional comprehensive tests for edge cases and error conditions in ami-agent."""

import json
from unittest.mock import MagicMock, Mock, patch

import pytest

from agents.ami.cli.claude_cli import ClaudeAgentCLI
from agents.ami.cli.config import AgentConfig
from agents.ami.cli.exceptions import AgentCommandNotFoundError, AgentExecutionError, AgentTimeoutError
from agents.ami.cli.mode_handlers import (
    mode_print,
)
from agents.ami.cli.process_utils import (
    handle_first_output_timeout,
    handle_process_completion,
    read_streaming_line,
    start_streaming_process,
)
from agents.ami.cli.provider_type import ProviderType
from agents.ami.cli.qwen_cli import QwenAgentCLI


class TestProcessUtilsErrorConditions:
    """Test error conditions in process utilities."""

    @patch("subprocess.Popen")
    @patch("agents.ami.cli.process_utils.get_unprivileged_env")
    def test_start_streaming_process_with_stdin(self, mock_get_env, mock_popen):
        """Test starting process with stdin data."""
        mock_get_env.return_value = {"ENV": "VAR"}
        cmd = ["test", "cmd"]
        
        # Test with stdin - should set stdin to PIPE
        start_streaming_process(cmd, "stdin data", None)
        
        args, kwargs = mock_popen.call_args
        assert kwargs["stdin"] == -1  # subprocess.PIPE is -1

    @patch("subprocess.Popen")
    def test_start_streaming_process_invalid_cmd(self, mock_popen):
        """Test starting process with invalid command format."""
        # Should validate command format if implemented, or just pass to Popen
        # Assuming Popen raises FileNotFoundError if cmd not found
        mock_popen.side_effect = FileNotFoundError("Cmd not found")
        
        with pytest.raises(AgentCommandNotFoundError):
            start_streaming_process(["invalid"], None, None)

    @patch("select.select")
    def test_read_streaming_line_select_error(self, mock_select):
        """Test reading line when select raises OSError."""
        mock_select.side_effect = OSError("Select failed")
        
        mock_process = Mock()
        mock_process.stdout = Mock()
        mock_process.communicate.return_value = ("stdout", "stderr")
        mock_process.returncode = 1
        
        with pytest.raises(AgentExecutionError):
            read_streaming_line(mock_process, 1.0, ["cmd"])

    def test_handle_first_output_timeout_exceeded(self):
        """Test handling first output timeout when exceeded."""
        started_at = 0  # Way in the past
        # Should not raise exception as per implementation (returns None or logs)
        # Actually it raises AgentTimeoutError if timeout > 0
        
        # Mock time.time to be > started_at + timeout
        with patch("time.time", return_value=100):
            with pytest.raises(AgentTimeoutError):
                handle_first_output_timeout(started_at=0, cmd=["cmd"], timeout=10)

    def test_handle_process_completion_non_zero_exit(self):
        """Test process completion with non-zero exit code."""
        mock_process = Mock()
        mock_process.poll.return_value = 1
        mock_process.communicate.return_value = ("stdout", "stderr")
        mock_process.returncode = 1
        
        with pytest.raises(AgentExecutionError):
            handle_process_completion(mock_process, ["cmd"], 0, "session")


class TestClaudeCLIErrorConditions:
    """Test error conditions in Claude CLI provider."""

    def test_compute_disallowed_tools_invalid_tool(self):
        """Test computing disallowed tools with invalid tool."""
        with pytest.raises(ValueError):
            ClaudeAgentCLI.compute_disallowed_tools(["InvalidTool"])

    def test_build_command_invalid_session_id(self):
        """Test building command with invalid session ID."""
        cli = ClaudeAgentCLI()
        config = AgentConfig(
            model="model",
            session_id="invalid-uuid",  # Not a UUID
            provider=ProviderType.CLAUDE
        )
        
        # Should handle gracefully (skip session arg or use as is depending on impl)
        # The implementation uses UUID(session_id) which raises ValueError
        # But it catches it and skips the flag
        with patch("agents.ami.cli.claude_cli.get_config") as mock_get_config:
            mock_get_config.return_value.get_provider_command.return_value = "claude"
            
            cmd = cli._build_command("instruction", None, config)
            # Should not contain --session-id flag if invalid UUID is skipped
            assert "--session-id" not in cmd

    def test_parse_stream_message_invalid_json(self):
        """Test parsing invalid JSON from stream."""
        cli = ClaudeAgentCLI()
        
        # Should return raw text if not valid JSON
        text, meta = cli._parse_stream_message("Not JSON", [], 0, Mock())
        assert text == "Not JSON"
        assert meta is None

    def test_parse_stream_message_unknown_type(self):
        """Test parsing JSON with unknown message type."""
        cli = ClaudeAgentCLI()
        
        # Should return json string if type unknown
        data = {"type": "unknown_type", "content": "test"}
        text, meta = cli._parse_stream_message(json.dumps(data), [], 0, Mock())
        # The implementation returns json.dumps(data) for unknown types
        assert json.loads(text) == data


class TestQwenCLIErrorConditions:
    """Test error conditions in Qwen CLI provider."""

    def test_compute_disallowed_tools_invalid_tool(self):
        """Test computing disallowed tools with invalid tool."""
        with pytest.raises(ValueError):
            QwenAgentCLI.compute_disallowed_tools(["InvalidTool"])

    def test_parse_stream_message_empty_line(self):
        """Test parsing empty line."""
        cli = QwenAgentCLI()
        text, meta = cli._parse_stream_message("   ", [], 0, Mock())
        assert text == ""
        assert meta is None

    def test_parse_stream_message_invalid_json(self):
        """Test parsing invalid JSON."""
        cli = QwenAgentCLI()
        text, meta = cli._parse_stream_message("Not JSON", [], 0, Mock())
        assert text == "Not JSON"
        assert meta is None


class TestHelperErrorConditions:
    """Test error conditions in helper functions."""

    @patch("agents.ami.cli.mode_handlers.validate_path_and_return_code")
    @patch("agents.ami.cli.mode_handlers.get_agent_cli")
    def test_mode_print_with_instruction_file_and_content(self, mock_get_cli, mock_validate):
        """Test print mode with both file and content (should be impossible via CLI but good for coverage)."""
        # This is hard to test via mode_print directly as it takes one or the other arg logic
        # But we can test run_print directly
        
        mock_validate.return_value = 0
        cli = ClaudeAgentCLI()
        
        # run_print raises ValueError if both instruction and instruction_file are provided
        # But mode_print logic prevents this call signature usually
        # Let's test calling run_print directly
        
        with pytest.raises(ValueError):
            cli.run_print(
                instruction="Instruction",
                instruction_file=MagicMock()
            )


if __name__ == "__main__":
    pytest.main([__file__])